"""Approved Python execution, bounded output, timeout and Windows process-tree stop."""
from __future__ import annotations
import ctypes
import codecs
from ctypes import wintypes as W
import json
import os
import pathlib
import shutil
import subprocess
import sys
import threading
import tempfile
import time
import uuid
if not (__name__=='__main__' and sys.argv[1:]==['--child']):
    from dev_workspace import save_json,stamp,manifest,contained

class Job:
    def __init__(self):
        if os.name!='nt':raise RuntimeError('The approved runner currently requires Windows Job Objects')
        self.lock=threading.Lock();k=self.k=ctypes.WinDLL('kernel32',use_last_error=True)
        class Basic(ctypes.Structure):
            _fields_=[('PerProcessUserTimeLimit',ctypes.c_int64),('PerJobUserTimeLimit',ctypes.c_int64),('LimitFlags',W.DWORD),('MinimumWorkingSetSize',ctypes.c_size_t),('MaximumWorkingSetSize',ctypes.c_size_t),('ActiveProcessLimit',W.DWORD),('Affinity',ctypes.c_size_t),('PriorityClass',W.DWORD),('SchedulingClass',W.DWORD)]
        class IO(ctypes.Structure):_fields_=[(n,ctypes.c_uint64) for n in ('ReadOperationCount','WriteOperationCount','OtherOperationCount','ReadTransferCount','WriteTransferCount','OtherTransferCount')]
        class Extended(ctypes.Structure):_fields_=[('BasicLimitInformation',Basic),('IoInfo',IO),('ProcessMemoryLimit',ctypes.c_size_t),('JobMemoryLimit',ctypes.c_size_t),('PeakProcessMemoryUsed',ctypes.c_size_t),('PeakJobMemoryUsed',ctypes.c_size_t)]
        k.CreateJobObjectW.argtypes=[ctypes.c_void_p,W.LPCWSTR];k.CreateJobObjectW.restype=W.HANDLE
        k.SetInformationJobObject.argtypes=[W.HANDLE,ctypes.c_int,ctypes.c_void_p,W.DWORD];k.SetInformationJobObject.restype=W.BOOL
        k.OpenProcess.argtypes=[W.DWORD,W.BOOL,W.DWORD];k.OpenProcess.restype=W.HANDLE
        k.AssignProcessToJobObject.argtypes=[W.HANDLE,W.HANDLE];k.AssignProcessToJobObject.restype=W.BOOL
        k.TerminateJobObject.argtypes=[W.HANDLE,W.UINT];k.TerminateJobObject.restype=W.BOOL
        k.CloseHandle.argtypes=[W.HANDLE];k.CloseHandle.restype=W.BOOL
        self.handle=k.CreateJobObjectW(None,None)
        if not self.handle:raise ctypes.WinError(ctypes.get_last_error())
        info=Extended();info.BasicLimitInformation.LimitFlags=0x2000|0x8;info.BasicLimitInformation.ActiveProcessLimit=32
        if not k.SetInformationJobObject(self.handle,9,ctypes.byref(info),ctypes.sizeof(info)):
            error=ctypes.WinError(ctypes.get_last_error());self.close();raise error
    def assign(self,pid):
        handle=self.k.OpenProcess(0x100|0x1|0x400,False,pid)
        if not handle:raise ctypes.WinError(ctypes.get_last_error())
        try:
            if not self.k.AssignProcessToJobObject(self.handle,handle):raise ctypes.WinError(ctypes.get_last_error())
        finally:self.k.CloseHandle(handle)
    def close(self):
        with self.lock:
            if self.handle:self.k.TerminateJobObject(self.handle,130);self.k.CloseHandle(self.handle);self.handle=None

