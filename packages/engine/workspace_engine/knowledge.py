"""Authored knowledge checkpoints. Saving never waits on Git or a network."""
import fcntl, hashlib, json, os, re, subprocess, tempfile, time
from pathlib import Path
from .storage import private_directory, sync_directory

TEXT_SUFFIXES={".md",".txt",".json",".yaml",".yml",".py",".js",".ts",".sh",".tmpl",".html",".css",".toml"}
SECRET=re.compile(r"(?:-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY|(?:gh[pousr]_|sk_live_)[A-Za-z0-9]{16,})")
def digest(raw):return hashlib.sha256(raw).hexdigest()
def atomic(path,raw):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    fd,temp=tempfile.mkstemp(prefix="."+path.name,dir=path.parent)
    try:
        with os.fdopen(fd,"wb") as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
        os.chmod(temp,0o600);os.replace(temp,path);sync_directory(path.parent)
    finally:
        if os.path.exists(temp):os.unlink(temp)

class KnowledgeLibrary:
    def __init__(self,root,data):
        self.root=Path(root).resolve()
        self.data=private_directory(data)
        if not (self.root/".git").exists():raise ValueError("Knowledge needs its own Git checkout")
        self.state_file=self.data/"knowledge-state.json"
        self.lock_file=self.data/"knowledge.lock"
    def state(self):
        return json.loads(self.state_file.read_text()) if self.state_file.exists() else {"files":{},"conflicts":[]}
    def git(self,*args):
        env={k:v for k,v in os.environ.items() if not k.startswith("GIT_")}
        return subprocess.run(["git","-C",str(self.root),*args],capture_output=True,text=True,timeout=30,env=env)
    def path(self,relative):
        relative=Path(relative)
        if relative.is_absolute() or any(x.startswith(".") or x in ("..","") for x in relative.parts):
            raise ValueError("Invalid knowledge path")
        path=self.root/relative
        if path.suffix not in TEXT_SUFFIXES:raise ValueError("Only authored text belongs in knowledge")
        if any(p.is_symlink() for p in (path,*path.parents)):raise ValueError("Knowledge symlinks are not supported")
        if not path.resolve().is_relative_to(self.root):raise ValueError("Invalid knowledge path")
        return path
    def stage(self,entries):
        with self.lock_file.open("a") as lock:
            fcntl.flock(lock,fcntl.LOCK_EX)
            state=self.state();conflicts=[];changed=[]
            for relative,value in entries.items():
                path=self.path(relative);raw=value.encode()
                if len(raw)>2_000_000 or SECRET.search(value):raise ValueError("Knowledge entry needs a safety review")
                desired=digest(raw);previous=state["files"].get(relative)
                current=digest(path.read_bytes()) if path.exists() else None
                if current and current not in (desired,previous):
                    conflicts.append(relative);continue
                if current!=desired:
                    atomic(path,raw);changed.append(relative)
                state["files"][relative]=desired
            # Missing source entries are retained for explicit review, never deleted.
            state["conflicts"]=conflicts
            if changed:state["changedAt"]=time.time()
            state["savedAt"]=time.time()
            atomic(self.state_file,(json.dumps(state,indent=2)+"\n").encode())
            return {"changed":changed,"conflicts":conflicts}
    def checkpoint(self,summary):
        if not isinstance(summary,str) or not 12<=len(summary)<=180 or len(summary.split())<3:
            raise ValueError("Describe the meaningful change in this checkpoint")
        with self.lock_file.open("a") as lock:
            fcntl.flock(lock,fcntl.LOCK_EX)
            state=self.state()
            if state.get("conflicts"):raise ValueError("Reconcile edited knowledge files before committing")
            paths=list(state["files"])
            if not paths:return self.status()
            for p in paths:self.path(p)
            add=self.git("add","--",*paths)
            if add.returncode:raise RuntimeError("Saved locally; staging failed")
            diff=self.git("diff","--cached","--name-only","--",*paths).stdout
            if diff:
                commit=self.git("commit","--only","-m",summary,"--",*paths)
                if commit.returncode:raise RuntimeError("Saved locally; commit failed")
            state["committedAt"]=time.time()
            state["commit"]=self.git("rev-parse","HEAD").stdout.strip()
            atomic(self.state_file,(json.dumps(state,indent=2)+"\n").encode())
        return self.status()
    def status(self):
        state=self.state();head=self.git("rev-parse","HEAD")
        pending=self.git("status","--porcelain").stdout
        return {"configured":True,"savedLocally":bool(state.get("savedAt")),
                "committed":head.returncode==0 and not pending,
                "backedUp":head.returncode==0 and not pending and state.get("backedUpCommit")==head.stdout.strip(),
                "conflicts":state.get("conflicts",[]),"commit":head.stdout.strip() if head.returncode==0 else None}
