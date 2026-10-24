import pathlib,sys,tempfile,unittest,zipfile,json,shutil
from unittest.mock import patch
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
from dev_workspace import Workspace,save_json,stamp
import project_git as pg
from environment_cache import state,dependency_key,sha

@unittest.skipUnless(shutil.which('git'),'Git required')
class GitUpdates(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=pathlib.Path(self.temp.name);self.ws=Workspace(self.root/'dev');self.p=self.ws.create('fixture',[{'path':'run.py','content':'print("old")'},{'path':'old.txt','content':'delete me'}]);self.pid=self.p['id'];self.source=self.ws.source(self.pid)
 def tearDown(self):self.temp.cleanup()
 def archive(self,files):
  target=self.root/'incoming.zip'
  with zipfile.ZipFile(target,'w') as z:
   for name,content in files.items():z.writestr('project/'+name,content)
  return target
 def test_review_apply_commit_preserves_project_and_venv(self):
  venv=self.ws.folder(self.pid)/'venv';venv.mkdir();(venv/'marker').write_text('KEEP_VENV')
  archive=self.archive({'run.py':'print("new")',pg.MESSAGE:'fix: update fixture\n\nPreserve project environment.'})
  review=pg.preview(self.ws,self.pid,archive,None);self.assertEqual((self.source/'run.py').read_text(),'print("old")');self.assertIn({'path':'old.txt','change':'deleted'},review['changes'])
  result=pg.apply(self.ws,self.pid,review['id'],review['baseRevision'],review['commitMessage'])
  self.assertEqual(result['project']['id'],self.pid);self.assertEqual((venv/'marker').read_text(),'KEEP_VENV');self.assertFalse((self.source/'old.txt').exists());self.assertIn('fix: update fixture',result['git']['log']);self.assertEqual(len(pg.git(pg.repo(self.ws,self.pid),'log','--format=%H').splitlines()),2)
  with self.assertRaises(ValueError):pg.apply(self.ws,self.pid,review['id'],review['baseRevision'],review['commitMessage'])
 def test_stale_review_keeps_source(self):
  review=pg.preview(self.ws,self.pid,self.archive({'run.py':'print("new")'}),None);(self.source/'run.py').write_text('print("local edit")')
  with self.assertRaisesRegex(ValueError,'Source'):pg.apply(self.ws,self.pid,review['id'],review['baseRevision'],'fix: change')
  self.assertEqual((self.source/'run.py').read_text(),'print("local edit")')
 def test_missing_message_needs_user_input(self):
  review=pg.preview(self.ws,self.pid,self.archive({'run.py':'print("new")'}),None);self.assertEqual(review['commitMessage'],'')
  with self.assertRaises(ValueError):pg.apply(self.ws,self.pid,review['id'],review['baseRevision'],'')
  self.assertEqual(self.ws.current(self.pid)['revision'],self.p['revision'])
 def test_git_failure_restores_source_file_directory_transition(self):
  review=pg.preview(self.ws,self.pid,self.archive({'run.py/inside.txt':'new directory'}),None)
  with patch('project_git.commit',side_effect=[{'head':'baseline'},ValueError('simulated git failure')]):
   with self.assertRaisesRegex(ValueError,'simulated'):pg.apply(self.ws,self.pid,review['id'],review['baseRevision'],'fix: transition')
  self.assertEqual(self.ws.current(self.pid)['revision'],self.p['revision'])
 def test_zip_git_metadata_refused(self):
  with self.assertRaisesRegex(ValueError,'.git'):pg.preview(self.ws,self.pid,self.archive({'.git/config':'bad','run.py':'print(1)'}),None)
 def test_commit_message_not_executed_as_shell(self):
  result=pg.commit(self.ws,self.pid,'fix: literal $(echo BAD) & echo NEVER')
  self.assertIn('$(echo BAD) & echo NEVER',result['log']);self.assertFalse((self.source/'NEVER').exists())

class EnvironmentReceipts(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.ws=Workspace(pathlib.Path(self.temp.name)/'dev');self.p=self.ws.create('fixture',[{'path':'run.py','content':'print(1)'},{'path':'requirements.txt','content':'colorama==0.4.6\n'}]);self.pid=self.p['id'];self.folder=self.ws.folder(self.pid);self.exe=self.folder/'venv/Scripts/python.exe';self.exe.parent.mkdir(parents=True);self.exe.write_bytes(b'known fake runtime, never executed')
  save_json(self.folder/'environment.json',{'key':dependency_key(self.ws.source(self.pid)),'runtimeSha256':sha(self.exe),'installedAt':stamp()})
 def tearDown(self):self.temp.cleanup()
 def test_source_only_edit_reuses_after_restart(self):
  (self.ws.source(self.pid)/'run.py').write_text('print(2)');self.assertTrue(state(self.ws,self.pid)['ready']);reloaded=Workspace(self.ws.root);self.assertTrue(state(reloaded,self.pid)['ready'])
 def test_requirements_change_needs_reset_approval(self):
  (self.ws.source(self.pid)/'requirements.txt').write_text('colorama==0.4.5\n');self.assertFalse(state(self.ws,self.pid)['ready'])
  approval=self.ws.propose(self.pid,kind='install',entrypoint='requirements.txt');self.assertTrue(approval['resetRuntime']);self.assertTrue(self.exe.exists())
 def test_runtime_change_invalidates_receipt(self):
  self.exe.write_bytes(b'changed');self.assertFalse(state(self.ws,self.pid)['ready'])
 def test_missing_or_failed_receipt_not_ready(self):
  (self.folder/'environment.json').unlink();self.assertFalse(state(self.ws,self.pid)['ready'])
if __name__=='__main__':unittest.main(verbosity=2)
