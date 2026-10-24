"""Frida-only bridge for an already running Windows Teams Copilot frame."""
from __future__ import annotations
import argparse
import base64
import hashlib
import json
import pathlib
import ctypes
from ctypes import wintypes
import time
import uuid
import frida
from memory_scan import discover_frames

HERE = pathlib.Path(__file__).resolve().parent

DRAFT_TEXT_JS = r'''((e)=>{
if(!e)return '';
const state=e.__lexicalEditor?.getEditorState?.().toJSON?.();
if(!state)return (e.innerText||'').replace(/[\u200B-\u200D\uFEFF]+$/g,'');
const walk=n=>n.type==='linebreak'?'\n':typeof n.text==='string'?n.text:(n.children||[]).map(walk).join('');
return (state.root?.children||[]).map(walk).join('\n').replace(/[\u200B-\u200D\uFEFF]+$/g,'');
})(document.querySelector('[contenteditable="true"][aria-label="Message Copilot"]'))'''

STATE_JS = r'''(() => {
const toMarkdown = __MARKDOWN_CONVERTER__;
const turns = Array.from(document.querySelectorAll('[data-testid="m365-chat-llm-web-ui-chat-message"]')).map(n => ({
  id:n.id,
  question:n.querySelector('[data-testid="chatQuestion"] [data-testid="chatOutput"]')?.innerText || '',
  answer:Array.from(n.querySelectorAll('[data-testid="markdown-reply"]')).map(e=>e.innerText).join('\n\n'),
  answerMarkdown:Array.from(n.querySelectorAll('[data-testid="markdown-reply"]')).map(e=>toMarkdown(e)).join('\n\n'),
  code:[...Array.from(n.querySelectorAll('pre code')).map(e=>e.textContent),
    ...Array.from(n.querySelectorAll('[aria-label="Code editor"]')).map(e=>Array.from(e.querySelectorAll('[data-line-index]')).sort((a,b)=>Number(a.dataset.lineIndex)-Number(b.dataset.lineIndex)).map(e=>e.textContent).join('\n'))],
  copyReady:!!n.querySelector('[data-testid="CopyButtonTestId"]')
}));
return {title:document.title, origin:location.origin,
  editorPresent:!!document.querySelector('[contenteditable="true"][aria-label="Message Copilot"]'),
  draft:__DRAFT_TEXT__,
  generating:Array.from(document.querySelectorAll('button')).some(e=>/stop (generating|response|responding)/i.test(e.getAttribute('aria-label')||'')),
  turns};
})()'''.replace('__DRAFT_TEXT__',DRAFT_TEXT_JS).replace('__MARKDOWN_CONVERTER__',(HERE/'copilot_markdown.js').read_text(encoding='utf-8'))

def teams_pid():
    """Enumerate native Windows processes without launching any shell."""
    class ProcessEntry(ctypes.Structure):
        _fields_ = [('dwSize',wintypes.DWORD),('cntUsage',wintypes.DWORD),
          ('th32ProcessID',wintypes.DWORD),('th32DefaultHeapID',ctypes.c_size_t),
          ('th32ModuleID',wintypes.DWORD),('cntThreads',wintypes.DWORD),
          ('th32ParentProcessID',wintypes.DWORD),('pcPriClassBase',wintypes.LONG),
          ('dwFlags',wintypes.DWORD),('szExeFile',wintypes.WCHAR*260)]
    kernel = ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD,wintypes.DWORD]
    kernel.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel.Process32FirstW.argtypes = [wintypes.HANDLE,ctypes.POINTER(ProcessEntry)]
    kernel.Process32FirstW.restype = wintypes.BOOL
    kernel.Process32NextW.argtypes = [wintypes.HANDLE,ctypes.POINTER(ProcessEntry)]
    kernel.Process32NextW.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    snapshot = kernel.CreateToolhelp32Snapshot(2,0)
    if snapshot == ctypes.c_void_p(-1).value: raise ctypes.WinError(ctypes.get_last_error())
    found = []
    try:
        entry = ProcessEntry();entry.dwSize = ctypes.sizeof(entry)
        ok = kernel.Process32FirstW(snapshot,ctypes.byref(entry))
        if not ok:raise ctypes.WinError(ctypes.get_last_error())
        while ok:
            if entry.szExeFile.casefold()=='ms-teams.exe':
                found.append((entry.th32ProcessID,entry.th32ParentProcessID))
            ok = kernel.Process32NextW(snapshot,ctypes.byref(entry))
    finally:
        kernel.CloseHandle(snapshot)
    ids = {pid for pid,parent in found}
    roots = [pid for pid,parent in found if parent not in ids]
    if len(roots)!=1:
        raise RuntimeError(f'Expected one Teams host, found {roots}; open Teams or pass --pid explicitly')
    return roots[0]

