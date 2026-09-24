from workspace_engine.storage import connect as durable_connect
"""Durable headquarters records. Local callers share the Mac trust boundary."""
import hashlib, json, re, sqlite3, time, uuid
from pathlib import Path

class HQConflict(ValueError): pass

def now():
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())

def text(d, key, limit=30000, required=False):
    v=d.get(key, '')
    if not isinstance(v,str) or len(v)>limit or (required and not v.strip()):
        raise ValueError('Invalid '+key)
    return v.strip() if key in ('title','actor') else v

class Headquarters:
    def __init__(self, db):
        self.db=db
        with self.connect() as c:
            c.executescript("""
            CREATE TABLE IF NOT EXISTS hq_records(kind TEXT,id TEXT,version INTEGER,body TEXT,PRIMARY KEY(kind,id));
            CREATE TABLE IF NOT EXISTS hq_events(seq INTEGER PRIMARY KEY AUTOINCREMENT,kind TEXT,record_id TEXT,actor TEXT,body TEXT,created TEXT);
            CREATE TABLE IF NOT EXISTS hq_requests(id TEXT PRIMARY KEY,digest TEXT,response TEXT);
            CREATE TABLE IF NOT EXISTS workspace_requests(id TEXT PRIMARY KEY,digest TEXT,response TEXT);
            """)
            for key,title in [('goal','Company goal'),('strategy','Strategy')]:
                c.execute('INSERT OR IGNORE INTO hq_records VALUES(?,?,0,?)',('company',key,json.dumps(dict(id=key,title=title,body='',source='',status='draft',updatedAt='',actor=''))))
    def connect(self):
        return durable_connect(self.db,timeout=15)
    def state(self):
        with self.connect() as c:
            records=[dict(json.loads(b),version=v) for k,i,v,b in c.execute('SELECT kind,id,version,body FROM hq_records WHERE kind IN ("company","decision")')]
            updates=[dict(json.loads(b),version=v) for v,b in c.execute('SELECT version,body FROM hq_records WHERE kind="update" ORDER BY rowid DESC LIMIT 200')]
            seq=c.execute('SELECT coalesce(max(seq),0) FROM hq_events').fetchone()[0]
        return dict(company=[r for r in records if r.get('kind')!='decision'],decisions=sorted([r for r in records if r.get('kind')=='decision'],key=lambda r:(r['status']!='open',r.get('due') or '9999',r['createdAt'])),updates=updates,revision=seq)
    def record(self,kind,key):
        with self.connect() as c:
            row=c.execute('SELECT version,body FROM hq_records WHERE kind=? AND id=?',(kind,key)).fetchone()
        if not row:raise ValueError('Record not found')
        return dict(json.loads(row[1]),version=row[0])
    def history(self,kind,key):
        with self.connect() as c:
            return [dict(seq=s,actor=a,createdAt=t,record=json.loads(b)) for s,a,t,b in c.execute('SELECT seq,actor,created,body FROM hq_events WHERE kind=? AND record_id=? ORDER BY seq DESC',(kind,key))]
    def mutate(self,d):
        request_id=text(d,'requestId',200,True); actor=text(d,'actor',120,True)
        action=text(d,'action',50,True); payload=d.get('record',{})
        if not isinstance(payload,dict):raise ValueError('Invalid record')
        digest=hashlib.sha256(json.dumps(d,sort_keys=True).encode()).hexdigest()
        with self.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            prior=c.execute('SELECT digest,response FROM hq_requests WHERE id=?',(request_id,)).fetchone()
            if prior:
                if prior[0]!=digest:raise HQConflict('Request ID was already used for different content.')
                return json.loads(prior[1])
            kind,verb=action.split('.',1)
            if kind not in ('company','decision','update'):raise ValueError('Unknown record type')
            key=text(payload,'id',200) or str(uuid.uuid4())
            old=c.execute('SELECT version,body FROM hq_records WHERE kind=? AND id=?',(kind,key)).fetchone()
            if verb=='create':
                if old:raise HQConflict('This record already exists.')
                r=dict(id=key,kind=kind,createdAt=now(),actor=actor)
                version=0
            else:
                if not old:raise ValueError('Record not found')
                version=old[0];r=json.loads(old[1])
                if d.get('version')!=version:raise HQConflict('This record changed. Reload it before saving; your draft is preserved.')
            if kind=='update' and verb=='create':
                r.update(title=text(payload,'title',200,True),body=text(payload,'body',30000,True),workId=text(payload,'workId',200),artifact=text(payload,'artifact',4000),checks=text(payload,'checks',30000),nextAction=text(payload,'nextAction',30000),status=payload.get('status','working'))
                if r['status'] not in ('working','waiting','returned','paused'):raise ValueError('Invalid update status')
            elif kind=='decision' and verb=='create':
                options=payload.get('options',[])
                if not isinstance(options,list) or not 2<=len(options)<=6 or any(not isinstance(o,str) or not o.strip() or len(o)>2000 for o in options):raise ValueError('Provide two to six concrete options.')
                r.update(title=text(payload,'title',200,True),body=text(payload,'body',30000,True),recommendation=text(payload,'recommendation',10000,True),options=options,workId=text(payload,'workId',200),artifact=text(payload,'artifact',4000),due=text(payload,'due',10),status='open',answer='',reason='',resolvedBy='',resolvedAt='')
                if r['due']:
                    import datetime
                    datetime.date.fromisoformat(r['due'])
            elif kind=='decision' and verb in ('resolve','reopen'):
                if verb=='resolve':
                    if r['status']!='open':raise HQConflict('This decision is already resolved.')
                    r.update(status='resolved',answer=text(payload,'answer',10000,True),reason=text(payload,'reason'),resolvedBy=actor,resolvedAt=now())
                else:r.update(status='open',answer='',reason='',resolvedBy='',resolvedAt='')
            elif kind=='company' and verb=='edit':
                status=payload.get('status','draft')
                if status not in ('draft','current'):raise ValueError('Invalid company status')
                r.update(body=text(payload,'body',40000,True),source=text(payload,'source',4000,True),status=status,actor=actor)
            else:raise ValueError('Unknown action')
            r['updatedAt']=now();version+=1
            c.execute('INSERT OR REPLACE INTO hq_records VALUES(?,?,?,?)',(kind,key,version,json.dumps(r)))
            c.execute('INSERT INTO hq_events(kind,record_id,actor,body,created) VALUES(?,?,?,?,?)',(kind,key,actor,json.dumps(dict(r,version=version)),now()))
            response=dict(ok=True,record=dict(r,version=version))
            c.execute('INSERT INTO hq_requests VALUES(?,?,?)',(request_id,digest,json.dumps(response)))
            return response

