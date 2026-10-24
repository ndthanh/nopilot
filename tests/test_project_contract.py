import sys,pathlib,tempfile,unittest,json,time,copy
from unittest.mock import Mock
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
from dev_workspace import Workspace
from project_contract import read_contract,propose_task,development_prompt
from web_server import Application

def spec():return {'schemaVersion':1,'name':'Contract fixture','runtime':'python','install':None,'tasks':{'start':{'entrypoint':'run.py','args':['one value'],'timeoutSeconds':30},'check':{'entrypoint':'check.py','args':[],'timeoutSeconds':30}}}
class ContractTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=pathlib.Path(self.temp.name);self.ws=Workspace(self.root/'dev')
  self.p=self.ws.create('fixture',[{'path':'run.py','content':'print("CONTRACT_START_OK")'},{'path':'check.py','content':'print("CONTRACT_CHECK_OK")'},{'path':'nopilot.json','content':json.dumps(spec())}]);self.pid=self.p['id'];self.source=self.ws.source(self.pid)
 def tearDown(self):self.temp.cleanup()
 def write(self,v):
  (self.source/'nopilot.json').write_text(json.dumps(v),encoding='utf-8');return read_contract(self.source)
 def test_read_and_propose_never_runs_and_preserves_argv(self):
  self.assertEqual(read_contract(self.source)['status'],'valid')
  a=propose_task(self.ws,self.pid,'start',self.p['revision'])
  self.assertEqual(a['status'],'pending');self.assertEqual(a['arguments'],['one value']);self.assertEqual(a['contractTask'],'start');self.assertFalse(self.ws.running)
 def test_reject_unknown_keys_shell_and_unsafe_paths(self):
  for mutator in (lambda s:s.update(shell='cmd /c x'),lambda s:s['tasks']['start'].update(entrypoint='../run.py'),lambda s:s['tasks']['start'].update(entrypoint='start.cmd'),lambda s:s['tasks']['start'].update(args='--flag'),lambda s:s['tasks']['start'].update(timeoutSeconds=True),lambda s:s['tasks'].update(exec=s['tasks']['start']),lambda s:s.update(runtime='node')):
   value=spec();mutator(value);self.assertEqual(self.write(value)['status'],'invalid',value)
 def test_preview_loopback_only(self):
  for url in ('https://example.com/','http://localhost:9000/','http://127.0.0.1:99999/','http://user@127.0.0.1:9000/','http://127.0.0.1:9000/#x'):
   v=spec();v['previewUrl']=url;self.assertEqual(self.write(v)['status'],'invalid',url)
  v=spec();v['previewUrl']='http://127.0.0.1:8899/';self.assertEqual(self.write(v)['status'],'valid')
 def test_install_requires_pins_and_success_before_start(self):
  v=spec();v['install']={'requirements':'requirements.txt','timeoutSeconds':120};(self.source/'requirements.txt').write_text('Flask>=3')
  self.assertEqual(self.write(v)['status'],'invalid');(self.source/'requirements.txt').write_text('Flask==3.1.2');self.assertEqual(self.write(v)['status'],'valid')
  revision=self.ws.current(self.pid)['revision']
  with self.assertRaisesRegex(ValueError,'dependency'):propose_task(self.ws,self.pid,'start',revision)
  a=propose_task(self.ws,self.pid,'install',revision);self.assertEqual(a['kind'],'install')
  from unittest.mock import patch
  with patch('environment_cache.state',return_value={'ready':True}):self.assertEqual(propose_task(self.ws,self.pid,'start',revision)['contractTask'],'start')
 def test_stale_revision_and_duplicate_json(self):
  with self.assertRaises(ValueError):propose_task(self.ws,self.pid,'start','wrong')
  (self.source/'nopilot.json').write_text('{"schemaVersion":1,"schemaVersion":1}')
  self.assertEqual(read_contract(self.source)['status'],'invalid')
 def test_missing_contract_has_manual_fallback(self):
  (self.source/'nopilot.json').unlink();self.assertEqual(read_contract(self.source)['status'],'missing')
 def test_develop_asks_schema_without_autoexecution(self):
  prompt=development_prompt('Build a calculator');self.assertIn('"schemaVersion"',prompt);self.assertIn('Build a calculator',prompt);self.assertIn('Không tự cài/chạy',prompt)
 def test_api_contract_run_completion_chat_and_log_no_model(self):
  app=Application(self.root/'web');cid=app.initial_id
  try:
   ws=app.workspace(cid);p=ws.create('known local test',[{'path':'run.py','content':'print("CONTRACT_START_OK")'},{'path':'check.py','content':'print("CONTRACT_CHECK_OK")'},{'path':'nopilot.json','content':json.dumps(spec())}])
   self.assertEqual(app.dev_state(cid)['projects'][0]['contract']['status'],'valid')
   a=app.dev_action(cid,'contract-propose',{'projectId':p['id'],'revision':p['revision'],'task':'check','approved':True})
   self.assertEqual(a['status'],'pending');self.assertFalse(app.runner(cid).runs)
   run=app.dev_action(cid,'approve',{'approvalId':a['id']});deadline=time.monotonic()+30
   while time.monotonic()<deadline:
    log=app.runner(cid).log(run['id'])
    if log['run']['status'] not in ('starting','running'):break
    time.sleep(.05)
   self.assertEqual(log['run']['status'],'succeeded',log);self.assertIn('CONTRACT_CHECK_OK',log['text']);self.assertEqual(log['run']['contractTask'],'check');self.assertIsNone(app.harness)
   self.assertTrue(any(m.get('artifacts') for m in app.conversations[cid]['messages']))
  finally:app.shutdown()
if __name__=='__main__':unittest.main(verbosity=2)
