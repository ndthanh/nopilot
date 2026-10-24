import json,pathlib,sys,tempfile,unittest
from unittest.mock import patch
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
from reliability import validate_actions,progress
from playwright_tool import parse
from image_tools import attach_images,record_images
from container_runner import plan
import test_explorer_state as fixtures
FakeBrowser=fixtures.FakeBrowser
Harness=fixtures.Harness

class SchemaTests(unittest.TestCase):
 def test_batch_rejects_bad_second_action(self):
  with self.assertRaises(ValueError):validate_actions([{'action':'click','selector':'button'},{'action':'fill','selector':'x','value':{'code':'oops'}}])
 def test_nested_rejects_code_and_extra_keys(self):
  for action in ({'action':'click','selector':'b','force':True},{'action':'check','selector':'b','checked':'true'},{'action':'record','data':'nested json'}, {'action':'for_each_row','table':'t','steps':[{'action':'goto','url':'https://example.com'}]}):
   with self.subTest(action=action),self.assertRaises(ValueError):validate_actions([action])
 def test_duplicate_keys_and_nonfinite_json(self):
  for answer in ('{"type":"final","run_id":"id","answer":"a","answer":"b"}','{"type":"final","run_id":"id","answer":NaN}'):
   with self.assertRaises(ValueError):parse({'answer':answer},'id')
 def test_unhashable_tool_is_protocol_error(self):
  with self.assertRaises(ValueError):parse({'answer':json.dumps({'type':'tool_call','run_id':'id','id':'c','tool':{},'arguments':{}})},'id')
 def test_native_structured_record(self):
  value={'type':'tool_call','run_id':'id','id':'c','tool':'playwright','arguments':{'actions':[{'action':'record','data':{'a':[1,None,'v']},'pause':True}]}}
  self.assertEqual(parse({'answer':json.dumps(value)},'id'),value)

class RecoveryTests(unittest.TestCase):
 setUp=fixtures.ExplorerTests.setUp
 tearDown=fixtures.ExplorerTests.tearDown
 task=fixtures.ExplorerTests.task
 call=fixtures.ExplorerTests.call
 advance=fixtures.ExplorerTests.advance
 def test_corrupt_latest_state_uses_checkpoint_without_gaining_turns(self):
  item=self.task(lambda i,n,p:self.call(i,n),turns=5);item['pauseRequested']=True;self.advance(item)
  directory=self.app.explorers.directory(item);(directory/'state.json').write_text('{BROKEN',encoding='utf-8')
  from explorer import Explorers
  engine=Explorers(self.app,FakeBrowser);restored=engine.get(self.cid,item['id'])
  self.assertTrue(restored['checkpointFallback']);self.assertEqual(restored['status'],'needs_recovery');self.assertEqual(restored['turns'],restored['budget'])
 def test_checkpoint_notes_reenter_context(self):
  item=self.task(lambda i,n,p:self.call(i,n),turns=1);self.advance(item)
  item['notes']=[{'name':'note.json','data':{'next_step':'IMPORTANT_NEXT_STEP'}}]
  prompt=self.app.explorers.context_prompt(item,'continue')
  self.assertIn('IMPORTANT_NEXT_STEP',prompt);self.assertIn('LOCAL CHECKPOINT',prompt)
 def test_large_recovery_context_is_bounded_and_full_memory_is_readable(self):
  item=self.task(lambda i,n,p:self.call(i,n),turns=1);self.advance(item)
  item['task']='task '*4500;item['notes']=[{'name':'large.json','data':{'text':'x'*60000}}]
  item['observation']={'text':'page '*4000,'fields':[{'html':'x'*5000} for _ in range(35)]}
  prompt=self.app.explorers.context_prompt(item,'continue '*3000)
  self.assertLessEqual(len(prompt),24000);self.assertIn('session.memory',prompt)
  result=self.app.explorers.tool(item,{'tool':'session.memory','arguments':{}})
  self.assertEqual(result['notes'],item['notes'])
 def test_stagnation_pauses_without_extra_call(self):
  item=self.task(lambda i,n,p:self.call(i,n,[{'action':'click','selector':'button'}]));self.advance(item)
  self.assertEqual(item['status'],'paused');self.assertEqual(item['turns'],3);self.assertTrue(item['progress']['reason']);self.assertTrue((self.app.explorers.directory(item)/'checkpoint.json').exists())

