import pathlib,sys,unittest
from unittest.mock import patch
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
from cli import Harness

class UploadTests(unittest.TestCase):
 def wait(self,states):
  h=Harness();clock=[0.0];calls=[]
  class Bridge:
   def evaluate(self,script):calls.append(script);return states[min(len(calls)-1,len(states)-1)]
  h.bridge=Bridge()
  def sleep(seconds):clock[0]+=seconds
  with patch('cli.time.monotonic',lambda:clock[0]),patch('cli.time.sleep',sleep):result=h.wait_upload('proof.jpg',timeout=15)
  return result,len(calls)
 def ui(self,**changes):return dict(text='',cardPresent=True,cloudIdAssigned=False,imageReady=True,busy=False,alerts=[],**changes)
 def test_native_image_without_filename_text(self):
  result,calls=self.wait([self.ui()]);self.assertEqual(calls,8);self.assertIn('image',result['completionSignal']);self.assertFalse(result['composerReportsFinished'])
 def test_busy_image_waits(self):
  ui=self.ui();busy={**ui,'busy':True};result,calls=self.wait([busy,busy,ui]);self.assertEqual(calls,10)
 def test_preview_missing_does_not_confirm(self):
  with self.assertRaises(TimeoutError):self.wait([{**self.ui(),'imageReady':False,'text':'proof.jpg'}])
 def test_cloud_file_still_uses_three_reads(self):
  result,calls=self.wait([{**self.ui(),'imageReady':False,'cloudIdAssigned':True,'text':'proof.jpg'}]);self.assertEqual(calls,3);self.assertIn('cloud-backed',result['completionSignal'])

if __name__=='__main__':unittest.main(verbosity=2)
