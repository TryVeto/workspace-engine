from workspace_engine.storage import connect as durable_connect, sync_directory
from workspace_engine.skill_identity import identity
"""Conditional Markdown writes; durable before-images and idempotent retries."""
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import tempfile
import threading
import time

class SkillConflict(Exception):
    pass

def digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def atomic(path, text):
    mode = path.stat().st_mode & 0o777
    fd, temp = tempfile.mkstemp(prefix="."+path.name+".", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            f.write(text); f.flush(); os.fsync(f.fileno())
        os.chmod(temp, mode)
        os.replace(temp, path)
        sync_directory(path.parent)
    finally:
        if os.path.exists(temp): os.unlink(temp)

class SkillEditor:
    def __init__(self, catalog, data):
        self.catalog = catalog
        self.db = Path(data)/"skill-history.sqlite3"
        self.db.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        with self.connect() as c:
            c.execute("""CREATE TABLE IF NOT EXISTS edits(
                request TEXT PRIMARY KEY, payload TEXT, path TEXT, old TEXT, new TEXT,
                created REAL, response TEXT)""")

            columns={r[1] for r in c.execute("PRAGMA table_info(edits)")}
            if "object_id" not in columns:c.execute("ALTER TABLE edits ADD COLUMN object_id TEXT")
            # Bind pre-identity journals while original source locations still exist.
            for (old_path,) in c.execute("SELECT DISTINCT path FROM edits"):
                original = Path(old_path)
                for key, item in self.catalog.items.items():
                    package = item["_path"].parent
                    if original.is_relative_to(package):
                        object_id = key + ":" + str(original.relative_to(package))
                        c.execute("UPDATE edits SET object_id=? WHERE path=?", (object_id, old_path))
                        break


    @contextmanager
    def connect(self):
        connection = durable_connect(self.db, timeout=15)
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def target(self, key, relative):
        doc = self.catalog.document(key, relative)
        path = Path(doc["path"])
        for ancestor in (path, *path.parents):
            if ancestor.is_symlink(): raise ValueError("Symbolic links cannot be edited")
        for spec in self.catalog.config.get("roots", []):
            root = Path(spec["path"]).expanduser()
            if spec.get("editable") is True and path.is_relative_to(root.resolve()):
                if path.suffix.lower() not in (".md", ".txt"):
                    raise ValueError("Only Markdown and text files can be edited here")
                return doc, path, root.resolve()
        raise ValueError("This skill source is read-only")

    def document(self, key, relative):
        doc = self.catalog.document(key, relative)
        try: self.target(key, relative); doc["editable"] = True
        except ValueError: doc["editable"] = False
        return doc

    def history(self, key, relative):
        doc = self.catalog.document(key, relative)
        with self.connect() as c:
            rows = c.execute("SELECT old,new,created,response FROM edits WHERE path=? OR object_id=? ORDER BY created DESC LIMIT 50", (doc["path"], self.catalog.resolve(key)+":"+relative)).fetchall()
        return {"versions": [{"text": old, "sha256": digest(old), "created": created,
                              "saved": bool(response)} for old,new,created,response in rows]}

    def sync_git(self, root, path, text):
        manifest = root/"MANIFEST.json"
        paths = [str(path.relative_to(root))]
        if manifest.is_file() and not manifest.is_symlink():
            data = json.loads(manifest.read_text())
            data[paths[0]] = digest(text)
            atomic(manifest, json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True)+"\n")
            paths.append("MANIFEST.json")
        if self.catalog.config.get("git_history",False) and not self.catalog.config.get("semantic_history",False) and (root/".git").is_dir():
            def git(*args):
                return subprocess.run(["git","-C",str(root),*args], capture_output=True, text=True, timeout=20)
            status=git("diff","HEAD","--",*paths)
            if status.returncode: raise RuntimeError("File saved; revision recording needs a retry")
            if status.stdout:
                result=git("commit","--only","-m","Edit skill document: "+paths[0],"--",*paths)
                if result.returncode: raise RuntimeError("File saved; revision recording needs a retry")

    def save(self, data):
        key, relative, text = data.get("id"), data.get("file"), data.get("text")
        request, expected = data.get("requestId"), data.get("sha256")
        if not all(isinstance(x,str) for x in (key,relative,text,request,expected)):
            raise ValueError("Invalid document edit")
        if not request or len(request)>200 or len(text.encode())>1_000_000:
            raise ValueError("Document or request exceeds the limit")
        payload=digest(json.dumps(data, sort_keys=True))
        with self.lock, open(str(self.db)+".lock","a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            doc,path,root=self.target(key,relative)
            with self.connect() as c:
                prior=c.execute("SELECT payload,old,new,response FROM edits WHERE request=?", (request,)).fetchone()
                if prior:
                    if prior[0]!=payload: raise SkillConflict("This save identity belongs to a different edit")
                    if prior[3]: return json.loads(prior[3])
                    if doc["sha256"] not in (digest(prior[1]),digest(prior[2])):
                        raise SkillConflict("The file changed after this save. Your draft is kept.")
                else:
                    if doc["sha256"]!=expected:
                        raise SkillConflict("Changed in another editor. Your draft is kept; compare the saved version.")
                    c.execute("INSERT INTO edits(request,payload,path,old,new,created,response,object_id) VALUES(?,?,?,?,?,?,NULL,?)",
                              (request,payload,str(path),doc["text"],text,time.time(),self.catalog.resolve(key)+":"+relative))
            # Before-image is committed before touching the source.
            if doc["text"]!=text:
                atomic(path,text)
            self.sync_git(root,path,text)
            result={"sha256":digest(text),"text":text,"requestId":request}
            with self.connect() as c:
                c.execute("UPDATE edits SET response=? WHERE request=?", (json.dumps(result),request))
            return result
