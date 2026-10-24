"""Reviewable local folder import. User folders are read, never modified."""
import copy,json,pathlib,threading,time,uuid,zipfile
from project_bundle import pack_project,MANIFEST,IGNORE_NAME
from dev_workspace import save_json,manifest
import project_git

class WorkspaceImports:
    def __init__(self,app):
        self.app=app;self.lock=threading.RLock();self.items={}
        for path in app.root.glob('conversations/*/workspace-imports/*/plan.json'):
            try:
                item=json.loads(path.read_text(encoding='utf-8'))
                if item['status']=='confirming':item['status']='interrupted';save_json(path,item)
                self.items[item['id']]=item
            except (OSError,ValueError,KeyError):continue

    def folder(self,cid,lid):return self.app.directory(cid)/'workspace-imports'/lid
    def save(self,item):save_json(self.folder(item['conversationId'],item['id'])/'plan.json',item)
    def get(self,cid,lid):
        item=self.items.get(lid)
        if not item or item['conversationId']!=cid:raise ValueError('Workspace plan không thuộc conversation này')
        return item
    def describe(self,item):
        result=copy.deepcopy(item);result.pop('snapshot',None);return result

    def prepare(self,cid,root,question=None,exclude=()):
        with self.lock:
            root=pathlib.Path(root)
            if not root.is_absolute() or not root.is_dir():raise ValueError('Workspace cần đường dẫn tuyệt đối tới thư mục source')
            root=root.resolve();lid=uuid.uuid4().hex;folder=self.folder(cid,lid)
            # Nopilot data/venvs must never be recursively imported into themselves.
            if root==self.app.root or self.app.root.is_relative_to(root) or root.is_relative_to(self.app.root):
                raise ValueError('Chọn thư mục code riêng ngoài data directory của Nopilot; project đã nhập dùng /iterate.')
            packed=pack_project(root,folder/'review.txt',exclude=[*exclude,'.[gG][iI][tT]'])
            snapshot=folder/'source.snapshot'
            with zipfile.ZipFile(packed['bundle']) as source,zipfile.ZipFile(snapshot,'x',zipfile.ZIP_DEFLATED) as target:
                for entry in source.infolist():
                    if entry.filename!=MANIFEST:target.writestr(entry.filename,source.read(entry))
                if IGNORE_NAME not in source.namelist():
                    rules=root/IGNORE_NAME
                    target.writestr(IGNORE_NAME,(rules if rules.is_file() else pathlib.Path(__file__).with_name(IGNORE_NAME)).read_bytes())
            ws=self.app.workspace(cid);project=ws.extract(snapshot)
            pid=project['id'];ws.projects[pid].update(name=root.name,launchStaged=True,importedFrom=str(root));ws.save(pid)
            project_git.source_manifest(ws.source(pid))
            from project_contract import read_contract
            current=ws.current(pid)
            item={'id':lid,'conversationId':cid,'projectId':pid,'name':root.name,'originalDirectory':str(root),'sourceDirectory':str(ws.source(pid)),
                  'revision':current['revision'],'snapshot':str(snapshot),'status':'review','expiresAt':time.time()+900,
                  'fileCount':len(current['files']),'sourceBytes':current['bytes'],'archiveBytes':snapshot.stat().st_size,'skippedCount':packed['skippedCount'],
                  'skipped':packed['skipped'],'ignore':packed['ignore'],'files':[f['path'] for f in current['files']],
                  'contractStatus':read_contract(ws.source(pid))['status'],'question':question,
                  'commitMessage':'chore: import '+root.name[:120]+' into Nopilot workspace'}
            self.items[lid]=item;self.save(item);return self.describe(item)

    def confirm(self,cid,lid):
        with self.lock:
            item=self.get(cid,lid)
            if item['status']=='accepted':return self.describe(item)
            if item['status']!='review' or time.time()>item['expiresAt']:raise ValueError('Workspace plan đã hết hạn hoặc không còn chờ duyệt; dùng /workspace để xem lại.')
            ws=self.app.workspace(cid);pid=item['projectId'];ws.idle(pid)
            if manifest(ws.source(pid))['revision']!=item['revision']:raise ValueError('Bản source nhập đã thay đổi; chọn lại thư mục để xem lại.')
            item['status']='confirming';self.save(item)
            try:
                result=project_git.commit(ws,pid,item['commitMessage'])
                ws.projects[pid].pop('launchStaged',None);ws.save(pid)
                with self.app.lock:
                    conversation=self.app.conversations[cid];conversation['activeProjectId']=pid
                    if conversation['title'] in ('Cuộc trò chuyện mới','Phiên hiện tại'):conversation['title']='Workspace · '+item['name'][:40]
                    self.app.save(cid)
                item.update(status='accepted',commit=result.get('head'));self.save(item)
                self.app.message(cid,'system','Workspace · Đã nhập bản sao source và lưu Git backup local '+(item.get('commit') or '')[:8]+'.\nSource đang làm việc: '+item['sourceDirectory']+'\nThư mục gốc được giữ nguyên. Dùng /iterate yêu cầu sửa; log gửi riêng bằng /upload.')
            except Exception:
                item['status']='review';self.save(item);raise
            return self.describe(item)

    def reject(self,cid,lid):
        with self.lock:
            item=self.get(cid,lid)
            if item['status']!='review':raise ValueError('Workspace không còn chờ duyệt')
            item['status']='rejected';self.save(item);return self.describe(item)

    def select(self,cid,lid):
        with self.lock:
            item=self.get(cid,lid)
            if item['status']!='accepted':raise ValueError('Duyệt nhập workspace trước khi chọn')
            ws=self.app.workspace(cid);ws.folder(item['projectId']);ws.idle(item['projectId'])
            with self.app.lock:self.app.conversations[cid]['activeProjectId']=item['projectId'];self.app.save(cid)
            return self.describe(item)
