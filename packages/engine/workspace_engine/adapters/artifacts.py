from workspace_engine.storage import connect as durable_connect, sync_directory
"""Immutable canonical artifacts backed by R2 or a local object store."""
import hashlib, json, mimetypes, os, re, shutil, sqlite3, subprocess, sys, tempfile, threading, uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

try:
    import boto3
    from botocore.exceptions import ClientError
except Exception:
    boto3 = None
    ClientError = Exception

TOP_LEVEL = {"Inbox", "Company", "Product", "Projects", "Brand", "Archive"}
TEXT_TYPES = {".md",".txt",".json",".csv",".py",".js",".ts",".tsx",".css",".html",".yaml",".yml",".toml"}

class ArtifactConflict(ValueError):
    pass

def now():
    return datetime.now(timezone.utc).isoformat()

def sha256_file(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda:f.read(1024*1024),b""): h.update(block)
    return h.hexdigest()
def logical_path(value, fallback_name=""):
    value=(value or "").strip().replace("\\","/")
    if not value: value="Inbox/"+fallback_name
    if value.endswith("/"): value+=fallback_name
    parts=value.split("/")
    if len(parts)<2 or parts[0] not in TOP_LEVEL or any(p in ("",".","..") or any(ord(c)<32 for c in p) for p in parts):
        raise ValueError("Choose a location inside Inbox, Company, Product, Projects, Brand, or Archive")
    if len(parts)>20 or len(value)>1000: raise ValueError("Artifact location is too deep")
    return "/".join(parts)

class LocalObjectStore:
    provider="local"
    def __init__(self, root):
        self.root=Path(root); self.root.mkdir(parents=True,exist_ok=True)
    def status(self):
        return {"provider":"local","ready":True,"label":"Stored on this device","cloud":False}
    def has(self,key):
        return (self.root/key).is_file()
    def put(self,path,key,digest,mime):
        target=self.root/key
        if target.is_file():
            if sha256_file(target)!=digest: raise ValueError("Stored object failed integrity check")
            return
        target.parent.mkdir(parents=True,exist_ok=True); tmp=target.with_suffix(".partial-"+uuid.uuid4().hex)
        shutil.copyfile(path,tmp)
        if sha256_file(tmp)!=digest: tmp.unlink(missing_ok=True); raise ValueError("Copied object failed integrity check")
        with tmp.open("rb") as durable:os.fsync(durable.fileno())
        os.replace(tmp,target)
        sync_directory(target.parent)
    def read(self,key,limit=None):
        with (self.root/key).open("rb") as f: return f.read(limit) if limit else f.read()
    def materialize(self,key,target):
        target=Path(target); target.parent.mkdir(parents=True,exist_ok=True); source=self.root/key
        # Application edits must never share an inode with the immutable object.
        shutil.copyfile(source,target)

from workspace_engine.secrets import SecretStore