class Runner:
    def __init__(self,workspace,artifacts,on_complete=None):
        self.workspace=workspace;self.root=pathlib.Path(artifacts).resolve();self.root.mkdir(parents=True,exist_ok=True)
        self.lock=threading.RLock();self.runs={};self.jobs={};self.threads={};self.on_complete=on_complete
        for path in self.root.glob('*/run.json'):
            item=json.loads(path.read_text(encoding='utf-8'))
            if item['status'] in ('starting','running'):item.update(status='interrupted',finishedAt=stamp());save_json(path,item)
            if item.get('completionDelivered') is False:
                item.update(completionDelivered=True,notificationInterrupted=True)
                save_json(path,item)  # No completion callback/model prompt is replayed.
            self.runs[item['id']]=item
    def save(self,rid):save_json(self.root/rid/'run.json',self.runs[rid])
    def start(self,aid):
        # Only the human-facing API/CLI calls this method. No model tool exposes it.
        approval=self.workspace.consume(aid);rid=uuid.uuid4().hex
        item={'id':rid,'approvalId':aid,'projectId':approval['projectId'],'revision':approval['revision'],'status':'starting','createdAt':stamp(),'exitCode':None,'commands':approval['commands'],'cwd':approval['cwd'],'timeout':approval['timeout'],'bytes':0}
        item.update(executionMode=approval.get('executionMode','host'),hostAccess=approval.get('hostAccess',True))
        for key in ('contractTask','previewUrl'):
            if key in approval:item[key]=approval[key]
        item['completionDelivered']=not bool(self.on_complete)
        with self.lock:
            self.runs[rid]=item;self.save(rid)
            thread=threading.Thread(target=self._run,args=(rid,approval),daemon=True,name='nopilot-run-'+rid[:6]);self.threads[rid]=thread;thread.start()
        return dict(item)
    def _run(self,rid,approval):
        item=self.runs[rid];job=None;process=None;folder=self.root/rid;folder.mkdir(exist_ok=True)
        stop_reason=None;private_temp=None
        try:
            execution_source=self.workspace.prepare_execution_source(approval)
            if approval.get('resetRuntime'):
                from dev_workspace import plain
                folder=self.workspace.folder(approval['projectId']).resolve();venv=folder/'venv';backup=folder/'environment-backups'/approval['id']
                if not venv.resolve().is_relative_to(folder) or not backup.resolve().is_relative_to(folder):raise ValueError('Runtime backup escapes project')
                plain(venv);backup.mkdir(parents=True,exist_ok=False)
                venv.rename(backup/'venv')
                receipt=folder/'environment.json'
                if receipt.exists():plain(receipt);receipt.rename(backup/'environment.json')
                item['previousEnvironment']=str(backup)
            if approval['kind']=='install':
                receipt=self.workspace.folder(approval['projectId'])/'environment.json'
                if receipt.exists():
                    from dev_workspace import plain
                    plain(receipt);history=receipt.parent/'receipt-history';history.mkdir(exist_ok=True);plain(history)
                    receipt.rename(history/(approval['id']+'.json'))
            job=Job()
            with self.lock:self.jobs[rid]=job
            env={key:value for key,value in os.environ.items() if key.upper() in ('SYSTEMROOT','WINDIR','COMSPEC','PATHEXT','NUMBER_OF_PROCESSORS','PROCESSOR_ARCHITECTURE','PROGRAMFILES','PROGRAMFILES(X86)','PROGRAMW6432','COMMONPROGRAMFILES','COMMONPROGRAMFILES(X86)')}
            # Chromium adds deep profile paths; conversation paths exceed MAX_PATH.
            private_temp=pathlib.Path(tempfile.mkdtemp(prefix='nopilot-')).resolve()
            temp=private_temp/'tmp';temp.mkdir();home=private_temp/'home';home.mkdir()
            (home/'AppData/Roaming').mkdir(parents=True);(home/'AppData/Local').mkdir(parents=True)
            env.update({'PATH':str(pathlib.Path(sys.executable).parent)+os.pathsep+str(pathlib.Path(os.environ.get('SystemRoot','C:/Windows'))/'System32'),'TEMP':str(temp),'TMP':str(temp),'USERPROFILE':str(home),'HOME':str(home),'APPDATA':str(home/'AppData/Roaming'),'LOCALAPPDATA':str(home/'AppData/Local'),'PIP_CONFIG_FILE':os.devnull,'PYTHONIOENCODING':'utf-8','PYTHONUTF8':'1','PYTHONNOUSERSITE':'1'})
            process=subprocess.Popen([sys.executable,'-I','-u',str(pathlib.Path(__file__).resolve()),'--child'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,env=env,creationflags=subprocess.CREATE_NO_WINDOW)
            job.assign(process.pid)  # Child blocks on stdin; no project code starts before assignment.
            with self.lock:
                if item.get('stopRequested'):stop_reason='stopped';job.close()
                else:item.update(status='running',pid=process.pid,startedAt=stamp());self.save(rid)
            if not stop_reason:
                if self.workspace.current(approval['projectId'])['revision']!=approval['revision']:raise ValueError('Project changed after approval; no command was started')
                process.stdin.write((json.dumps({'commands':approval['commands'],'cwd':approval['cwd']})+'\n').encode());process.stdin.flush();process.stdin.close()
                deadline=time.monotonic()+approval['timeout']
                def consume():
                    try:
                        for raw in iter(process.stdout.readline,b''):
                            try:event=json.loads(raw)
                            except ValueError:event={'stream':'stderr','text':raw.decode('utf-8',errors='replace')}
                            stream=event.get('stream','stderr');stream=stream if stream in ('stdout','stderr','system') else 'stderr'
                            text=str(event.get('text',''));data=text.encode('utf-8',errors='replace')
                            with self.lock:
                                remaining=1024*1024-item['bytes'];data=data[:max(0,remaining)];item['bytes']+=len(data)
                                if data:
                                    with (folder/(stream+'.log')).open('ab') as file:file.write(data)
                                    with (folder/'combined.log').open('ab') as file:file.write(('['+stream+'] ').encode()+data+(b'' if data.endswith(b'\n') else b'\n'))
                                if item['bytes']>=1024*1024:item['logLimit']=True;job.close()
                    except Exception as error:
                        with self.lock:item['readerError']=str(error);job.close()
                reader=threading.Thread(target=consume,daemon=True);reader.start()
                while process.poll() is None:
                    if time.monotonic()>deadline:stop_reason='timeout';job.close();break
                    if item.get('stopRequested'):stop_reason='stopped';job.close();break
                    time.sleep(.05)
                process.wait(timeout=5);reader.join(timeout=5)
                if reader.is_alive():job.close();reader.join(timeout=2)
            item['exitCode']=process.wait(timeout=5)
            if item.get('stopRequested'):stop_reason='stopped'
            if item.get('logLimit'):stop_reason='log_limit'
            item['status']=stop_reason or ('succeeded' if item['exitCode']==0 else 'failed')
        except Exception as error:
            item.update(status='error',error=str(error))
        finally:
            if job:job.close()
            if approval.get('executionMode')=='container':
                from container_runner import cleanup
                item['containerCleanup']=cleanup(approval['dockerCommand'],approval['containerName'])
            if process:
                if process.poll() is None:process.kill()
                try:process.wait(timeout=5)
                except subprocess.TimeoutExpired:pass
                for pipe in (process.stdin,process.stdout):
                    if pipe:
                        try:pipe.close()
                        except OSError:pass
            if private_temp and private_temp.parent==pathlib.Path(tempfile.gettempdir()).resolve() and private_temp.name.startswith('nopilot-'):
                shutil.rmtree(private_temp,ignore_errors=True)
            try:
                snapshot=pathlib.Path(approval['cwd'])
                if snapshot.is_dir():
                    current=manifest(snapshot);original={f['path']:f['sha256'] for f in approval['files']};copied=[];total=0
                    for entry in current['files']:
                        if original.get(entry['path'])==entry['sha256']:continue
                        if len(copied)>=100 or total+entry['bytes']>8*1024*1024:continue
                        output_root=folder/'outputs';output_root.mkdir(exist_ok=True);target=contained(output_root,entry['path']);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(contained(snapshot,entry['path']),target);copied.append(entry);total+=entry['bytes']
                    item['outputs']=copied
            except Exception as error:item['outputCollectionWarning']=str(error)
            if item['status']=='succeeded' and approval['kind']=='install':
                try:
                    from environment_cache import record
                    record(self.workspace,approval)
                except Exception as error:item.update(status='error',error='Dependency receipt failed: '+str(error))
            with self.lock:item['finishedAt']=stamp();self.save(rid);self.jobs.pop(rid,None)
            with self.workspace.lock:
                self.workspace.running.discard(approval['projectId']);self.workspace.approvals[approval['id']]['status']=item['status'];self.workspace.save_approval(approval['id'])
            if self.on_complete:
                try:self.on_complete(dict(item))
                except Exception as error:item['callbackError']=str(error);self.save(rid)
            with self.lock:item['completionDelivered']=True;self.save(rid)
    def describe(self,rid):
        item=dict(self.runs[rid])
        if not item.get('completionDelivered',True) and item['status'] not in ('starting','running'):
            item['status']='running';item['finalizing']=True
        return item
    def stop(self,rid):
        with self.lock:
            if rid not in self.runs:raise ValueError('Run not found')
            item=self.runs[rid]
            if item['status'] not in ('starting','running'):return dict(item)
            item['stopRequested']=True;self.save(rid)
            if rid in self.jobs:self.jobs[rid].close()
            return dict(item)
    def log(self,rid,offset=0):
        with self.lock:
            if rid not in self.runs:raise ValueError('Run not found')
            path=self.root/rid/'combined.log';size=path.stat().st_size if path.exists() else 0
            offset=max(0,min(int(offset),size))
            if size-offset>65536:offset=size-65536
            if path.exists():
                with path.open('rb') as file:file.seek(offset);data=file.read(65536)
            else:data=b''
            return {'run':self.describe(rid),'text':data.decode('utf-8',errors='replace'),'offset':offset+len(data)}
    def close(self):
        for rid in list(self.runs):self.stop(rid)
        for thread in list(self.threads.values()):thread.join(timeout=8)

def child():
    # This helper can execute only a plan sent by the already-approved parent.
    plan=json.loads(sys.stdin.buffer.readline(128000));lock=threading.Lock()
    def emit(stream,text):
        with lock:sys.stdout.write(json.dumps({'stream':stream,'text':text},ensure_ascii=True)+'\n');sys.stdout.flush()
    for command in plan['commands']:
        emit('system',subprocess.list2cmdline(command)+'\n')
        process=subprocess.Popen(command,cwd=plan['cwd'],stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,shell=False)
        def relay(pipe,stream):
            decoder=codecs.getincrementaldecoder('utf-8')(errors='replace')
            while chunk:=pipe.read1(4096):
                text=decoder.decode(chunk)
                if text:emit(stream,text)
            text=decoder.decode(b'',final=True)
            if text:emit(stream,text)
            pipe.close()
        threads=[threading.Thread(target=relay,args=(process.stdout,'stdout')),threading.Thread(target=relay,args=(process.stderr,'stderr'))]
        for t in threads:t.start()
        code=process.wait()
        for t in threads:t.join()
        if code:return code
    return 0

if __name__=='__main__':
    if sys.argv[1:]==['--child']:raise SystemExit(child())
    raise SystemExit('Use the nopilot approval workflow to start a run')
