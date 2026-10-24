"""Conversation-owned projects. No code executes during inspect/extract/edit."""
from __future__ import annotations
import datetime as dt
import difflib
import hashlib
import json
import os
import pathlib
import re
import shutil
import stat
import threading
import time
import unicodedata
import uuid
import zipfile

MAX_FILES=2000
MAX_BYTES=32*1024*1024
RESERVED={'CON','PRN','AUX','NUL',*[f'COM{i}' for i in range(10)],*[f'LPT{i}' for i in range(10)]}
def stamp():return dt.datetime.now(dt.timezone.utc).isoformat()
def digest(data):return hashlib.sha256(data).hexdigest()
def save_json(path,value):
    path=pathlib.Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
    temp.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8');temp.replace(path)
def relative(name):
    if not isinstance(name,str) or not name or len(name)>220 or '\\' in name or name.startswith('/') or '\x00' in name:raise ValueError('Invalid relative project path')
    parts=name.split('/')
    for part in parts:
        if not part or part in ('.','..') or re.search(r'[<>:"|?*\x00-\x1f]',part) or part.rstrip(' .')!=part or unicodedata.normalize('NFKC',part.split('.')[0]).upper() in RESERVED:raise ValueError('Unsafe Windows project path: '+name)
    return pathlib.PurePosixPath(*parts).as_posix()
def plain(path):
    info=path.lstat()
    if path.is_symlink() or getattr(info,'st_file_attributes',0)&0x400:raise ValueError('Symlink/reparse points are not allowed: '+str(path))
    return info
def contained(root,name):
    name=relative(name);root=pathlib.Path(root).resolve();target=root.joinpath(*name.split('/'))
    if not target.resolve().is_relative_to(root):raise ValueError('Path escapes project')
    current=root
    plain(root)
    for part in name.split('/'):
        current=current/part
        if current.exists() or current.is_symlink():plain(current)
    return target
def manifest(root):
    root=pathlib.Path(root).resolve();plain(root);files=[];total=0;seen=set()
    for base,dirs,names in os.walk(root,followlinks=False):
        for name in dirs:plain(pathlib.Path(base)/name)
        for name in sorted(names):
            path=pathlib.Path(base)/name;info=plain(path)
            if not stat.S_ISREG(info.st_mode):raise ValueError('Only regular files are allowed')
            key=relative(path.relative_to(root).as_posix());normal=unicodedata.normalize('NFC',key).casefold()
            if normal in seen:raise ValueError('Case/Unicode path collision')
            seen.add(normal);total+=info.st_size
            if len(files)>=MAX_FILES or total>MAX_BYTES:raise ValueError('Project exceeds file/size limits')
            files.append({'path':key,'bytes':info.st_size,'sha256':digest(path.read_bytes())})
    files.sort(key=lambda x:x['path'])
    return {'revision':digest(json.dumps(files,sort_keys=True).encode()),'files':files,'bytes':total}

def inspect_zip(path):
    path=pathlib.Path(path)
    if path.stat().st_size>8*1024*1024:raise ValueError('ZIP exceeds 8 MiB')
    files=[];seen={};total=0
    with zipfile.ZipFile(path) as z:
        if len(z.infolist())>MAX_FILES:raise ValueError('ZIP has too many entries')
        for entry in z.infolist():
            name=relative(entry.filename.rstrip('/') if entry.is_dir() else entry.filename)
            normal=unicodedata.normalize('NFC',name).casefold()
            if normal in seen:raise ValueError('Duplicate ZIP entry after Windows path normalization')
            mode=entry.external_attr>>16
            if stat.S_ISLNK(mode) or (mode and stat.S_IFMT(mode) not in (0,stat.S_IFREG,stat.S_IFDIR)):raise ValueError('ZIP contains a special file')
            if entry.flag_bits&1:raise ValueError('Encrypted ZIP is not supported')
            if entry.external_attr&0x400:raise ValueError('ZIP reparse point is not supported')
            seen[normal]='directory' if entry.is_dir() else 'file'
            total+=entry.file_size
            if total>MAX_BYTES or (entry.file_size>1024*1024 and entry.file_size/max(1,entry.compress_size)>200):raise ValueError('ZIP expansion exceeds limits')
            files.append({'path':name,'bytes':entry.file_size,'directory':entry.is_dir()})
        for name in seen:
            parts=name.split('/')
            if any(seen.get('/'.join(parts[:i]))=='file' for i in range(1,len(parts))):raise ValueError('ZIP file/directory collision')
    roots={f['path'].split('/')[0] for f in files}
    strip=next(iter(roots)) if len(roots)==1 and any('/' in f['path'] for f in files) and not any(f['path']==next(iter(roots)) and not f['directory'] for f in files) else None
    return {'name':path.name,'zipSha256':digest(path.read_bytes()),'bytes':path.stat().st_size,'expandedBytes':total,'files':files,'stripRoot':strip}

