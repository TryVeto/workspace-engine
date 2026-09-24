from __future__ import annotations
from workspace_engine.storage import connect as durable_connect
"""Private, loopback-only prompt review. No agent, paid API, or external writes.
SQLite is authoritative; editable Markdown files are the preserved first drafts.
"""


import argparse, copy, datetime as dt, hashlib, json, os, secrets, sqlite3

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from pathlib import Path

from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent

def utc() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()

def pack(value) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'))

def digest(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()

class Store:
    def __init__(self, directory: Path):
        self.directory = directory
        directory.mkdir(parents=True, exist_ok=True)
        os.chmod(directory, 0o700)
        self.db = directory / 'prompts.sqlite3'
        with self.connect() as c:
            c.executescript('''
                CREATE TABLE IF NOT EXISTS meta (id INTEGER PRIMARY KEY, data TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS prompts (id TEXT PRIMARY KEY, position INTEGER NOT NULL, revision INTEGER NOT NULL, data TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS events (seq INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT NOT NULL, prompt_id TEXT NOT NULL, actor TEXT NOT NULL, action TEXT NOT NULL, before_data TEXT, after_data TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS requests (id TEXT PRIMARY KEY, request_hash TEXT NOT NULL, response TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS archived_prompts (id TEXT PRIMARY KEY, position INTEGER NOT NULL, revision INTEGER NOT NULL, data TEXT NOT NULL, archived_at TEXT NOT NULL, actor TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS catalog_events (seq INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT NOT NULL, actor TEXT NOT NULL, before_data TEXT NOT NULL, after_data TEXT NOT NULL);
            ''')
            if not c.execute('SELECT 1 FROM meta').fetchone():
                seed = {'prompts': [], 'sources': [], 'appVersion': '1', 'catalogVersion': '1'}
                rows = seed.pop('prompts')
                c.execute('INSERT INTO meta VALUES(1,?)', (pack(seed),))
                for pos, p in enumerate(rows):
                    p.update(revision=1, updatedAt=utc(), sha256=digest(p['body']))
                    c.execute('INSERT INTO prompts VALUES(?,?,?,?)', (p['id'], pos, 1, pack(p)))
                    c.execute('INSERT INTO events(at,prompt_id,actor,action,before_data,after_data) VALUES(?,?,?,?,?,?)',
                              (utc(), p['id'], 'initial-draft', 'created', None, pack(p)))
        os.chmod(self.db, 0o600)

    def connect(self):
        c = durable_connect(self.db, timeout=15)
        c.row_factory = sqlite3.Row
        c.execute('PRAGMA foreign_keys=ON')
        return c

    def state(self, c=None):
        if c is None:
            with self.connect() as conn: return self.state(conn)
        state = json.loads(c.execute('SELECT data FROM meta WHERE id=1').fetchone()[0])
        state['prompts'] = [json.loads(r[0]) for r in c.execute('SELECT data FROM prompts ORDER BY position')]
        state['readAt'] = utc()
        state['mode'] = 'wording-review-only'
        return state

    def events(self, c=None):
        if c is None:
            with self.connect() as conn: return self.events(conn)
        return [dict(r) | {'before_data': json.loads(r['before_data']) if r['before_data'] else None,
                          'after_data': json.loads(r['after_data'])}
                for r in c.execute('SELECT * FROM events ORDER BY seq')]

    def scope_prompts(self, active_ids, actor='agent-revision'):
        if not isinstance(active_ids, list) or not active_ids or len(active_ids) != len(set(active_ids)):
            return 400, {'error': 'Use a non-empty unique active prompt list.'}
        with self.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            rows={r['id']:r for r in c.execute('SELECT * FROM prompts')}
            if any(i not in rows for i in active_ids): return 404, {'error': 'An active prompt ID was not found.'}
            archived=[]
            for pid,row in rows.items():
                if pid in active_ids: continue
                data=row['data']; at=utc()
                c.execute('INSERT OR REPLACE INTO archived_prompts(id,position,revision,data,archived_at,actor) VALUES(?,?,?,?,?,?)',
                          (pid,row['position'],row['revision'],data,at,actor))
                c.execute('DELETE FROM prompts WHERE id=?',(pid,))
                current=json.loads(data); after=dict(current, archiveStatus='archived', archivedAt=at)
                c.execute('INSERT INTO events(at,prompt_id,actor,action,before_data,after_data) VALUES(?,?,?,?,?,?)',
                          (at,pid,actor,'archived',data,pack(after)))
                archived.append(pid)
            for pos,pid in enumerate(active_ids): c.execute('UPDATE prompts SET position=? WHERE id=?',(pos,pid))
            meta=json.loads(c.execute('SELECT data FROM meta WHERE id=1').fetchone()[0])
            meta['activePromptIds']=active_ids
            meta['archivedPromptIds']=sorted(set(meta.get('archivedPromptIds',[])+archived))
            c.execute('UPDATE meta SET data=? WHERE id=1',(pack(meta),))
            c.commit()
            return 200, {'activePromptIds':active_ids,'archivedPromptIds':archived}

    def create_prompt(self, prompt, actor='agent-revision', request_id=None):
        if not isinstance(prompt, dict): return 400, {'error': 'A prompt object is required.'}
        required={'id','title','subtitle','useWhen','skipWhen','reviewQuestion','rationale','sources','body','group','contrast','example','evaluation','notes','status','promptVersion','approval','model','aliases','defaultDepth','changeNote'}
        defaults={key:'' for key in ('subtitle','useWhen','skipWhen','reviewQuestion','rationale','group','contrast','example','evaluation','notes','model','aliases','changeNote','key')}
        defaults.update(sources=[],status='pending',promptVersion=1,approval=None,defaultDepth='20')
        if set(prompt)-(required|{'key'}):return 400, {'error':'Unsupported prompt field.'}
        prompt={**defaults,**prompt,'status':'pending','approval':None,'promptVersion':1}
        if not {'id','title','body'}<=set(prompt):return 400, {'error':'Provide id, title, and body.'}
        if request_id is not None and (not isinstance(request_id,str)or not 8<=len(request_id)<=150):return 400,{'error':'A stable request ID is required.'}
        request_hash=digest(pack({'prompt':prompt,'actor':actor}))
        if not isinstance(prompt['id'], str) or not 1 <= len(prompt['id']) <= 12: return 400, {'error': 'Invalid prompt ID.'}
        if not isinstance(prompt['title'], str) or not prompt['title'].strip() or len(prompt['title']) > 80: return 400, {'error': 'Invalid prompt title.'}
        if not isinstance(prompt['body'], str) or not prompt['body'].strip(): return 400, {'error': 'The prompt cannot be empty.'}
        if len(prompt['body'])>100000:return 400,{'error':'Prompt exceeds the text limit.'}
        if any(not isinstance(prompt[key],str)or len(prompt[key])>12000 for key in defaults if key not in ('sources','status','promptVersion','approval')):return 400,{'error':'Invalid prompt metadata.'}
        if len(prompt['key'])>1 or (prompt['key'] and not prompt['key'].isascii()):return 400,{'error':'Use one shortcut character.'}
        with self.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            if request_id:
                prior=c.execute('SELECT request_hash,response FROM requests WHERE id=?',(request_id,)).fetchone()
                if prior:
                    if prior[0]!=request_hash:return 409,{'error':'Request ID reused for different content.'}
                    return 201,json.loads(prior[1])
            if c.execute('SELECT 1 FROM prompts WHERE id=?', (prompt['id'],)).fetchone(): return 409, {'error': 'Prompt ID already exists.'}
            valid={s['id'] for s in self.state(c)['sources']}
            if not isinstance(prompt['sources'], list) or any(x not in valid for x in prompt['sources']): return 400, {'error': 'Unknown source reference.'}
            row=copy.deepcopy(prompt)
            row.update(revision=1, updatedAt=utc(), sha256=digest(row['body']))
            pos=c.execute('SELECT COALESCE(MAX(position),-1)+1 FROM prompts').fetchone()[0]
            c.execute('INSERT INTO prompts VALUES(?,?,?,?)', (row['id'], pos, 1, pack(row)))
            c.execute('INSERT INTO events(at,prompt_id,actor,action,before_data,after_data) VALUES(?,?,?,?,?,?)',
                      (utc(), row['id'], actor, 'created', None, pack(row)))
            response={'prompt':row}
            if request_id:c.execute('INSERT INTO requests VALUES(?,?,?)',(request_id,request_hash,pack(response)))
            c.commit()
            return 201,response

    def mutate(self, req):
        if not isinstance(req, dict): return 400, {'error': 'A JSON object is required.'}
        key, actor, action = req.get('requestId'), req.get('actor', 'browser-review'), req.get('action')
        if not isinstance(key, str) or not 8 <= len(key) <= 150: return 400, {'error': 'A stable request ID is required.'}
        if not isinstance(actor, str) or not 1 <= len(actor) <= 120: return 400, {'error': 'Invalid actor.'}
        if action not in {'save', 'approve', 'changes', 'defer', 'reopen', 'restore', 'revise', 'rename'}: return 400, {'error': 'Unknown action.'}
        rh = digest(pack(req))
        with self.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            prior = c.execute('SELECT * FROM requests WHERE id=?', (key,)).fetchone()
            if prior:
                if prior['request_hash'] != rh: return 409, {'error': 'This request ID was already used for a different action.'}
                return 200, json.loads(prior['response'])
            saved = c.execute('SELECT data FROM prompts WHERE id=?', (req.get('id'),)).fetchone()
            if not saved: return 404, {'error': 'Unknown prompt.'}
            old = json.loads(saved[0])
            if req.get('expectedRevision') != old['revision']:
                return 409, {'error': 'A newer saved version exists. Your local draft is retained. Compare before replacing it.', 'current': old}
            changes = req.get('changes', {})
            allowed = {'body', 'notes'} if action != 'revise' else {'body', 'model', 'aliases', 'defaultDepth', 'changeNote', 'rationale', 'reviewQuestion', 'sources', 'group'}
            if action == 'rename': allowed = {'title', 'subtitle', 'aliases'}
            if not isinstance(changes, dict) or set(changes) - allowed:
                return 400, {'error': 'Unsupported editable field.'}
            for name, value in changes.items():
                if name == 'sources':
                    valid = {s['id'] for s in self.state(c)['sources']}
                    if not isinstance(value, list) or len(value) > 100 or any(not isinstance(x, str) or x not in valid for x in value):
                        return 400, {'error': 'Unknown source reference.'}
                elif not isinstance(value, str) or len(value) > 100000:
                    return 400, {'error': 'Invalid text field.'}
            if 'defaultDepth' in changes and changes['defaultDepth'] not in {'10','20','60'}:
                return 400, {'error': 'Unknown effort preference.'}
            if action == 'revise' and ('body' not in changes or not changes['body'].strip()):
                return 400, {'error': 'A revision requires complete prompt text.'}
            if action == 'rename' and (not changes.get('title', '').strip() or len(changes['title']) > 80):
                return 400, {'error': 'Use a clear title of 1 to 80 characters.'}
            row = copy.deepcopy(old)
            if action == 'restore':
                version = req.get('version')
                if not isinstance(version, int): return 400, {'error': 'Choose a historical prompt version.'}
                historical = None
                for e in c.execute('SELECT after_data FROM events WHERE prompt_id=? ORDER BY seq', (old['id'],)):
                    p = json.loads(e[0])
                    if p['promptVersion'] == version: historical = p; break
                if historical is None: return 404, {'error': 'Version not found.'}
                changes = dict(changes, body=historical['body'])
            text_changed = changes.get('body', old['body']) != old['body']
            if 'body' in changes and not changes['body'].strip(): return 400, {'error': 'The prompt cannot be empty.'}
            row.update(changes)
            if text_changed:
                row['promptVersion'] += 1
                row.update(approval=None, status='pending', sha256=digest(row['body']))
            if action == 'approve':
                if req.get('expectedHash') != row['sha256']: return 409, {'error': 'The saved prompt changed. Inspect the current text before approving.', 'current': old}
                row['approval'] = {'at': utc(), 'actor': actor, 'promptVersion': row['promptVersion'], 'sha256': row['sha256'],
                                   'body': row['body'], 'scope': 'wording-only', 'executionAuthorized': False}
                row['status'] = 'approved'
            elif action in {'changes', 'defer', 'reopen'}:
                if action == 'changes' and not row['notes'].strip(): return 400, {'error': 'Add a review note describing what needs to change.'}
                row.update(approval=None, status={'changes':'changes_requested','defer':'deferred','reopen':'pending'}[action])
            if action == 'save' and not text_changed and row['notes'] == old['notes']:
                response = {'prompt': old}
            else:
                row.update(revision=old['revision'] + 1, updatedAt=utc())
                c.execute('UPDATE prompts SET revision=?,data=? WHERE id=?', (row['revision'], pack(row), row['id']))
                c.execute('INSERT INTO events(at,prompt_id,actor,action,before_data,after_data) VALUES(?,?,?,?,?,?)',
                          (utc(), row['id'], actor, action, pack(old), pack(row)))
                response = {'prompt': row}
            c.execute('INSERT INTO requests VALUES(?,?,?)', (key, rh, pack(response)))
            c.commit()
            return 200, response


    def update_catalog(self, req):
        if not isinstance(req, dict): return 400, {'error':'A JSON object is required.'}
        key=req.get('requestId'); actor=req.get('actor','agent-revision')
        if not isinstance(key,str) or not 8 <= len(key) <= 150: return 400, {'error':'Stable request ID required.'}
        if not isinstance(actor,str) or not 1 <= len(actor) <= 120: return 400, {'error':'Invalid actor.'}
        changes=req.get('changes',{})
        if not isinstance(changes,dict) or set(changes)-{'appVersion','catalogVersion','sources'}: return 400, {'error':'Unsupported catalog field.'}
        for name in ['appVersion','catalogVersion']:
            if name in changes and (not isinstance(changes[name],str) or not 1<=len(changes[name])<=60): return 400, {'error':'Invalid version.'}
        for ref in changes.get('sources',[]):
            if not isinstance(ref,dict) or set(ref)!={'id','title','url','kind','note'}: return 400, {'error':'Invalid reference.'}
            if any(not isinstance(v,str) or len(v)>12000 for v in ref.values()): return 400, {'error':'Invalid source value.'}
            if not (ref['url'].startswith('https://') or (ref['url'].startswith('/docs/') and '..' not in ref['url'])): return 400, {'error':'Invalid source URL.'}
        rh=digest(pack(req))
        with self.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            previous=c.execute('SELECT * FROM requests WHERE id=?',(key,)).fetchone()
            if previous:
                if previous['request_hash']!=rh: return 409, {'error':'Request ID reused with different content.'}
                return 200,json.loads(previous['response'])
            old=json.loads(c.execute('SELECT data FROM meta WHERE id=1').fetchone()[0])
            if req.get('expectedCatalogVersion')!=old['catalogVersion']: return 409, {'error':'Catalog changed. Reread before updating.'}
            new=copy.deepcopy(old)
            by_id={s['id']:s for s in old['sources']}
            for ref in changes.get('sources',[]): by_id[ref['id']]=ref
            new.update({k:v for k,v in changes.items() if k!='sources'});new['sources']=list(by_id.values())
            c.execute('UPDATE meta SET data=? WHERE id=1',(pack(new),))
            c.execute('INSERT INTO catalog_events(at,actor,before_data,after_data) VALUES(?,?,?,?)',(utc(),actor,pack(old),pack(new)))
            response={'catalogVersion':new['catalogVersion'],'appVersion':new['appVersion'],'sourceCount':len(new['sources'])}
            c.execute('INSERT INTO requests VALUES(?,?,?)',(key,rh,pack(response)));c.commit()
            return 200,response

