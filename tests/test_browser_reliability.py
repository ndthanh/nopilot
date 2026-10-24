"""Real Edge tests against a temporary local fixture, without Copilot/model calls."""
import json,pathlib,sys,tempfile,threading,unittest,zipfile
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from unittest.mock import patch
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
import playwright_runtime as runtime
from playwright_tool import export_project

class Fixture(BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def do_GET(self):
  if self.path=='/fail':self.send_response(503);self.end_headers();return
  self.send_response(200);self.send_header('Content-Type','text/html');self.end_headers()
  self.wfile.write(b'''<!doctype html><html><head><title>Reliability fixture</title></head><body>
  <p id="result">READY</p><button id="go" onclick="document.querySelector('#result').innerText='SUCCESS 42'">Run</button>
  <script>console.error('fixture error');fetch('/fail');setTimeout(()=>{throw Error('fixture pageerror')},1);</script>
  </body></html>''')

class BrowserReliabilityTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  try:import playwright.sync_api
  except ImportError:raise unittest.SkipTest('Install requirements-browser.txt')
  cls.server=ThreadingHTTPServer(('127.0.0.1',0),Fixture);cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start();cls.url='http://127.0.0.1:'+str(cls.server.server_port)+'/'
 @classmethod
 def tearDownClass(cls):cls.server.shutdown();cls.server.server_close();cls.thread.join(3)
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=pathlib.Path(self.temp.name)
  # Test-only local fixture opt-in. Production public URL validation stays intact.
  self.guard=patch.object(runtime,'public',side_effect=lambda url:url);self.guard.start()
  self.session=runtime.BrowserSession(self.url,self.root/'downloads')
 def tearDown(self):self.session.close();self.guard.stop();self.temp.cleanup()
 def test_diagnostics_and_entire_batch_prevalidation(self):
  self.session.page.wait_for_timeout(100)
  kinds={e['kind'] for e in self.session.diagnostics()['events']}
  self.assertTrue({'console','pageerror','http_error'}<=kinds,kinds)
  with self.assertRaises(ValueError):self.session.run([{'action':'click','selector':'#go'},{'action':'click','selector':'#go','javascript':'bad'}])
  self.assertEqual(self.session.page.locator('#result').inner_text(),'READY')
  self.session.run([{'action':'click','selector':'#missing'}])
  result=self.session.run([{'action':'assert_text','text':'missing'}]);self.assertIn('diagnostics',result)
  self.assertNotIn('secret=42',runtime.BrowserSession.safe_url('https://example.com/test?secret=42'))
 def test_export_verified_in_fresh_context_and_replay_bundle(self):
  self.session.run([{'action':'inspect','selector':'button'},{'action':'click','selector':'#go'}])
  target=export_project(self.session,{'name':'fixture','success_text':'SUCCESS 42'},self.root)
  with zipfile.ZipFile(target) as archive:
   report=json.loads(archive.read('fixture/replay-verification.json'));self.assertTrue(report['passed'],report)
   actions=json.loads(archive.read('fixture/actions.json'))['actions'];self.assertFalse(any(a['action']=='inspect' for a in actions))
   self.assertIn('fixture/reliability.py',archive.namelist());self.assertIn('fixture/replay-evidence.png',archive.namelist())
 def test_failed_replay_is_retained_and_labeled_unverified(self):
  self.session.history.append({'action':'click','selector':'#stale-selector'})
  self.session.run([{'action':'click','selector':'#go'}])
  target=export_project(self.session,{'name':'failed-fixture','success_text':'SUCCESS 42'},self.root)
  with zipfile.ZipFile(target) as archive:
   report=json.loads(archive.read('failed-fixture/replay-verification.json'));self.assertFalse(report['passed']);self.assertIn('FAILED / UNVERIFIED',archive.read('failed-fixture/README.md').decode())

if __name__=='__main__':unittest.main(verbosity=2)