class Workspace:
    def __init__(self,root):
        self.root=pathlib.Path(root).resolve();self.root.mkdir(parents=True,exist_ok=True)
        self.lock=threading.RLock();self.projects={};self.approvals={};self.running=set()
        for file in self.root.glob('projects/*/project.json'):
            item=json.loads(file.read_text(encoding='utf-8'));self.projects[item['id']]=item
        for file in self.root.glob('approvals/*.json'):
            item=json.loads(file.read_text(encoding='utf-8'))
            if item['status']=='executing':item['status']='interrupted';save_json(file,item)
            self.approvals[item['id']]=item
    def folder(self,pid):
        if not isinstance(pid,str) or not re.fullmatch('[a-f0-9]{32}',pid) or pid not in self.projects:raise ValueError('Project not found')
        folder=self.root/'projects'/pid
        for path in (self.root,self.root/'projects',folder):
            if path.exists():plain(path)
        if not folder.resolve().is_relative_to(self.root):raise ValueError('Project directory escapes workspace')
        return folder
    def source(self,pid):return self.folder(pid)/'source'
    def save(self,pid):save_json(self.folder(pid)/'project.json',self.projects[pid])
    def idle(self,pid):
        if pid in self.running:raise ValueError('Project is running; stop it before editing')
    def current(self,pid):return manifest(self.source(pid))
    def list(self):
        with self.lock:return [self.describe(pid) for pid in self.projects]
    def describe(self,pid):
        with self.lock:
            item=self.projects[pid];m=self.current(pid)
            checkpoints=[json.loads(p.read_text(encoding='utf-8')) for p in (self.folder(pid)/'checkpoints').glob('*/checkpoint.json')]
            return {**item,**m,'running':pid in self.running,'sourceDirectory':str(self.source(pid)),
                    'checkpoints':[{k:c[k] for k in ('id','label','at','revision','bytes')} for c in sorted(checkpoints,key=lambda c:c['at'],reverse=True)[:30]]}
    def extract(self,path,expected_hash=None):
        with self.lock:
            info=inspect_zip(path)
            if expected_hash and info['zipSha256']!=expected_hash:raise ValueError('ZIP changed since inspection')
            pid=uuid.uuid4().hex;folder=self.root/'projects'/pid;source=folder/'source';source.mkdir(parents=True)
            total=0
            with zipfile.ZipFile(path) as z:
                for entry in z.infolist():
                    name=entry.filename.rstrip('/') if entry.is_dir() else entry.filename
                    if info['stripRoot']:
                        if name==info['stripRoot']:continue
                        name=name[len(info['stripRoot'])+1:]
                    target=contained(source,name)
                    if entry.is_dir():target.mkdir(parents=True,exist_ok=True);continue
                    target.parent.mkdir(parents=True,exist_ok=True)
                    with z.open(entry) as src,target.open('xb') as dest:
                        while chunk:=src.read(65536):
                            total+=len(chunk)
                            if total>MAX_BYTES:raise ValueError('ZIP actual expansion exceeds limit')
                            dest.write(chunk)
            self.projects[pid]={'id':pid,'name':info['stripRoot'] or pathlib.Path(path).stem,'createdAt':stamp(),'zipSha256':info['zipSha256']}
            self.save(pid);self.checkpoint(pid,'Imported ZIP');return self.describe(pid)
    def create(self,name,files):
        with self.lock:
            pid=uuid.uuid4().hex;folder=self.root/'projects'/pid;source=folder/'source';source.mkdir(parents=True)
            self.projects[pid]={'id':pid,'name':str(name)[:100],'createdAt':stamp(),'zipSha256':None};self.save(pid)
            self.patch(pid,self.current(pid)['revision'],files,'Initial files');return self.describe(pid)
    def read(self,pid,path):
        target=contained(self.source(pid),path)
        if not target.is_file() or target.stat().st_size>1024*1024:raise ValueError('Text file missing or exceeds 1 MiB')
        try:content=target.read_text(encoding='utf-8')
        except UnicodeError as error:raise ValueError('Selected file is not UTF-8 text') from error
        return {'path':path,'content':content,'sha256':digest(target.read_bytes()),'revision':self.current(pid)['revision']}
    def checkpoint(self,pid,label):
        with self.lock:
            self.idle(pid);m=self.current(pid);cid=uuid.uuid4().hex
            root=self.folder(pid)/'checkpoints'/cid;dest=root/'files';dest.mkdir(parents=True)
            for item in m['files']:
                target=contained(dest,item['path']);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(contained(self.source(pid),item['path']),target)
            item={'id':cid,'label':str(label)[:120],'at':stamp(),**m};save_json(root/'checkpoint.json',item);return item
    def checkpoint_data(self,pid,cid):
        if not isinstance(cid,str) or not re.fullmatch('[a-f0-9]{32}',cid):raise ValueError('Invalid checkpoint')
        folder=self.folder(pid)/'checkpoints'/cid
        item=json.loads((folder/'checkpoint.json').read_text(encoding='utf-8'))
        if manifest(folder/'files')['revision']!=item['revision']:raise ValueError('Checkpoint files changed')
        return folder,item
    def diff(self,pid,cid):
        folder,before=self.checkpoint_data(pid,cid);after=self.current(pid)
        old={i['path']:i for i in before['files']};new={i['path']:i for i in after['files']};parts=[]
        for name in sorted(old.keys()|new.keys()):
            if old.get(name)==new.get(name):continue
            try:
                a=contained(folder/'files',name).read_text(encoding='utf-8').splitlines(True) if name in old else []
                b=contained(self.source(pid),name).read_text(encoding='utf-8').splitlines(True) if name in new else []
                parts.extend(difflib.unified_diff(a,b,fromfile='before/'+name,tofile='after/'+name))
            except UnicodeError:parts.append('Binary file changed: '+name+'\n')
        text=''.join(parts);return {'checkpoint':cid,'revision':after['revision'],'diff':text[:200000],'truncated':len(text)>200000}
    def patch(self,pid,revision,files,label='Before edit'):
        with self.lock:
            self.idle(pid)
            if self.current(pid)['revision']!=revision:raise ValueError('Stale project revision')
            if not isinstance(files,list) or not 1<=len(files)<=30:raise ValueError('Expected 1..30 file changes')
            changes=[];seen=set();size=0
            for item in files:
                if set(item)!={'path','content'}:raise ValueError('File edit keys must be path, content (null deletes)')
                path=relative(item['path']);key=unicodedata.normalize('NFC',path).casefold()
                if key in seen:raise ValueError('Duplicate edit path')
                seen.add(key);target=contained(self.source(pid),path);content=item['content']
                if content is not None and not isinstance(content,str):raise ValueError('Content must be text or null')
                data=content.encode('utf-8') if content is not None else None;size+=len(data or b'')
                if target.exists() and not target.is_file():raise ValueError('File edit targets a directory')
                if size>1024*1024:raise ValueError('Edit exceeds 1 MiB')
                changes.append((target,data))
            current={f['path']:f['bytes'] for f in self.current(pid)['files']}
            for target,data in changes:
                key=target.relative_to(self.source(pid)).as_posix()
                if data is None:current.pop(key,None)
                else:current[key]=len(data)
            if len(current)>MAX_FILES or sum(current.values())>MAX_BYTES:raise ValueError('Edit exceeds project limits')
            normal=[unicodedata.normalize('NFC',n).casefold() for n in current]
            if len(set(normal))!=len(normal):raise ValueError('Path collision after edit')
            keys=set(normal)
            for key in keys:
                parts=key.split('/')
                if any('/'.join(parts[:i]) in keys for i in range(1,len(parts))):raise ValueError('File/directory collision after edit')
            cp=self.checkpoint(pid,label)
            for target,data in changes:
                if data is None:
                    if target.is_file():target.unlink()
                else:
                    target.parent.mkdir(parents=True,exist_ok=True);temp=target.with_name(target.name+'.'+uuid.uuid4().hex+'.tmp');temp.write_bytes(data);temp.replace(target)
            self.save(pid);return {'project':self.describe(pid),'checkpoint':cp['id'],'diff':self.diff(pid,cp['id'])}
    def rollback(self,pid,cid):
        with self.lock:
            self.idle(pid);folder,item=self.checkpoint_data(pid,cid);backup=self.checkpoint(pid,'Before rollback')
            wanted={i['path'] for i in item['files']}
            for entry in self.current(pid)['files']:
                if entry['path'] not in wanted:contained(self.source(pid),entry['path']).unlink()
            for entry in item['files']:
                target=contained(self.source(pid),entry['path']);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(contained(folder/'files',entry['path']),target)
            self.save(pid);return {'project':self.describe(pid),'recoveryCheckpoint':backup['id']}
    def propose(self,pid,kind='run',entrypoint='run.py',arguments=None,timeout=120,revision=None,execution_mode='host'):
        with self.lock:
            self.idle(pid);m=self.current(pid)
            if revision and revision!=m['revision']:raise ValueError('Stale project revision')
            if kind not in ('run','install'):raise ValueError('Run kind must be run or install')
            if type(timeout) is not int or not 1<=timeout<=600:raise ValueError('Timeout must be 1..600 seconds')
            arguments=arguments or []
            if not isinstance(arguments,list) or len(arguments)>30 or any(not isinstance(a,str) or len(a)>2000 or '\x00' in a for a in arguments):raise ValueError('Invalid script arguments')
            if kind=='install' and arguments:raise ValueError('Install arguments are fixed by the pinned requirements')
            source=self.source(pid);venv=self.folder(pid)/'venv';exe=venv/'Scripts'/'python.exe'
            from environment_cache import state as environment_state
            reset_runtime=kind=='install' and exe.exists() and not environment_state(self,pid)['ready']
            aid=uuid.uuid4().hex;execution_source=self.folder(pid)/'approved-sources'/aid
            from sys import executable
            commands=[]
            if not exe.exists() or reset_runtime:commands.append([executable,'-I','-m','venv',str(venv)])
            if kind=='run':
                entry=contained(source,entrypoint)
                if entry.suffix.lower()!='.py' or not entry.is_file():raise ValueError('Select an existing Python entrypoint')
                commands.append([str(exe),'-u','-s','-B',str(execution_source/entrypoint),*arguments])
            else:
                req=contained(source,entrypoint)
                if req.name!='requirements.txt' or not req.is_file():raise ValueError('Select requirements.txt')
                lines=[line.strip() for line in req.read_text(encoding='utf-8').splitlines() if line.strip() and not line.lstrip().startswith('#')]
                if not lines or any(not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*(?:\[[A-Za-z0-9_,.-]+\])?==[A-Za-z0-9][A-Za-z0-9_.+!-]*',line) for line in lines):raise ValueError('Install accepts pinned package==version only; no URLs, options, local paths or nested files')
                commands.append([str(exe),'-u','-s','-m','pip','--isolated','install','--no-cache-dir','--index-url','https://pypi.org/simple','--extra-index-url','https://pypi.org/simple','--no-input','-r',str(execution_source/entrypoint)])
            item={'id':aid,'projectId':pid,'kind':kind,'entrypoint':entrypoint,'arguments':arguments,'timeout':timeout,'revision':m['revision'],'files':m['files'],'commands':commands,'cwd':str(execution_source),'originalSource':str(source),'createdAt':stamp(),'expiresAt':time.time()+900,'status':'pending','runtimeHash':digest(exe.read_bytes()) if exe.exists() else None,'hostAccess':True}
            item['resetRuntime']=reset_runtime
            if kind=='install':item['requirements']=req.read_text(encoding='utf-8')
            if execution_mode not in ('host','container'):raise ValueError('Execution mode must be host or container')
            item['executionMode']=execution_mode
            if execution_mode=='container':
                if kind!='run':raise ValueError('Container mode supports run only; prepare dependencies in an image outside this workflow')
                from container_runner import container_runtime,plan
                docker,image=container_runtime();name='nopilot-'+aid
                item.update(hostAccess=False,containerName=name,dockerCommand=docker,imageId=image)
                item['commands']=[plan(docker,image,name,execution_source,entrypoint,arguments)]
            self.approvals[aid]=item;self.save_approval(aid);return item
    def save_approval(self,aid):save_json(self.root/'approvals'/(aid+'.json'),self.approvals[aid])
    def consume(self,aid):
        with self.lock:
            if aid not in self.approvals:raise ValueError('Approval not found')
            item=self.approvals[aid];pid=item['projectId'];self.idle(pid)
            if item['status']!='pending':raise ValueError('Approval is no longer pending')
            if time.time()>item['expiresAt']:item['status']='expired';self.save_approval(aid);raise ValueError('Approval expired')
            exe=self.folder(pid)/'venv'/'Scripts'/'python.exe'
            runtime=digest(exe.read_bytes()) if exe.exists() else None
            if self.current(pid)['revision']!=item['revision'] or runtime!=item['runtimeHash']:
                item['status']='stale';self.save_approval(aid);raise ValueError('Project/runtime changed; request a new approval')
            item['status']='executing';item['approvedAt']=stamp();self.save_approval(aid);self.running.add(pid)
            return json.loads(json.dumps(item))
    def prepare_execution_source(self,approval):
        with self.lock:
            pid=approval['projectId'];source=self.source(pid);expected=self.folder(pid)/'approved-sources'/approval['id'];target=pathlib.Path(approval['cwd'])
            if target!=expected:raise ValueError('Approval execution directory mismatch')
            if expected.parent.exists():plain(expected.parent)
            target.mkdir(parents=True,exist_ok=False)
            for entry in approval['files']:
                dest=contained(target,entry['path']);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(contained(source,entry['path']),dest)
            if manifest(target)['revision']!=approval['revision'] or self.current(pid)['revision']!=approval['revision']:raise ValueError('Source changed before execution snapshot was ready; no command started')
            return target
    def reject(self,aid):
        with self.lock:
            item=self.approvals[aid]
            if item['status']!='pending':raise ValueError('Approval is no longer pending')
            item['status']='rejected';self.save_approval(aid);return item
