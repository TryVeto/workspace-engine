"""Revisioned workspace model with explicit instance-owned sources."""
import hashlib, json, os, secrets, sqlite3, threading, time, uuid
from pathlib import Path
from urllib.parse import urlsplit
from .storage import connect, private_directory
from .adapters.prompts import Store
from .adapters.skills import Catalog
from .adapters.skill_editor import SkillEditor
from .adapters.skill_examples import SkillExamples
from .adapters.file_catalog import FileCatalog
from .adapters.artifacts import ArtifactCatalog
from .adapters.headquarters import Headquarters
from .adapters.ai_runtime import LoopbackAIProvider
from .web_pages import WebPages
from .providers import ProviderRegistry
from .search import SearchIndex
from .skill_runs import SkillRuns
from .knowledge import KnowledgeLibrary

class Conflict(ValueError):
    pass

class LocalTaskProvider:

    def __init__(self, workspace):
        self.workspace = workspace

    def list(self):
        with connect(self.workspace.config['tasks']) as db:
            return json.loads(db.execute('SELECT body FROM state WHERE id=1').fetchone()[0])

    def edit(self, request):
        return self.workspace.edit(request)

class Workspace:

    def __init__(self, config, data):
        self.config = dict(config)
        self.data = private_directory(data)
        self.started = time.time()
        self.lock = threading.Lock()
        self._catalog_lock = threading.Lock()
        self._catalog_cache = None
        self._catalog_until = 0
        libraries = self.data / 'libraries'
        libraries.mkdir(exist_ok=True, mode=448)
        for key, name in [('prompts', 'prompts/prompts.sqlite3'), ('culture', 'culture.sqlite3'), ('tasks', 'tasks.sqlite3')]:
            if key in config and (not Path(config[key]).is_file()):
                raise ValueError('Configured source is missing: ' + key)
            self.config.setdefault(key, str(libraries / name))
        self.config.setdefault('culture_seed', str(libraries / 'culture.json'))
        self.config.setdefault('skills_config', str(libraries / 'skills.json'))
        for key, value in [('culture_seed', {'entries': []}), ('skills_config', {'roots': []})]:
            path = Path(self.config[key])
            if key in config and (not path.is_file()):
                raise ValueError('Configured source is missing: ' + key)
            if not path.exists():
                path.write_text(json.dumps(value))
        self.prompts = Store(Path(self.config['prompts']).parent)
        with connect(self.config['culture']) as c:
            c.executescript('CREATE TABLE IF NOT EXISTS requests(id TEXT PRIMARY KEY,digest TEXT,response TEXT); CREATE TABLE IF NOT EXISTS blocks(id TEXT PRIMARY KEY,body TEXT,rev INTEGER); CREATE TABLE IF NOT EXISTS notes(id TEXT PRIMARY KEY,title TEXT,body TEXT,rev INTEGER); CREATE TABLE IF NOT EXISTS history(id INTEGER PRIMARY KEY,block TEXT,body TEXT,rev INTEGER,created TEXT,note TEXT);')
        with connect(self.config['tasks']) as c:
            c.executescript('CREATE TABLE IF NOT EXISTS state(id INTEGER PRIMARY KEY,body TEXT); CREATE TABLE IF NOT EXISTS history(id INTEGER PRIMARY KEY,revision INTEGER,body TEXT); CREATE TABLE IF NOT EXISTS requests(id TEXT PRIMARY KEY,digest TEXT,response TEXT);')
            c.execute('INSERT OR IGNORE INTO state VALUES(1,?)', (json.dumps({'revision': 0, 'tasks': []}),))
        self.skills = Catalog(json.loads(Path(self.config['skills_config']).read_text()))
        self.skill_editor = SkillEditor(self.skills, self.data)
        self.skill_runs = SkillRuns(self.data / "skill-runs.sqlite3", self.skills)
        self.knowledge = KnowledgeLibrary(config["knowledge_root"],self.data) if config.get("knowledge_root") else None
        self.skill_examples = SkillExamples(self.data / 'skills', config.get('skills_preview_port', 0))
        self.db = self.data / 'workspace.sqlite3'
        with self.connect() as c:
            c.executescript('PRAGMA journal_mode=WAL; CREATE TABLE IF NOT EXISTS workspace(id INTEGER PRIMARY KEY,revision INTEGER,body TEXT); CREATE TABLE IF NOT EXISTS history(id INTEGER PRIMARY KEY,revision INTEGER,body TEXT,created TEXT DEFAULT CURRENT_TIMESTAMP);')
            initial = {'name': config.get('name', 'Workspace'), 'boards': [{'id': 'main', 'title': 'Working canvas', 'cards': []}], 'notes': [], 'work': []}
            c.execute('INSERT OR IGNORE INTO workspace VALUES(1,0,?)', (json.dumps(initial),))
        self.hq = Headquarters(self.db)
        self.files = FileCatalog(self.data / 'files', config.get('file_roots', []))
        self.artifacts = ArtifactCatalog(self.data / 'artifacts', config.get('artifact_store', {'provider': 'local'}), self.files)
        self.search_index = SearchIndex(self.data / 'search-index.sqlite3')
        self.web = WebPages(self.data / 'web')
        self.providers = ProviderRegistry()
        self.providers.register('files', self.files, {'inventory': 'filesystem.read', 'collections': 'filesystem.read', 'status': 'filesystem.read'})
        self.providers.register('tasks', LocalTaskProvider(self), {'list': 'tasks.read', 'edit': 'tasks.write'})
        self.providers.register('search', self.search_index, {'search': 'search.read'})
        self.providers.register('skills', self.skill_editor, {'document': 'skills.read', 'history': 'skills.read', 'save': 'skills.write'})
        self.providers.register('web', self.web, {'listing':'web.read','get':'web.read','capture':'web.capture'})
        self.ai = LoopbackAIProvider(config['ai_runtime_url']) if config.get('ai_runtime_url') else None
        if self.ai:
            self.providers.register('ai', self.ai, {
                'status': 'ai.read',
                'login': 'ai.manage',
                'login_status': 'ai.read',
                'logout': 'ai.manage',
            })

    def connect(self):
        return connect(self.db)

    def invalidate(self):
        self._catalog_until = 0

    def catalog(self):
        with self._catalog_lock:
            if self._catalog_cache is not None and time.monotonic() < self._catalog_until:
                return self._catalog_cache
            result = []
            warnings = []
            for p in self.prompts.state()['prompts']:
                result.append(dict(id='prompts:' + p['id'], mode='prompts', title=p['title'], description=p.get('subtitle', ''), group=p.get('group', ''), key=p.get('key', ''), body=p['body'], revision=p['revision'], status=p.get('status', ''), approval=p.get('approval')))
            with connect(self.config['culture']) as c:
                blocks = {r[0]: {'body': r[1], 'revision': r[2]} for r in c.execute('SELECT id,body,rev FROM blocks')}
            seed = json.loads(Path(self.config['culture_seed']).read_text())
            seen = set()
            for e in seed.get('entries', []):
                parts = [k for k in e['parts'] if k in blocks]
                seen.update(parts)
                result.append(dict(id='culture:' + e['id'], mode='culture', title=e['title'], description=e.get('detail', ''), group=e.get('group', 'Culture'), key=e.get('key', ''), body='\n\n'.join((blocks[k]['body'] for k in parts)), parts=[dict(id=k, **blocks[k]) for k in parts]))
            for key, block in blocks.items():
                if key not in seen:
                    result.append(dict(id='culture:block-' + key, mode='culture', title=key.replace('-', ' ').capitalize(), group='Culture', body=block['body'], parts=[dict(id=key, **block)]))
            tasks = LocalTaskProvider(self).list()
            for task in tasks['tasks']:
                result.append(dict(id='tasks:' + task['id'], mode='tasks', title=task['title'], description=task.get('group', ''), group=task.get('group', 'Tasks'), body='\n\n'.join((task.get(k, '') for k in ('outcome', 'doneWhen', 'context') if task.get(k))), task=task, revision=tasks['revision']))
            self.skills.config = json.loads(Path(self.config['skills_config']).read_text())
            self.skills.refresh()
            warnings += self.skills.warnings
            for sk in sorted(self.skills.listing()['skills'], key=lambda x: (x.get('order', 1000000), x['name'])):
                doc = self.skills.document(sk['id'])
                result.append(dict(id='skills:' + sk['id'], mode='skills', title=sk.get('label', sk['name']), description=sk['description'], group=sk.get('group', 'Skills'), key=sk.get('shortcut', ''), body=doc['text'], readonly=True, folder=sk['folder'], source=sk['source'], skillName=sk['name'], sha256=doc['sha256'], files=self.skills.files(sk['id']), aliases=sk.get('aliases',[]), stable=sk.get('stable',False), skillRevision=sk.get('revision','')))
            for collection in self.files.collections():
                result.append(dict(id='files:' + collection['id'], mode='files', title=collection['title'], description=collection['summary'], group=collection.get('project', ''), body='\n'.join((f['path'] for f in collection['files'])), readonly=True))
            for artifact in self.artifacts.listing()['artifacts']:
                result.append(dict(id='files:artifact-' + artifact['id'], mode='files', title=artifact['title'], description=artifact['logical_path'], group=artifact.get('project') or 'Files', body=artifact['logical_path'], readonly=True))
            for page in self.web.listing()['pages']:
                body='\n\n'.join(x for x in (page.get('selection',''),page.get('body','')) if x)[:20000]
                result.append(dict(id=page['ref'],mode='web',title=page['title'],description=page['description'],group=page['host'],body=body,url=page['url'],capturedAt=page['capturedAt'],browser=page['browser'],screenshot=bool(page.get('screenshot')),readonly=True))
            references = self.config.get('references')
            if references:
                for reference in json.loads(Path(references).read_text()):
                    if reference.get('mode') != 'design':
                        raise ValueError('Unsupported reference record')
                    result.append(dict(reference, readonly=True))
            self.search_index.update(result)
            self._catalog_cache = {'items': result, 'warnings': warnings, 'designSources': [], 'skillExamples': self.skill_examples.listing()}
            self._catalog_until = time.monotonic() + 2
            return self._catalog_cache

    def state(self):
        with self.connect() as c:
            rev, body = c.execute('SELECT revision,body FROM workspace WHERE id=1').fetchone()
        state = json.loads(body)
        state.setdefault('work', [])
        return dict(state, revision=rev)

    def save(self, d):
        b = d.get('state')
        if not (isinstance(b, dict) and isinstance(b.get('boards'), list) and isinstance(b.get('notes'), list)):
            raise ValueError('Invalid workspace')
        if not (0 < len(b['boards']) <= 100 and len(b['notes']) <= 3000):
            raise ValueError('Workspace limit exceeded')
        ids = set()
        for board in b['boards']:
            if not (isinstance(board.get('id'), str) and board['id'] not in ids and isinstance(board.get('title'), str) and (0 < len(board['title']) <= 200)):
                raise ValueError('Invalid board')
            ids.add(board['id'])
            if not (isinstance(board.get('cards'), list) and len(board['cards']) <= 1000):
                raise ValueError('Invalid cards')
            ci = set()
            for card in board['cards']:
                if not (isinstance(card.get('id'), str) and card['id'] not in ci and isinstance(card.get('ref'), str)):
                    raise ValueError('Invalid card')
                ci.add(card['id'])
                for k in ('x', 'y', 'w'):
                    if not (isinstance(card.get(k), (int, float)) and -100000 <= card[k] <= 100000):
                        raise ValueError('Invalid position')
                if not 240 <= card['w'] <= 1000:
                    raise ValueError('Invalid width')
        ids = set()
        for n in b['notes']:
            if not (isinstance(n.get('id'), str) and n['id'] not in ids and isinstance(n.get('title'), str) and (0 < len(n['title']) <= 200) and isinstance(n.get('body'), str) and (len(n['body']) <= 100000)):
                raise ValueError('Invalid note')
            ids.add(n['id'])
            if n.get('url'):
                if not (isinstance(n['url'], str) and len(n['url']) <= 4000 and (urlsplit(n['url']).scheme in ('http', 'https')) and urlsplit(n['url']).netloc):
                    raise ValueError('Invalid link')
            if n.get('image'):
                if not (isinstance(n['image'], str) and len(n['image']) < 1500000 and n['image'].startswith(('data:image/png;base64,', 'data:image/jpeg;base64,', 'data:image/webp;base64,'))):
                    raise ValueError('Invalid image')
        work = b.setdefault('work', [])
        if not (isinstance(work, list) and len(work) <= 500):
            raise ValueError('Invalid work records')
        wi = set()
        for w in work:
            if not (isinstance(w, dict) and isinstance(w.get('id'), str) and (w['id'] not in wi)):
                raise ValueError('Invalid work record')
            wi.add(w['id'])
            for k, limit in [('title', 200), ('outcome', 30000), ('artifact', 4000), ('decision', 30000), ('nextAction', 30000), ('contextQuery', 500)]:
                if not (isinstance(w.get(k, ''), str) and len(w.get(k, '')) <= limit):
                    raise ValueError('Invalid ' + k)
            if not (w.get('title', '').strip() and w.get('status', 'active') in ('active', 'waiting', 'done')):
                raise ValueError('Invalid work status')
            sources = w.get('sources', [])
            if not (isinstance(sources, list) and len(sources) <= 80 and all((isinstance(x, str) and 0 < len(x) <= 500 for x in sources))):
                raise ValueError('Invalid work sources')
            returns = w.get('returns', [])
            if not (isinstance(returns, list) and len(returns) <= 500):
                raise ValueError('Invalid result history')
            ri = set()
            for r in returns:
                if not (isinstance(r, dict) and isinstance(r.get('id'), str) and (r['id'] not in ri)):
                    raise ValueError('Invalid result')
                ri.add(r['id'])
                for k, limit in [('artifact', 4000), ('change', 40000), ('checks', 30000), ('createdAt', 100)]:
                    if not (isinstance(r.get(k, ''), str) and len(r.get(k, '')) <= limit):
                        raise ValueError('Invalid result ' + k)
                if not r.get('review', 'unreviewed') in ('unreviewed', 'direction', 'implementation', 'superseded'):
                    raise ValueError('Invalid result review state')
        if not (isinstance(b.get('name'), str) and 0 < len(b['name']) <= 80):
            raise ValueError('Invalid name')
        b = {k: b[k] for k in ('name', 'boards', 'notes', 'work')}
        request_id = d.get('requestId')
        digest = hashlib.sha256(json.dumps(b, sort_keys=True).encode()).hexdigest()
        if not (isinstance(request_id, str) and 0 < len(request_id) <= 200):
            raise ValueError('A stable request ID is required')
        with self.lock, self.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            if request_id:
                prior = c.execute('SELECT digest,response FROM workspace_requests WHERE id=?', (request_id,)).fetchone()
                if prior:
                    if prior[0] != digest:
                        raise Conflict('Request ID reused for different content')
                    return json.loads(prior[1])
            rev, old = c.execute('SELECT revision,body FROM workspace WHERE id=1').fetchone()
            if d.get('revision') != rev:
                raise Conflict('Workspace changed in another tab. Your draft is kept; reload after copying it.')
            c.execute('INSERT INTO history(revision,body) VALUES(?,?)', (rev, old))
            c.execute('UPDATE workspace SET revision=?,body=? WHERE id=1', (rev + 1, json.dumps(b)))
            if request_id:
                c.execute('INSERT INTO workspace_requests VALUES(?,?,?)', (request_id, digest, json.dumps({'revision': rev + 1})))
        return {'revision': rev + 1}

    def agent_work(self, d):
        from .adapters.headquarters import text, now
        request_id = text(d, 'requestId', 200, True)
        actor = text(d, 'actor', 120, True)
        action = text(d, 'action', 50, True)
        payload = d.get('record', {})
        if not isinstance(payload, dict):
            raise ValueError('Invalid record')
        digest = hashlib.sha256(json.dumps(d, sort_keys=True).encode()).hexdigest()
        receipt = 'work:' + request_id
        with self.lock, self.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            prior = c.execute('SELECT digest,response FROM hq_requests WHERE id=?', (receipt,)).fetchone()
            if prior:
                if prior[0] != digest:
                    raise Conflict('Request ID reused for different content')
                return json.loads(prior[1])
            rev, body = c.execute('SELECT revision,body FROM workspace WHERE id=1').fetchone()
            s = json.loads(body)
            s.setdefault('work', [])
            if action == 'work.create':
                key = text(payload, 'id', 200) or str(uuid.uuid4())
                if not not any((w['id'] == key for w in s['work'])):
                    raise ValueError('Work ID already exists')
                w = dict(id=key, title=text(payload, 'title', 200, True), outcome=text(payload, 'outcome'), artifact=text(payload, 'artifact', 4000), decision=text(payload, 'decision'), nextAction=text(payload, 'nextAction'), contextQuery='', status='active', sources=[], returns=[])
                if not len(s['work']) < 500:
                    raise ValueError('Work record limit reached')
                s['work'].append(w)
            elif action == 'work.return':
                key = text(payload, 'workId', 200, True)
                w = next((w for w in s['work'] if w['id'] == key), None)
                if not w is not None:
                    raise ValueError('Work not found')
                brief = text(payload, 'briefId', 200)
                if not (not brief or any((b['id'] == brief for b in w.get('handoffs', [])))):
                    raise ValueError('Brief is not attached to this work')
                r = dict(id=str(uuid.uuid4()), artifact=text(payload, 'artifact', 4000), change=text(payload, 'change', 40000, True), checks=text(payload, 'checks'), briefId=brief, review='unreviewed', createdAt=now(), actor=actor)
                if not len(w.get('returns', [])) < 500:
                    raise ValueError('Result history limit reached')
                w.setdefault('returns', []).append(r)
            else:
                raise ValueError('Agents can create work or return a result. Use the review UI for adoption.')
            c.execute('INSERT INTO history(revision,body) VALUES(?,?)', (rev, body))
            c.execute('UPDATE workspace SET revision=?,body=? WHERE id=1', (rev + 1, json.dumps(s)))
            out = dict(ok=True, workId=key, revision=rev + 1)
            if action == 'work.return':
                out['resultId'] = r['id']
            c.execute('INSERT INTO hq_requests VALUES(?,?,?)', (receipt, digest, json.dumps(out)))
            return out

    def edit(self, d):
        ref = d['id']
        mode, key = ref.split(':', 1)
        if mode == 'prompts':
            code, result = self.prompts.mutate(dict(id=key, action='revise', actor='workspace', expectedRevision=d['revision'], requestId=d.get('requestId', str(uuid.uuid4())), changes={'body': d['body'], 'changeNote': 'Edited in Workspace'}))
            if code == 409:
                raise Conflict(result.get('error', 'Prompt changed'))
            if code != 200:
                raise ValueError(result.get('error', 'Prompt could not be saved'))
            return {'ok': True, 'prompt': result['prompt']}
        elif mode == 'culture':
            parts = d.get('parts')
            if not (isinstance(parts, list) and parts):
                raise ValueError('No source blocks')
            with connect(self.config['culture'], timeout=15) as c:
                c.execute('BEGIN IMMEDIATE')
                request_id=d.get('requestId')
                if not isinstance(request_id,str) or not 0<len(request_id)<=200:raise ValueError('A stable request ID is required')
                payload_digest=hashlib.sha256(json.dumps(d,sort_keys=True).encode()).hexdigest()
                prior=c.execute('SELECT digest,response FROM requests WHERE id=?',(request_id,)).fetchone()
                if prior:
                    if prior[0]!=payload_digest:raise Conflict('Request ID reused for different content')
                    return json.loads(prior[1])
                for p in parts:
                    if not (isinstance(p['body'], str) and len(p['body']) <= 60000):
                        raise ValueError('Invalid text')
                    row = c.execute('SELECT body,rev FROM blocks WHERE id=?', (p['id'],)).fetchone()
                    if not row:
                        raise ValueError('Unknown source block')
                    if row[1] != p['revision']:
                        raise Conflict('Culture changed in another tab. Your draft is kept.')
                    c.execute('INSERT INTO history(block,body,rev,created,note) VALUES(?,?,?,?,?)', (p['id'], row[0], row[1], time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'Edited in Workspace'))
                    c.execute('UPDATE blocks SET body=?,rev=rev+1 WHERE id=?', (p['body'], p['id']))
                c.execute('INSERT INTO requests VALUES(?,?,?)',(request_id,payload_digest,json.dumps({'ok':True})))
        elif mode == 'tasks':
            with connect(self.config['tasks'], timeout=15) as c:
                c.execute('BEGIN IMMEDIATE')
                request_id = d.get('requestId')
                payload_digest = hashlib.sha256(json.dumps(d, sort_keys=True).encode()).hexdigest()
                if not isinstance(request_id, str) or not request_id or len(request_id) > 200:
                    raise ValueError('A stable request ID is required')
                prior = c.execute('SELECT digest,response FROM requests WHERE id=?', (request_id,)).fetchone()
                if prior:
                    if prior[0] != payload_digest:
                        raise Conflict('Request ID reused for different content')
                    return json.loads(prior[1])
                current = json.loads(c.execute('SELECT body FROM state WHERE id=1').fetchone()[0])
                if d.get('revision') != current['revision']:
                    raise Conflict('Tasks changed elsewhere. Your draft is kept; reload before saving.')
                t = d['task']
                if not isinstance(t, dict):
                    raise ValueError('Invalid task')
                for k, limit in [('title', 200), ('group', 80), ('owner', 120), ('due', 10), ('outcome', 20000), ('doneWhen', 20000), ('context', 20000)]:
                    if not (isinstance(t.get(k), str) and len(t[k]) <= limit):
                        raise ValueError('Invalid ' + k)
                if not (t['title'].strip() and t.get('status') in ('open', 'doing', 'waiting', 'done')):
                    raise ValueError('Invalid task')
                if key == 'new':
                    t['id'] = 'workspace-' + uuid.uuid4().hex
                    current['tasks'].append(t)
                else:
                    target = next((x for x in current['tasks'] if x['id'] == key), None)
                    if target is None:
                        raise ValueError('Task not found')
                    target.update({k: v for k, v in t.items() if k in ('title', 'group', 'owner', 'due', 'outcome', 'doneWhen', 'context', 'status')})
                old = c.execute('SELECT body FROM state WHERE id=1').fetchone()[0]
                c.execute('INSERT INTO history(revision,body) VALUES(?,?)', (current['revision'], old))
                current['revision'] += 1
                c.execute('UPDATE state SET body=? WHERE id=1', (json.dumps(current),))
                c.execute('INSERT INTO requests VALUES(?,?,?)', (request_id, payload_digest, json.dumps({'ok': True, 'id': 'tasks:' + t.get('id', key)})))
            return {'ok': True, 'id': 'tasks:' + t.get('id', key)}
        else:
            raise ValueError('This source is read-only')
        return {'ok': True}

    def history(self, ref):
        mode, key = ref.split(':', 1)
        if mode == 'prompts':
            with self.prompts.connect() as c:
                return [dict(r) for r in c.execute('SELECT at,action,before_data,after_data FROM events WHERE prompt_id=? ORDER BY seq DESC LIMIT 40', (key,))]
        if mode == 'culture':
            with connect(self.config['culture']) as c:
                return [{'revision': r[0], 'body': r[1], 'created': r[2]} for r in c.execute('SELECT rev,body,created FROM history WHERE block=? ORDER BY id DESC LIMIT 40', (key,))]
        return []
