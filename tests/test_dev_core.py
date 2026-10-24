import sys,pathlib,tempfile,unittest,zipfile,json,time,os,ctypes,stat
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
from dev_workspace import Workspace,inspect_zip,relative
from execution import Runner

class DevTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory(prefix='nopilot-test-');self.root=pathlib.Path(self.temp.name).resolve();self.workspace=Workspace(self.root/'dev');self.runner=Runner(self.workspace,self.root/'artifacts')
 def tearDown(self):self.runner.close();self.temp.cleanup()
 def create(self,code):return self.workspace.create('Synthetic test',[{'path':'run.py','content':code}])
 def wait(self,rid):
  deadline=time.monotonic()+45
  while time.monotonic()<deadline:
   item=self.runner.runs[rid]
   if item['status'] not in ('starting','running'):self.runner.threads[rid].join(3);return item
   time.sleep(.04)
  self.fail('Run never finished')
 def run_code(self,code,timeout=15):
  p=self.create(code);approval=self.workspace.propose(p['id'],timeout=timeout);rid=self.runner.start(approval['id'])['id'];return p,self.wait(rid),self.runner.log(rid)['text']
 def test_windows_paths(self):
  for name in ('../outside','/absolute','C:/escape','a\\b','a/../b','CON.py','nul.txt','foo:stream','folder/a.','folder/ b '):
   with self.subTest(name=name),self.assertRaises(ValueError):relative(name)
 def test_zip_inspect_extract(self):
  path=self.root/'project.zip'
  with zipfile.ZipFile(path,'w') as z:z.writestr('project/run.py','print("proof")');z.writestr('project/README.md','# Test')
  info=inspect_zip(path);p=self.workspace.extract(path,info['zipSha256'])
  self.assertEqual([f['path'] for f in p['files']],['README.md','run.py']);self.assertFalse((self.workspace.folder(p['id'])/'venv').exists())
  with self.assertRaises(ValueError):self.workspace.extract(path,'incorrect hash')
 def test_bad_zips(self):
  cases=[['../escape.py'],['C:/escape.py'],['run.py','RUN.py'],['a','a/b.py'],['safe/CON.txt']]
  for names in cases:
   path=self.root/('bad-'+str(len(list(self.root.glob('bad*'))))+'.zip')
   with zipfile.ZipFile(path,'w') as z:
    for name in names:z.writestr(name,'x')
   with self.subTest(names=names),self.assertRaises(ValueError):inspect_zip(path)
  path=self.root/'symlink.zip';entry=zipfile.ZipInfo('link');entry.create_system=3;entry.external_attr=(stat.S_IFLNK|0o777)<<16
  with zipfile.ZipFile(path,'w') as z:z.writestr(entry,'/outside')
  with self.assertRaises(ValueError):inspect_zip(path)
  path=self.root/'bomb.zip'
  with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as z:z.writestr('large',b'0'*(2*1024*1024))
  with self.assertRaises(ValueError):inspect_zip(path)
 def test_patch_diff_rollback(self):
  p=self.create('print("before")\n');result=self.workspace.patch(p['id'],p['revision'],[{'path':'run.py','content':'print("after")\n'},{'path':'new.txt','content':'new'}])
  self.assertIn('+print("after")',result['diff']['diff']);self.assertNotEqual(p['revision'],result['project']['revision'])
  with self.assertRaises(ValueError):self.workspace.patch(p['id'],p['revision'],[{'path':'run.py','content':'stale'}])
  restored=self.workspace.rollback(p['id'],result['checkpoint']);self.assertEqual(restored['project']['revision'],p['revision']);self.assertFalse((self.workspace.source(p['id'])/'new.txt').exists())
  self.workspace.rollback(p['id'],restored['recoveryCheckpoint']);self.assertIn('after',self.workspace.read(p['id'],'run.py')['content'])
 def test_no_execution_before_approval(self):
  p=self.create('open("executed.txt","w").write("ran")');approval=self.workspace.propose(p['id'])
  time.sleep(.2);self.assertFalse((self.workspace.source(p['id'])/'executed.txt').exists());self.workspace.reject(approval['id'])
  with self.assertRaises(ValueError):self.runner.start(approval['id'])
 def test_stale_expired_and_single_use(self):
  p=self.create('print("OK")');a=self.workspace.propose(p['id']);self.workspace.patch(p['id'],p['revision'],[{'path':'run.py','content':'print("changed")'}])
  with self.assertRaises(ValueError):self.runner.start(a['id'])
  a=self.workspace.propose(p['id']);a['expiresAt']=0
  with self.assertRaises(ValueError):self.runner.start(a['id'])
  a=self.workspace.propose(p['id']);rid=self.runner.start(a['id'])['id']
  with self.assertRaises(ValueError):self.runner.start(a['id'])
  self.assertEqual(self.wait(rid)['status'],'succeeded')
 def test_stdout_stderr_and_environment(self):
  os.environ['NOPILOT_TEST_SECRET']='must-not-be-inherited'
  try:p,run,log=self.run_code('import sys,os\nprint("STDOUT_PROOF")\nprint("STDERR_PROOF",file=sys.stderr)\nprint("ENV_"+str(os.environ.get("NOPILOT_TEST_SECRET")))')
  finally:os.environ.pop('NOPILOT_TEST_SECRET',None)
  self.assertEqual(run['status'],'succeeded',run);self.assertIn('STDOUT_PROOF',log);self.assertIn('STDERR_PROOF',log);self.assertIn('ENV_None',log);self.assertNotIn('must-not-be-inherited',log)
 def test_short_private_temp_and_edge_install_environment(self):
  _,run,log=self.run_code('import os,pathlib\np=pathlib.Path(os.environ["TEMP"])\nprint("TEMP_PROOF_"+str(len(str(p))<100))\nprint("PRIVATE_DIR_PROOF_"+str(p.is_dir() and pathlib.Path(os.environ["LOCALAPPDATA"]).is_dir()))\nprint("PROGRAMFILES_PROOF_"+str(bool(os.environ.get("PROGRAMFILES") or os.environ.get("ProgramFiles"))))\nprint("TEMP_PATH="+str(p))')
  self.assertEqual(run['status'],'succeeded',log)
  for proof in ('TEMP_PROOF_True','PRIVATE_DIR_PROOF_True','PROGRAMFILES_PROOF_True'):self.assertIn(proof,log)
  path=pathlib.Path(log.split('TEMP_PATH=')[1].splitlines()[0].strip());self.assertFalse(path.exists(),'Private runtime temp was not cleaned')
 def test_nested_subprocess_text_decodes_unicode_as_utf8(self):
  code='import subprocess,sys\ns="Xin chào, Nopilot!"\nr=subprocess.run([sys.executable,"-c","print("+repr(s)+")"],capture_output=True,text=True,check=True)\nassert r.stdout.strip()==s,repr(r.stdout)\nprint("UNICODE_SUBPROCESS_PASS")'
  _,run,log=self.run_code(code)
  self.assertEqual(run['status'],'succeeded',log);self.assertIn('UNICODE_SUBPROCESS_PASS',log)
 def test_nonzero_and_timeout(self):
  _,run,_=self.run_code('raise SystemExit(7)');self.assertEqual(run['exitCode'],7);self.assertEqual(run['status'],'failed')
  p=self.create('import time\ntime.sleep(60)');a=self.workspace.propose(p['id'],timeout=1);run=self.wait(self.runner.start(a['id'])['id']);self.assertEqual(run['status'],'timeout',run)
 def test_process_tree_stop_and_active_edit_guard(self):
  p=self.create('import subprocess,sys,pathlib,time\np=subprocess.Popen([sys.executable,"-c","import time;time.sleep(60)"])\npathlib.Path("child.pid").write_text(str(p.pid))\nprint("CHILD_STARTED",flush=True)\ntime.sleep(60)')
  a=self.workspace.propose(p['id'],timeout=40);rid=self.runner.start(a['id'])['id'];deadline=time.monotonic()+20;pidfile=pathlib.Path(self.runner.runs[rid]['cwd'])/'child.pid'
  while not pidfile.exists() and time.monotonic()<deadline:time.sleep(.05)
  self.assertTrue(pidfile.exists(),self.runner.runs[rid]);child=int(pidfile.read_text())
  with self.assertRaises(ValueError):self.workspace.patch(p['id'],self.workspace.current(p['id'])['revision'],[{'path':'run.py','content':'bad'}])
  self.runner.stop(rid);run=self.wait(rid);self.assertEqual(run['status'],'stopped',run)
  kernel=ctypes.WinDLL('kernel32',use_last_error=True);kernel.OpenProcess.restype=ctypes.c_void_p;kernel.OpenProcess.argtypes=[ctypes.c_uint32,ctypes.c_int,ctypes.c_uint32];handle=kernel.OpenProcess(0x1000,False,child)
  if handle:
   kernel.GetExitCodeProcess.argtypes=[ctypes.c_void_p,ctypes.POINTER(ctypes.c_uint32)];code=ctypes.c_uint32();kernel.GetExitCodeProcess(handle,ctypes.byref(code));kernel.CloseHandle.argtypes=[ctypes.c_void_p];kernel.CloseHandle(handle);self.assertNotEqual(code.value,259,'Child process survived stop')
 def test_install_inputs(self):
  p=self.workspace.create('deps',[{'path':'requirements.txt','content':'-r C:/secrets.txt'}])
  with self.assertRaises(ValueError):self.workspace.propose(p['id'],kind='install',entrypoint='requirements.txt')
 def test_restart_pending_approval(self):
  p=self.create('print("x")');a=self.workspace.propose(p['id']);loaded=Workspace(self.workspace.root);self.assertEqual(loaded.approvals[a['id']]['status'],'pending')
 def test_output_limit_and_immediate_stop(self):
  _,run,_=self.run_code('import sys\nsys.stdout.write("x"*2000000)\nsys.stdout.flush()',timeout=30)
  self.assertEqual(run['status'],'log_limit',run);self.assertLessEqual(run['bytes'],1024*1024)
  p=self.create('open("MUST_NOT_EXIST","w").write("bad")');a=self.workspace.propose(p['id']);rid=self.runner.start(a['id'])['id'];self.runner.stop(rid)
  self.assertEqual(self.wait(rid)['status'],'stopped');self.assertFalse((self.workspace.source(p['id'])/'MUST_NOT_EXIST').exists())
 @unittest.skipUnless(os.environ.get("NOPILOT_INTEGRATION_TESTS")=="1","Set NOPILOT_INTEGRATION_TESTS=1 to install a known PyPI package")
 def test_pinned_dependency_install_then_run(self):
  p=self.workspace.create('Known registry package',[{'path':'requirements.txt','content':'colorama==0.4.6\n'},{'path':'run.py','content':'import colorama\nprint("DEPENDENCY_PROOF_"+colorama.__version__)'}])
  approval=self.workspace.propose(p['id'],kind='install',entrypoint='requirements.txt',timeout=120);rid=self.runner.start(approval['id'])['id'];result=self.wait(rid)
  self.assertEqual(result['status'],'succeeded',self.runner.log(rid)['text'])
  approval=self.workspace.propose(p['id']);rid=self.runner.start(approval['id'])['id'];self.assertEqual(self.wait(rid)['status'],'succeeded');self.assertIn('DEPENDENCY_PROOF_0.4.6',self.runner.log(rid)['text'])
 def test_runtime_tampering_requires_new_approval(self):
  p,run,_=self.run_code('print("bootstrap")');approval=self.workspace.propose(p['id']);exe=self.workspace.folder(p['id'])/'venv/Scripts/python.exe';exe.write_bytes(exe.read_bytes()+b'QA_TAMPER')
  with self.assertRaises(ValueError):self.runner.start(approval['id'])
 def test_data_directory_lock(self):
  from data_lock import DataLock
  lock=DataLock(self.root/'data')
  try:
   with self.assertRaises(RuntimeError):DataLock(self.root/'data')
  finally:lock.close()
  lock=DataLock(self.root/'data');lock.close()
 def test_approved_snapshot_and_output_collection(self):
  p=self.create('import pathlib,time\nprint("SNAPSHOT_STARTED",flush=True)\ntime.sleep(1)\npathlib.Path("result.txt").write_text("APPROVED_OUTPUT")\nprint("FROZEN_APPROVED_CODE")')
  a=self.workspace.propose(p['id'],timeout=30);rid=self.runner.start(a['id'])['id'];deadline=time.monotonic()+20
  while 'SNAPSHOT_STARTED' not in self.runner.log(rid)['text'] and time.monotonic()<deadline:time.sleep(.02)
  self.assertIn('SNAPSHOT_STARTED',self.runner.log(rid)['text'])
  (self.workspace.source(p['id'])/'run.py').write_text('print("UNAPPROVED_CHANGE")',encoding='utf-8')
  result=self.wait(rid);log=self.runner.log(rid)['text'];self.assertEqual(result['status'],'succeeded');self.assertIn('FROZEN_APPROVED_CODE',log);self.assertNotIn('UNAPPROVED_CHANGE',log)
  self.assertFalse((self.workspace.source(p['id'])/'result.txt').exists());self.assertEqual((self.runner.root/rid/'outputs/result.txt').read_text(),'APPROVED_OUTPUT')

if __name__=='__main__':unittest.main(verbosity=2)
