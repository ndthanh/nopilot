import pathlib,sys,tempfile,unittest,zipfile,json,time
from unittest.mock import Mock
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
from project_bundle import pack_project,parse_project_command,MANIFEST
from cli import Harness

class ProjectLoopTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.base=pathlib.Path(self.temp.name);self.root=self.base/'source';self.root.mkdir();(self.root/'app.py').write_text('print("source")',encoding='utf-8')
 def tearDown(self):self.temp.cleanup()
 def test_parser_preserves_question_quotes_newlines(self):
  line='/project "'+str(self.root)+'" --exclude "data/**" Hãy sửa "Hello world"\nvà đọc log.'
  root,question,exclude=parse_project_command(line)
  self.assertEqual(root,self.root);self.assertEqual(exclude,['data/**']);self.assertEqual(question,'Hãy sửa "Hello world"\nvà đọc log.')
 def test_parser_rejects_bad_options_and_relative_path(self):
  for suffix in ('--exclude','--exclude --oops','--unknown'):
   with self.assertRaises(ValueError):parse_project_command('/project "'+str(self.root)+'" '+suffix)
  with self.assertRaises(ValueError):parse_project_command('/project relative')
 def test_current_selector_preserves_options_and_question(self):
  root,question,exclude=parse_project_command('/project current --exclude "screenshots/**" Đổi URL sang https://facebook.com',current_root=lambda:self.root)
  self.assertEqual(root,self.root);self.assertEqual(exclude,['screenshots/**']);self.assertEqual(question,'Đổi URL sang https://facebook.com')
  with self.assertRaisesRegex(ValueError,'conversation'):parse_project_command('/project current sửa')
  with self.assertRaisesRegex(ValueError,'tuyệt đối'):parse_project_command('/project "current" sửa',current_root=self.root)
 def test_current_project_is_conversation_scoped_and_never_guesses(self):
  from web_server import Application
  app=Application(self.base/'selectors');cid=app.initial_id
  try:
   ws=app.workspace(cid)
   with self.assertRaises(ValueError):app.current_project_source(cid)
   first=ws.create('first',[{'path':'app.py','content':'print(1)'}])['id']
   self.assertEqual(app.current_project_source(cid),ws.source(first))
   second=ws.create('second',[{'path':'app.py','content':'print(2)'}])['id']
   with self.assertRaises(ValueError):app.current_project_source(cid)
   app.conversations[cid]['activeProjectId']=first
   self.assertEqual(app.current_project_source(cid),ws.source(first))
   other=app.create()['id'];app.conversations[other]['activeProjectId']=first
   with self.assertRaises(ValueError):app.current_project_source(other)
   ws.projects[first]['launchStaged']=True
   with self.assertRaises(ValueError):app.current_project_source(cid)
  finally:app.shutdown()
 def test_bundle_skips_heavy_folders_logs_archives_and_secrets(self):
  for name in ('.venv','node_modules','.VENV','logs'):
   folder=self.root/name;folder.mkdir(exist_ok=True)
   with (folder/'large.bin').open('wb') as f:f.truncate(20*1024*1024)
  for name in ('start.log','old.zip','.env','key.pem'):(self.root/name).write_text('EXCLUDE_ME')
  result=pack_project(self.root,self.base/'project.txt',max_source_bytes=100)
  with zipfile.ZipFile(result['bundle']) as z:self.assertEqual(set(z.namelist()),{MANIFEST,'app.py'})
  self.assertGreaterEqual(result['skippedCount'],7);self.assertEqual(result['compressionLevel'],3);self.assertEqual(pathlib.Path(result['bundle']).read_bytes()[:2],b'PK')
 def test_custom_subtree_excluded_before_read(self):
  folder=self.root/'data';folder.mkdir()
  with (folder/'huge.bin').open('wb') as f:f.truncate(20*1024*1024)
  result=pack_project(self.root,self.base/'project.txt',exclude=['data/**'],max_source_bytes=100)
  self.assertIn('data/',result['skipped']);self.assertEqual(result['fileCount'],1)
 def test_deterministic_binary_with_txt_name(self):
  a=pack_project(self.root,self.base/'a.txt');b=pack_project(self.root,self.base/'b.txt')
  self.assertEqual(pathlib.Path(a['bundle']).read_bytes(),pathlib.Path(b['bundle']).read_bytes())
 def bundle_names(self):
  result=pack_project(self.root,self.base/'rules.txt')
  with zipfile.ZipFile(result['bundle']) as z:names=set(z.namelist())
  return result,names
 def test_project_ignore_replaces_defaults_and_records_source(self):
  (self.root/'.nopilotignore').write_text('# Project rules\n*.tmp\n',encoding='utf-8')
  (self.root/'omit.tmp').write_text('omit');(self.root/'keep.log').write_text('keep')
  result,names=self.bundle_names()
  self.assertNotIn('omit.tmp',names);self.assertIn('keep.log',names)
  self.assertEqual(result['ignore']['source'],'project');self.assertEqual(result['ignore']['ruleCount'],1)
 def test_gitignore_negation_root_anchor_double_star_and_escape(self):
  (self.root/'.nopilotignore').write_text('# comment\n/root.txt\n**/cache/\n*.tmp\n!important.tmp\n\\#literal\n',encoding='utf-8')
  for name in ('root.txt','omit.tmp','important.tmp','#literal','sub/root.txt','sub/cache/large.bin'):
   p=self.root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('data')
  _,names=self.bundle_names()
  self.assertIn('important.tmp',names);self.assertIn('sub/root.txt',names)
  for name in ('root.txt','omit.tmp','#literal','sub/cache/large.bin'):self.assertNotIn(name,names)
 def test_excluded_parent_cannot_be_reincluded_by_file_rule(self):
  (self.root/'.nopilotignore').write_text('data/\n!data/keep.txt\n')
  p=self.root/'data/keep.txt';p.parent.mkdir();p.write_text('not included')
  _,names=self.bundle_names();self.assertNotIn('data/keep.txt',names)
 def test_unignored_parent_allows_specific_child(self):
  (self.root/'.nopilotignore').write_text('data/*\n!data/keep.txt\n')
  for name in ('keep.txt','drop.txt'):
   p=self.root/'data'/name;p.parent.mkdir(exist_ok=True);p.write_text('data')
  _,names=self.bundle_names();self.assertIn('data/keep.txt',names);self.assertNotIn('data/drop.txt',names)
 def test_invalid_encoding_fails_before_output(self):
  (self.root/'.nopilotignore').write_bytes(b'\xff')
  with self.assertRaisesRegex(ValueError,'UTF-8'):self.bundle_names()
  self.assertFalse((self.base/'rules.txt').exists())
 def harness(self,count):
  h=Harness();h.bridge=Mock();h.bridge.state.return_value={'generating':False,'draft':''};h.bridge.evaluate.return_value=count
  h.upload=Mock(return_value={'finished':True});h.ask=Mock(return_value={'answer':'MODEL_FIXTURE','requestId':'fixture'});h.downloads=Mock(return_value=[]);return h
 def test_log_attachment_kept_and_one_project_slot_added(self):
  for count in (1,2):
   h=self.harness(count);stages=[]
   result=h.project(self.root,question='Sửa lỗi theo log',out_dir=self.base/str(count),on_stage=lambda stage,data:stages.append(stage))
   self.assertEqual(stages,['packing','packed','uploading','uploaded','asking','answered']);h.upload.assert_called_once();h.ask.assert_called_once();self.assertIn('Sửa lỗi theo log',h.ask.call_args.args[0]);self.assertEqual(result['project']['attachmentSlots'],1)
 def test_three_pending_files_refused_before_pack_upload_or_ask(self):
  h=self.harness(3)
  with self.assertRaises(RuntimeError):h.project(self.root,out_dir=self.base/'blocked')
  self.assertFalse((self.base/'blocked').exists());h.upload.assert_not_called();h.ask.assert_not_called()
 def test_web_project_stages_are_persisted_in_chat(self):
  from web_server import Application
  app=Application(self.base/'web');cid=app.initial_id;app.harness=self.harness(1);app.ensure=lambda *a,**k:None;app.capture_route=lambda *a:None
  try:
   ws=app.workspace(cid);pid=ws.create('current fixture',[{'path':'app.py','content':'print("CURRENT_SOURCE")'}])['id']
   app.conversations[cid]['activeProjectId']=pid
   job=app.submit(cid,'/project current Sửa lỗi theo log')
   deadline=time.monotonic()+5
   while job['state'] in ('queued','running') and time.monotonic()<deadline:time.sleep(.02)
   self.assertEqual(job['state'],'done',job)
   messages=app.conversations[cid]['messages'];steps=[m for m in messages if m['role']=='system' and m['text'].startswith('Project ·')]
   self.assertEqual(len(steps),5);self.assertTrue(steps[1]['artifacts']);self.assertEqual(messages[-1]['text'],'MODEL_FIXTURE');self.assertEqual(messages[-1]['role'],'assistant')
   uploaded=app.harness.upload.call_args.args[0]
   with zipfile.ZipFile(uploaded) as z:self.assertIn('CURRENT_SOURCE',z.read('app.py').decode())
  finally:app.shutdown()

if __name__=='__main__':unittest.main(verbosity=2)
