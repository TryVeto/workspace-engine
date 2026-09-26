import base64
import http.client
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'packages/engine'))
from workspace_engine.instance import demo
from workspace_engine.server import make_server
from workspace_engine.web_pages import WebPages

class WebPageStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.store=WebPages(Path(self.temp.name)/'web')
    def test_capture_is_idempotent_and_private_asset_is_retrievable(self):
        shot='data:image/jpeg;base64,'+base64.b64encode(b'fake-jpeg').decode()
        request={'requestId':'capture-1','record':{'title':'Example','url':'https://example.test/a','selection':'chosen','text':'page body','screenshot':shot,'browser':'Fixture','tabs':[{'title':'Other','url':'https://example.test/b'}]}}
        first=self.store.capture(request,'Bridge');second=self.store.capture(request,'Bridge')
        self.assertEqual(first,second);record=self.store.get(first['id'])
        self.assertEqual(record['selection'],'chosen');self.assertEqual(record['tabs'][0]['title'],'Other')
        raw,mime=self.store.asset(first['id']);self.assertEqual(raw,b'fake-jpeg');self.assertEqual(mime,'image/jpeg')
    def test_capture_rejects_credentials_and_non_web_urls(self):
        for url in ('file:///tmp/x',('https://'+'user:pass@'+'example.test/x'),'javascript:alert(1)'):
            with self.assertRaises(ValueError):
                self.store.capture({'requestId':'x-'+str(len(url)),'record':{'url':url}},'Bridge')

class WebHTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        config,root=demo(Path(self.temp.name)/'runtime');self.secret='bridge-'+os.urandom(18).hex()
        self.env=patch.dict(os.environ,{'WEB_BRIDGE_TEST':self.secret});self.env.start();self.addCleanup(self.env.stop)
        config['agents']={'Browser bridge':{'secretRef':'env:WEB_BRIDGE_TEST','capabilities':['web.capture']}}
        self.server=make_server(config,root,0);self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start();self.addCleanup(self.close)
        self.origin='http://127.0.0.1:'+str(self.server.server_port)
        code,state,headers=self.request('GET','/api/state');self.assertEqual(code,200);self.cookie=headers['Set-Cookie'].split(';')[0];self.token=state['token']
    def close(self):self.server.shutdown();self.server.server_close();self.thread.join()
    def request(self,method,path,data=None,headers=None):
        conn=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=5);raw=json.dumps(data)if data is not None else None
        h={'Content-Type':'application/json'}if raw is not None else{};h.update(headers or {});conn.request(method,path,raw,h);response=conn.getresponse();body=response.read();meta=dict(response.getheaders());code=response.status;conn.close()
        try:body=json.loads(body)
        except ValueError:pass
        return code,body,meta
    def test_bridge_can_capture_but_cannot_read(self):
        auth={'Authorization':'Bearer '+self.secret}
        request={'action':'capture','requestId':'native-1','record':{'title':'Captured','url':'https://example.test/page','text':'Evidence from the page','browser':'Fixture'}}
        code,result,_=self.request('POST','/api/web',request,auth);self.assertEqual(code,200);self.assertTrue(result['ref'].startswith('web:'))
        self.assertEqual(self.request('GET','/api/web',headers=auth)[0],403)
        owner={'Cookie':self.cookie};code,pages,_=self.request('GET','/api/web',headers=owner);self.assertEqual(code,200);self.assertEqual(pages['pages'][0]['title'],'Captured')
        code,catalog,_=self.request('GET','/api/catalog',headers=owner);self.assertEqual(code,200);self.assertTrue(any(i['id']==result['ref']for i in catalog['items']))
        self.assertEqual(self.request('POST','/api/web',request,{**auth,'Origin':self.origin})[0],403)
    def test_owner_can_capture_through_csrf_boundary(self):
        request={'action':'capture','requestId':'owner-1','record':{'title':'Owner capture','url':'https://example.test/owner'}}
        headers={'Cookie':self.cookie,'Origin':self.origin,'X-Workspace-Token':self.token}
        self.assertEqual(self.request('POST','/api/web',request,headers)[0],200)

if __name__=='__main__':unittest.main()
