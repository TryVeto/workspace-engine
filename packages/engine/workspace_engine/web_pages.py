"""Captured web pages are local evidence that can be attached to Workspace work."""
from __future__ import annotations
import base64, hashlib, json, sqlite3, uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit
from .storage import connect

class WebPages:
    def __init__(self, root: Path):
        self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True,mode=0o700)
        self.assets=self.root/'assets';self.assets.mkdir(exist_ok=True,mode=0o700)
        self.db=self.root/'web.sqlite3'
        with connect(self.db) as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS pages(
              id TEXT PRIMARY KEY,title TEXT NOT NULL,url TEXT NOT NULL,host TEXT NOT NULL,
              selection TEXT NOT NULL,body TEXT NOT NULL,screenshot TEXT,
              tabs TEXT NOT NULL,browser TEXT NOT NULL,captured_at TEXT NOT NULL,actor TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS requests(
              id TEXT PRIMARY KEY,digest TEXT NOT NULL,response TEXT NOT NULL);
            ''')

    def _record(self,row):
        if not row:return None
        keys=('id','title','url','host','selection','body','screenshot','tabs','browser','capturedAt','actor')
        out=dict(zip(keys,row));out['tabs']=json.loads(out['tabs'] or '[]')
        out['ref']='web:'+out['id'];out['mode']='web'
        out['description']=(out['selection'] or out['body'][:240]).strip()
        return out

    def listing(self,limit=200):
        with connect(self.db) as db:
            rows=db.execute('SELECT id,title,url,host,selection,body,screenshot,tabs,browser,captured_at,actor FROM pages ORDER BY captured_at DESC LIMIT ?',(limit,)).fetchall()
        return {'pages':[self._record(row) for row in rows]}

    def get(self,key):
        key=str(key).removeprefix('web:')
        with connect(self.db) as db:
            row=db.execute('SELECT id,title,url,host,selection,body,screenshot,tabs,browser,captured_at,actor FROM pages WHERE id=?',(key,)).fetchone()
        if not row:raise FileNotFoundError(key)
        return self._record(row)

    def _screenshot(self,key,value):
        if not value:return None
        if not isinstance(value,str) or ',' not in value:raise ValueError('Invalid page screenshot')
        header,encoded=value.split(',',1)
        mime={'data:image/jpeg;base64':'jpg','data:image/png;base64':'png'}.get(header)
        if not mime:raise ValueError('Use a JPEG or PNG screenshot')
        try:raw=base64.b64decode(encoded,validate=True)
        except Exception:raise ValueError('Invalid page screenshot') from None
        if len(raw)>3_000_000:raise ValueError('Page screenshot is too large')
        path=self.assets/f'{key}.{mime}';path.write_bytes(raw)
        return path.name

    def capture(self,request,actor):
        request_id=request.get('requestId');record=request.get('record')
        if not isinstance(request_id,str) or not 0<len(request_id)<=200:raise ValueError('A stable request ID is required')
        if not isinstance(record,dict):raise ValueError('Invalid web page')
        title=str(record.get('title') or 'Web page').strip()[:300]
        url=str(record.get('url') or '').strip()
        parsed=urlsplit(url)
        if parsed.scheme not in ('http','https') or not parsed.netloc or parsed.username or parsed.password:raise ValueError('Use a complete HTTP or HTTPS page URL')
        selection=str(record.get('selection') or '')[:20_000]
        body=str(record.get('text') or '')[:250_000]
        browser=str(record.get('browser') or 'Browser')[:120]
        tabs=record.get('tabs') or []
        if not isinstance(tabs,list):raise ValueError('Invalid tab context')
        safe_tabs=[]
        for tab in tabs[:100]:
            if not isinstance(tab,dict):continue
            candidate=str(tab.get('url') or '')
            u=urlsplit(candidate)
            if u.scheme not in ('http','https') or not u.netloc:continue
            safe_tabs.append({'title':str(tab.get('title') or '')[:300],'url':candidate[:4000],'active':bool(tab.get('active')),'pinned':bool(tab.get('pinned'))})
        digest=hashlib.sha256(json.dumps(record,sort_keys=True).encode()).hexdigest()
        with connect(self.db) as db:
            prior=db.execute('SELECT digest,response FROM requests WHERE id=?',(request_id,)).fetchone()
            if prior:
                if prior[0]!=digest:raise ValueError('Request ID reused for different page content')
                return json.loads(prior[1])
            key=str(uuid.uuid4());screenshot=self._screenshot(key,record.get('screenshot'))
            captured=str(record.get('capturedAt') or datetime.now(timezone.utc).isoformat())[:80]
            db.execute('INSERT INTO pages VALUES(?,?,?,?,?,?,?,?,?,?,?)',(key,title,url,parsed.hostname or '',selection,body,screenshot,json.dumps(safe_tabs),browser,captured,str(actor)[:120]))
            result={'id':key,'ref':'web:'+key,'title':title,'url':url,'openUrl':'/#web/'+key}
            db.execute('INSERT INTO requests VALUES(?,?,?)',(request_id,digest,json.dumps(result)))
        return result

    def asset(self,key):
        record=self.get(key);name=record.get('screenshot')
        if not name:raise FileNotFoundError(key)
        path=(self.assets/name).resolve()
        if not path.is_relative_to(self.assets.resolve()) or not path.is_file():raise FileNotFoundError(key)
        return path.read_bytes(),'image/jpeg' if path.suffix=='.jpg' else'image/png'
