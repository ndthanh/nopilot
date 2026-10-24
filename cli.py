"""CMD/Python CLI for Teams Copilot. No shell is launched by this module."""
from __future__ import annotations
import argparse
import datetime
import hashlib
import json
import mimetypes
import pathlib
import re
import shlex
import sys
import time
import uuid
from bridge import Bridge
from project_bundle import pack_project
from data_lock import default_directory

DOWNLOADS_JS = r'''(() => {
const turn=Array.from(document.querySelectorAll('[data-testid="m365-chat-llm-web-ui-chat-message"]')).at(-1);
return Array.from(turn?.querySelectorAll('a[download]')||[]).filter(e=>e.download).map(e=>({name:e.download,text:e.innerText,scheme:e.href.split(':')[0]}));
})()'''

class Harness:
    def __init__(self,pid=None,journal=None,ensure_open=True):
        self.pid=pid
        self.journal=pathlib.Path(journal) if journal else None
        self.bridge=None
        self.ensure_open=ensure_open
        self.artifacts_dir=None
        self.local_session_id=uuid.uuid4().hex

    def connect(self,force_open=False):
        self.close()
        self.bridge=Bridge(self.pid,open_copilot=self.ensure_open,force_open=force_open)
        return self.status()

    def close(self):
        if self.bridge:
            self.bridge.close()
            self.bridge=None

    def record(self,kind,**values):
        if self.journal:
            self.journal.parent.mkdir(parents=True,exist_ok=True)
            entry={'time':datetime.datetime.now(datetime.timezone.utc).isoformat(),'kind':kind,**values}
            with self.journal.open('a',encoding='utf-8') as out:
                out.write(json.dumps(entry,ensure_ascii=False)+'\n')
                out.flush()

    def status(self):
        state=self.bridge.state()
        return {'connected':True,**self.bridge.metadata,'title':state['title'],
                'editorPresent':state['editorPresent'],'generating':state['generating'],
                'hasDraft':bool(state['draft'].strip()),'visibleTurns':len(state['turns'])}

    def ask(self,prompt,timeout=300):
        if not prompt.strip():raise ValueError('Prompt is empty')
        request_id=uuid.uuid4().hex
        self.record('request-intent',requestId=request_id,prompt=prompt)
        try:
            turn=self.bridge.ask(prompt,timeout=timeout)
        except BaseException as error:
            self.record('needs-attention',requestId=request_id,error=str(error),automaticRetry=False)
            raise
        self.record('response',requestId=request_id,response=turn)
        return {'requestId':request_id,**turn}

    def read(self):
        turns=self.bridge.state()['turns']
        return turns[-1] if turns else {'answer':'','question':'','code':[]}

    def new_chat(self,timeout=30):
        state=self.bridge.state()
        if state['generating']:raise RuntimeError('Copilot is generating; wait before starting a new chat')
        if state['draft'].strip():raise RuntimeError('Existing draft present; refusing to discard it')
        pending=self.bridge.evaluate('!!document.querySelector(\'button[aria-label^="Remove attachment "]\')')
        if not pending and not state['turns'] and self.bridge.evaluate('location.pathname')=='/chat':
            self.local_session_id=uuid.uuid4().hex
            return {'newChat':True,'editorPresent':True,'visibleTurns':0,'previousChatDeleted':False,'alreadyEmpty':True}
        click_script=r'''(() => {
if(document.querySelector('button[aria-label^="Remove attachment "]'))return {error:'An unsent attachment is present'};
const visible=e=>!e.disabled && e.getAttribute('aria-disabled')!=='true';
let nodes=Array.from(document.querySelectorAll('button[data-testid="newChatButton"],button#new-chat-button')).filter(visible);
if(!nodes.length)nodes=Array.from(document.querySelectorAll('button[aria-label="New chat"],[role="button"][aria-label="New chat"]')).filter(visible);
if(nodes.length!==1)return {error:'New chat button is missing or ambiguous',matches:nodes.length};
nodes[0].click();return {clicked:true};})()'''
        clicked=self.bridge.evaluate(click_script)
        if clicked and clicked.get('matches')==0:
            self.bridge.evaluate('document.querySelector(\'button[data-testid="expand-button"]\')?.click();true')
            deadline=time.monotonic()+timeout
            while time.monotonic()<deadline:
                clicked=self.bridge.evaluate(click_script)
                if clicked and (clicked.get('clicked') or clicked.get('matches')!=0):break
                time.sleep(.5)
        if not clicked or not clicked.get('clicked'):raise RuntimeError(f'Cannot start a new chat: {clicked}')
        self.record('new-chat-clicked')
        deadline=time.monotonic()+timeout
        stable=0
        reconnected=False
        while time.monotonic()<deadline:
            try:state=self.bridge.state()
            except Exception:
                if reconnected:raise
                self.connect()  # Rediscover a replaced frame; never click New chat twice.
                reconnected=True
                continue
            ready=state['editorPresent'] and not state['turns'] and not state['draft'].strip() and not state['generating']
            stable=stable+1 if ready else 0
            if stable>=2:
                result={'newChat':True,'editorPresent':True,'visibleTurns':0,'previousChatDeleted':False}
                self.record('new-chat-ready',**result)
                self.local_session_id=uuid.uuid4().hex
                return result
            time.sleep(.4)
        raise TimeoutError('New chat was clicked, but an empty ready composer is unconfirmed; inspect Teams before retrying')

    def downloads(self):
        return self.bridge.evaluate(DOWNLOADS_JS)

    def restore_chat(self,conversation_id,timeout=30):
        if not re.fullmatch(r'[a-fA-F0-9-]{36}',conversation_id):raise ValueError('Invalid conversation ID')
        expected='/chat/conversation/'+conversation_id
        if self.bridge.evaluate('location.pathname')==expected:return
        state=self.bridge.state()
        pending=self.bridge.evaluate('!!document.querySelector(\'button[aria-label^="Remove attachment "]\')')
        if state['draft'].strip() or state['generating'] or pending:
            raise RuntimeError('Teams has an unsent draft, attachment or response; finish it before switching conversations')
        self.bridge.evaluate('document.querySelector(\'button[data-testid="expand-button"]\')?.click();true')
        deadline=time.monotonic()+timeout;clicked=False;stable=0
        while time.monotonic()<deadline:
            if not clicked:
                clicked=self.bridge.evaluate('(()=>{const e=document.getElementById('+json.dumps(conversation_id)+');if(e?.tagName!=="BUTTON"||e.disabled)return false;e.click();return true;})()')
            if clicked:
                route=self.bridge.evaluate('location.pathname')
                state=self.bridge.state()
                ready=route==expected and state['editorPresent'] and bool(state['turns']) and not state['generating']
                stable=stable+1 if ready else 0
                if stable>=3:return
            time.sleep(.5)
        raise RuntimeError('Could not restore the selected chat through Copilot history; open it in Teams and reconnect. No prompt was sent')

    def read_url(self,url,question=None,*,mode='auto',directory=None,timeout=300,on_stage=None):
        from url_context import feed_url
        if directory is None:
            route=self.bridge.evaluate('location.pathname')
            match=re.search(r'/chat/conversation/([a-fA-F0-9-]{36})',route or '')
            session_id=match.group(1) if match else self.local_session_id
            directory=(self.artifacts_dir or default_directory('work/nopilot-cli/conversations')/session_id/'artifacts')/'context'
        return feed_url(self,url,question,directory=directory,mode=mode,timeout=timeout,on_stage=on_stage)

    def browse(self,url,task,*,max_turns=20,directory=None,timeout=300,on_stage=None):
        from playwright_tool import run_browser_agent
        directory=directory or (self.artifacts_dir or default_directory('work/nopilot-cli/conversations')/self.local_session_id/'artifacts')/'browser'
        return run_browser_agent(self,url,task,directory=directory,max_turns=max_turns,timeout=timeout,on_stage=on_stage)

    def project(self,root,*,question=None,out_dir='work/project-bundles',exclude=(),timeout=300,on_stage=None):
        state=self.bridge.state()
        if state['generating'] or state['draft'].strip():raise RuntimeError('Composer must be idle with no draft before uploading a project')
        count=self.bridge.evaluate('Array.from(document.querySelectorAll(\'button[aria-label^="Remove attachment "]\')).filter(e=>e.getClientRects().length).length')
        if count>=3:raise RuntimeError('Copilot đã có3attachment chưa gửi; cần chừa1slot cho project. Không file nào được upload và không prompt nào được gửi.')
        if on_stage:on_stage('packing',{'source':str(pathlib.Path(root).resolve()),'existingAttachments':count})
        name='project-'+uuid.uuid4().hex[:10]+'.txt'
        packed=pack_project(root,pathlib.Path(out_dir)/name,question=question,exclude=exclude)
        self.record('project-packed',**packed)
        if on_stage:on_stage('packed',packed)
        if on_stage:on_stage('uploading',{'name':pathlib.Path(packed['bundle']).name,'bytes':packed['archiveBytes']})
        uploaded=self.upload(packed['bundle'])
        if on_stage:on_stage('uploaded',{'name':pathlib.Path(packed['bundle']).name})
        prompt=pathlib.Path(packed['promptFile']).read_text(encoding='utf-8')
        if on_stage:on_stage('asking',{'question':question})
        response=self.ask(prompt,timeout=timeout)
        if on_stage:on_stage('answered',{'requestId':response.get('requestId')})
        return {'project':packed,'upload':uploaded,'response':response,'answer':response['answer'],'answerMarkdown':response.get('answerMarkdown')}

    def upload(self,path,timeout=90):
        path=pathlib.Path(path)
        mime=mimetypes.guess_type(path.name)[0] or 'application/octet-stream'
        result=self.bridge.attach_file(path,mime=mime)
        if not result or not result.get('dispatched'):raise RuntimeError(f'Upload rejected: {result}')
        self.record('upload-dispatched',**result)
        ready={**result,**self.wait_upload(path.name,timeout)}
        self.record('upload-finished',**ready)
        return ready

    def wait_upload(self,name,timeout=90):
        deadline=time.monotonic()+timeout
        stable=0
        while time.monotonic()<deadline:
            ui=self.bridge.evaluate(r'''(() => {
const name=__NAME__;
const node=document.querySelector('#chat-input-wrapper')||document.querySelector('[data-testid="bizchat-input-section"]');
const card=Array.from(document.querySelectorAll('div[aria-label]')).find(e=>e.getAttribute('aria-label')===name && e.querySelector('button[aria-label]')?.getAttribute('aria-label')==='Remove attachment '+name);
const image=card?.querySelector('img');
const imageReady=/\.(png|jpe?g|webp|gif|bmp)$/i.test(name)&&!!card?.id&&!!image?.complete&&image.naturalWidth>0&&image.naturalHeight>0&&/^(data:image\/|blob:)/.test(image.currentSrc||image.src)&&!card.querySelector('button[aria-label]')?.disabled;
return {text:node?.innerText||card?.innerText||'',cardPresent:!!card,cloudIdAssigned:!!card?.id.startsWith('SPO_'),imageReady,busy:!!(node||card)?.querySelector('[role="progressbar"],[aria-busy="true"]'),alerts:Array.from(document.querySelectorAll('[role="alert"]')).map(e=>e.innerText)};
})()'''.replace('__NAME__',json.dumps(name)))
            text=ui['text']
            if name in text and ('upload failed' in text.lower() or 'upload error' in text.lower()):
                raise RuntimeError('Teams reported an upload error')
            explicit='upload finished' in text.lower()
            image_ready=ui.get('imageReady',False)
            complete=not ui['busy'] and ((name in text and (explicit or (ui['cardPresent'] and ui['cloudIdAssigned']))) or image_ready)
            stable=stable+1 if complete else 0
            if stable>=(8 if image_ready else 3):
                return {'composerReportsFinished':explicit,'completionSignal':'upload finished text' if explicit else 'decoded image attachment preview ready (heuristic)' if image_ready else 'cloud-backed attachment card ready','alerts':ui['alerts']}
            time.sleep(.75)
        raise TimeoutError('File was dispatched, but upload completion is unconfirmed; inspect Teams before retrying')

    def download(self,name,target):
        target=pathlib.Path(target)
        if target.exists():raise FileExistsError(f'Refusing to overwrite {target}')
        if not target.parent.exists():raise FileNotFoundError(f'Destination directory does not exist: {target.parent}')
        data=self.bridge.read_download(name)
        with target.open('xb') as out:out.write(data)
        result={'name':name,'saved':str(target.resolve()),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
        self.record('download',**result)
        return result

def emit(value,json_mode=False):
    if json_mode or not isinstance(value,dict) or 'answer' not in value:
        print(json.dumps(value,ensure_ascii=False,indent=2),flush=True)
    else:
        print(value['answer'],flush=True)

def words(line):
    # posix=False preserves backslashes in Windows paths; strip enclosing quotes.
    return [part[1:-1] if len(part)>1 and part[0]==part[-1] and part[0] in "\"'" else part
            for part in shlex.split(line,posix=False)]

HELP = '''Enter a prompt and press Enter to send it.
/help                         Show commands
/status                       Show connection and composer state
/read                         Read the latest response without sending
/new                          Start a new Copilot chat; keep the previous chat
/multiline                    Enter lines; finish with a line containing /send
/file "prompt.txt"            Send a UTF-8 prompt file
/upload "local-log.txt"       Attach file and wait for upload finished
/project "project-dir" task   Apply .nopilotignore, pack ZIP as .txt, keep uploaded logs, ask Copilot
/develop task              Request a Python project ZIP with nopilot.json for reviewed local tasks
/url URL question             Read HTML as Markdown; feed inline or upload context file
/browse URL task              Copilot + local Playwright tool, max 20 model turns
/downloads                    List download names in the latest response
/download "name.zip" "out.zip" Save file, without overwriting
/reconnect                    Rediscover Teams PID/thread/frame; never resend
/open                         Switch Teams to Copilot and reconnect
/quit                         Disconnect and exit
Ctrl+C at the prompt cancels input; after a send, use /read to inspect before retrying.
'''

def chat(harness,timeout):
    print('nopilot · Connected to Teams Copilot. /help for commands.',flush=True)
    while True:
        try:
            line=input('nopilot> ').strip()
            if not line:continue
            if line in ('/quit','/exit'):return
            if line=='/help':print(HELP);continue
            if line=='/status':emit(harness.status());continue
            if line=='/reconnect':emit(harness.connect());continue
            if line=='/open':emit(harness.connect(force_open=True));continue
            if line=='/read':emit(harness.read());continue
            if line=='/new':emit(harness.new_chat());continue
            if line=='/downloads':emit(harness.downloads());continue
            if line.startswith('/develop '):
                from project_contract import development_prompt
                emit(harness.ask(development_prompt(line[len('/develop '):].strip()),timeout));continue
            if line.startswith(('/url ','/readurl ')):
                parts=line.split(maxsplit=2)
                emit(harness.read_url(parts[1],parts[2] if len(parts)>2 else None,timeout=timeout));continue
            if line.startswith('/browse '):
                parts=line.split(maxsplit=2)
                emit(harness.browse(parts[1],parts[2] if len(parts)>2 else 'Explore this website and describe possible automation.',timeout=timeout));continue
            if line=='/multiline':
                print('Multiline mode: Enter adds a line; nothing is sent yet.\nType /send on its own line to submit, or /cancel to discard.\nThe ... prefix is printed by the CLI; do not type it yourself.')
                lines=[]
                while True:
                    part=input('... ')
                    if part=='/send':break
                    if part=='/cancel':lines=[];break
                    lines.append(part)
                if lines:emit(harness.ask('\n'.join(lines),timeout))
                continue
            if line.startswith('/'):
                args=words(line)
                if args[0]=='/file' and len(args)==2:
                    emit(harness.ask(pathlib.Path(args[1]).read_text(encoding='utf-8-sig'),timeout))
                elif args[0]=='/upload' and len(args)==2:emit(harness.upload(args[1]))
                elif args[0]=='/project':
                    from project_bundle import parse_project_command
                    root,question,exclude=parse_project_command(line)
                    emit(harness.project(root,question=question,exclude=exclude,timeout=timeout,on_stage=lambda stage,data:print('[project] '+stage+' '+json.dumps(data,ensure_ascii=False),flush=True)))
                elif args[0]=='/download' and len(args)==3:emit(harness.download(args[1],args[2]))
                else:print('Unknown command or arguments. Use /help.',file=sys.stderr)
                continue
            emit(harness.ask(line,timeout))
        except EOFError:return
        except KeyboardInterrupt:
            print('\nInterrupted. A submitted prompt is not cancelled or resent. Use /read or /reconnect.',file=sys.stderr)
        except Exception as error:
            print(f'Error: {error}\nUse /status or /reconnect; a submitted prompt is never automatically resent.',file=sys.stderr)

def parser():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--pid',type=int,help='Override automatic Teams host discovery')
    p.add_argument('--json',action='store_true',help='Machine-readable JSON on stdout')
    p.add_argument('--journal',type=pathlib.Path,help='Append requests/responses to a UTF-8 JSONL file (opt-in)')
    commands=p.add_subparsers(dest='command')
    dev=commands.add_parser('dev',help='Inspect/extract projects, checkpoint/diff, human-reviewed install/run',add_help=False);dev.add_argument('options',nargs=argparse.REMAINDER)
    workflow=commands.add_parser('workflow',help='Persistent browser/dev explorer with human turn grants',add_help=False);workflow.add_argument('options',nargs=argparse.REMAINDER)
    commands.add_parser('status',help='Locate Copilot and show state; sends nothing')
    commands.add_parser('open',help='Open Copilot from the Teams navigation if necessary')
    commands.add_parser('read',help='Read the latest response; sends nothing')
    commands.add_parser('new',help='Start a new Copilot chat without deleting the previous chat')
    commands.add_parser('downloads',help='List files in the latest response')
    c=commands.add_parser('chat',help='Interactive terminal session (default)')
    c.add_argument('--timeout',type=float,default=300)
    a=commands.add_parser('ask',help='Send one prompt and wait for its response')
    source=a.add_mutually_exclusive_group(required=True)
    source.add_argument('-p','--prompt')
    source.add_argument('-f','--file',help='UTF-8 file, or - to read UTF-8 from stdin')
    a.add_argument('--timeout',type=float,default=300)
    a.add_argument('-o','--output',type=pathlib.Path,help='Save JSON result to a new file')
    u=commands.add_parser('upload',help='Upload a local file and wait for the composer')
    u.add_argument('path',type=pathlib.Path);u.add_argument('--timeout',type=float,default=90)
    d=commands.add_parser('download',help='Fetch named file from the latest response')
    d.add_argument('name');d.add_argument('destination',type=pathlib.Path)
    bundle=commands.add_parser('pack',help='Offline: package source as ZIP bytes in one .txt file')
    bundle.add_argument('directory',type=pathlib.Path)
    bundle.add_argument('-o','--output',type=pathlib.Path,required=True)
    bundle.add_argument('--exclude',action='append',default=[],metavar='GLOB')
    send=commands.add_parser('project',help='Package a project, upload one attachment, explain its ZIP format and ask Copilot')
    send.add_argument('directory',type=pathlib.Path)
    send.add_argument('--out-dir',type=pathlib.Path,default=pathlib.Path('work/project-bundles'))
    send.add_argument('--exclude',action='append',default=[],metavar='GLOB')
    send.add_argument('--timeout',type=float,default=300)
    for sub in (bundle,send):
        query=sub.add_mutually_exclusive_group()
        query.add_argument('-q','--question')
        query.add_argument('--question-file',type=pathlib.Path)
    read=commands.add_parser('url',help='Read public HTML as Markdown and feed it to Copilot')
    read.add_argument('url');read.add_argument('-q','--question')
    read.add_argument('--context-mode',choices=['auto','inline','file'],default='auto')
    read.add_argument('--out-dir',type=pathlib.Path)
    read.add_argument('--local-only',action='store_true',help='Fetch and save Markdown without attaching to Teams')
    read.add_argument('--timeout',type=float,default=300)
    browser=commands.add_parser('browse',help='Copilot uses the local stateful Python Playwright tool')
    browser.add_argument('url');browser.add_argument('-q','--question',required=True)
    browser.add_argument('--max-turns',type=int,default=20);browser.add_argument('--out-dir',type=pathlib.Path)
    browser.add_argument('--timeout',type=float,default=300)
    return p

def main(argv=None):
    # UTF-8 for CMD, redirected stdin/stdout, Vietnamese prompts and JSON logs.
    for stream in (sys.stdin,sys.stdout,sys.stderr):
        if hasattr(stream,'reconfigure'):stream.reconfigure(encoding='utf-8',errors='strict')
    raw=list(sys.argv[1:] if argv is None else argv)
    if raw and raw[0] in ('dev','workflow'):
        from workflow_cli import dev_main,explorer_main
        try:return (dev_main if raw[0]=='dev' else explorer_main)(raw[1:])
        except KeyboardInterrupt:return 130
        except Exception as error:print('Error: '+str(error),file=sys.stderr);return 1
    p=parser();args=p.parse_args(argv)
    command=args.command or 'chat'
    if args.json and command=='chat':p.error('--json is for one-shot commands; choose status/ask/read/upload/download/downloads')
    if command=='ask' and args.output and args.output.exists():p.error('Output file already exists')
    harness=Harness(args.pid,args.journal,ensure_open=command!='status')
    try:
        if command in ('dev','workflow'):
            from workflow_cli import dev_main,explorer_main
            return (dev_main if command=='dev' else explorer_main)(args.options)
        if command in ('pack','project'):
            question=args.question_file.read_text(encoding='utf-8-sig') if args.question_file else args.question
        if command=='pack':
            emit(pack_project(args.directory,args.output,question=question,exclude=args.exclude),args.json)
            return 0
        if command=='url' and args.local_only:
            from url_context import fetch_markdown,save_context
            context=fetch_markdown(args.url)
            path,meta=save_context(context,args.out_dir or default_directory('work/nopilot-url-context'))
            emit({**{k:v for k,v in context.items() if k!='markdown'},'markdownFile':str(path),'metadataFile':str(meta)},args.json)
            return 0
        status=harness.connect(force_open=command in ('open','chat'))
        if command=='chat':chat(harness,getattr(args,'timeout',300));return 0
        if command in ('status','open'):result=status
        elif command=='read':result=harness.read()
        elif command=='new':result=harness.new_chat()
        elif command=='downloads':result=harness.downloads()
        elif command=='upload':result=harness.upload(args.path,args.timeout)
        elif command=='download':result=harness.download(args.name,args.destination)
        elif command=='project':result=harness.project(args.directory,question=question,out_dir=args.out_dir,exclude=args.exclude,timeout=args.timeout)
        elif command=='url':result=harness.read_url(args.url,args.question,mode=args.context_mode,directory=args.out_dir,timeout=args.timeout)
        elif command=='browse':result=harness.browse(args.url,args.question,max_turns=args.max_turns,directory=args.out_dir,timeout=args.timeout)
        elif command=='ask':
            prompt=args.prompt if args.prompt is not None else (sys.stdin.read() if args.file=='-' else pathlib.Path(args.file).read_text(encoding='utf-8-sig'))
            result=harness.ask(prompt,args.timeout)
            if args.output:
                with args.output.open('x',encoding='utf-8') as out:json.dump(result,out,ensure_ascii=False,indent=2)
        emit(result,args.json)
        return 0
    except KeyboardInterrupt:
        print('Interrupted. A submitted prompt may still complete; inspect with read before retrying.',file=sys.stderr)
        return 130
    except Exception as error:
        print(f'Error: {error}',file=sys.stderr)
        return 1
    finally:
        harness.close()

if __name__=='__main__':raise SystemExit(main())
