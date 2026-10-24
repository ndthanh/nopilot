"""One human consent for a fixed contract plan: update, install if needed, run.

No LLM participates in planning or execution. Interrupted plans never resume.
"""
import copy,json,pathlib,threading,time,uuid
from dev_workspace import save_json,manifest,stamp
from project_contract import read_contract,propose_task
from environment_cache import state as environment_state,dependency_key,sha
import project_git

ACTIVE=('starting','installing','running')

class ChatLaunches:
    def __init__(self,app):
        self.app=app;self.lock=threading.RLock();self.items={};self.threads={};self.closing=False
        for path in app.root.glob('conversations/*/launches/*.json'):
            try:
                item=json.loads(path.read_text(encoding='utf-8'))
                if item['status'] in ACTIVE:
                    item.update(status='interrupted',stage='Backend đã dừng. Xem trạng thái rồi tạo kế hoạch mới; không tự chạy lại.')
                    save_json(path,item)
                self.items[item['id']]=item
            except (ValueError,OSError,KeyError):continue

    def save(self,item):save_json(self.app.directory(item['conversationId'])/'launches'/(item['id']+'.json'),item)
    def get(self,cid,lid):
        item=self.items.get(lid)
        if not item or item['conversationId']!=cid:raise ValueError('Không tìm thấy kế hoạch trong conversation này')
        return item
    def runtime(self,ws,pid):
        exe=ws.folder(pid)/'venv/Scripts/python.exe'
        return sha(exe) if exe.exists() else None

    def prepare(self,cid,artifact_id,target=None,fresh=False):
        with self.lock:
            if self.closing:raise ValueError('Backend đang dừng')
            ws=self.app.workspace(cid)
            if target=='new':target=None;explicit=True
            else:
                explicit=bool(target)
                if target is None:
                    target=self.app.conversations[cid].get('activeProjectId')
                    # Legacy conversations can select their existing single project.
                    visible=[p for p in ws.projects.values() if not p.get('launchStaged')]
                    if not target and len(visible)==1:target=visible[0]['id']
            previous=sorted([i for i in self.items.values() if i['conversationId']==cid and i.get('artifactId')==artifact_id],key=lambda i:i.get('createdAt',''))
            if not fresh:
                for item in reversed(previous):
                    if (item['status']!='review' or item.get('planVersion')==1) and (not explicit or item.get('targetProjectId')==target) and (item['status']!='review' or time.time()<item['expiresAt']):return self.describe(item)
            if any(i['status'] in ACTIVE for i in previous):raise ValueError('ZIP này đang chạy; dừng trước khi lập kế hoạch khác')
            path,artifact=self.app.artifact_file(cid,artifact_id)
            if path.suffix.lower()!='.zip':raise ValueError('Chỉ ZIP dự án có nopilot.json mới chạy thử được')
            lid=uuid.uuid4().hex
            if target:
                ws.folder(target);ws.idle(target)
                review=project_git.preview(ws,target,path,artifact['sha256'])
                staging=type(ws)(ws.folder(target)/'updates'/review['id'])
                source=staging.source(review['candidateId']);pid=target;revision=review['candidateRevision']
                update={'id':review['id'],'baseRevision':review['baseRevision'],'changes':review['changes'],'diff':review['diff']} if review['changes'] else None
                message=review['commitMessage']
            else:
                project=ws.extract(path,artifact['sha256']);pid=project['id'];source=ws.source(pid);revision=project['revision']
                ws.projects[pid]['launchStaged']=True;ws.save(pid)
                update=None;message=project_git.suggested(source) or 'chore: import project into Nopilot'
            contract=read_contract(source)
            if contract['status']!='valid':raise ValueError('Chưa chạy được ZIP: '+contract.get('error','Thiếu nopilot.json'))
            project_git.source_manifest(source)
            result=self.create(cid,lid,pid,source,revision,contract['manifest'],artifact_id,target,update,message)
            if target and not update:
                self.items[lid]['skipGit']=True;self.save(self.items[lid]);result=self.describe(self.items[lid])
            return result

    def create(self,cid,lid,pid,source,revision,spec,artifact_id=None,target=None,update=None,message=''):
        ws=self.app.workspace(cid)
        env=environment_state(ws,pid,source=source)
        install=bool(spec.get('install')) and not env['ready']
        item={'id':lid,'planVersion':1,'conversationId':cid,'projectId':pid,'projectName':spec['name'],'targetProjectName':ws.projects[pid]['name'],'artifactId':artifact_id,'targetProjectId':target,
              'source':str(source),'revision':revision,'baseRevision':update['baseRevision'] if update else revision,'update':update,
              'contract':spec,'installNeeded':install,'dependencyKey':dependency_key(source),'runtimeHash':self.runtime(ws,pid),
              'commitMessage':message,'task':'start','status':'review','stage':'Bạn có muốn chạy thử dự án này?',
              'createdAt':stamp(),'expiresAt':time.time()+900,'runIds':[]}
        if spec.get('install'):item['requirements']=(source/'requirements.txt').read_text(encoding='utf-8')
        self.items[lid]=item;self.save(item);return self.describe(item)

    def check_plan(self,cid,pid,task='check'):
        with self.lock:
            if self.closing:raise ValueError('Backend đang dừng')
            ws=self.app.workspace(cid);ws.idle(pid);source=ws.source(pid);spec=read_contract(source)
            if task not in ('start','check') or spec['status']!='valid' or task not in spec['manifest']['tasks']:raise ValueError('Project chưa khai báo task hợp lệ')
            item=self.create(cid,uuid.uuid4().hex,pid,source,ws.current(pid)['revision'],spec['manifest'])
            raw=self.items[item['id']];raw.update(task=task,skipGit=True,stage='Chạy task '+task+' theo contract?');self.save(raw)
            return self.describe(raw)

    def describe(self,item):
        with self.lock:result=copy.deepcopy(item)
        result.pop('source',None)
        if result.get('runId'):
            runner=self.app.runner(result['conversationId'])
            with runner.lock:
                if result['runId'] in runner.runs:result['run']=runner.describe(result['runId'])
        return result

    def confirm(self,cid,lid,message=None):
        with self.lock:
            if self.closing:raise ValueError('Backend đang dừng')
            item=self.get(cid,lid)
            if item['status'] in ACTIVE or item['status']=='succeeded':return self.describe(item)
            if item['status']!='review' or time.time()>item['expiresAt']:raise ValueError('Kế hoạch đã dùng/hết hạn. Xem lại kế hoạch mới.')
            ws=self.app.workspace(cid);pid=item['projectId'];ws.idle(pid)
            if any(i['projectId']==pid and i['conversationId']==cid and i['status'] in ACTIVE for i in self.items.values()):raise ValueError('Project đang có chuỗi chạy khác')
            if ws.current(pid)['revision']!=item['baseRevision']:raise ValueError('Source đã thay đổi; xem lại kế hoạch')
            source=pathlib.Path(item['source'])
            if manifest(source)['revision']!=item['revision'] or dependency_key(source)!=item['dependencyKey'] or self.runtime(ws,pid)!=item['runtimeHash']:raise ValueError('Source/Python/runtime đã đổi; xem lại kế hoạch')
            if item['contract'].get('install') and not item['installNeeded'] and not environment_state(ws,pid,source=source)['ready']:raise ValueError('Môi trường đã đổi; xem lại kế hoạch cài')
            if item['update'] and time.time()>json.loads((ws.folder(pid)/'updates'/item['update']['id']/'review.json').read_text(encoding='utf-8'))['expiresAt']:raise ValueError('Diff cập nhật hết hạn; xem lại kế hoạch')
            if not item.get('skipGit'):item['commitMessage']=project_git.message(message if message is not None else item['commitMessage'])
            item.update(status='starting',stage='Đã đồng ý kế hoạch; đang chuẩn bị',approvedAt=stamp())
            self.save(item)
            thread=threading.Thread(target=self.execute,args=(item,),daemon=True,name='nopilot-chat-launch-'+lid[:8]);self.threads[lid]=thread;thread.start()
            return self.describe(item)

    def transition(self,item,status,stage):
        with self.lock:item.update(status=status,stage=stage);self.save(item)
        self.app.message(item['conversationId'],'system','Dự án · '+stage)

    def execute(self,item):
        cid=item['conversationId'];pid=item['projectId'];ws=self.app.workspace(cid)
        try:
            with self.lock:
                if item.get('stopRequested') or self.closing:raise InterruptedError('Đã dừng trước khi chạy')
                if item['update']:
                    self.transition(item,'starting','Lưu source hiện tại vào Git, áp dụng ZIP đã xem diff')
                    result=project_git.apply(ws,pid,item['update']['id'],item['baseRevision'],item['commitMessage']);item['commit']=result['git'].get('head');self.app.project_changed(cid,pid)
                elif not item.get('skipGit'):
                    if ws.current(pid)['revision']!=item['revision']:raise ValueError('Source đã đổi trước khi tạo Git checkpoint')
                    item['commit']=project_git.commit(ws,pid,item['commitMessage']).get('head')
                ws.projects[pid].pop('launchStaged',None);ws.save(pid)
                self.app.conversations[cid]['activeProjectId']=pid;self.app.save(cid)
            tasks=(['install'] if item['installNeeded'] else [])+[item['task']]
            for index,task in enumerate(tasks):
                with self.lock:
                    if item.get('stopRequested') or self.closing:raise InterruptedError('Đã dừng chuỗi chạy')
                    if ws.current(pid)['revision']!=item['revision']:raise ValueError('Source thay đổi trong lúc thực hiện; không chạy bước tiếp theo')
                    approval=propose_task(ws,pid,task,item['revision'])
                    if index==0 and approval['runtimeHash']!=item['runtimeHash']:
                        approval['status']='stale';ws.save_approval(approval['id']);raise ValueError('Runtime đổi sau khi đồng ý; xem lại kế hoạch')
                    # The human consent is limited to this saved install + task plan.
                    approval['chatLaunchId']=item['id'];ws.save_approval(approval['id'])
                    run=self.app.runner(cid).start(approval['id']);item['runIds'].append(run['id']);item['runId']=run['id']
                    self.transition(item,'installing' if task=='install' else 'running','Đang cài dependencies' if task=='install' else 'Đang chạy kiểm tra' if task=='check' else 'Đang chạy dự án')
                while True:
                    result=self.app.runner(cid).describe(run['id'])
                    if result['status'] not in ('starting','running'):break
                    with self.lock:
                        if item.get('stopRequested') or self.closing:self.app.runner(cid).stop(run['id'])
                    time.sleep(.1)
                if result['status']!='succeeded':
                    self.transition(item,result['status'],'Bước '+task+' kết thúc: '+result['status']+' · exit '+str(result.get('exitCode')));return
            self.transition(item,'succeeded','Hoàn tất · '+item['task']+' thành công')
        except InterruptedError as error:self.transition(item,'stopped',str(error))
        except Exception as error:self.transition(item,'failed',str(error))

    def stop(self,cid,lid):
        with self.lock:
            item=self.get(cid,lid);item['stopRequested']=True
            if item.get('runId'):self.app.runner(cid).stop(item['runId'])
            self.save(item);return self.describe(item)

    def close(self):
        with self.lock:
            self.closing=True
            for item in self.items.values():
                if item['status'] in ACTIVE:self.stop(item['conversationId'],item['id'])
        for thread in list(self.threads.values()):thread.join(timeout=10)
