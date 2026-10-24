import pathlib,sys,tempfile,unittest
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
from workflow_cli import paused_command

class PauseTests(unittest.TestCase):
 def setUp(self):
  self.events=[];self.pool=ThreadPoolExecutor(max_workers=1)
  self.app=SimpleNamespace(executor=self.pool,ensure=lambda cid:self.events.append(('ensure',cid)),harness=SimpleNamespace(upload=lambda path:self.events.append(('upload',str(path))) or {'knownFixture':True}),explorers=SimpleNamespace(control=lambda *args:self.events.append(('control',args))),queue=lambda *args,**kw:self.events.append(('queue',args,kw)))
 def tearDown(self):self.pool.shutdown()
 def test_resume_queues_same_session(self):
  self.assertTrue(paused_command(self.app,'cid',{'id':'task'},'/resume'));self.assertEqual(self.events[0],('control',('cid','task','resume')))
 def test_upload_does_not_resume_or_grant(self):
  with tempfile.TemporaryDirectory(prefix='nopilot-cli-pause-') as temporary:
   file=pathlib.Path(temporary)/'known proof.txt';file.write_text('fixture')
   self.assertTrue(paused_command(self.app,'cid',{'id':'task'},'/upload "'+str(file)+'"'))
  self.assertEqual([e[0] for e in self.events],['ensure','upload'])
 def test_exit_and_unknown_commands(self):
  self.assertFalse(paused_command(self.app,'cid',{'id':'task'},'/quit'));self.assertEqual(self.events,[])
  with self.assertRaises(ValueError):paused_command(self.app,'cid',{'id':'task'},'/grant 100')

if __name__=='__main__':unittest.main(verbosity=2)
