import pathlib,sys,tempfile,unittest,zipfile,json,time,threading
from unittest.mock import patch
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
from web_server import Application
from chat_launch import ChatLaunches

def spec(install=None):return {'schemaVersion':1,'name':'Chat flow fixture','runtime':'python','install':install,'tasks':{'start':{'entrypoint':'run.py','args':[],'timeoutSeconds':30},'check':{'entrypoint':'check.py','args':[],'timeoutSeconds':30}}}
class FakeRunner:
 def __init__(self,ws,result='failed'):self.ws=ws;self.result=result;self.runs={};self.lock=threading.RLock();self.started=[]
 def start(self,aid):
  a=self.ws.approvals[aid];self.started.append(a['kind']);rid=str(len(self.runs));self.runs[rid]={'id':rid,'status':self.result,'exitCode':1};return self.runs[rid]
 def describe(self,rid):return dict(self.runs[rid])
 def stop(self,rid):self.runs[rid]['status']='stopped';return self.runs[rid]
 def close(self):pass
class ChatLaunchTests(unittest.TestCase):
 def setUp(self):self.temp=tempfile.TemporaryDirectory();self.root=pathlib.Path(self.temp.name);self.app=Application(self.root/'web');self.cid=self.app.initial_id;self.ws=self.app.workspace(self.cid)
 def tearDown(self):self.app.shutdown();self.temp.cleanup()
 def artifact(self,text='print("CHAT_FLOW_START")',install=None):
  folder=self.app.directory(self.cid)/'artifacts';folder.mkdir(exist_ok=True);path=folder/('fixture-'+str(time.time_ns())+'.zip')
  with zipfile.ZipFile(path,'w') as z:
   z.writestr('nopilot.json',json.dumps(spec(install)));z.writestr('run.py',text);z.writestr('check.py','print("CHAT_FLOW_CHECK")');z.writestr('NOPILOT_COMMIT_MESSAGE.txt','feat: update chat fixture')
   if install:z.writestr('requirements.txt','colorama==0.4.6\n')
  return self.app.artifact(self.cid,path,'download')['id']
 def wait(self,lid):
  end=time.monotonic()+40
  while time.monotonic()<end:
   item=self.app.launches.get(self.cid,lid)
   if item['status'] not in ('starting','installing','running'):return item
   time.sleep(.05)
  self.fail('launch did not finish')
 def test_plan_does_not_execute_and_caches_same_artifact(self):
  aid=self.artifact();p=self.app.launches.prepare(self.cid,aid)
  self.assertEqual(p['status'],'review');self.assertFalse(self.app.runner(self.cid).runs);self.assertIsNone(self.app.harness)
  self.assertEqual(self.app.launches.prepare(self.cid,aid)['id'],p['id']);self.assertNotIn('source',p)
 def test_latest_plan_wins_independent_of_disk_load_order(self):
  aid=self.artifact();newest=self.app.launches.prepare(self.cid,aid)
  old=self.app.launches.prepare(self.cid,aid,fresh=True)
  self.app.launches.items[newest['id']].update(status='succeeded',createdAt='2026-10-24T10:00:00+00:00')
  self.app.launches.items[old['id']]['createdAt']='2026-10-24T09:00:00+00:00'
  self.assertEqual(self.app.launches.prepare(self.cid,aid)['id'],newest['id'])
 def test_one_consent_runs_then_update_preserves_venv(self):
  p=self.app.launches.prepare(self.cid,self.artifact());self.app.launches.confirm(self.cid,p['id']);self.app.launches.confirm(self.cid,p['id'])
  first=self.wait(p['id']);self.assertEqual(first['status'],'succeeded',first);self.assertEqual(len(first['runIds']),1)
  same=self.app.launches.prepare(self.cid,p['artifactId'],fresh=True)
  self.assertIsNone(same['update']);self.assertTrue(same['skipGit'])
  exe=self.ws.folder(p['projectId'])/'venv/Scripts/python.exe';mtime=exe.stat().st_mtime_ns
  updated=self.app.launches.prepare(self.cid,self.artifact('print("UPDATED_FLOW")'))
  self.assertEqual(updated['projectId'],p['projectId']);self.assertTrue(updated['update']);self.assertIn('CHAT_FLOW_START',(self.ws.source(p['projectId'])/'run.py').read_text())
  self.app.launches.confirm(self.cid,updated['id'],updated['commitMessage']);done=self.wait(updated['id']);self.assertEqual(done['status'],'succeeded',done);self.assertEqual(exe.stat().st_mtime_ns,mtime)
  self.assertIn('UPDATED_FLOW',self.app.runner(self.cid).log(done['runId'])['text']);self.assertIsNone(self.app.harness)
 def test_failed_install_never_starts_project(self):
  p=self.app.launches.prepare(self.cid,self.artifact(install={'requirements':'requirements.txt','timeoutSeconds':60}));fake=FakeRunner(self.ws)
  with patch.object(self.app,'runner',return_value=fake):
   self.app.launches.confirm(self.cid,p['id']);result=self.wait(p['id'])
  self.assertEqual(result['status'],'failed');self.assertEqual(fake.started,['install'])
 def test_stale_source_and_cross_conversation_refused(self):
  p=self.app.launches.prepare(self.cid,self.artifact());(self.ws.source(p['projectId'])/'run.py').write_text('print("changed")')
  with self.assertRaisesRegex(ValueError,'Source'):self.app.launches.confirm(self.cid,p['id'])
  other=self.app.create()['id']
  with self.assertRaises(ValueError):self.app.launches.confirm(other,p['id'])
 def test_stop_during_install_prevents_followup_start(self):
  p=self.app.launches.prepare(self.cid,self.artifact(install={'requirements':'requirements.txt','timeoutSeconds':60}));fake=FakeRunner(self.ws,'running')
  with patch.object(self.app,'runner',return_value=fake):
   self.app.launches.confirm(self.cid,p['id']);end=time.monotonic()+5
   while not fake.started and time.monotonic()<end:time.sleep(.02)
   self.app.launches.stop(self.cid,p['id']);result=self.wait(p['id'])
  self.assertEqual(result['status'],'stopped');self.assertEqual(fake.started,['install'])
 def test_expiry_and_restart_never_resend(self):
  p=self.app.launches.prepare(self.cid,self.artifact());raw=self.app.launches.get(self.cid,p['id']);raw['expiresAt']=0
  with self.assertRaises(ValueError):self.app.launches.confirm(self.cid,p['id'])
  raw.update(status='installing',stage='interrupted fixture');self.app.launches.save(raw)
  restored=ChatLaunches(self.app);self.assertEqual(restored.get(self.cid,p['id'])['status'],'interrupted');self.assertFalse(restored.threads)
  raw['status']='interrupted'
 def test_check_plan_is_current_source_and_not_old_zip(self):
  p=self.app.launches.prepare(self.cid,self.artifact());pid=p['projectId'];(self.ws.source(pid)/'run.py').write_text('print("local current source")')
  plan=self.app.launches.check_plan(self.cid,pid,'start');self.assertTrue(plan['skipGit']);self.assertEqual(plan['revision'],self.ws.current(pid)['revision']);self.assertIsNone(plan['update'])
if __name__=='__main__':unittest.main(verbosity=2)