class R2ObjectStore:
    provider="r2"
    def __init__(self,cfg):
        self.bucket=cfg.get("bucket") or os.getenv("R2_BUCKET","")
        self.endpoint=cfg.get("endpoint") or os.getenv("R2_ENDPOINT","")
        self.access=SecretStore().get(cfg["accessKeyRef"]) if cfg.get("accessKeyRef") else os.getenv(cfg.get("accessKeyEnv","R2_ACCESS_KEY_ID"),"")
        self.secret=SecretStore().get(cfg["secretKeyRef"]) if cfg.get("secretKeyRef") else os.getenv(cfg.get("secretKeyEnv","R2_SECRET_ACCESS_KEY"),"")
        self.aws=cfg.get("awsBin") or "/opt/homebrew/bin/aws"; self.client=None; self.verified=False
        self.backend="boto3" if boto3 else ("aws-cli" if Path(self.aws).is_file() else None)
        self.ready=bool(self.bucket and self.endpoint and self.access and self.secret and self.backend)
        if self.ready and self.backend=="boto3":
            self.client=boto3.client("s3",endpoint_url=self.endpoint,region_name="auto",
                aws_access_key_id=self.access,aws_secret_access_key=self.secret)
    def status(self):
        label="R2 configured" if self.ready else "R2 not configured"
        return {"provider":"r2","ready":self.ready,"verified":self.verified,"label":label,
            "cloud":True,"bucket":self.bucket or None,"backend":self.backend}
    def _require(self):
        if not self.ready: raise ValueError("R2 is selected but its bucket, credentials, or runtime client are not configured")
    def _env(self):
        env=os.environ.copy();env.update(AWS_ACCESS_KEY_ID=self.access,AWS_SECRET_ACCESS_KEY=self.secret,
            AWS_DEFAULT_REGION="auto",AWS_EC2_METADATA_DISABLED="true",AWS_PAGER="")
        return env
    def _run(self,args,timeout=180):
        r=subprocess.run([self.aws,*args,"--endpoint-url",self.endpoint],env=self._env(),
            capture_output=True,text=True,timeout=timeout)
        return r
    def _head(self,key):
        self._require()
        if self.client:
            try:
                out=self.client.head_object(Bucket=self.bucket,Key=key);return out
            except ClientError as e:
                code=str(e.response.get("Error",{}).get("Code",""))
                if code in ("404","NoSuchKey","NotFound"): return None
                raise ValueError("R2 request failed")
        r=self._run(["s3api","head-object","--bucket",self.bucket,"--key",key])
        if r.returncode==0:
            return json.loads(r.stdout or "{}")
        low=(r.stderr or "").lower()
        if "404" in low or "not found" in low or "nosuchkey" in low:
            return None
        raise ValueError("R2 request failed")
    def has(self,key):
        return self._head(key) is not None
    def put(self,path,key,digest,mime):
        self._require()
        if not self.has(key):
            if self.client:
                self.client.upload_file(str(path),self.bucket,key,
                    ExtraArgs={"ContentType":mime,"Metadata":{"sha256":digest}})
            else:
                r=self._run(["s3","cp",str(path),"s3://"+self.bucket+"/"+key,
                    "--content-type",mime,"--metadata","sha256="+digest,"--only-show-errors"],timeout=3600)
                if r.returncode: raise ValueError("R2 upload failed")
        head=self._head(key) or {}
        size=int(head.get("ContentLength",head.get("ContentLength",-1)))
        if size!=Path(path).stat().st_size: raise ValueError("R2 object size did not verify")
        remote=(head.get("Metadata") or {}).get("sha256")
        if remote!=digest: raise ValueError("R2 object hash metadata did not verify")
        # Metadata is supplied by us; only a byte round trip proves stored content.
        self.verified=False
        with tempfile.TemporaryDirectory(prefix="workspace-r2-verify-") as folder:
            downloaded=Path(folder)/"object"
            self.materialize(key,downloaded)
            if sha256_file(downloaded)!=digest:
                raise ValueError("R2 object bytes failed integrity check")
        self.verified=True
    def read(self,key,limit=None):
        self._require()
        if self.client:
            kwargs={"Bucket":self.bucket,"Key":key}
            if limit: kwargs["Range"]=f"bytes=0-{max(0,limit-1)}"
            body=self.client.get_object(**kwargs)["Body"].read();return body
        fd,tmp=tempfile.mkstemp(prefix="workspace-r2-read-");os.close(fd)
        try:
            args=["s3api","get-object","--bucket",self.bucket,"--key",key]
            if limit: args+=["--range",f"bytes=0-{max(0,limit-1)}"]
            args.append(tmp);r=self._run(args)
            if r.returncode: raise ValueError("R2 read failed")
            return Path(tmp).read_bytes()
        finally: Path(tmp).unlink(missing_ok=True)
    def materialize(self,key,target):
        self._require();target=Path(target);target.parent.mkdir(parents=True,exist_ok=True)
        if self.client:self.client.download_file(self.bucket,key,str(target))
        else:
            r=self._run(["s3","cp","s3://"+self.bucket+"/"+key,str(target),"--only-show-errors"],timeout=3600)
            if r.returncode: raise ValueError("R2 download failed")

