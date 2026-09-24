"""Incremental local full-text index. Original records remain authoritative."""
import hashlib
from .storage import connect

class SearchIndex:
    def __init__(self, path):
        self.path = path
        with connect(path) as db:
            db.executescript('CREATE TABLE IF NOT EXISTS documents(id TEXT PRIMARY KEY, digest TEXT); CREATE VIRTUAL TABLE IF NOT EXISTS search USING fts5(id UNINDEXED,title,body);')
    def update(self, records):
        with connect(self.path) as db:
            old = dict(db.execute('SELECT id,digest FROM documents'))
            current = set()
            for record in records:
                key = record['id']; current.add(key)
                body = str(record.get('body', '')); title = str(record.get('title', ''))
                digest = hashlib.sha256((title+'\0'+body).encode()).hexdigest()
                if old.get(key) == digest:
                    continue
                db.execute('DELETE FROM search WHERE id=?', (key,))
                db.execute('INSERT INTO search VALUES(?,?,?)', (key,title,body))
                db.execute('INSERT OR REPLACE INTO documents VALUES(?,?)', (key,digest))
            for key in old.keys()-current:
                db.execute('DELETE FROM search WHERE id=?', (key,))
                db.execute('DELETE FROM documents WHERE id=?', (key,))
    def search(self, query, limit=30):
        words = str(query).split()[:12]
        if not words:
            return []
        match = ' AND '.join('"'+word.replace('"','""')+'"' for word in words)
        with connect(self.path) as db:
            return [dict(id=row[0],title=row[1],excerpt=row[2]) for row in db.execute("SELECT id,title,snippet(search,2,'','', '…',24) FROM search WHERE search MATCH ? ORDER BY rank LIMIT ?", (match,min(100,max(1,int(limit)))))]
