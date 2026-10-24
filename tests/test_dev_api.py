import sys,pathlib,tempfile,unittest,threading,json,urllib.request,urllib.error,re,time,zipfile
from unittest.mock import patch
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
from web_server import Application,Server,Handler

class APITests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory(prefix='nopilot-test-');self.app=Application(self.temp.name);self.cid=self.app.initial_id;self.other=self.app.create('Other')['id'];self.server=Server(('127.0.0.1',0),Handler);self.server.app=self.app;self.server.token='qa-csrf-token';self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start();self.base='http://127.0.0.1:'+str(self.server.server_address[1])
 def tearDown(self):self.server.shutdown();self.server.server_close();self.app.shutdown();self.thread.join();self.temp.cleanup()
 def request(self,path,value=None,headers=None):
  h={'Content-Type':'application/json','X-Nopilot-Token':self.server.token};h.update(headers or {})
  request=urllib.request.Request(self.base+path,None if value is None else json.dumps(value).encode(),headers=h)
  with urllib.request.urlopen(request,timeout=10) as r:return json.load(r)
 def post(self,action,value):return self.request('/api/dev/'+self.cid+'/'+action,value)
 def project(self):return self.post('create',{'name':'API fixture','files':[{'path':'run.py','content':'import sys\nprint("API_RUN_PROOF")\nprint("API_STDERR",file=sys.stderr)'}]})
 def code(self,call,expected):
  with self.assertRaises(urllib.error.HTTPError) as error:call()
  self.assertEqual(error.exception.code,expected)
  error.exception.close()
 def test_csrf_origin_host(self):
  path='/api/dev/'+self.cid+'/create';body={'name':'Unauthorized','files':[{'path':'run.py','content':'print(1)'}]}
  self.code(lambda:self.request(path,body,{'X-Nopilot-Token':''}),403)
  self.code(lambda:self.request(path,body,{'Origin':'https://evil.example'}),403)
  self.code(lambda:self.request('/api/state',headers={'Host':'evil.example'}),403)
  self.assertFalse(self.app.workspace(self.cid).projects)
 def test_foreign_project_and_approval(self):
  p=self.project();a=self.post('propose',{'projectId':p['id'],'entrypoint':'run.py'})
  self.code(lambda:self.request('/api/dev/'+self.other+'/read',{'projectId':p['id'],'path':'run.py'}),400)
  self.code(lambda:self.request('/api/dev/'+self.other+'/approve',{'approvalId':a['id']}),400)
  self.assertEqual(self.app.workspace(self.cid).approvals[a['id']]['status'],'pending')
 def test_chat_plan_requires_human_confirmation_and_same_conversation(self):
  folder=self.app.directory(self.cid)/'artifacts';folder.mkdir();path=folder/'chat-plan.zip'
  contract={'schemaVersion':1,'name':'HTTP chat fixture','runtime':'python','install':None,'tasks':{'start':{'entrypoint':'run.py','args':[],'timeoutSeconds':30}}}
  with zipfile.ZipFile(path,'w') as z:z.writestr('nopilot.json',json.dumps(contract));z.writestr('run.py','print("NOT_BEFORE_CONSENT")')
  artifact=self.app.artifact(self.cid,path,'download');plan=self.post('launch-plan',{'artifactId':artifact['id'],'approved':True})
  self.assertEqual(plan['status'],'review');self.assertFalse(self.app.runner(self.cid).runs)
  self.code(lambda:self.request('/api/dev/'+self.cid+'/launch-confirm',{'launchId':plan['id']},{'X-Nopilot-Token':''}),403)
  self.code(lambda:self.request('/api/dev/'+self.other+'/launch-confirm',{'launchId':plan['id']}),400)
  self.code(lambda:self.request('/api/launches/'+self.other+'/'+plan['id']),404)
  self.assertFalse(self.app.runner(self.cid).runs)
 def test_model_approved_field_does_not_execute(self):
  p=self.project();a=self.post('propose',{'projectId':p['id'],'entrypoint':'run.py','approved':True})
  self.assertEqual(a['status'],'pending');self.assertFalse(self.request('/api/dev/'+self.cid)['runs']);self.assertIsNone(self.app.harness)
 def test_run_logs_and_reuse_guard(self):
  p=self.project();a=self.post('propose',{'projectId':p['id'],'entrypoint':'run.py','revision':p['revision'],'arguments':'"argument with spaces" --flag'})
  self.assertEqual(a['arguments'],['argument with spaces','--flag']);run=self.post('approve',{'approvalId':a['id']});deadline=time.monotonic()+30
  while time.monotonic()<deadline:
   log=self.request('/api/dev/'+self.cid+'/logs?runId='+run['id'])
   if log['run']['status'] not in ('starting','running'):break
   time.sleep(.1)
  self.assertEqual(log['run']['status'],'succeeded',log);self.assertIn('API_RUN_PROOF',log['text']);self.assertIn('API_STDERR',log['text'])
  self.code(lambda:self.post('approve',{'approvalId':a['id']}),400)
  self.assertTrue(any(a['kind']=='log' for a in self.app.conversations[self.cid]['artifacts']))
 def test_patch_diff_invalidates_old_approval(self):
  p=self.project();a=self.post('propose',{'projectId':p['id'],'entrypoint':'run.py'})
  changed=self.post('patch',{'projectId':p['id'],'revision':p['revision'],'files':[{'path':'run.py','content':'print("NEW_REVISION")'}]})
  self.assertIn('NEW_REVISION',changed['diff']['diff']);self.assertEqual(self.app.workspace(self.cid).approvals[a['id']]['status'],'stale')
  self.code(lambda:self.post('approve',{'approvalId':a['id']}),400)
  restored=self.post('rollback',{'projectId':p['id'],'checkpoint':changed['checkpoint']});self.assertEqual(restored['project']['revision'],p['revision'])
 def test_zip_inspect_extract_and_export(self):
  folder=self.app.directory(self.cid)/'artifacts';folder.mkdir();path=folder/'fixture.zip'
  with zipfile.ZipFile(path,'w') as z:z.writestr('demo/run.py','print("zip")')
  a=self.app.artifact(self.cid,path,'project');info=self.post('inspect',{'artifactId':a['id']});p=self.post('extract',{'artifactId':a['id'],'zipSha256':info['zipSha256']})
  self.assertEqual(p['files'][0]['path'],'run.py');export=self.post('export',{'projectId':p['id']});self.assertEqual(export['kind'],'project')
  data=urllib.request.urlopen(self.base+'/api/artifacts/'+self.cid+'/'+export['id']).read();self.assertTrue(data.startswith(b'PK'))
 def test_path_escape_and_unknown_action(self):
  p=self.project();self.code(lambda:self.post('read',{'projectId':p['id'],'path':'../project.json'}),400)
  self.code(lambda:self.post('propose',{'projectId':p['id'],'entrypoint':'../evil.py'}),400)
  self.code(lambda:self.post('execute',{'approved':True}),400)
 def test_container_request_never_silently_uses_host(self):
  p=self.project()
  with patch('container_runner.container_runtime',side_effect=ValueError('engine unavailable')):
   self.code(lambda:self.post('propose',{'projectId':p['id'],'entrypoint':'run.py','executionMode':'container'}),400)
  self.assertFalse(self.app.workspace(self.cid).approvals)

if __name__=='__main__':unittest.main(verbosity=2)
