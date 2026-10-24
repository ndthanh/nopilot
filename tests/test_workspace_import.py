import json,pathlib,sys,tempfile,time,unittest,zipfile
from unittest.mock import Mock
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
from web_server import Application
from dev_workspace import manifest
from cli import Harness
import project_git

class WorkspaceImportTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.base=pathlib.Path(self.temp.name);self.source=self.base/'my-code';self.source.mkdir()
  (self.source/'main.py').write_text('print("ORIGINAL")',encoding='utf-8')
  (self.source/'.nopilotignore').write_text('.env\nlogs/\n.venv/\n',encoding='utf-8')
  for name in ('.env','logs/private.log','.venv/large.bin','.git/config'):
   p=self.source/name;p.parent.mkdir(exist_ok=True);p.write_text('DO_NOT_IMPORT')
  self.app=Application(self.base/'data');self.cid=self.app.initial_id
 def tearDown(self):self.app.shutdown();self.temp.cleanup()
 def prepare(self):return self.app.imports.prepare(self.cid,self.source)
 def test_preview_filters_and_never_uploads_runs_or_commits(self):
  p=self.prepare();source=pathlib.Path(p['sourceDirectory'])
  self.assertEqual(set(p['files']),{'main.py','.nopilotignore'});self.assertIsNone(self.app.harness)
  self.assertNotIn('activeProjectId',self.app.conversations[self.cid]);self.assertFalse(project_git.status(self.app.workspace(self.cid),p['projectId'])['initialized'])
  self.assertTrue((source/'main.py').is_file());self.assertEqual(p['contractStatus'],'missing')
 def test_confirm_is_idempotent_and_preserves_original_repo(self):
  before=manifest(self.source)['revision'];p=self.prepare();accepted=self.app.imports.confirm(self.cid,p['id'])
  self.assertEqual(accepted['status'],'accepted');self.assertTrue(accepted['commit'])
  self.assertEqual(self.app.imports.confirm(self.cid,p['id'])['commit'],accepted['commit'])
  self.assertEqual(self.app.current_project_source(self.cid),pathlib.Path(p['sourceDirectory']))
  self.assertEqual(manifest(self.source)['revision'],before);self.assertIsNone(self.app.harness)
 def test_git_worktree_pointer_file_is_excluded(self):
  gitdir=self.source/'.git';(gitdir/'config').unlink();gitdir.rmdir();gitdir.write_text('gitdir: C:/private/git/worktree')
  p=self.prepare();self.assertNotIn('.git',p['files'])
 def test_reject_expiry_tamper_and_foreign_conversation(self):
  p=self.prepare();other=self.app.create()['id']
  with self.assertRaises(ValueError):self.app.imports.confirm(other,p['id'])
  self.app.imports.reject(self.cid,p['id'])
  with self.assertRaises(ValueError):self.app.imports.confirm(self.cid,p['id'])
  p=self.prepare();self.app.imports.items[p['id']]['expiresAt']=0
  with self.assertRaises(ValueError):self.app.imports.confirm(self.cid,p['id'])
  p=self.prepare();(pathlib.Path(p['sourceDirectory'])/'main.py').write_text('CHANGED')
  with self.assertRaises(ValueError):self.app.imports.confirm(self.cid,p['id'])
  self.assertNotIn('activeProjectId',self.app.conversations[self.cid])
 def test_import_does_not_recurse_into_nopilot_data(self):
  for path in (self.app.root,self.app.root.parent,self.app.directory(self.cid)):
   with self.assertRaises(ValueError):self.app.imports.prepare(self.cid,path)
 def test_git_backup_handles_deep_windows_workspace_path(self):
  app=Application(self.base/('nested-path-'*6)/'data')
  try:
   p=app.imports.prepare(app.initial_id,self.source)
   self.assertTrue(app.imports.confirm(app.initial_id,p['id'])['commit'])
  finally:app.shutdown()
 def test_defaults_copied_and_explicit_rules_retained_when_self_ignored(self):
  (self.source/'.nopilotignore').unlink();p=self.prepare()
  self.assertEqual(p['ignore']['source'],'defaults');self.assertTrue((pathlib.Path(p['sourceDirectory'])/'.nopilotignore').is_file())
  (self.source/'.nopilotignore').write_text('.nopilotignore\n.env\nlogs/\n.venv/\n')
  p=self.prepare();self.assertEqual((pathlib.Path(p['sourceDirectory'])/'.nopilotignore').read_bytes(),(self.source/'.nopilotignore').read_bytes())
 def wait_job(self,job):
  deadline=time.monotonic()+5
  while job['state'] in ('queued','running') and time.monotonic()<deadline:time.sleep(.02)
  self.assertEqual(job['state'],'done',job)
 def test_workspace_command_works_without_teams_and_iterate_uses_managed_source(self):
  self.wait_job(self.app.submit(self.cid,'/workspace "'+str(self.source)+'"'))
  self.assertIsNone(self.app.harness);planid=self.app.conversations[self.cid]['messages'][-1]['workspacePlanId']
  p=self.app.imports.confirm(self.cid,planid);managed=pathlib.Path(p['sourceDirectory']);(managed/'main.py').write_text('print("LOCAL_WORKSPACE_EDIT")')
  h=Harness();h.bridge=Mock();h.bridge.state.return_value={'generating':False,'draft':''};h.bridge.evaluate.return_value=0
  h.upload=Mock(return_value={'finished':True});h.ask=Mock(return_value={'answer':'fixed','answerMarkdown':'**fixed**'});h.downloads=Mock(return_value=[])
  self.app.harness=h;self.app.ensure=Mock();self.app.capture_route=Mock()
  self.wait_job(self.app.submit(self.cid,'/iterate Thêm tính năng TEST_FEATURE'))
  uploaded=h.upload.call_args.args[0];self.assertEqual(pathlib.Path(uploaded).suffix,'.txt')
  with zipfile.ZipFile(uploaded) as z:
   self.assertIn('LOCAL_WORKSPACE_EDIT',z.read('main.py').decode());self.assertNotIn('.env',z.namelist());self.assertFalse(any(n.startswith('.git/') for n in z.namelist()))
  prompt=h.ask.call_args.args[0]
  self.assertIn('NOPILOT DEVELOPMENT CONTRACT v1',prompt);self.assertIn('TEST_FEATURE',prompt);self.assertIn('NOPILOT_COMMIT_MESSAGE.txt',prompt)
  self.assertEqual(self.app.conversations[self.cid]['messages'][-1]['markdown'],'**fixed**')
 def test_switch_workspace_uses_only_accepted_plan(self):
  first=self.prepare();second=self.prepare()
  self.app.imports.confirm(self.cid,first['id'])
  with self.assertRaises(ValueError):self.app.imports.select(self.cid,second['id'])
  self.app.imports.confirm(self.cid,second['id']);self.app.imports.select(self.cid,first['id'])
  self.assertEqual(self.app.conversations[self.cid]['activeProjectId'],first['projectId'])
  self.app.dev_action(self.cid,'select-project',{'projectId':second['projectId']})
  self.assertEqual(self.app.conversations[self.cid]['activeProjectId'],second['projectId'])
  with self.assertRaises(ValueError):self.app.dev_action(self.app.create()['id'],'select-project',{'projectId':second['projectId']})
 def test_duplicate_download_names_and_bytes_produce_one_artifact(self):
  self.app.harness=Mock();self.app.harness.downloads.return_value=[{'name':'project.zip'},{'name':'1.zip'},{'name':'1.zip'}]
  self.app.harness.download.side_effect=lambda name,target:target.write_bytes(b'SAME_ZIP_FIXTURE')
  cards=self.app.download_all(self.cid)
  self.assertEqual(len(cards),1);self.assertEqual(cards[0]['name'],'project.zip')
  self.assertEqual(self.app.harness.download.call_count,2)
  self.assertEqual(len(list((self.app.directory(self.cid)/'artifacts/downloads').iterdir())),1)

if __name__=='__main__':unittest.main(verbosity=2)
