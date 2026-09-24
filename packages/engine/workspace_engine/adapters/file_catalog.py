from workspace_engine.storage import connect as durable_connect
'Local file inventory and revisioned collections. Never moves source files.'
import json, os, sqlite3, threading, time, uuid, subprocess, sys
from pathlib import Path
from datetime import datetime, timezone
from contextlib import contextmanager

class FileConflict(ValueError):
    pass

def now():
    return datetime.now(timezone.utc).isoformat()

class FileCatalog:
    EXCLUDE = {'.git', 'node_modules', '__pycache__', '.venv', 'venv', 'build', 'dist', 'target', 'DerivedData', 'Pods', 'backups', 'Library', 'vendor', 'runtime', 'site-packages', 'cache', 'fixture-source'}

    def __init__(self, data, roots=None, interval=600):
        self.home = Path(data)
        self.home.mkdir(parents=True, exist_ok=True)
        self.db = self.home / 'files.sqlite3'
        self.lock = threading.Lock()
        self.scanning = False
        self.interval = interval
        self.roots = [Path(p).expanduser().resolve() for p in roots or []]
        with self.connect() as c:
            c.executescript('CREATE TABLE IF NOT EXISTS inventory(id TEXT PRIMARY KEY,path TEXT UNIQUE,root TEXT,device INTEGER,inode INTEGER,size INTEGER,modified REAL,seen TEXT,status TEXT);\n            CREATE INDEX IF NOT EXISTS inventory_identity ON inventory(device,inode);\n            CREATE INDEX IF NOT EXISTS inventory_recent ON inventory(modified DESC);\n            CREATE TABLE IF NOT EXISTS collections(id TEXT PRIMARY KEY,revision INTEGER,body TEXT);\n            CREATE TABLE IF NOT EXISTS history(seq INTEGER PRIMARY KEY,collection_id TEXT,revision INTEGER,body TEXT,at TEXT);\n            CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY,value TEXT);')

    @contextmanager
    def connect(self):
        c = durable_connect(self.db, timeout=20)
        c.row_factory = sqlite3.Row
        try:
            with c:
                yield c
        finally:
            c.close()

    def permitted(self, p):
        p = Path(p).expanduser().resolve()
        if not any((p.is_relative_to(r) for r in self.roots)):
            raise ValueError('File is outside the indexed folders')
        return p

    def start(self):

        def loop():
            while True:
                try:
                    self.scan()
                except Exception as e:
                    with self.connect() as c:
                        c.execute('INSERT OR REPLACE INTO metadata VALUES(?,?)', ('scan', json.dumps({'at': now(), 'errors': [str(e)]})))
                time.sleep(self.interval)
        threading.Thread(target=loop, daemon=True, name='file-inventory').start()

    def scan_async(self):
        if not self.scanning:
            threading.Thread(target=self.scan, daemon=True).start()
        return {'ok': True, 'scanning': True}

    def scan(self):
        if not self.lock.acquire(False):
            return {'scanning': True}
        self.scanning = True
        stamp = now()
        count = 0
        errors = []
        capped = False
        try:
            with self.connect() as c:
                for root in self.roots:
                    if not root.is_dir():
                        errors.append(str(root) + ': unavailable')
                        c.execute("UPDATE inventory SET status='unavailable' WHERE root=?", (str(root),))
                        c.commit()
                        continue
                    old = {r['path']: dict(r) for r in c.execute('SELECT * FROM inventory WHERE root=?', (str(root),))}
                    identities = {}
                    for r in old.values():
                        identities.setdefault((r['device'], r['inode']), []).append(r)
                    seen = set()
                    root_errors = []
                    root_count = 0
                    root_capped = False
                    batch = []

                    def onerror(e):
                        root_errors.append(str(e))
                    for folder, dirs, files in os.walk(root, followlinks=False, onerror=onerror):
                        dirs[:] = [d for d in dirs if not d.startswith('.') and d not in self.EXCLUDE and (not d.endswith(('.app', '.photoslibrary', '.bundle'))) and (not Path(folder, d).is_symlink())]
                        if Path(folder) == self.home or self.home in Path(folder).parents:
                            dirs[:] = []
                            continue
                        for name in files:
                            if name.startswith('.') or name.endswith(('.pyc', '.log', '.sqlite3-wal', '.sqlite3-shm')):
                                continue
                            p = Path(folder, name)
                            try:
                                if p.is_symlink() or not p.is_file():
                                    continue
                                st = p.stat()
                            except OSError as e:
                                root_errors.append(str(e))
                                continue
                            path = str(p)
                            row = old.get(path)
                            if not row:
                                prior = [v for v in identities.get((st.st_dev, st.st_ino), []) if not Path(v['path']).exists()]
                                if len(prior) == 1:
                                    row = prior[0]
                            fid = row['id'] if row else str(uuid.uuid4())
                            seen.add(fid)
                            if not row or row['path'] != path or row['size'] != st.st_size or (row['modified'] != st.st_mtime) or (row['status'] != 'available'):
                                batch.append((fid, path, str(root), st.st_dev, st.st_ino, st.st_size, st.st_mtime, stamp, 'available'))
                            count += 1
                            root_count += 1
                            if len(batch) >= 1000:
                                c.executemany('INSERT OR REPLACE INTO inventory VALUES(?,?,?,?,?,?,?,?,?)', batch)
                                c.commit()
                                batch = []
                            if root_count >= 250000:
                                capped = True
                                root_capped = True
                                break
                        if root_capped:
                            break
                    if batch:
                        c.executemany('INSERT OR REPLACE INTO inventory VALUES(?,?,?,?,?,?,?,?,?)', batch)
                    for r in old.values():
                        if r['id'] not in seen:
                            state = 'unchecked' if root_errors or root_capped else 'excluded' if Path(r['path']).exists() else 'missing'
                            if r['status'] != state:
                                c.execute('UPDATE inventory SET status=? WHERE id=?', (state, r['id']))
                    c.commit()
                    errors += root_errors[:5]
                    if root_capped:
                        errors.append(str(root) + ': 250,000-file scan limit reached; coverage is incomplete')
                result = {'at': stamp, 'count': count, 'errors': errors, 'capped': capped}
                c.execute('INSERT OR REPLACE INTO metadata VALUES(?,?)', ('scan', json.dumps(result)))
            return result
        finally:
            self.scanning = False
            self.lock.release()

    def status(self):
        with self.connect() as c:
            r = c.execute("SELECT value FROM metadata WHERE key='scan'").fetchone()
            return {'roots': [str(p) for p in self.roots], 'scanning': self.scanning, 'intervalSeconds': self.interval, 'scan': json.loads(r[0]) if r else None, 'total': c.execute('SELECT count(*) FROM inventory WHERE status<>"excluded"').fetchone()[0]}

    def inventory(self, q='', offset=0):
        tokens = str(q).lower().split()[:12]
        where = ' AND '.join(("lower(path) LIKE ? ESCAPE '\\'" for _ in tokens)) or '1'
        where = "status<>'excluded' AND (" + where + ')'
        args = ['%' + s.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_') + '%' for s in tokens]
        with self.connect() as c:
            rows = c.execute('SELECT * FROM inventory WHERE ' + where + ' ORDER BY modified DESC,path LIMIT 100 OFFSET ?', (*args, max(0, int(offset)))).fetchall()
            total = c.execute('SELECT count(*) FROM inventory WHERE ' + where, args).fetchone()[0]
        return {'files': [dict(r) for r in rows], 'total': total}

    def file(self, fid):
        with self.connect() as c:
            r = c.execute('SELECT * FROM inventory WHERE id=?', (fid,)).fetchone()
        if not r:
            raise ValueError('File not found')
        return dict(r)

    def collections(self):
        with self.connect() as c:
            rows = c.execute('SELECT * FROM collections').fetchall()
        out = []
        for r in rows:
            b = json.loads(r['body'])
            b.update(id=r['id'], revision=r['revision'])
            b['files'] = [self.file(x) for x in b.get('fileIds', [])]
            current = next((f for f in b['files'] if f['id'] == b.get('currentId')), None)
            b['needsReview'] = not current or current['status'] != 'available' or current['modified'] != b.get('currentModified') or (current['size'] != b.get('currentSize'))
            out.append(b)
        return sorted(out, key=lambda b: (not b.get('pinned', False), b['title'].lower()))

    def mutate(self, d):
        action = d.get('action')
        if action == 'scan':
            return self.scan_async()
        if action in ('open', 'reveal', 'preview'):
            f = self.file(d['fileId'])
            p = self.permitted(f['path'])
            if not p.is_file():
                raise ValueError('File is unavailable. Refresh the inventory.')
            if action == 'preview':
                if p.suffix.lower() not in {'.md', '.txt', '.json', '.csv', '.py', '.js', '.ts', '.tsx', '.css', '.html', '.yaml', '.yml', '.toml'}:
                    return {'text': 'Use Open to inspect this file in its application.', 'supported': False}
                with p.open('rb') as stream:
                    raw = stream.read(20001)
                return {'text': raw[:20000].decode('utf-8', errors='replace'), 'truncated': len(raw) > 20000, 'supported': True}
            if sys.platform != 'darwin':
                raise ValueError('Open and Reveal require the Mac host')
            if action == 'open' and p.suffix.lower() not in {'.html', '.htm', '.pdf', '.md', '.txt', '.png', '.jpg', '.jpeg', '.webp', '.gif', '.mp4', '.mov', '.docx', '.xlsx', '.pptx', '.csv', '.json'}:
                raise ValueError('Use Reveal in Finder for this file type')
            subprocess.run(['/usr/bin/open', *(['-R'] if action == 'reveal' else []), str(p)], check=True, timeout=10)
            return {'ok': True}
        if action == 'save':
            return self.save(d)
        raise ValueError('Unknown file action')

    def save(self, d):
        b = d.get('record', {})
        if not isinstance(b, dict):
            raise ValueError('Invalid record')
        clean = {}
        for k, limit in [('title', 200), ('summary', 4000), ('project', 120), ('evidence', 8000)]:
            v = b.get(k, '')
            if not (isinstance(v, str) and len(v) <= limit):
                raise ValueError('Invalid ' + k)
            clean[k] = v.strip()
        if not clean['title']:
            raise ValueError('Add a title')
        ids = b.get('fileIds', [])
        if not (isinstance(ids, list) and len(ids) <= 100 and all((isinstance(v, str) for v in ids))):
            raise ValueError('Invalid files')
        paths = b.get('paths', [])
        if not (isinstance(paths, list) and len(paths) <= 100):
            raise ValueError('Invalid paths')
        with self.connect() as c:
            for p in paths:
                if not isinstance(p, str):
                    raise ValueError('Invalid path')
                r = c.execute('SELECT id FROM inventory WHERE path=?', (str(self.permitted(p)),)).fetchone()
                if not r:
                    raise ValueError('Path is not in the inventory: ' + p)
                ids = ids + [r['id']]
        clean['fileIds'] = list(dict.fromkeys(ids))
        for fid in clean['fileIds']:
            self.file(fid)
        clean['pinned'] = bool(b.get('pinned', False))
        clean['updatedAt'] = now()
        key = d.get('id') or str(uuid.uuid4())
        if not (isinstance(key, str) and len(key) <= 100):
            raise ValueError('Invalid ID')
        with self.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            old = c.execute('SELECT * FROM collections WHERE id=?', (key,)).fetchone()
            if old and d.get('revision') != old['revision']:
                raise FileConflict('This entry changed elsewhere. Your draft is kept; reload before saving.')
            if not old and d.get('revision') not in (None, 0):
                raise FileConflict('Entry no longer exists')
            prev = json.loads(old['body']) if old else {}
            for k in ('currentId', 'currentModified', 'currentSize', 'selectedAt'):
                clean[k] = prev.get(k)
            if d.get('chooseCurrent'):
                fid = d['chooseCurrent']
                if not fid in clean['fileIds']:
                    raise ValueError('Current file must belong to this entry')
                f = self.file(fid)
                p = self.permitted(f['path'])
                st = p.stat()
                clean.update(currentId=fid, currentModified=st.st_mtime, currentSize=st.st_size, selectedAt=now())
            if clean.get('currentId') and clean['currentId'] not in clean['fileIds']:
                raise ValueError('Keep the current file attached, or choose another current file')
            rev = old['revision'] + 1 if old else 1
            if old:
                c.execute('INSERT INTO history(collection_id,revision,body,at) VALUES(?,?,?,?)', (key, old['revision'], old['body'], now()))
            c.execute('INSERT OR REPLACE INTO collections VALUES(?,?,?)', (key, rev, json.dumps(clean)))
        return {'id': key, 'revision': rev, 'ok': True}

    def history(self, key):
        with self.connect() as c:
            return [dict(r) for r in c.execute('SELECT revision,body,at FROM history WHERE collection_id=? ORDER BY seq DESC LIMIT 30', (key,))]

    def export(self):
        return {'version': 1, 'exportedAt': now(), 'status': self.status(), 'collections': self.collections()}