class ProgressTests(unittest.TestCase):
 def test_readonly_not_a_loop(self):
  item={'turns':0};call={'id':'x','tool':'playwright','arguments':{'actions':[{'action':'snapshot'}]}}
  for _ in range(20):progress(item,call,{'ok':True,'observation':{'text':'same'}})
  self.assertFalse(item.get('pauseRequested',False))
 def test_changing_state_not_stalled(self):
  item={'turns':0};call={'id':'x','tool':'playwright','arguments':{'actions':[{'action':'click','selector':'button'}]}}
  for n in range(8):progress(item,call,{'ok':True,'observation':{'text':str(n)}})
  self.assertFalse(item.get('pauseRequested',False))
 def test_consecutive_errors_pause(self):
  item={'turns':0};call={'id':'x','tool':'playwright','arguments':{'actions':[{'action':'inspect','selector':'x'}]}}
  for _ in range(3):progress(item,call,{'ok':False,'error':'missing'})
  self.assertTrue(item['pauseRequested'])

class ImageTests(unittest.TestCase):
 def setUp(self):
  from PIL import Image
  self.temp=tempfile.TemporaryDirectory();self.root=pathlib.Path(self.temp.name);self.item={};self.harness=Harness(None)
  self.session=FakeBrowser('https://example.com',self.root)
  for n in range(2):
   path=self.root/f'{n}.png';Image.new('RGB',(100,120),('red','blue')[n]).save(path);self.session.files[path.name]=path
 def tearDown(self):self.temp.cleanup()
 def test_labeled_contact_sheet_and_shuffled_record_identity(self):
  result=attach_images(self.item,self.session,['0.png','1.png'],self.harness)
  self.assertEqual(len(self.harness.uploads),1)
  records=[{'image_id':image['image_id'],'fields':{'text':image['name']}} for image in reversed(result['images'])]
  value=record_images(self.item,{'batch_id':result['batch_id'],'records':records},self.root)
  self.assertFalse(value['verified']);self.assertTrue(all(r['name']==r['fields']['text'] for r in value['records']))
 def test_unknown_and_duplicate_ids_rejected(self):
  result=attach_images(self.item,self.session,['0.png','1.png'],self.harness);known=result['images'][0]['image_id']
  for ids in ([known,known],[known,'foreign']):
   with self.assertRaises(ValueError):record_images(self.item,{'batch_id':result['batch_id'],'records':[{'image_id':i,'fields':{}} for i in ids]},self.root)
 def test_path_whitelist_and_limit(self):
  for names in (['C:/secret.png'],['0.png']*4):
   with self.assertRaises(ValueError):attach_images(self.item,self.session,names,self.harness)
  self.assertFalse(self.harness.uploads)
 def test_upload_failure_does_not_claim_attached(self):
  self.harness.upload=lambda path:(_ for _ in ()).throw(TimeoutError('uncertain upload'))
  with self.assertRaises(TimeoutError):attach_images(self.item,self.session,['0.png'],self.harness)
  self.assertEqual(next(iter(self.item['imageBatches'].values()))['status'],'upload_pending')

class ContainerTests(unittest.TestCase):
 def test_completion_not_published_until_logs_registered(self):
  from execution import Runner
  runner=Runner.__new__(Runner);runner.runs={'id':{'status':'succeeded','completionDelivered':False}}
  self.assertEqual(runner.describe('id')['status'],'running')
  runner.runs['id']['completionDelivered']=True
  self.assertEqual(runner.describe('id')['status'],'succeeded')
 def test_restart_does_not_leave_finished_run_stuck_finalizing(self):
  from execution import Runner
  with tempfile.TemporaryDirectory() as root:
   folder=pathlib.Path(root)/'saved';folder.mkdir();(folder/'run.json').write_text(json.dumps({'id':'saved','status':'succeeded','completionDelivered':False}),encoding='utf-8')
   runner=Runner(None,root)
   self.assertEqual(runner.describe('saved')['status'],'succeeded');self.assertTrue(runner.runs['saved']['notificationInterrupted']);runner.close()
 def test_plan_limits_and_no_host_write_or_network(self):
  command=plan(['docker','--host','local'], 'sha256:'+'a'*64,'nopilot-test',pathlib.Path('C:/approved'),'run.py',['--arg'])
  for flag in ('--network=none','--read-only','--cap-drop=ALL','--security-opt=no-new-privileges','--pids-limit=64','--memory=512m','--user=65534:65534','--pull=never'):self.assertIn(flag,command)
  mounts=[a for a in command if a.startswith('type=bind')];self.assertEqual(len(mounts),1);self.assertTrue(mounts[0].endswith(',readonly'))
 def test_unavailable_engine_refuses_approval(self):
  from dev_workspace import Workspace
  with tempfile.TemporaryDirectory() as root:
   workspace=Workspace(root);p=workspace.create('safe',[{'path':'run.py','content':'print(1)'}])
   with patch('container_runner.container_runtime',side_effect=ValueError('engine unavailable')):
    with self.assertRaises(ValueError):workspace.propose(p['id'],execution_mode='container')
   self.assertFalse(workspace.approvals);self.assertFalse(workspace.running)

if __name__=='__main__':unittest.main(verbosity=2)
