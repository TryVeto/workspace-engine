"""Loopback HTTP adapter. UI requests never receive integration credentials."""
import gzip
import hashlib
import json
import mimetypes
import secrets
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlsplit
from . import __version__
from .model import Workspace
from .security import RequestPolicy, Sessions
from .adapters.file_tree import children as tree_children
from .adapters.skill_video import byte_range

ROOT=Path(__file__).resolve().parents[3]
CSP="default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; media-src 'self'; connect-src 'self'; frame-src http://*.skill-example.localhost:*; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"

def public_instance(config):
    url=config.get('assistant_url','')
    if url and urlsplit(url).scheme not in ('http','https'):
        raise ValueError('Assistant URL must use HTTP or HTTPS')
    return dict(name=config.get('name','Workspace'),owner=config.get('owner','Workspace owner'),assistantUrl=url,aiConfigured=bool(config.get('ai_runtime_url')),version=__version__)

def make_server(config, data, port=8988, app_factory=Workspace):
    instance=public_instance(config);app=app_factory(config,data)
    sessions=Sessions(instance['owner'],config.get('session_ttl_seconds',1800),config.get('agents'),capabilities=config.get('capabilities'))
    assets=json.loads((ROOT/'apps/web/assets.json').read_text())
    class Handler(BaseHTTPRequestHandler):
        protocol_version='HTTP/1.1'
        def log_message(self,*args):pass
        def setup(self):
            super().setup();self.connection.settimeout(15)
        def send(self,status,value,mime='application/json',headers=None):
            raw=value if isinstance(value,bytes) else json.dumps(value,ensure_ascii=False).encode()
            extra=dict(headers or {})
            if len(raw)>2048 and not mime.startswith(('image/','video/')) and 'gzip' in self.headers.get('Accept-Encoding',''):
                raw=gzip.compress(raw,compresslevel=3);extra.update({'Content-Encoding':'gzip','Vary':'Accept-Encoding'})
            self.send_response(status)
            defaults={'Content-Type':mime+('; charset=utf-8' if mime.startswith(('text/','application/json','application/javascript'))else''),'Content-Length':str(len(raw)),'Cache-Control':'no-store','X-Content-Type-Options':'nosniff','Referrer-Policy':'no-referrer','Content-Security-Policy':CSP,'Cross-Origin-Resource-Policy':'same-origin','Permissions-Policy':'camera=(), microphone=(), geolocation=()'}
            for key,value in {**defaults,**extra}.items():self.send_header(key,value)
            self.end_headers()
            if self.command!='HEAD':self.wfile.write(raw)
        def route_path(self):return unquote(urlsplit(self.path).path)
        def permitted_request(self):
            return self.server.policy.allowed(self.command,self.route_path(),self.headers)
        def identity(self,capability,write=False):
            principal=sessions.principal(self.headers,write);principal.require(capability);return principal
        def error(self,error):
            if isinstance(error,PermissionError):
                return self.send(401 if str(error).startswith('Session expired') else 403,{'error':str(error)})
            if 'Conflict' in type(error).__name__:return self.send(409,{'error':str(error)})
            if isinstance(error,FileNotFoundError):return self.send(404,{'error':'Record or file not found'})
            if isinstance(error,(ValueError,KeyError,TypeError,LookupError)):return self.send(400,{'error':str(error) if isinstance(error,ValueError) else 'Invalid request'})
            reference=secrets.token_hex(4)
            return self.send(500,{'error':'Could not complete the request. Your draft is kept.','reference':reference})
        def do_GET(self):
            if not self.permitted_request():return self.send(403,{'error':'Unrecognized local origin'})
            path=self.route_path();q=parse_qs(urlsplit(self.path).query)
            try:
                if path=='/instance.js':return self.send(200,('const INSTANCE=Object.freeze('+json.dumps(instance).replace('<','\\u003c')+');').encode(),'application/javascript')
                if path in assets:
                    file=ROOT/assets[path]
                    if file.is_symlink() or not file.resolve().is_relative_to(ROOT) or any(p.is_symlink() for p in file.parents if p.is_relative_to(ROOT)):raise FileNotFoundError()
                    raw=file.read_bytes();tag='"'+hashlib.sha256(raw).hexdigest()+'"'
                    headers={'ETag':tag,'Cache-Control':'private, max-age=0, must-revalidate'}
                    if self.headers.get('If-None-Match')==tag:return self.send(304,b'',headers=headers)
                    return self.send(200,raw,mimetypes.guess_type(file)[0]or'application/octet-stream',headers)
                if path=='/api/state':
                    if self.headers.get('Authorization'):
                        self.identity('workspace.read');return self.send(200,app.state())
                    if 'workspace.read' not in sessions.capabilities:raise PermissionError('Missing capability: workspace.read')
                    key,csrf=sessions.issue(self.headers)
                    return self.send(200,dict(app.state(),token=csrf),headers={'Set-Cookie':f'workspace-session={key}; HttpOnly; SameSite=Strict; Path=/; Max-Age={sessions.ttl}'})
                if path=='/api/health':
                    self.identity('workspace.read')
                    return self.send(200,dict(ok=True,version=__version__,workspaceRevision=app.state()['revision'],hqRevision=app.hq.state()['revision'],uptimeSeconds=int(time.time()-app.started)))
                if path=='/api/knowledge':
                    self.identity('knowledge.read');return self.send(200,app.knowledge.status() if app.knowledge else {'configured':False})
                if path=='/api/insights/skills':
                    self.identity('insights.read');return self.send(200,app.skill_runs.insights())
                if path=='/api/skill-runs':
                    self.identity('insights.read');return self.send(200,app.skill_runs.listing(q.get('skillId',[None])[0],q.get('runId',[None])[0]))
                if path=='/api/catalog':
                    principal=sessions.principal(self.headers)
                    result=app.catalog();requirements={'prompts':'prompts.read','tasks':'tasks.read','skills':'skills.read','files':'filesystem.read','web':'web.read'}
                    result={**result,'items':[item for item in result['items'] if requirements.get(item['mode'],'workspace.read')in principal.capabilities]}
                    if 'skills.read'not in principal.capabilities:result['skillExamples']={}
                    return self.send(200,result)
                if path=='/api/hq':
                    principal=sessions.principal(self.headers);result=app.hq.state()
                    return self.send(200,{**result,'company':result['company']if'workspace.read'in principal.capabilities else[],'decisions':result['decisions']if'decisions.read'in principal.capabilities else[],'updates':result['updates']if'updates.read'in principal.capabilities else[]})
                if path.startswith('/api/hq/'):
                    parts=path.split('/');kind=parts[3]
                    self.identity({'decision':'decisions.read','update':'updates.read','company':'workspace.read'}[kind])
                    return self.send(200,app.hq.history(kind,parts[4])if len(parts)==6 and parts[5]=='history'else app.hq.record(kind,parts[4]))
                if path=='/api/agent':
                    self.identity('workspace.read');return self.send(200,(ROOT/'docs/AGENTS.md').read_bytes(),'text/plain')
                if path=='/api/providers':
                    self.identity('providers.inspect');return self.send(200,app.providers.describe())
                if path=='/api/web':
                    return self.send(200,app.providers.call(self.identity('web.read'),'web','listing'))
                if path.startswith('/api/web-asset/'):
                    self.identity('web.read');raw,mime=app.web.asset(path[len('/api/web-asset/'):])
                    return self.send(200,raw,mime,{'Content-Security-Policy':"default-src 'none'; sandbox; frame-ancestors 'none'"})
                if path.startswith('/api/web/'):
                    return self.send(200,app.providers.call(self.identity('web.read'),'web','get',path[len('/api/web/'):]))
                if path=='/api/ai/status':
                    if not app.ai:return self.send(200,{'configured':False})
                    out=app.providers.call(self.identity('ai.read'),'ai','status')
                    return self.send(200,{'configured':True,**out})
                if path.startswith('/api/ai/login/'):
                    if not app.ai:raise ValueError('AI runtime is not configured')
                    login_id=path[len('/api/ai/login/'):]
                    return self.send(200,app.providers.call(self.identity('ai.read'),'ai','login_status',login_id))
                if path=='/api/search':
                    principal=self.identity('search.read')
                    # Search must not broaden access beyond the authorized catalog.
                    allowed={i['id']for i in app.catalog()['items']if {'tasks':'tasks.read','skills':'skills.read','prompts':'prompts.read','files':'filesystem.read','web':'web.read'}.get(i['mode'],'workspace.read')in principal.capabilities}
                    return self.send(200,{'results':[r for r in app.providers.call(principal,'search','search',q.get('q',[''])[0])if r['id']in allowed]})
                if path=='/api/prompts':self.identity('prompts.read');return self.send(200,{'prompts':app.prompts.state()['prompts']})
                if path.startswith('/api/prompts/'):
                    self.identity('prompts.read');record=next((p for p in app.prompts.state()['prompts']if p['id']==path.rsplit('/',1)[-1]),None)
                    return self.send(200,{'prompt':record})if record else self.send(404,{'error':'Prompt not found'})
                if path.startswith('/api/history/'):
                    ref=path[len('/api/history/'):];self.identity('prompts.read'if ref.startswith('prompts:')else'workspace.read');return self.send(200,app.history(ref))
                if path=='/api/files/status':return self.send(200,app.providers.call(self.identity('filesystem.read'),'files','status'))
                if path=='/api/files/inventory':return self.send(200,app.providers.call(self.identity('filesystem.read'),'files','inventory',q.get('q',[''])[0],q.get('offset',[0])[0]))
                if path=='/api/files/collections':return self.send(200,app.providers.call(self.identity('filesystem.read'),'files','collections'))
                if path=='/api/files/export':self.identity('export.read');return self.send(200,app.files.export())
                if path=='/api/files/tree':self.identity('filesystem.read');return self.send(200,tree_children(app.files,q.get('path',[''])[0],q.get('offset',[0])[0]))
                if path=='/api/files/history':self.identity('filesystem.read');return self.send(200,app.files.history(q.get('id',[''])[0]))
                if path=='/api/artifacts':self.identity('filesystem.read');return self.send(200,app.artifacts.listing())
                if path=='/api/artifacts/history':self.identity('filesystem.read');return self.send(200,app.artifacts.history(q.get('id',[''])[0]))
                if path.startswith('/api/skill-doc/'):
                    return self.send(200,app.providers.call(self.identity('skills.read'),'skills','document',path[len('/api/skill-doc/'):],q.get('file',['SKILL.md'])[0]))
                if path.startswith('/api/skill-history/'):
                    return self.send(200,app.providers.call(self.identity('skills.read'),'skills','history',path[len('/api/skill-history/'):],q.get('file',['SKILL.md'])[0]))
                if path.startswith('/api/skill-asset/'):
                    self.identity('skills.read');relative=q.get('file',[''])[0];raw,mime=app.skills.image_asset(path[len('/api/skill-asset/'):],relative)
                    status,body,headers=byte_range(raw,self.headers.get('Range'))if mime.startswith('video/')else(200,raw,{})
                    headers.update({'Content-Disposition':('attachment'if q.get('download')==['1']else'inline')+"; filename*=UTF-8''"+quote(Path(relative).name),'Content-Security-Policy':"default-src 'none'; sandbox; frame-ancestors 'none'"})
                    return self.send(status,body,mime,headers)
                if path=='/api/export':self.identity('export.read');return self.send(200,dict(workspace=app.state(),catalog=app.catalog(),headquarters=app.hq.state()))
                return self.send(404,{'error':'Not found'})
            except Exception as error:return self.error(error)
        do_HEAD=do_GET
        def do_POST(self):
            if not self.permitted_request():return self.send(403,{'error':'Unrecognized local origin'})
            try:
                lengths=self.headers.get_all('Content-Length',[])
                if self.headers.get('Transfer-Encoding')or len(lengths)!=1 or not lengths[0].isdigit():return self.send(400,{'error':'A single content length is required'})
                size=int(lengths[0])
                if not 0<size<=4_000_000:return self.send(413,{'error':'Request exceeds the limit'})
                if self.headers.get_content_type()!='application/json':return self.send(415,{'error':'Use application/json'})
                principal=sessions.principal(self.headers,True)
                request=json.loads(self.rfile.read(size))
                if not isinstance(request,dict):raise ValueError('Use a JSON object')
                path=self.route_path()
                if path=='/api/knowledge':
                    principal.require('knowledge.commit')
                    if not app.knowledge:raise ValueError('No knowledge library configured')
                    out=app.knowledge.checkpoint(request.get('summary'))
                elif path=='/api/skill-runs':out=app.skill_runs.apply(request,principal)
                elif path=='/api/workspace':principal.require('workspace.write');out=app.save(request)
                elif path=='/api/prompts':
                    principal.require('prompts.write')
                    if not request.get('requestId'):raise ValueError('A stable request ID is required')
                    code,out=app.prompts.create_prompt(request.get('prompt'),principal.name,request['requestId'])
                    app.invalidate();return self.send(code,out)
                elif path=='/api/work':
                    principal.require('workspace.write');request['actor']=principal.name;out=app.agent_work(request)
                elif path=='/api/edit':
                    capability={'prompts':'prompts.write','tasks':'tasks.write','culture':'workspace.write'}.get(str(request.get('id','')).split(':')[0])
                    if not capability:raise ValueError('Unsupported record type')
                    principal.require(capability);out=app.providers.call(principal,'tasks','edit',request)if capability=='tasks.write'else app.edit(request)
                elif path=='/api/hq':
                    capability={'decision.create':'decisions.request','decision.resolve':'decisions.resolve','decision.reopen':'decisions.resolve','update.create':'updates.write','company.edit':'company.write'}.get(request.get('action'))
                    if not capability:raise ValueError('Unsupported headquarters action')
                    principal.require(capability);request['actor']=principal.name;out=app.hq.mutate(request)
                elif path=='/api/skill-save':out=app.providers.call(principal,'skills','save',request)
                elif path in ('/api/files','/api/artifacts'):
                    action=request.get('action');cap='filesystem.open'if action in('open','reveal')else'filesystem.read'if action in('preview','scan')else'filesystem.write'
                    principal.require(cap);out=(app.files if path=='/api/files'else app.artifacts).mutate(request)
                elif path=='/api/recall':
                    principal.require('search.read');allowed={i['id']for i in app.catalog()['items']if {'tasks':'tasks.read','skills':'skills.read','prompts':'prompts.read','files':'filesystem.read','web':'web.read'}.get(i['mode'],'workspace.read')in principal.capabilities}
                    results=app.providers.call(principal,'search','search',request.get('query',''),request.get('limit',12));out={'results':[dict(r,provider='Workspace',body=r['excerpt'])for r in results if r['id']in allowed],'warnings':[]}
                elif path=='/api/web':
                    if request.get('action')!='capture':raise ValueError('Unsupported web action')
                    out=app.providers.call(principal,'web','capture',request,principal.name)
                elif path=='/api/ai':
                    if not app.ai:raise ValueError('AI runtime is not configured')
                    action=request.get('action')
                    if action=='login':out=app.providers.call(principal,'ai','login')
                    elif action=='logout':out=app.providers.call(principal,'ai','logout')
                    else:raise ValueError('Unsupported AI action')
                else:return self.send(404,{'error':'Action not available'})
                app.invalidate();return self.send(200,out)
            except Exception as error:return self.error(error)
        def do_OPTIONS(self):return self.send(403,{'error':'Cross-origin requests are disabled'})
        def do_PUT(self):return self.send(405,{'error':'Method not allowed'})
        do_DELETE=do_PATCH=do_PUT
    server=ThreadingHTTPServer(('127.0.0.1',port),Handler);server.daemon_threads=True
    server.policy=RequestPolicy(server.server_port,config.get('host_aliases',()))
    server.workspace=app;server.sessions=sessions
    return server
