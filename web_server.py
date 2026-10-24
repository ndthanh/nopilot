"""nopilot local web UI: one serialized Teams worker, conversation-scoped artifacts."""
from __future__ import annotations
import argparse
import concurrent.futures
import datetime
import hashlib
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
import mimetypes
import os
import pathlib
import re
import secrets
import shutil
import subprocess
import sys
import threading
import time
import urllib.parse
import uuid
import zipfile
from cli import Harness,words
from project_bundle import parse_project_command
from project_contract import read_contract,propose_task,development_prompt
from environment_cache import state as environment_state
import project_git
from chat_launch import ChatLaunches
from workspace_import import WorkspaceImports
from data_lock import default_directory
from dev_workspace import Workspace,inspect_zip
from execution import Runner
from explorer import Explorers

HERE=pathlib.Path(__file__).resolve().parent
BUILD_ID=hashlib.sha256(b''.join(p.read_bytes() for p in sorted([*HERE.glob('*.py'),*(HERE/'web').glob('*')]) if p.is_file())).hexdigest()[:12]
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def atomic_json(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix('.tmp');temp.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8');temp.replace(path)

class Application:
    def __init__(self,root,pid=None):
        self.root=pathlib.Path(root).resolve();self.root.mkdir(parents=True,exist_ok=True)
        self.lock=threading.RLock();self.conversations={};self.jobs={};self.harness=None
        self.pid=pid;self.native_active=None;self.connection='disconnected'
        self.workspaces={};self.runners={}
        self.executor=concurrent.futures.ThreadPoolExecutor(max_workers=1,thread_name_prefix='nopilot-teams')
        for path in self.root.glob('conversations/*/conversation.json'):
            try:
                item=json.loads(path.read_text(encoding='utf-8'));self.conversations[item['id']]=item
            except (ValueError,OSError,KeyError):continue
        if not self.conversations:self.create('Phiên hiện tại',adopt=True)
        available=[c for c in self.conversations.values() if not c.get('deletedAt')]
        if not available:available=[self.create()]
        self.initial_id=max(available,key=lambda c:c['updatedAt'])['id']
        self.explorers=Explorers(self)
        self.launches=ChatLaunches(self)
        self.imports=WorkspaceImports(self)

    def workspace(self,cid):
        self.directory(cid)
        with self.lock:
            if cid not in self.workspaces:self.workspaces[cid]=Workspace(self.directory(cid)/'dev')
            return self.workspaces[cid]

    def current_project_source(self,cid):
        workspace=self.workspace(cid)
        with workspace.lock:
            pid=self.conversations[cid].get('activeProjectId')
            if not pid:
                candidates=[p for p in workspace.list() if not p.get('launchStaged')]
                if len(candidates)!=1:raise ValueError('Conversation chưa có project hiện tại duy nhất. Chạy/áp dụng project trên card trước hoặc dùng /project "đường dẫn tuyệt đối".')
                pid=candidates[0]['id']
            if pid not in workspace.projects or workspace.projects[pid].get('launchStaged'):
                raise ValueError('Project hiện tại không còn khả dụng. Chọn project trên card hoặc dùng đường dẫn tuyệt đối.')
            source=workspace.source(pid)
            if not source.is_dir():raise ValueError('Thư mục source của project hiện tại không còn tồn tại.')
            return source

    def runner(self,cid):
        with self.lock:
            if cid not in self.runners:self.runners[cid]=Runner(self.workspace(cid),self.directory(cid)/'artifacts'/'runs',lambda result:self.run_finished(cid,result))
            return self.runners[cid]

    def run_finished(self,cid,result):
        self.register_files(cid,self.directory(cid)/'artifacts'/'runs'/result['id'],recursive=False)
        outputs=self.directory(cid)/'artifacts'/'runs'/result['id']/'outputs'
        if outputs.exists():self.register_files(cid,outputs)
        log_cards=[a for a in self.conversations[cid]['artifacts'] if a['relative']==f'runs/{result["id"]}/combined.log']
        explorer_run=any(t['conversationId']==cid and t.get('approvalId')==result['approvalId'] for t in self.explorers.tasks.values())
        log_note='Log sẽ được trả về explorer theo phiếu duyệt.' if explorer_run else 'Log chưa được tự gửi lên Copilot.'
        self.message(cid,'system',f'Run {result["id"][:8]} · {result.get("contractTask","run")}: {result["status"]}; exit code {result["exitCode"]}. Mở Dev workspace để xem log. '+log_note,artifacts=log_cards)
        log=self.runner(cid).log(result['id'])
        # Return a bounded log tail to this explorer only, never arbitrary host files.
        self.explorers.run_result(cid,result['approvalId'],{'run':result,'logTail':log['text'],'ok':result['status']=='succeeded'})

    def register_files(self,cid,folder,recursive=True):
        folder=pathlib.Path(folder);paths=folder.rglob('*') if recursive else folder.glob('*')
        cards=[]
        for path in paths:
            if not path.is_file() or path.name in ('state.json','checkpoint-state.json'):continue
            relative=path.resolve().relative_to((self.directory(cid)/'artifacts').resolve()).as_posix();sha=hashlib.sha256(path.read_bytes()).hexdigest()
            with self.lock:existing=next((a for a in self.conversations[cid]['artifacts'] if a['relative']==relative),None)
            if existing:
                if existing['sha256']!=sha:
                    with self.lock:existing.update(sha256=sha,bytes=path.stat().st_size,at=now());self.save(cid)
                cards.append(existing)
            else:cards.append(self.artifact(cid,path,'project' if path.suffix.lower()=='.zip' else 'output' if '/outputs/' in relative else 'log' if path.suffix=='.log' else 'browser'))
        return cards

    def dev_state(self,cid):
        workspace=self.workspace(cid);runner=self.runner(cid)
        with workspace.lock:approvals=[{**a,'returnsLogToCopilot':any(t['conversationId']==cid and t.get('approvalId')==a['id'] and t['status']=='awaiting_approval' for t in self.explorers.tasks.values())} for a in sorted(workspace.approvals.values(),key=lambda a:a.get('createdAt',''))[-30:]]
        with runner.lock:runs=sorted([runner.describe(rid) for rid in runner.runs],key=lambda r:r.get('createdAt',''))[-30:]
        projects=workspace.list()
        for project in projects:
            project['contract']=read_contract(workspace.source(project['id']))
            project['environment']=environment_state(workspace,project['id'])
            # Git subprocesses are requested explicitly, never on the polling path.
            project['gitInitialized']=(workspace.folder(project['id'])/'git-worktree/.git').is_dir()
        return {'projects':projects,'approvals':approvals,'runs':runs,'explorers':self.explorers.list(cid)}

    def dev_action(self,cid,action,data):
        workspace=self.workspace(cid);pid=data.get('projectId')
        if action=='workspace-confirm':return self.imports.confirm(cid,data['planId'])
        if action=='workspace-reject':return self.imports.reject(cid,data['planId'])
        if action=='workspace-select':return self.imports.select(cid,data['planId'])
        if action=='select-project':
            workspace.folder(pid);workspace.idle(pid)
            if workspace.projects[pid].get('launchStaged'):raise ValueError('Duyệt project trước khi chọn làm workspace')
            if any(j['conversationId']==cid and j['state'] in ('queued','running') for j in self.jobs.values()):raise ValueError('Đợi lượt chat hiện tại hoàn tất trước khi đổi project')
            with self.lock:self.conversations[cid]['activeProjectId']=pid;self.save(cid)
            return {'projectId':pid,'sourceDirectory':str(workspace.source(pid))}
        if action=='launch-plan':return self.launches.prepare(cid,data['artifactId'],data.get('targetProjectId'),data.get('fresh') is True)
        if action=='launch-confirm':return self.launches.confirm(cid,data['launchId'],data.get('message'))
        if action=='launch-stop':return self.launches.stop(cid,data['launchId'])
        if action=='launch-check':return self.launches.check_plan(cid,pid)
        if action=='launch-rerun':return self.launches.check_plan(cid,pid,'start')
        if action=='inspect':
            path,_=self.artifact_file(cid,data['artifactId']);return inspect_zip(path)
        if action=='extract':
            path,_=self.artifact_file(cid,data['artifactId']);result=workspace.extract(path,data.get('zipSha256'))
            contract=read_contract(workspace.source(result['id']))
            self.message(cid,'system',f'Dev · Đã giải nén {path.name} vào source: {result["sourceDirectory"]}. Contract: {contract["status"]}. Chưa cài/chạy mã. Mở Dev → Luồng chạy dự án để duyệt từng bước.')
            return result
        if action=='create':return workspace.create(data['name'],data['files'])
        if action=='read':return workspace.read(pid,data['path'])
        if action=='patch':
            result=workspace.patch(pid,data['revision'],data['files']);self.project_changed(cid,pid);return result
        if action=='checkpoint':return workspace.checkpoint(pid,data.get('label','Manual checkpoint'))
        if action=='diff':return workspace.diff(pid,data['checkpoint'])
        if action=='rollback':
            result=workspace.rollback(pid,data['checkpoint']);self.project_changed(cid,pid);return result
        if action=='propose':
            arguments=data.get('arguments',[])
            if isinstance(arguments,str):arguments=words('arguments '+arguments)[1:]
            return workspace.propose(pid,kind=data.get('kind','run'),entrypoint=data['entrypoint'],arguments=arguments,timeout=data.get('timeout',120),revision=data.get('revision'),execution_mode=data.get('executionMode','host'))
        if action=='contract-propose':
            result=propose_task(workspace,pid,data.get('task'),data.get('revision'))
            self.message(cid,'system',f'Dev · Chờ duyệt {result["contractTask"]} cho {workspace.projects[pid]["name"]}; revision {result["revision"][:12]}. Lệnh và cwd nằm trong phiếu duyệt ở Dev. Chưa chạy mã.')
            return result
        if action=='git-status':return {**project_git.status(workspace,pid),'suggestedMessage':project_git.suggested(workspace.source(pid))}
        if action=='git-commit':
            with workspace.lock:
                workspace.idle(pid)
                if workspace.current(pid)['revision']!=data.get('revision'):raise ValueError('Source changed; review again')
                result=project_git.commit(workspace,pid,data.get('message'))
            self.message(cid,'system','Git · Đã commit local: '+result.get('head','')+'\n'+data['message'])
            return result
        if action=='update-preview':
            path,_=self.artifact_file(cid,data['artifactId'])
            result=project_git.preview(workspace,pid,path,data.get('zipSha256'))
            self.message(cid,'system',f'Dev · Đã chuẩn bị diff ZIP cho {workspace.projects[pid]["name"]}: {len(result["changes"])} file thay đổi; source chưa được áp dụng.')
            return result
        if action=='update-apply':
            result=project_git.apply(workspace,pid,data.get('reviewId'),data.get('revision'),data.get('message'))
            self.project_changed(cid,pid)
            env=environment_state(workspace,pid)
            self.message(cid,'system',f'Dev · Đã áp dụng ZIP vào project hiện tại, giữ venv. Git commit {result["git"].get("head","")}. {env["reason"]}\nCommit message: '+data['message'])
            return {**result,'environment':env}
        if action=='approve':
            try:result=self.runner(cid).start(data['approvalId'])
            except ValueError:
                approval=workspace.approvals.get(data['approvalId'])
                if approval and approval['status'] in ('stale','expired'):self.explorers.run_result(cid,approval['id'],{'ok':False,'approvalStatus':approval['status'],'note':'Human approval attempt was rejected; no command ran. Request a fresh review.'})
                raise
            for item in self.explorers.tasks.values():
                if item['conversationId']==cid and item.get('approvalId')==data['approvalId']:item['runId']=result['id'];self.explorers.save(item)
            self.message(cid,'system',f'Dev · Đã duyệt một lần; bắt đầu {result.get("contractTask","run")} · run {result["id"][:8]}. Xem stdout/stderr trong Dev.')
            return result
        if action=='reject':
            approval=workspace.reject(data['approvalId']);self.explorers.run_result(cid,approval['id'],{'ok':False,'denied':True,'message':'Human rejected the request; no process was started'});return approval
        if action=='stop':return self.runner(cid).stop(data['runId'])
        if action=='open-folder':
            os.startfile(str(workspace.source(pid)));return {'opened':True}
        if action=='open-run-folder':
            run=self.runner(cid).runs[data['runId']];path=pathlib.Path(run['cwd'])
            expected=workspace.folder(run['projectId'])/'approved-sources'/run['approvalId']
            if path!=expected or not path.is_dir():raise ValueError('Execution snapshot folder is unavailable')
            os.startfile(str(path));return {'opened':True}
        if action=='export':
            workspace.idle(pid);current=workspace.current(pid);folder=self.directory(cid)/'artifacts'/'dev-exports';folder.mkdir(parents=True,exist_ok=True);path=folder/('project-'+pid[:8]+'-'+uuid.uuid4().hex[:8]+'.zip')
            with zipfile.ZipFile(path,'x',zipfile.ZIP_DEFLATED) as archive:
                for file in current['files']:archive.write(workspace.source(pid)/file['path'],file['path'])
            return self.artifact(cid,path,'project')
        raise ValueError('Unknown dev action')

    def project_changed(self,cid,pid):
        workspace=self.workspace(cid);revision=workspace.current(pid)['revision'];invalid=[]
        with workspace.lock:
            for approval in workspace.approvals.values():
                if approval['projectId']==pid and approval['status']=='pending' and approval['revision']!=revision:
                    approval['status']='stale';workspace.save_approval(approval['id']);invalid.append(approval['id'])
        for aid in invalid:self.explorers.run_result(cid,aid,{'ok':False,'approvalStatus':'stale','note':'User edited/rolled back the project; previous approval is invalid. Read the new revision before proposing again.'})

    def shutdown(self):
        self.launches.close()
        for item in self.explorers.tasks.values():item['pauseRequested']=True
        for runner in self.runners.values():runner.close()
        self.executor.submit(self.explorers.close_all).result(timeout=360)
        self.executor.shutdown(wait=True)
        if self.harness:self.harness.close()

    def directory(self,cid):
        if not re.fullmatch(r'[a-f0-9]{32}',cid) or cid not in self.conversations:raise KeyError('Conversation not found')
        return self.root/'conversations'/cid

    def save(self,cid):
        with self.lock:
            item=self.conversations[cid];item['updatedAt']=now()
            atomic_json(self.directory(cid)/'conversation.json',item)

    def create(self,title='Cuộc trò chuyện mới',adopt=False):
        cid=uuid.uuid4().hex
        item={'id':cid,'title':title,'createdAt':now(),'updatedAt':now(),'serviceId':None,
              'adoptCurrent':adopt,'messages':[],'artifacts':[]}
        with self.lock:self.conversations[cid]=item;self.save(cid)
        return item

    def message(self,cid,role,text,**values):
        with self.lock:
            value={'id':uuid.uuid4().hex,'role':role,'text':text,'at':now(),**values}
            self.conversations[cid]['messages'].append(value);self.save(cid)
            return value

    def artifact(self,cid,path,kind):
        path=pathlib.Path(path).resolve();base=(self.directory(cid)/'artifacts').resolve()
        if not path.is_relative_to(base) or not path.is_file():raise ValueError('Artifact must be a file in this conversation')
        data=path.read_bytes()
        item={'id':uuid.uuid4().hex,'name':path.name,'relative':path.relative_to(base).as_posix(),
              'kind':kind,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'at':now()}
        with self.lock:self.conversations[cid]['artifacts'].append(item);self.save(cid)
        return item

    def artifact_file(self,cid,aid):
        with self.lock:item=next((a for a in self.conversations[cid]['artifacts'] if a['id']==aid),None)
        if not item:raise KeyError('Artifact not found')
        base=(self.directory(cid)/'artifacts').resolve();path=(base/item['relative']).resolve()
        if not path.is_relative_to(base) or not path.is_file():raise ValueError('Artifact is unavailable')
        return path,item

    def capture_route(self,cid):
        path=self.harness.bridge.evaluate('location.pathname')
        match=re.search(r'/chat/conversation/([a-fA-F0-9-]{36})',path or '')
        if match:self.conversations[cid]['serviceId']=match.group(1);self.save(cid)

    def ensure(self,cid,new=False):
        if not self.harness or not self.harness.bridge:
            self.harness=Harness(self.pid)
            self.harness.connect();self.connection='connected'
        self.harness.journal=self.directory(cid)/'journal.jsonl'
        self.harness.artifacts_dir=self.directory(cid)/'artifacts'
        if new:
            self.harness.new_chat();self.native_active=cid;self.conversations[cid]['adoptCurrent']=False;self.save(cid)
            return
        if self.native_active==cid:return
        item=self.conversations[cid]
        if item.get('adoptCurrent'):
            self.native_active=cid;item['adoptCurrent']=False;self.capture_route(cid);return
        target=item.get('serviceId')
        if target:
            self.harness.restore_chat(target)
        else:self.harness.new_chat()
        self.native_active=cid

    def submit(self,cid,text,mode='chat'):
        if self.conversations[cid].get('deletedAt'):raise ValueError('Conversation has been removed locally')
        if mode not in ('chat','url','browser'):raise ValueError('Invalid chat mode')
        if not isinstance(text,str) or not text.strip() or len(text)>32000:raise ValueError('Message must contain 1..32000 characters')
        self.message(cid,'user',text)
        if (not text.startswith('/') or text.startswith('/develop ')) and self.conversations[cid]['title'] in ('Phiên hiện tại','Cuộc trò chuyện mới'):
            title=text[len('/develop '):] if text.startswith('/develop ') else text
            self.conversations[cid]['title']=title.splitlines()[0][:52];self.save(cid)
        return self.queue(cid,'send',text=text,mode=mode)

    def queue(self,cid,kind,**values):
        self.directory(cid)
        job={'id':uuid.uuid4().hex,'conversationId':cid,'kind':kind,'state':'queued','stage':'Đang chờ','createdAt':now()}
        with self.lock:self.jobs[job['id']]=job
        self.executor.submit(self.run_job,job,values)
        return job

    def stage(self,job,text):
        with self.lock:job['stage']=text

    def finish_explorer(self,cid,item):
        cards=self.register_files(cid,self.explorers.directory(item))
        # Detailed traces stay in Artifacts; avoid a second assistant answer
        # containing every internal file after the model's actual conclusion.
        cards=[c for c in cards if c['name'].lower().endswith(('.zip','.png','.verification.json')) or c['name'].startswith('ocr-')]
        cards.sort(key=lambda c:c['at'],reverse=True)
        cards.sort(key=lambda c:0 if c['name'].endswith('.zip') else 1 if c['name'].endswith('.verification.json') else 2 if c['name'].startswith('ocr-') else 3)
        cards=cards[:6]
        if item['status']=='completed' and item.get('answer'):
            with self.lock:
                message=next((m for m in reversed(self.conversations[cid]['messages']) if m['role']=='assistant' and m['text']==item['answer']),None)
                if message:message['artifacts']=cards;self.save(cid);return
        if item['status'] not in ('closed','waiting_turns'):
            reason=item.get('progress',{}).get('reason') or item.get('error','')
            self.message(cid,'system','Explorer: '+item['status']+'. '+reason+' Mở Dev workspace để xem tiến độ và thao tác tiếp.')

    def download_all(self,cid):
        cards=[];seen_names=set();seen_hashes=set()
        for link in (self.harness.downloads() or [])[:5]:
            if link['name'] in seen_names:continue
            seen_names.add(link['name'])
            name=pathlib.PureWindowsPath(link['name']).name
            name=re.sub(r'[<>:"/\\|?*\x00-\x1f]','_',name).strip('. ') or 'download.bin'
            folder=self.directory(cid)/'artifacts'/'downloads';folder.mkdir(parents=True,exist_ok=True)
            target=folder/name;index=2
            while target.exists():target=folder/(pathlib.Path(name).stem+f'-{index}'+pathlib.Path(name).suffix);index+=1
            try:
                self.harness.download(link['name'],target)
                digest=hashlib.sha256(target.read_bytes()).hexdigest()
                if digest in seen_hashes:
                    target.unlink();continue  # Only the duplicate file just created by this download.
                seen_hashes.add(digest);cards.append(self.artifact(cid,target,'download'))
            except Exception as error:self.message(cid,'system','Không tải được '+name+': '+str(error))
        return cards

    def run_job(self,job,values):
        cid=job['conversationId']
        with self.lock:job.update(state='running',stage='Đang kết nối Teams')
        try:
            if job['kind']=='explorer':
                item=self.explorers.get(cid,values['task_id'])
                if not item.get('closeRequested'):self.ensure(cid);self.explorers.prepare_result(item)
                self.explorers.advance(cid,item['id'],lambda text:self.stage(job,text))
                self.finish_explorer(cid,item)
            elif job['kind']=='new':
                self.ensure(cid,new=True);self.message(cid,'system','Đã mở cuộc trò chuyện Copilot mới.');result={'newChat':True}
            elif job['kind']=='connect':
                if self.harness:self.harness.close();self.harness=None
                self.native_active=None;self.ensure(cid);result=self.harness.status()
            else:
                text=values['text'].strip();mode=values['mode'];result=None
                local_workspace=text.startswith('/workspace ')
                if not local_workspace:self.ensure(cid)
                if text in ('/help','/status'):
                    result={'answer':HELP if text=='/help' else json.dumps(self.harness.status(),ensure_ascii=False,indent=2)}
                elif text in ('/open','/reconnect'):
                    self.harness.connect(force_open=text=='/open');result={'answer':'Đã kết nối lại Copilot.'}
                elif text=='/read':result=self.harness.read()
                elif text.startswith('/develop '):
                    self.stage(job,'Đang yêu cầu ZIP theo Nopilot development contract v1')
                    result=self.harness.ask(development_prompt(text[len('/develop '):].strip()))
                elif text.startswith('/upload '):
                    args=words(text)
                    if len(args)!=2:raise ValueError('Dùng /upload "C:\\đường dẫn tuyệt đối\\file.txt"')
                    source=pathlib.Path(args[1])
                    if not source.is_absolute() or not source.is_file():raise ValueError('Upload cần đường dẫn tuyệt đối tới file local có sẵn')
                    if source.stat().st_size>1024*1024:raise ValueError('Upload hiện giới hạn 1 MiB')
                    folder=self.directory(cid)/'artifacts'/'uploads'/uuid.uuid4().hex[:8];folder.mkdir(parents=True)
                    target=folder/source.name;shutil.copyfile(source,target)
                    self.stage(job,'Đang đưa file local sang Copilot');self.harness.upload(target)
                    card=self.artifact(cid,target,'upload')
                    result={'answer':'Đã đính kèm '+source.name+'. Bạn có thể gửi câu hỏi về file này.','localArtifacts':[card]}
                elif text.startswith('/workspace '):
                    root,question,exclude=parse_project_command('/project '+text[len('/workspace '):])
                    self.stage(job,'Đọc .nopilotignore và chuẩn bị card nhập workspace')
                    plan=self.imports.prepare(cid,root,question,exclude)
                    result={'answer':'Chọn thư mục làm workspace: xem danh sách source và duyệt nhập bản sao bên dưới. Chưa upload, chưa chạy code.','workspacePlanId':plan['id']}
                elif text.startswith(('/project ','/iterate ')):
                    if text.startswith('/iterate '):
                        task=text[len('/iterate '):].strip()
                        if not task:raise ValueError('Dùng /iterate yêu cầu sửa dự án hiện tại')
                        root=self.current_project_source(cid);question=development_prompt(task);exclude=[]
                    else:root,question,exclude=parse_project_command(text,current_root=lambda:self.current_project_source(cid))
                    self.stage(job,'Đang đóng gói và gửi dự án')
                    folder=self.directory(cid)/'artifacts'/'project-bundles'
                    def project_stage(stage,data):
                        if stage=='packing':
                            note='Project ·1/5: Đang đóng gói '+data['source']+'. Đọc .nopilotignore ở gốc dự án; nếu chưa có thì dùng file quy tắc mặc định của Nopilot.'
                            if data['existingAttachments']:note+=f' Giữ {data["existingAttachments"]} attachment bạn đã chọn; project dùng thêm1slot.'
                        elif stage=='packed':
                            manifest=self.artifact(cid,pathlib.Path(data['manifest']),'project')
                            bundle=self.artifact(cid,pathlib.Path(data['bundle']),'project')
                            self.artifact(cid,pathlib.Path(data['promptFile']),'project')
                            examples=', '.join(data['skipped'][:12]) or 'không có'
                            rules=data['ignore']
                            note=f'Project ·2/5: Đã nén {data["fileCount"]} file ({data["sourceBytes"]:,} byte) thành ZIP {data["archiveBytes"]:,} byte trong {data["elapsedSeconds"]:.3f}s; bỏ qua {data["skippedCount"]} mục: {examples}. Quy tắc: {rules["file"]} ({rules["ruleCount"]} patterns). ZIP được lưu trực tiếp với đuôi .txt. Xem manifest để biết danh sách file.'
                            self.stage(job,note);self.message(cid,'system',note,artifacts=[bundle,manifest]);return
                        elif stage=='uploading':note='Project ·3/5: Đang upload '+data['name']+' vào Copilot (1attachment).'
                        elif stage=='uploaded':note='Project ·4/5: Copilot đã nhận attachment '+data['name']+'.'
                        elif stage=='asking':note='Project ·5/5: Đang gửi yêu cầu và chờ Copilot trả lời. Log chỉ gồm những file bạn đã đính kèm riêng bằng /upload.'
                        else:return
                        self.stage(job,note);self.message(cid,'system',note)
                    result=self.harness.project(root,question=question,exclude=exclude,out_dir=folder,on_stage=project_stage)
                elif text.startswith('/download '):
                    args=words(text)
                    if len(args)!=2:raise ValueError('Dùng /download "tên-file-do-Copilot-trả-về"')
                    name=pathlib.PureWindowsPath(args[1]).name
                    if name!=args[1] or re.search(r'[<>:"/\\|?*]',name):raise ValueError('Chỉ nhập tên file download, không nhập đường dẫn')
                    folder=self.directory(cid)/'artifacts'/'downloads';folder.mkdir(parents=True,exist_ok=True)
                    target=folder/name;self.harness.download(name,target)
                    result={'answer':'Đã lưu '+name,'localArtifacts':[self.artifact(cid,target,'download')]}
                elif text=='/downloads':result={'answer':json.dumps(self.harness.downloads(),ensure_ascii=False,indent=2)}
                elif text.startswith(('/url ','/readurl ','/browse ')) or mode in ('url','browser'):
                    task=text.split(' ',1)[1] if text.startswith(('/url ','/readurl ','/browse ')) else text
                    found=re.search(r'https?://[^\s<>"\']+',task)
                    if not found:raise ValueError('Hãy nhập URL HTTP(S) trong câu hỏi, hoặc dùng /url URL câu hỏi')
                    url=found.group(0).rstrip('.,)');question=(task[:found.start()]+task[found.end():]).strip() or None
                    if mode=='browser' or text.startswith('/browse '):
                        item=self.explorers.create(cid,url,question or 'Explore the website and explain possible automation.')
                        self.explorers.advance(cid,item['id'],lambda stage:self.stage(job,stage))
                        self.finish_explorer(cid,item)
                    else:result=self.harness.read_url(url,question,on_stage=lambda stage:self.stage(job,stage))
                elif text.startswith('/'):
                    raise ValueError('Slash command không hỗ trợ. Gõ /help để xem lệnh.')
                else:
                    self.stage(job,'Đang chờ Copilot trả lời');result=self.harness.ask(text)
                if result is not None:
                    if result.get('localFiles'):
                        browser_run='projects' in result
                        projects=set(result.get('projects',[]))
                        result.setdefault('localArtifacts',[]).extend(self.artifact(cid,path,'project' if path in projects else 'browser' if browser_run else 'context') for path in result['localFiles'])
                    if 'trace' in result or 'search' in result:
                        folder=self.directory(cid)/'artifacts'/'research';folder.mkdir(parents=True,exist_ok=True)
                        path=folder/(job['id']+'.json');atomic_json(path,result)
                        result.setdefault('localArtifacts',[]).append(self.artifact(cid,path,'research'))
                    cards=result.get('localArtifacts',[])
                    if not text.startswith(('/workspace ','/upload ','/help','/status','/downloads','/download ','/open','/reconnect')):
                        self.stage(job,'Đang lưu artifacts');cards+=self.download_all(cid)
                    local_command=text.split()[0] in ('/workspace','/help','/status','/open','/reconnect','/upload','/download','/downloads')
                    self.message(cid,'system' if local_command else 'assistant',result.get('answer',''),artifacts=cards,sources=result.get('sources',[]),markdown=result.get('answerMarkdown') or result.get('response',{}).get('answerMarkdown'),workspacePlanId=result.get('workspacePlanId'))
                if not local_workspace:self.capture_route(cid)
            with self.lock:job.update(state='done',stage='Hoàn tất',finishedAt=now())
        except Exception as error:
            self.message(cid,'system',str(error),error=True)
            with self.lock:job.update(state='error',stage=str(error),finishedAt=now())
            if self.harness:
                try:self.harness.status()
                except Exception:self.connection='disconnected'

    def state(self):
        with self.lock:
            return {'buildId':BUILD_ID,'connection':self.connection,'activeId':self.native_active or self.initial_id,
                    'conversations':[{'id':c['id'],'title':c['title'],'pinned':c.get('pinned',False),'updatedAt':c['updatedAt'],'messageCount':len(c['messages'])} for c in sorted(self.conversations.values(),key=lambda c:(c.get('pinned',False),c['updatedAt']),reverse=True) if not c.get('deletedAt')],
                    'jobs':list(self.jobs.values())[-20:]}

    def local_action(self,cid,action):
        with self.lock:
            item=self.conversations[cid]
            if action=='pin':item['pinned']=not item.get('pinned',False)
            elif action=='delete':
                if any(i['conversationId']==cid and i['status']=='confirming' for i in self.imports.items.values()):raise ValueError('Đợi nhập workspace hoàn tất trước khi xóa conversation')
                if any(i['conversationId']==cid and i['status'] in ('starting','installing','running') for i in self.launches.items.values()):raise ValueError('Dừng chuỗi chạy dự án trước khi xóa conversation')
                if any(j['conversationId']==cid and j['state'] in ('queued','running') for j in self.jobs.values()):raise ValueError('Wait for this conversation to finish before removing it')
                if any(t['status']!='closed' for t in self.explorers.tasks.values() if t['conversationId']==cid):raise ValueError('Close this conversation’s explorer before removing it')
                if cid in self.runners and any(r['status'] in ('starting','running') for r in self.runners[cid].runs.values()):raise ValueError('Stop the local run before removing this conversation')
                item['deletedAt']=now()
                if self.native_active==cid:self.native_active=None
            self.save(cid)
            visible=[c for c in self.conversations.values() if not c.get('deletedAt')]
            if not visible:visible=[self.create()]
            selected=max(visible,key=lambda c:c['updatedAt'])['id']
            self.initial_id=selected
            return {'conversationId':selected,'pinned':item.get('pinned',False),'localOnly':True}

HELP='''/workspace \"C:\\src\\my-project\" — xem .nopilotignore, duyệt nhập bản sao source và Git backup; không sửa thư mục gốc
/iterate yêu cầu sửa — tự đóng gói project hiện tại thành ZIP đuôi TXT, upload và yêu cầu ZIP đầy đủ theo contract
/new — cuộc trò chuyện mới
/develop yêu cầu — tạo dự án Python ZIP có nopilot.json; giải nén và duyệt cài/chạy trong Dev
/upload "C:\\đường dẫn\\file.txt" — backend đọc file local và đính kèm vào Copilot
/project current yêu cầu sửa — tự lấy source project đang dùng trong conversation, nén ZIP đuôi TXT và gửi cùng yêu cầu; không chọn lại thư mục
/project "C:\\đường dẫn\\dự án" [--exclude "data/**"] yêu cầu sửa — đọc .nopilotignore ở gốc dự án (hoặc quy tắc mặc định), ZIP mang đuôi TXT, một attachment; dùng được cùng log đã /upload
/url https://trang-web câu hỏi — tải HTML, chuyển Markdown, gửi context hoặc upload file MD
/browse https://trang-web yêu cầu — Copilot gọi Playwright tool, tối đa 20 lượt
/downloads — liệt kê file trong câu trả lời cuối
/download "file.zip" — lưu file vào artifacts của conversation
/open, /reconnect, /read, /status, /help'''

class Server(ThreadingHTTPServer):
    daemon_threads=True

class Handler(BaseHTTPRequestHandler):
    def log_message(self,fmt,*args):pass
    def trusted(self,write=False):
        port=self.server.server_address[1]
        allowed={f'127.0.0.1:{port}',f'localhost:{port}'}
        if self.headers.get('Host') not in allowed:raise PermissionError('Host not allowed')
        origin=self.headers.get('Origin')
        if origin and origin not in {'http://'+host for host in allowed}:raise PermissionError('Origin not allowed')
        if write and self.headers.get('X-Nopilot-Token',self.headers.get('X-Kopilot-Token'))!=self.server.token:raise PermissionError('Missing local session token')
    def respond(self,status,value,content_type='application/json; charset=utf-8'):
        body=json.dumps(value,ensure_ascii=False).encode() if content_type.startswith('application/json') else value
        self.send_response(status);self.send_header('Content-Type',content_type);self.send_header('Content-Length',str(len(body)));self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.end_headers();self.wfile.write(body)
    def do_GET(self):
        try:
            self.trusted();path=urllib.parse.urlsplit(self.path).path;app=self.server.app
            if path=='/':
                body=(HERE/'web'/'index.html').read_text(encoding='utf-8').replace('__CSRF_TOKEN__',self.server.token).replace('__BUILD_ID__',BUILD_ID).encode()
                return self.respond(200,body,'text/html; charset=utf-8')
            if path in ('/app.js','/theme.js','/dev.js','/chat_projects.js','/markdown.js','/style.css','/markdown.css','/workspaces.js'):
                file=HERE/'web'/path[1:];return self.respond(200,file.read_bytes(),'text/javascript; charset=utf-8' if path.endswith('.js') else 'text/css; charset=utf-8')
            if path=='/help':return self.respond(200,(HERE/'web/help.html').read_bytes(),'text/html; charset=utf-8')
            match=re.fullmatch(r'/api/workspaces/([a-f0-9]{32})/([a-f0-9]{32})',path)
            if match:return self.respond(200,app.imports.describe(app.imports.get(*match.groups())))
            if path in ('/vendor/markdown-it.min.js','/vendor/highlight.min.js'):
                return self.respond(200,(HERE/'web'/path.lstrip('/')).read_bytes(),'text/javascript; charset=utf-8')
            if path=='/api/state':return self.respond(200,app.state())
            match=re.fullmatch(r'/api/launches/([a-f0-9]{32})/([a-f0-9]{32})',path)
            if match:
                cid,lid=match.groups();app.directory(cid)
                return self.respond(200,app.launches.describe(app.launches.get(cid,lid)))
            match=re.fullmatch(r'/api/dev/([a-f0-9]{32})(/logs)?',path)
            if match:
                cid,logs=match.groups();app.directory(cid)
                if logs:
                    query=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
                    return self.respond(200,app.runner(cid).log(query.get('runId',[''])[0],int(query.get('offset',['0'])[0])))
                return self.respond(200,app.dev_state(cid))
            match=re.fullmatch(r'/api/conversations/([a-f0-9]{32})',path)
            if match:
                cid=match.group(1);app.directory(cid)
                with app.lock:return self.respond(200,app.conversations[cid])
            match=re.fullmatch(r'/api/artifacts/([a-f0-9]{32})/([a-f0-9]{32})',path)
            if match:
                file,item=app.artifact_file(*match.groups());body=file.read_bytes()
                self.send_response(200);self.send_header('Content-Type',mimetypes.guess_type(file.name)[0] or 'application/octet-stream');self.send_header('Content-Disposition',"attachment; filename*=UTF-8''"+urllib.parse.quote(file.name));self.send_header('Content-Length',str(len(body)));self.send_header('X-Content-Type-Options','nosniff');self.end_headers();self.wfile.write(body);return
            self.respond(404,{'error':'Not found'})
        except PermissionError as error:self.respond(403,{'error':str(error)})
        except (KeyError,ValueError,FileNotFoundError) as error:self.respond(404,{'error':str(error)})
        except Exception as error:self.respond(500,{'error':str(error)})
    def do_POST(self):
        try:
            self.trusted(write=True);length=int(self.headers.get('Content-Length','0'))
            limit=2*1024*1024 if self.path.startswith('/api/dev/') else 65536
            if not 0<length<=limit:raise ValueError('Invalid request size')
            data=json.loads(self.rfile.read(length));path=urllib.parse.urlsplit(self.path).path;app=self.server.app
            if not isinstance(data,dict):raise ValueError('Expected a JSON object')
            if path=='/api/shutdown':
                self.respond(200,{'stopping':True})
                threading.Thread(target=self.server.shutdown,daemon=True).start();return
            if path=='/api/path-chooser':
                kind=data.get('kind','file')
                if kind not in ('file','directory'):raise ValueError('Invalid path chooser kind')
                result=subprocess.run([sys.executable,'-B',str(HERE/'path_chooser.py'),kind],capture_output=True,text=True,encoding='utf-8',timeout=180)
                if result.returncode:raise RuntimeError('Cannot open Windows path chooser: '+result.stderr[-800:])
                return self.respond(200,json.loads(result.stdout))
            if path=='/api/conversations':
                item=app.create();job=app.queue(item['id'],'new');return self.respond(202,{'conversationId':item['id'],'job':job})
            match=re.fullmatch(r'/api/dev/([a-f0-9]{32})/([a-z-]+)',path)
            if match:
                cid,action=match.groups();app.directory(cid)
                if app.conversations[cid].get('deletedAt'):raise ValueError('Conversation removed locally')
                return self.respond(200,app.dev_action(cid,action,data))
            match=re.fullmatch(r'/api/explorers/([a-f0-9]{32})/([a-f0-9]{32})/(pause|resume|grant|iterate|recover|open_url|close)',path)
            if match:
                cid,tid,action=match.groups();app.directory(cid)
                should_queue=app.explorers.control(cid,tid,action,data)
                job=app.queue(cid,'explorer',task_id=tid) if should_queue else None
                return self.respond(202,{'job':job})
            match=re.fullmatch(r'/api/conversations/([a-f0-9]{32})/(send|connect|open-folder|pin|delete)',path)
            if not match:return self.respond(404,{'error':'Not found'})
            cid,action=match.groups();app.directory(cid)
            if action in ('pin','delete'):return self.respond(200,app.local_action(cid,action))
            if action=='open-folder':
                if data.get('artifactId'):folder=app.artifact_file(cid,data['artifactId'])[0].parent
                else:folder=app.directory(cid)/'artifacts'
                folder.mkdir(exist_ok=True)
                if os.name=='nt':os.startfile(str(folder))
                else:raise RuntimeError('Open folder is supported on Windows')
                return self.respond(200,{'opened':True})
            if action=='connect':return self.respond(202,{'job':app.queue(cid,'connect')})
            text=data.get('text','')
            if text.strip()=='/new':
                item=app.create();job=app.queue(item['id'],'new');return self.respond(202,{'conversationId':item['id'],'job':job})
            return self.respond(202,{'job':app.submit(cid,text,data.get('mode','chat'))})
        except PermissionError as error:self.respond(403,{'error':str(error)})
        except (ValueError,KeyError,zipfile.BadZipFile) as error:self.respond(400,{'error':str(error)})
        except Exception as error:self.respond(500,{'error':str(error)})

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--port',type=int,default=8765);p.add_argument('--data-dir',type=pathlib.Path,default=default_directory('work/nopilot'));p.add_argument('--pid',type=int);p.add_argument('--offline',action='store_true',help='Start with local workspace/history; connect Teams only when sending')
    args=p.parse_args()
    from data_lock import DataLock
    data_lock=DataLock(args.data_dir);app=Application(args.data_dir,args.pid)
    server=Server(('127.0.0.1',args.port),Handler);server.app=app;server.token=secrets.token_urlsafe(32)
    if not args.offline:app.queue(app.initial_id,'connect')
    print(f'nopilot Local: http://127.0.0.1:{server.server_address[1]}',flush=True)
    print('Conversations and artifacts: '+str(app.root),flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:
        server.server_close();app.shutdown();data_lock.close()

if __name__=='__main__':main()
