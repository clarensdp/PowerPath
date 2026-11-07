import base64, importlib.util, json, os, tempfile, threading, unittest, urllib.request, urllib.error
from http.server import ThreadingHTTPServer
from pathlib import Path
os.environ['POWERPATH_VAULT_PASSWORD']='test-only-a-strong-pass'
spec=importlib.util.spec_from_file_location('vault',Path(__file__).with_name('vault_server.py'))
v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v)
class TestVault(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.tmp=tempfile.TemporaryDirectory();v.DATA=Path(cls.tmp.name);v.init_db();cls.server=ThreadingHTTPServer(('127.0.0.1',0),v.Handler);cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start();cls.url=f'http://127.0.0.1:{cls.server.server_port}/api/v23/projects/project_1'
 @classmethod
 def tearDownClass(cls): cls.server.shutdown();cls.server.server_close();cls.tmp.cleanup()
 def request(self,path,method='GET',data=None,auth=True,headers=None):
  h=headers or {}
  if auth:h['Authorization']='Basic '+base64.b64encode(b'powerpath:test-only-a-strong-pass').decode()
  req=urllib.request.Request(self.url+path,method=method,data=data,headers=h)
  return urllib.request.urlopen(req)
 def test_lifecycle(self):
  with self.assertRaises(urllib.error.HTTPError) as e:self.request('/documents',auth=False)
  self.assertEqual(e.exception.code,401)
  h={'X-PP-Name':'test.pdf','X-PP-Category':'Utility study'}
  with self.request('/documents',method='POST',data=b'fixture',headers=h) as r: doc=json.load(r)
  self.assertEqual(len(doc['sha256']),64)
  with self.request('/documents') as r:self.assertEqual(json.load(r)['documents'][0]['name'],'test.pdf')
  with self.request('/documents/'+doc['id']) as r:self.assertEqual(r.read(),b'fixture')
  with self.request('/documents/'+doc['id'],method='DELETE') as r:self.assertTrue(json.load(r)['deleted'])
  with self.request('/audit') as r:self.assertEqual(len(json.load(r)['events']),2)
 def test_origin_rejected(self):
  with self.assertRaises(urllib.error.HTTPError) as e:self.request('/documents',method='POST',data=b'x',headers={'Origin':'https://attacker.example'})
  self.assertEqual(e.exception.code,403)
 def test_id_path_rejected(self):
  with self.assertRaises(urllib.error.HTTPError):self.request('/documents/..%2Fsecret')
if __name__=='__main__':unittest.main(verbosity=2)