class Bridge:
    def __init__(self, pid=None, open_copilot=False, force_open=False):
        self.session = frida.attach(pid or teams_pid())
        self.script = None
        try:
            manifest = json.loads((HERE / 'build.json').read_text())
            # Read module path before installing hooks; fail closed for another build.
            probe = self.session.create_script("rpc.exports.path=()=>Process.getModuleByName('EmbeddedBrowserWebView.dll').path")
            probe.load()
            module_path = probe.exports_sync.path()
            probe.unload()
            digest = hashlib.sha256(pathlib.Path(module_path).read_bytes()).hexdigest()
            if digest != manifest['moduleSha256']:
                raise RuntimeError('WebView2 build changed. Regenerate the symbol manifest before attaching native calls.')
            source = (HERE / 'agent.js').read_text().replace('__CONFIG__', json.dumps(manifest))
            self.script = self.session.create_script(source)
            self.script.load()
            self.rpc = self.script.exports_sync
            self.metadata = self.rpc.metadata()
            candidates = discover_frames(self.metadata['pid'],int(self.metadata['moduleBase'],16)+manifest['frameVtable'])
            self.frame = None
            self._select_frame(candidates)
            if open_copilot and (not self.frame or force_open):
                self._open_copilot(manifest)
                deadline=time.monotonic()+30
                while time.monotonic()<deadline:
                    candidates=discover_frames(self.metadata['pid'],int(self.metadata['moduleBase'],16)+manifest['frameVtable'])
                    self._select_frame(candidates)
                    if self.frame:break
                    time.sleep(.5)
            if not self.frame:
                raise RuntimeError('No accessible Copilot frame found; open Copilot Chat in Teams')
            self.metadata.update(frame=self.frame, discoveredFrames=len(candidates['frames']), skippedScanBytes=candidates['skippedBytes'],discoveryMethod=candidates['method'],failedReadBytes=candidates['failedReadBytes'])
        except Exception:
            self.close()
            raise

    def _select_frame(self,candidates):
        selected=[]
        for address in candidates['frames']:
            try:
                state=self.rpc.evaluate(address,STATE_JS)
                if isinstance(state,dict) and state.get('editorPresent') and 'copilot' in state.get('origin','').lower():selected.append(address)
            except frida.core.RPCException as exc:
                if self.rpc.pending():raise RuntimeError('A native callback is still pending; leave Teams running and investigate') from exc
        if len(selected)>1:raise RuntimeError('More than one Copilot frame is open; close the extra frame')
        self.frame=selected[0] if selected else None

    def _open_copilot(self,manifest):
        if 'coreVtable' not in manifest or 'coreExecute' not in manifest:
            raise RuntimeError('Manifest has no Teams shell WebView offsets; refresh the build manifest')
        candidates=discover_frames(self.metadata['pid'],int(self.metadata['moduleBase'],16)+manifest['coreVtable'])
        matches=[]
        probe=r'''(() => {
const nodes=Array.from(document.querySelectorAll('button[aria-label="Copilot"],[role="button"][aria-label="Copilot"]')).filter(e=>e.getClientRects().length && e.getAttribute('aria-disabled')!=='true' && !e.disabled);
return {origin:location.origin,count:nodes.length};})()'''
        for address in candidates['frames']:
            value=self.rpc.evaluate(address,probe,'core')
            if isinstance(value,dict) and value.get('origin')=='https://teams.microsoft.com' and value.get('count'):
                matches.append((address,value['count']))
        if len(matches)!=1 or matches[0][1]!=1:
            raise RuntimeError(f'Cannot uniquely locate the Teams Copilot navigation button: {matches}')
        opened=self.rpc.evaluate(matches[0][0],r'''(() => {
const nodes=Array.from(document.querySelectorAll('button[aria-label="Copilot"],[role="button"][aria-label="Copilot"]')).filter(e=>e.getClientRects().length && e.getAttribute('aria-disabled')!=='true' && !e.disabled);
if(location.origin!=='https://teams.microsoft.com' || nodes.length!==1)return {opened:false};
nodes[0].click();return {opened:true,method:'Teams shell DOM click; no OS input'};})()''','core')
        if not opened or not opened.get('opened'):raise RuntimeError('Copilot navigation changed before click')
        self.metadata['navigation']=opened

    def evaluate(self, expression):
        return self.rpc.evaluate(self.frame, expression)

    def state(self):
        try:return self.evaluate(STATE_JS)
        except frida.core.RPCException as error:
            if 'WebView object has changed; rediscover' not in str(error):raise
            manifest=json.loads((HERE/'build.json').read_text())
            candidates=discover_frames(self.metadata['pid'],int(self.metadata['moduleBase'],16)+manifest['frameVtable'])
            self._select_frame(candidates)
            if not self.frame:raise RuntimeError('Copilot frame was replaced; reconnect before sending another prompt') from error
            self.metadata['frame']=self.frame
            return self.evaluate(STATE_JS)  # Read only: never repeat a send or upload.

    def fill_draft(self, prompt, replace_expected=None):
        payload = {'prompt': prompt, 'expected': replace_expected or ''}
        return self.evaluate(r'''(() => {
const p=__PAYLOAD__;
const e=document.querySelector('[contenteditable="true"][aria-label="Message Copilot"]');
if(!e || (__DRAFT_TEXT__).trim()!==p.expected.trim())return {error:'Draft changed'};
const editor=e.__lexicalEditor;
if(!editor || typeof editor.parseEditorState!=='function')return {error:'Lexical API unavailable'};
const children=[];
p.prompt.split('\n').forEach((line,i)=>{
 if(i)children.push({type:'linebreak',version:1});
 if(line)children.push({detail:0,format:0,mode:'normal',style:'',text:line,type:'text',version:1});
});
const root={children:[{children,direction:null,format:'',indent:0,type:'paragraph',version:1}],direction:null,format:'',indent:0,type:'root',version:1};
editor.setEditorState(editor.parseEditorState(JSON.stringify({root})));
return {inserted:true,method:'Lexical.setEditorState'};
})()'''.replace('__PAYLOAD__', json.dumps(payload)).replace('__DRAFT_TEXT__',DRAFT_TEXT_JS))

    def attach_file(self, path, mime='text/plain'):
        path = pathlib.Path(path)
        data = path.read_bytes()
        if len(data) > 1024 * 1024:
            raise ValueError('PoC attachment bridge is limited to 1 MiB')
        payload = {'name': path.name, 'mime': mime, 'base64': base64.b64encode(data).decode('ascii')}
        return self.evaluate(r'''(() => {
const p=__PAYLOAD__, input=document.querySelector('input[type="file"]#upload-file-button');
if(!input || input.disabled)return {error:'Upload input unavailable'};
const attachments=Array.from(document.querySelectorAll('button[aria-label^="Remove attachment "]')).filter(e=>e.getClientRects().length);
if(attachments.length>=3)return {error:'Attachment limit reached (3 files)'};
if(attachments.some(e=>e.getAttribute('aria-label')==='Remove attachment '+p.name))return {error:'This filename is already attached'};
const data=Uint8Array.from(atob(p.base64),c=>c.charCodeAt(0));
const transfer=new DataTransfer();
transfer.items.add(new File([data],p.name,{type:p.mime}));
input.files=transfer.files;
input.dispatchEvent(new Event('change',{bubbles:true}));
return {dispatched:true,name:p.name,bytes:data.length};
})()'''.replace('__PAYLOAD__', json.dumps(payload)).replace('__DRAFT_TEXT__',DRAFT_TEXT_JS))

    def read_download(self, name, timeout=30):
        key='__frida_download_'+uuid.uuid4().hex
        payload=json.dumps({'name':name,'key':key})
        started=self.evaluate(r'''(() => {
const p=__PAYLOAD__;
const turn=Array.from(document.querySelectorAll('[data-testid="m365-chat-llm-web-ui-chat-message"]')).at(-1);
const link=Array.from(turn?.querySelectorAll('a')||[]).find(e=>e.download===p.name);
if(!link)return {error:'Named download link missing from latest turn'};
if(!/^(blob:|data:|https:)/.test(link.href))return {error:'Unsupported download URL scheme'};
window[p.key]={status:'pending'};
(async()=>{try{
 const response=await fetch(link.href);
 if(!response.ok)throw new Error('Download HTTP '+response.status);
 const blob=await response.blob();
 if(blob.size>1024*1024)throw new Error('PoC downloads are limited to 1 MiB');
 const bytes=new Uint8Array(await blob.arrayBuffer());
 let binary='';for(const value of bytes)binary+=String.fromCharCode(value);
 window[p.key]={status:'done',base64:btoa(binary),bytes:bytes.length,mime:blob.type};
}catch(error){window[p.key]={status:'error',error:String(error)};}})();
return {started:true};
})()'''.replace('__PAYLOAD__',payload))
        if not started or not started.get('started'):
            raise RuntimeError(f'Cannot read download: {started}')
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            result=self.evaluate('window['+json.dumps(key)+']')
            if result and result.get('status') in ('done','error'):
                self.evaluate('delete window['+json.dumps(key)+']')
                if result['status']=='error':raise RuntimeError(result['error'])
                return base64.b64decode(result['base64'],validate=True)
            time.sleep(.5)
        raise TimeoutError('Download fetch timed out')

    def ask(self, prompt, timeout=180, resume_draft=False):
        state = self.state()
        if state['generating']:
            raise RuntimeError('Copilot is already generating')
        matching_draft = resume_draft and state['draft'].strip() == prompt.strip()
        if state['draft'].strip() and not matching_draft:
            raise RuntimeError('Existing draft present; refusing to overwrite')
        canonical=lambda text: ''.join(text.split())
        if any(canonical(t['question']) == canonical(prompt) for t in state['turns']):
            raise RuntimeError('Identical prompt already exists; refusing an automatic duplicate')
        text = json.dumps(prompt)
        inserted = {'inserted': True} if matching_draft else self.fill_draft(prompt)
        if not inserted or not inserted.get('inserted'):
            raise RuntimeError(f'Could not fill editor: {inserted}')
        deadline = time.monotonic() + 12
        while time.monotonic() < deadline:
            if self.state()['draft'].strip() == prompt.strip():
                break
            time.sleep(.3)
        else:
            raise RuntimeError('Editor did not settle; prompt has not been sent')
        sent = self.evaluate((r'''(() => {
const e=document.querySelector('[contenteditable="true"][aria-label="Message Copilot"]');
const b=document.querySelector('button[aria-label="Send"]');
if((__DRAFT_TEXT__).trim()!==''' + text + '''.trim() || !b || b.disabled)return {error:'Draft changed or Send unavailable'};
b.click();return {sent:true};})()''').replace('__DRAFT_TEXT__',DRAFT_TEXT_JS))
        if not sent or not sent.get('sent'):
            raise RuntimeError(f'Could not send: {sent}')
        # Once submitted, never auto-retry the prompt on a timeout.
        deadline = time.monotonic() + timeout
        previous = None
        stable = 0
        while time.monotonic() < deadline:
            state = self.state()
            turn = next((t for t in reversed(state['turns']) if canonical(t['question']) == canonical(prompt)), None)
            if turn and turn['answer'] and turn['copyReady'] and not state['generating']:
                stable = stable + 1 if turn['answer'] == previous else 0
                previous = turn['answer']
                if stable >= 2:
                    return turn
            else:
                stable = 0
            time.sleep(1.5)
        raise TimeoutError('Prompt submitted, but response completion is unconfirmed. Inspect before retrying.')

    def close(self):
        if self.session is not None:
            try:
                if self.script is not None:
                    stable=0;deadline=time.monotonic()+2
                    while time.monotonic()<deadline:
                        pending=self.script.exports_sync.pending()
                        stable=stable+1 if not pending else 0
                        if stable>=3:break
                        time.sleep(.1)
                    if stable<3:raise RuntimeError('Native callback or COM reference pending: refusing to unload its code')
            except frida.InvalidOperationError:
                pass  # The target or script has already gone away.
            try:self.session.detach()
            except frida.InvalidOperationError:pass
            self.session = None

    def __enter__(self): return self
    def __exit__(self, *_): self.close()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--pid', type=int)
    parser.add_argument('--prompt-file', type=pathlib.Path)
    parser.add_argument('--eval-file', type=pathlib.Path)
    parser.add_argument('--upload-file', type=pathlib.Path)
    parser.add_argument('--download-name')
    parser.add_argument('--save-as', type=pathlib.Path)
    args = parser.parse_args()
    with Bridge(args.pid) as bridge:
        selected=sum(bool(v) for v in (args.prompt_file,args.eval_file,args.upload_file,args.download_name))
        if selected>1:parser.error('Choose only one operation per invocation')
        if args.download_name:
            if not args.save_as:parser.error('--download-name requires --save-as')
            if args.save_as.exists():raise FileExistsError(args.save_as)
            data=bridge.read_download(args.download_name)
            with args.save_as.open('xb') as target:target.write(data)
            result={'saved':str(args.save_as.resolve()),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
        elif args.upload_file:
            result=bridge.attach_file(args.upload_file)
        elif args.prompt_file:
            result = bridge.ask(args.prompt_file.read_text(encoding='utf-8-sig'))
        elif args.eval_file:
            result = bridge.evaluate(args.eval_file.read_text(encoding='utf-8-sig'))
        else:
            state = bridge.state()
            result = {'metadata':bridge.metadata, 'title':state['title'], 'editorPresent':state['editorPresent'], 'turnCount':len(state['turns'])}
        print(json.dumps(result, ensure_ascii=True, indent=2))

if __name__ == '__main__': main()