class ArtifactCatalog:
    def __init__(self,home,cfg,files):
        self.home=Path(home);self.home.mkdir(parents=True,exist_ok=True);self.files=files
        self.db=self.home/"artifacts.sqlite3";self.cache=self.home/"cache"
        cfg=cfg or {}; self.cache_max=max(0,int(cfg.get("cacheMaxBytes",2*1024*1024*1024)))
        self.cache_lock=threading.Lock()
        provider=cfg.get("provider","local")
        if provider not in ("local","r2"): raise ValueError("Unknown artifact storage provider")
        self.store=R2ObjectStore(cfg) if provider=="r2" else LocalObjectStore(cfg.get("path") or self.home/"objects")
        with self.connect() as c:
            c.executescript("""CREATE TABLE IF NOT EXISTS artifacts(
            id TEXT PRIMARY KEY,revision INTEGER,title TEXT,logical_path TEXT UNIQUE,project TEXT,kind TEXT,
            current_version_id TEXT,created_at TEXT,updated_at TEXT,archived INTEGER DEFAULT 0);
            CREATE TABLE IF NOT EXISTS versions(
            id TEXT PRIMARY KEY,artifact_id TEXT,sha256 TEXT,object_key TEXT,size INTEGER,mime TEXT,
            source_path TEXT,source_file_id TEXT,created_at TEXT,UNIQUE(artifact_id,sha256));
            CREATE INDEX IF NOT EXISTS versions_artifact ON versions(artifact_id,created_at DESC);""")
    @contextmanager
    def connect(self):
        c=durable_connect(self.db,timeout=20);c.row_factory=sqlite3.Row
        try:
            with c: yield c
        finally:c.close()
    def status(self):
        with self.connect() as c:
            count=c.execute("SELECT count(*) FROM artifacts WHERE archived=0").fetchone()[0]
            versions=c.execute("SELECT count(*) FROM versions").fetchone()[0]
            size=c.execute("SELECT coalesce(sum(size),0) FROM versions").fetchone()[0]
        return {**self.store.status(),"artifacts":count,"versions":versions,"logicalBytes":size}
    def _row(self,key):
        with self.connect() as c:
            r=c.execute("""SELECT a.*,v.sha256,v.object_key,v.size,v.mime,v.source_path,
            v.source_file_id,v.created_at version_created_at FROM artifacts a
            LEFT JOIN versions v ON v.id=a.current_version_id WHERE a.id=?""",(key,)).fetchone()
        if not r: raise ValueError("Artifact not found")
        return dict(r)
    def listing(self):
        with self.connect() as c:
            rows=c.execute("""SELECT a.*,v.sha256,v.object_key,v.size,v.mime,v.source_path,
            v.source_file_id,v.created_at version_created_at FROM artifacts a
            LEFT JOIN versions v ON v.id=a.current_version_id WHERE a.archived=0
            ORDER BY a.logical_path COLLATE NOCASE""").fetchall()
        return {"status":self.status(),"artifacts":[dict(r) for r in rows]}
    def history(self,key):
        with self.connect() as c:
            return [dict(r) for r in c.execute("SELECT * FROM versions WHERE artifact_id=? ORDER BY created_at DESC",(key,))]
    def promote(self,d):
        f=self.files.file(d.get("fileId","")); source=self.files.permitted(f["path"])
        if not source.is_file(): raise ValueError("Source file is unavailable")
        title=(d.get("title") or source.name).strip()
        if not title or len(title)>255: raise ValueError("Invalid artifact title")
        dest=logical_path(d.get("logicalPath"),title)
        mime=mimetypes.guess_type(title)[0] or "application/octet-stream"
        # Upload an independent, stable snapshot rather than a changing source.
        with tempfile.TemporaryDirectory(prefix="intake-",dir=self.home) as folder:
            snapshot=Path(folder)/"object"
            before=source.stat()
            shutil.copyfile(source,snapshot)
            after=source.stat()
            identity=lambda st:(st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns,st.st_ctime_ns)
            if identity(before)!=identity(after):
                raise ValueError("Source changed during intake; try again")
            digest=sha256_file(snapshot);size=snapshot.stat().st_size
            key=f"objects/{digest[:2]}/{digest}"
            self.store.put(snapshot,key,digest,mime)
        stamp=now()
        project=dest.split("/")[1] if dest.startswith("Projects/") and len(dest.split("/"))>2 else ""
        kind=(d.get("kind") or ("Project file" if project else dest.split("/")[0])).strip()[:80]
        with self.connect() as c:
            c.execute("BEGIN IMMEDIATE")
            old=c.execute("SELECT * FROM artifacts WHERE logical_path=?",(dest,)).fetchone()
            if old:
                current=c.execute("SELECT sha256 FROM versions WHERE id=?",(old["current_version_id"],)).fetchone()
                if current and current["sha256"]==digest:
                    return {"ok":True,"artifact":self._row(old["id"]),"verified":True,"sourcePreserved":True}
                if d.get("revision")!=old["revision"]:
                    raise ArtifactConflict("This location already contains an artifact; reload and confirm a new version")
                prior=c.execute("SELECT id FROM versions WHERE artifact_id=? AND sha256=?",(old["id"],digest)).fetchone()
                if prior:
                    c.execute("UPDATE artifacts SET current_version_id=?,updated_at=?,revision=revision+1 WHERE id=?",
                        (prior["id"],stamp,old["id"]));aid=old["id"];vid=prior["id"]
                else:
                    aid=old["id"];vid=str(uuid.uuid4())
                    c.execute("INSERT INTO versions VALUES(?,?,?,?,?,?,?,?,?)",
                        (vid,aid,digest,key,size,mime,str(source),f["id"],stamp))
                    c.execute("UPDATE artifacts SET current_version_id=?,updated_at=?,revision=revision+1,title=?,project=?,kind=? WHERE id=?",
                        (vid,stamp,title,project,kind,aid))
            else:
                aid=str(uuid.uuid4());vid=str(uuid.uuid4())
                c.execute("INSERT INTO artifacts VALUES(?,?,?,?,?,?,?,?,?,0)",
                    (aid,1,title,dest,project,kind,vid,stamp,stamp))
                c.execute("INSERT INTO versions VALUES(?,?,?,?,?,?,?,?,?)",
                    (vid,aid,digest,key,size,mime,str(source),f["id"],stamp))
        return {"ok":True,"artifact":self._row(aid),"verified":True,"sourcePreserved":True}
    def move(self,d):
        a=self._row(d.get("id",""))
        if d.get("revision")!=a["revision"]: raise ArtifactConflict("This artifact changed elsewhere; reload before moving it")
        dest=logical_path(d.get("logicalPath"),a["title"]);stamp=now()
        project=dest.split("/")[1] if dest.startswith("Projects/") and len(dest.split("/"))>2 else ""
        with self.connect() as c:
            try:
                changed=c.execute("UPDATE artifacts SET logical_path=?,project=?,updated_at=?,revision=revision+1 WHERE id=? AND revision=?",
                    (dest,project,stamp,a["id"],d.get("revision")))
                if changed.rowcount!=1: raise ArtifactConflict("This artifact changed elsewhere; reload before moving it")
            except sqlite3.IntegrityError: raise ValueError("Another artifact already uses that location")
        return {"ok":True,"artifact":self._row(a["id"])}
    def preview(self,key):
        a=self._row(key); suffix=Path(a["title"]).suffix.lower()
        if suffix not in TEXT_TYPES and not str(a["mime"] or "").startswith("text/"):
            return {"supported":False,"text":"Open this artifact to inspect it in its application."}
        raw=self.store.read(a["object_key"],20001)
        return {"supported":True,"text":raw[:20000].decode("utf-8",errors="replace"),"truncated":len(raw)>20000}
    def _prune_cache(self,reserve=0):
        if not self.cache.is_dir() or not self.cache_max:return
        files=[p for p in self.cache.rglob("*") if p.is_file() and ".partial" not in p.name]
        total=sum(p.stat().st_size for p in files); target=max(0,self.cache_max-int(reserve or 0))
        for p in sorted(files,key=lambda x:x.stat().st_mtime):
            if total<=target:break
            try:size=p.stat().st_size;p.unlink();total-=size
            except OSError:pass
    def open(self,key):
        a=self._row(key)
        allowed={".html",".htm",".pdf",".md",".txt",".png",".jpg",".jpeg",".webp",".gif",".mp4",".mov",".docx",".xlsx",".pptx",".csv",".json"}
        if Path(a["title"]).suffix.lower() not in allowed:
            raise ValueError("Use Preview for code or executable file types")
        if sys.platform!="darwin": raise ValueError("Open requires the Mac host")
        with self.cache_lock:
            folder=self.cache/a["id"]/a["current_version_id"];folder.mkdir(parents=True,exist_ok=True)
            safe=re.sub(r"[^A-Za-z0-9._ -]+","_",a["title"]).strip() or "artifact"
            target=folder/safe
            if not target.is_file() or target.stat().st_nlink>1 or sha256_file(target)!=a["sha256"]:
                self._prune_cache(a["size"] or 0)
                tmp=target.with_name(target.name+".partial-"+uuid.uuid4().hex)
                try:
                    self.store.materialize(a["object_key"],tmp)
                    if sha256_file(tmp)!=a["sha256"]:raise ValueError("Cached artifact failed integrity check")
                    with tmp.open("rb") as durable:os.fsync(durable.fileno())
                    os.replace(tmp,target)
                    sync_directory(target.parent)
                finally:tmp.unlink(missing_ok=True)
            target.touch()
            subprocess.run(["/usr/bin/open",str(target)],check=True,timeout=10)
        return {"ok":True,"cached":True,"path":str(target)}
    def mutate(self,d):
        action=d.get("action")
        if action=="promote": return self.promote(d)
        if action=="move": return self.move(d)
        if action=="preview": return self.preview(d.get("id",""))
        if action=="open": return self.open(d.get("id",""))
        raise ValueError("Unknown artifact action")
