import pathlib,sys,tempfile,time,unittest
from unittest.mock import Mock
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
from web_server import Application

class MarkdownPersistenceTests(unittest.TestCase):
 def test_plain_answer_and_markdown_are_saved_separately(self):
  with tempfile.TemporaryDirectory() as folder:
   app=Application(folder);cid=app.initial_id;app.harness=Mock()
   app.ensure=lambda *a,**k:None;app.capture_route=lambda *a:None;app.download_all=lambda *a:[]
   app.harness.ask.return_value={'answer':'Title\nhello','answerMarkdown':'## Title\n\n**hello**'}
   try:
    job=app.submit(cid,'Formatting test')
    deadline=time.monotonic()+3
    while job['state'] in ('queued','running') and time.monotonic()<deadline:time.sleep(.01)
    self.assertEqual(job['state'],'done',job)
    message=app.conversations[cid]['messages'][-1]
    self.assertEqual(message['text'],'Title\nhello');self.assertEqual(message['markdown'],'## Title\n\n**hello**')
    import json
    saved=json.loads((app.directory(cid)/'conversation.json').read_text(encoding='utf-8'))
    self.assertEqual(saved['messages'][-1]['markdown'],message['markdown'])
   finally:app.shutdown()

if __name__=='__main__':unittest.main()
