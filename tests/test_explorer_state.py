import sys,pathlib,tempfile,unittest,json,time,re,uuid
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
from web_server import Application
from explorer import Explorers

class Page:
 def __init__(self,url):self.url=url
 def screenshot(self,**kwargs):pass
class FakeBrowser:
 def __init__(self,url,directory):self.page=Page(url);self.url=url;self.history=[];self.files={};self.tables={};self.closed=False;self.clicks=0;self.directory=pathlib.Path(directory).resolve();self.directory.mkdir(parents=True,exist_ok=True)
 def snapshot(self):return {'url':self.page.url,'title':'Synthetic browser','text':'Demo page','fields':[],'links':[]}
 def run(self,actions):
  for action in actions:
   if self.cancel_check():return {'ok':False,'error':'Pause requested'}
   if action['action']=='click':self.clicks+=1
   self.history.append(action)
  return {'ok':True,'observation':self.snapshot()}
 def close(self):self.closed=True
class Harness:
 def __init__(self,fn):self.fn=fn;self.calls=[];self.uploads=[]
 def ask(self,prompt,timeout=300):self.calls.append(prompt);return {'answer':json.dumps(self.fn(len(self.calls),prompt))}
 def upload(self,path):self.uploads.append(str(path))
 def close(self):pass

class ExplorerTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory(prefix='nopilot-test-');self.app=Application(self.temp.name);self.cid=self.app.initial_id;self.app.explorers.factory=FakeBrowser;self.app.ensure=lambda *a,**k:None;self.app.capture_route=lambda *a:None
 def tearDown(self):self.app.shutdown();self.temp.cleanup()
 def task(self,fn,turns=20):
  item=self.app.explorers.create(self.cid,'https://example.com/','Synthetic workflow test',turns);self.app.harness=Harness(lambda number,prompt:fn(item,number,prompt));return item
 def call(self,item,n,actions=None,tool='playwright',args=None):return {'type':'tool_call','run_id':item['id'],'id':'call_'+str(n),'tool':tool,'arguments':args if args is not None else {'actions':actions or [{'action':'snapshot'}]}}
 def final(self,item,text='Done'):return {'type':'final','run_id':item['id'],'answer':text}
 def advance(self,item):return self.app.explorers.advance(self.cid,item['id'])
 def test_exact_20_then_explicit_grant(self):
  item=self.task(lambda item,n,p:self.call(item,n) if n<=20 else self.final(item));self.advance(item);browser=self.app.explorers.browsers[item['id']]
  self.assertEqual(item['status'],'waiting_turns');self.assertEqual(len(self.app.harness.calls),20);self.assertFalse(browser.closed)
  time.sleep(.1);self.assertEqual(len(self.app.harness.calls),20)
  with self.assertRaises(ValueError):self.app.explorers.control(self.cid,item['id'],'grant',{'turns':100})
  self.app.explorers.control(self.cid,item['id'],'grant',{'turns':20});self.advance(item)
  self.assertEqual(item['status'],'completed');self.assertEqual(item['turns'],21);self.assertEqual(item['budget'],40);self.assertIs(browser,self.app.explorers.browsers[item['id']])
 def test_pause_after_model_response_does_not_send_again(self):
  def response(item,n,p):
   if n==1:item['pauseRequested']=True;return self.call(item,n,[{'action':'click','selector':'button'}])
   return self.final(item)
  item=self.task(response);self.advance(item);browser=self.app.explorers.browsers[item['id']]
  self.assertEqual(item['status'],'paused');self.assertEqual(browser.clicks,0);self.assertEqual(item['phase'],'have_response')
  self.app.explorers.control(self.cid,item['id'],'resume');self.advance(item)
  self.assertEqual(browser.clicks,1);self.assertEqual(item['turns'],2);self.assertEqual(item['status'],'completed')
 def test_duplicate_call_replays_result_not_click(self):
  item=self.task(lambda item,n,p:self.call(item,1,[{'action':'click','selector':'button'}]) if n<3 else self.final(item));self.advance(item)
  self.assertEqual(self.app.explorers.browsers[item['id']].clicks,1);self.assertEqual(item['status'],'completed')
  self.assertNotEqual(json.loads(self.app.harness.calls[1])['nonce'],json.loads(self.app.harness.calls[2])['nonce'])
 def test_transport_result_unique_at_same_turn_count(self):
  item=self.task(lambda i,n,p:self.final(i));engine=self.app.explorers
  engine.prompt_result(item,'cached','playwright',{'ok':True});first=item['nextPrompt']
  engine.prompt_result(item,'cached','playwright',{'ok':True});self.assertNotEqual(first,item['nextPrompt'])
  self.assertEqual(json.loads(first)['result'],json.loads(item['nextPrompt'])['result'])
 def test_model_cannot_approve_or_grant(self):
  item=self.task(lambda item,n,p:self.call(item,n,tool='project.approve',args={'approved':True,'turns':1000}));self.advance(item)
  self.assertEqual(item['budget'],20);self.assertEqual(item['turns'],3);self.assertEqual(item['status'],'needs_recovery');self.assertFalse(self.app.workspace(self.cid).approvals)
 def test_pause_close_keeps_workspace(self):
  item=self.task(lambda item,n,p:self.call(item,n),turns=1);self.advance(item);browser=self.app.explorers.browsers[item['id']]
  self.app.workspace(self.cid).create('Durable',[{'path':'run.py','content':'print("retained")'}])
  self.app.explorers.control(self.cid,item['id'],'close');self.advance(item);self.assertTrue(browser.closed);self.assertEqual(item['status'],'closed');self.assertEqual(len(self.app.workspace(self.cid).list()),1)
 def test_restart_requires_ack_and_no_automatic_replay(self):
  item=self.task(lambda item,n,p:self.call(item,n),turns=1);self.advance(item);original=self.app.explorers.browsers[item['id']];count=len(self.app.harness.calls)
  self.app.explorers.close_all();loaded=Explorers(self.app,FakeBrowser);self.app.explorers=loaded;item=loaded.tasks[item['id']]
  self.assertEqual(item['status'],'needs_recovery');self.assertEqual(len(self.app.harness.calls),count)
  with self.assertRaises(ValueError):loaded.control(self.cid,item['id'],'recover',{'acknowledge':False})
  loaded.control(self.cid,item['id'],'recover',{'acknowledge':True});self.advance(item)
  self.assertEqual(item['status'],'waiting_turns');self.assertEqual(len(self.app.harness.calls),count);self.assertIsNot(original,loaded.browsers[item['id']]);self.assertEqual(loaded.browsers[item['id']].clicks,0)
 def test_uncertain_model_is_not_automatically_resent(self):
  item=self.task(lambda i,n,p:self.call(i,n))
  def uncertain(prompt,timeout=300):raise TimeoutError('Submitted but completion uncertain')
  self.app.harness.ask=uncertain;self.advance(item);self.assertEqual(item['phase'],'model_inflight');self.assertEqual(item['status'],'needs_recovery');self.assertEqual(item['turns'],1)
 def test_project_run_pauses_until_human_then_returns_logs(self):
  def response(item,n,p):
   if n==1:return self.call(item,n,tool='project.create',args={'name':'Synthetic human gate','files':[{'path':'run.py','content':'print("HUMAN_GATE_PROOF")'}]})
   if n==2:
    project=self.app.workspace(self.cid).list()[0]
    return self.call(item,n,tool='project.propose_run',args={'project_id':project['id'],'revision':project['revision'],'kind':'run','entrypoint':'run.py','timeout':30})
   self.assertIn('HUMAN_GATE_PROOF',p);return self.final(item,'Logs received')
  item=self.task(response);self.advance(item);self.assertEqual(item['status'],'awaiting_approval');self.assertEqual(len(self.app.runner(self.cid).runs),0)
  run=self.app.dev_action(self.cid,'approve',{'approvalId':item['approvalId']});deadline=time.monotonic()+45
  while item['status']!='completed' and time.monotonic()<deadline:time.sleep(.05)
  self.assertEqual(item['status'],'completed',item.get('error'));self.assertEqual(self.app.runner(self.cid).runs[run['id']]['status'],'succeeded');self.assertEqual(len(self.app.harness.calls),3)
 def test_reject_never_runs_code(self):
  project=self.app.workspace(self.cid).create('Rejected',[{'path':'run.py','content':'raise RuntimeError("MUST_NOT_RUN")'}])
  item=self.task(lambda item,n,p:self.call(item,n,tool='project.propose_run',args={'project_id':project['id'],'revision':project['revision'],'kind':'run','entrypoint':'run.py'}) if n==1 else self.final(item,'Denied'))
  self.advance(item);self.app.dev_action(self.cid,'reject',{'approvalId':item['approvalId']});deadline=time.monotonic()+4
  while item['status']!='completed' and time.monotonic()<deadline:time.sleep(.02)
  self.assertEqual(item['status'],'completed');self.assertFalse(self.app.runner(self.cid).runs)
 def test_iteration_keeps_same_browser(self):
  item=self.task(lambda item,n,p:self.call(item,n) if n==1 else self.final(item));self.advance(item);browser=self.app.explorers.browsers[item['id']]
  self.app.explorers.control(self.cid,item['id'],'iterate',{'task':'Inspect the next step'});self.advance(item)
  self.assertIs(browser,self.app.explorers.browsers[item['id']]);self.assertEqual(item['turns'],3);self.assertEqual(item['status'],'completed')
 def test_recovery_resends_schema_and_live_observation(self):
  item=self.task(lambda item,n,p:self.call(item,n) if n==1 else self.final(item));self.advance(item)
  item['status']='needs_recovery';item['repairs']=3;turns=item['turns']
  self.app.explorers.control(self.cid,item['id'],'recover',{'acknowledge':True,'task':'NEW_RECOVERY_REQUEST'})
  self.assertEqual(item['repairs'],0);self.advance(item);prompt=self.app.harness.calls[-1]
  for required in ('Call schema:', '"tool":"playwright"', 'Final schema:', 'NEW_RECOVERY_REQUEST','Demo page',item['id']):self.assertIn(required,prompt)
  self.assertLessEqual(len(prompt),24000);self.assertEqual(item['turns'],turns+1);self.assertEqual(item['budget'],20)
 def test_human_open_url_preserves_budget_and_resets_browser(self):
  item=self.task(lambda i,n,p:self.call(i,n),turns=1);self.advance(item);before=self.app.explorers.browsers[item['id']]
  before.tables['old']=[{'private':'not carried'}]
  self.app.explorers.control(self.cid,item['id'],'open_url',{'url':'https://example.org/','task':'Explicit next challenge'})
  self.advance(item);after=self.app.explorers.browsers[item['id']]
  self.assertTrue(before.closed);self.assertIsNot(before,after);self.assertEqual(after.page.url,'https://example.org/');self.assertEqual(after.tables,{})
  self.assertEqual(item['turns'],1);self.assertEqual(item['budget'],1);self.assertEqual(len(self.app.harness.calls),1)
 def test_bundle_only_session_downloads(self):
  item=self.task(lambda i,n,p:self.call(i,n),turns=1);self.advance(item);browser=self.app.explorers.browsers[item['id']]
  path=browser.directory/'sample.txt';path.write_text('KNOWN_PUBLIC_FIXTURE');browser.files['sample.txt']=path
  result=self.app.explorers.tool(item,{'tool':'browser.bundle_downloads','arguments':{'names':['sample.txt']}})
  self.assertTrue(result['ok']);self.assertEqual(len(self.app.harness.uploads),1)
  with self.assertRaises(ValueError):self.app.explorers.tool(item,{'tool':'browser.bundle_downloads','arguments':{'names':['C:/secret.txt']}})
 def test_record_can_pause_without_another_model_turn(self):
  item=self.task(lambda i,n,p:self.call(i,n,[{'action':'record','data':{'known':'fixture'},'pause':True}]));self.advance(item)
  self.assertEqual(item['status'],'paused');self.assertEqual(item['turns'],1);self.assertEqual(len(self.app.harness.calls),1)
 def test_protocol_retry_can_keep_live_dom(self):
  item=self.task(lambda i,n,p:{'bad':'schema'});self.advance(item);browser=self.app.explorers.browsers[item['id']]
  self.assertEqual(item['status'],'needs_recovery');self.assertEqual(item['turns'],3)
  self.app.harness.fn=lambda n,p:self.call(item,n) if n==4 else self.final(item)
  self.app.explorers.control(self.cid,item['id'],'recover',{'acknowledge':True,'keepBrowser':True,'task':'Valid retry only'})
  self.advance(item);self.assertIs(browser,self.app.explorers.browsers[item['id']]);self.assertFalse(browser.closed);self.assertEqual(item['status'],'completed');self.assertEqual(item['turns'],5)

if __name__=='__main__':unittest.main(verbosity=2)
