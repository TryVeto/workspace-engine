"""Read-only skill examples, served on one isolated loopback origin per run."""
import hashlib, json, mimetypes, re
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlsplit

class SkillExamples:
 def __init__(self, root, port=8989):
  self.root=Path(root);self.port=port
 def manifest(self):
  p=self.root/'manifest.json'
  return json.loads(p.read_text()) if p.is_file() else {'examples':[], 'runs':{}}
 def listing(self):
  m=self.manifest();examples=[]
  for original in m.get('examples',[]):
   item=dict(original);item['runs']={}
   for arm,key in original.get('runs',{}).items():
    run=m['runs'][key]
    item['runs'][arm]={k:run[k] for k in ('id','status','elapsed_seconds','skill_hash','output_hash','model') if k in run}
    item['runs'][arm]['url']=f'http://{key}.skill-example.localhost:{self.port}/index.html'
    item['runs'][arm]['files']=[f['path'] for f in run['files']]
   examples.append(item)
  research=self.root/'research.md'
  return {'examples':examples,'research':research.read_text() if research.is_file() else ''}
 def artifact(self, key, relative):
  run=self.manifest().get('runs',{}).get(key)
  if not run: raise FileNotFoundError('Example not found')
  entry=next((f for f in run['files'] if f['path']==relative),None)
  if not entry or any(x in ('','..','.') or x.startswith('.') for x in relative.split('/')) or '\\' in relative:raise FileNotFoundError('File not supplied')
  base=self.root/'artifacts'/key;path=base/relative
  if any(p.is_symlink() for p in (path,*path.parents) if p.is_relative_to(base)) or not path.resolve().is_relative_to(base.resolve()):raise FileNotFoundError('File not supplied')
  raw=path.read_bytes()
  if hashlib.sha256(raw).hexdigest()!=entry['sha256']:raise ValueError('Example integrity check failed')
  return raw, path.suffix.lower()

def make_preview_server(library, port):
 class Handler(BaseHTTPRequestHandler):
  def log_message(self,*args):pass
  def send(self,status,raw,mime='text/plain; charset=utf-8',extra=None):
   self.send_response(status)
   for k,v in {'Content-Type':mime,'Content-Length':str(len(raw)),'Cache-Control':'no-store','X-Content-Type-Options':'nosniff','Referrer-Policy':'no-referrer','Content-Security-Policy':"default-src 'none'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; media-src 'self' blob:; font-src 'self' data:; connect-src 'none'; frame-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors http://workspace.localhost http://workspace.localhost:* http://127.0.0.1:* http://localhost:*",**(extra or {})}.items():self.send_header(k,v)
   self.end_headers()
   if self.command!='HEAD':self.wfile.write(raw)
  def do_GET(self):
   hosts=self.headers.get_all('Host',[])
   match=re.fullmatch(r'([a-z0-9-]+)\.skill-example\.localhost:'+str(self.server.server_port),hosts[0]) if len(hosts)==1 else None
   if not match:return self.send(403,b'Unknown example origin')
   relative=unquote(urlsplit(self.path).path).lstrip('/') or 'index.html'
   try:raw,ext=library.artifact(match[1],relative)
   except FileNotFoundError:return self.send(404,b'File not supplied')
   except (OSError,ValueError):return self.send(409,b'Example integrity check failed')
   mime={'.html':'text/html; charset=utf-8','.htm':'text/html; charset=utf-8','.js':'text/javascript; charset=utf-8','.css':'text/css; charset=utf-8'}.get(ext,mimetypes.guess_type(relative)[0] or 'text/plain; charset=utf-8')
   if ext in ('.swift','.sh','.py','.cjs','.md','.txt'):mime='text/plain; charset=utf-8'
   headers={'Accept-Ranges':'bytes'};req=self.headers.get('Range')
   if req:
    m=re.fullmatch(r'bytes=(\d*)-(\d*)',req)
    if not m or not any(m.groups()):return self.send(416,b'',mime,{'Content-Range':f'bytes */{len(raw)}'})
    a,b=m.groups();start=int(a) if a else max(0,len(raw)-int(b));end=min(int(b),len(raw)-1) if a and b else len(raw)-1
    if start>end or start>=len(raw):return self.send(416,b'',mime,{'Content-Range':f'bytes */{len(raw)}'})
    headers['Content-Range']=f'bytes {start}-{end}/{len(raw)}'
    return self.send(206,raw[start:end+1],mime,headers)
   return self.send(200,raw,mime,headers)
  do_HEAD=do_GET
  def do_POST(self):self.send(405,b'Read-only example')
  do_PUT=do_PATCH=do_DELETE=do_POST
 server=ThreadingHTTPServer(('127.0.0.1',port),Handler);server.daemon_threads=True;library.port=server.server_port
 return server
