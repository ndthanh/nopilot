"""Private local Git history and reviewed full-ZIP updates for managed projects."""
import difflib,json,os,pathlib,shutil,subprocess,time,uuid
from dev_workspace import contained,plain,manifest,save_json,Workspace,relative

MESSAGE='NOPILOT_COMMIT_MESSAGE.txt'

def git(folder,*args):
    exe=shutil.which('git')
    if not exe:raise ValueError('Git chưa có trong PATH. Cài Git rồi thử lại; source chưa được áp dụng.')
    env={k:v for k,v in os.environ.items() if not k.upper().startswith('GIT_')}
    env.update(GIT_CONFIG_NOSYSTEM='1',GIT_CONFIG_GLOBAL=os.devnull,GIT_TERMINAL_PROMPT='0')
    command=[exe,'-c','core.longpaths=true','-c','core.hooksPath='+str(folder.parent/'disabled-git-hooks'),'-c','commit.gpgSign=false','-c','core.autocrlf=false','-c','user.name=Nopilot','-c','user.email=nopilot@localhost','-C',str(folder),*args]
    result=subprocess.run(command,env=env,capture_output=True,timeout=60,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    if result.returncode:raise ValueError('Git: '+result.stderr.decode('utf-8',errors='replace')[-1500:])
    return result.stdout.decode('utf-8',errors='replace')

def message(value):
    if not isinstance(value,str) or not value.strip() or len(value)>4000 or '\x00' in value:raise ValueError('Commit message cần1..4000ký tự')
    value=value.strip()
    if len(value.splitlines()[0])>200:raise ValueError('Dòng đầu commit message tối đa200ký tự')
    return value

def suggested(source):
    path=contained(source,MESSAGE)
    if path.is_file() and path.stat().st_size<=16000:
        try:return message(path.read_text(encoding='utf-8-sig'))
        except (ValueError,UnicodeError):pass
    return None

def repo(workspace,pid):
    path=workspace.folder(pid)/'git-worktree'
    if path.exists():plain(path)
    if (path/'.git').exists():plain(path/'.git')
    return path

def status(workspace,pid):
    path=repo(workspace,pid)
    if not (path/'.git').is_dir():return {'initialized':False}
    try:return {'initialized':True,'head':git(path,'rev-parse','HEAD').strip(),'log':git(path,'log','-8','--format=%h %s').strip()}
    except (OSError,ValueError,subprocess.TimeoutExpired) as error:return {'initialized':True,'error':str(error)}

def source_manifest(source):
    value=manifest(source)
    for base,dirs,files in os.walk(source):
        if any(name.casefold()=='.git' for name in dirs+files):raise ValueError('Source ZIP không được chứa .git')
    if any('.git' in [p.casefold() for p in f['path'].split('/')] for f in value['files']):raise ValueError('Source ZIP không được chứa .git')
    return value

def sync(source,path):
    value=source_manifest(source)
    # This directory is the private mirror owned by this project, never a user checkout.
    for child in path.iterdir():
        if child.name=='.git':continue
        plain(child);resolved=child.resolve()
        if not resolved.is_relative_to(path.resolve()) or resolved==path.resolve():raise ValueError('Git mirror path escaped project')
        if child.is_dir():
            for base,dirs,files in os.walk(child):
                for name in dirs+files:plain(pathlib.Path(base)/name)
            shutil.rmtree(child)
        else:child.unlink()
    for item in value['files']:
        target=contained(path,item['path']);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(contained(source,item['path']),target)

def commit(workspace,pid,text):
    text=message(text);source=workspace.source(pid);source_manifest(source);path=repo(workspace,pid)
    path.mkdir(exist_ok=True)
    if not (path/'.git').exists():git(path,'init')
    sync(source,path);git(path,'add','--force','--all','--','.')
    if not git(path,'diff','--cached','--name-only').strip():return status(workspace,pid)
    file=workspace.folder(pid)/('commit-message-'+uuid.uuid4().hex+'.txt');file.write_text(text,encoding='utf-8')
    try:git(path,'commit','--file',str(file))
    finally:file.unlink(missing_ok=True)
    return status(workspace,pid)

def diff(before,after):
    old={f['path']:f for f in source_manifest(before)['files']};new={f['path']:f for f in source_manifest(after)['files']};changes=[];chunks=[];size=0
    for name in sorted(old.keys()|new.keys()):
        if old.get(name)==new.get(name):continue
        kind='added' if name not in old else 'deleted' if name not in new else 'modified';changes.append({'path':name,'change':kind})
        if size>=200000:continue
        try:
            if max(old.get(name,{}).get('bytes',0),new.get(name,{}).get('bytes',0))>1024*1024:raise UnicodeError()
            a=contained(before,name).read_text(encoding='utf-8').splitlines(True) if name in old else []
            b=contained(after,name).read_text(encoding='utf-8').splitlines(True) if name in new else []
            text=''.join(difflib.unified_diff(a,b,fromfile='before/'+name,tofile='after/'+name))
        except UnicodeError:text=kind+': '+name+' (binary/large file)\n'
        text=text[:200000-size];chunks.append(text);size+=len(text)
    return changes,''.join(chunks)

def replace_source(workspace,pid,source):
    target=workspace.source(pid)
    for entry in workspace.current(pid)['files']:contained(target,entry['path']).unlink()
    for base,dirs,files in os.walk(target,topdown=False):
        for name in dirs:pathlib.Path(base,name).rmdir()
    for entry in manifest(source)['files']:
        dest=contained(target,entry['path']);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(contained(source,entry['path']),dest)

def preview(workspace,pid,archive,expected_hash):
    workspace.idle(pid);base=workspace.current(pid);token=uuid.uuid4().hex
    staging=Workspace(workspace.folder(pid)/'updates'/token);candidate=staging.extract(archive,expected_hash)
    source=staging.source(candidate['id']);source_manifest(source)
    from project_contract import read_contract
    contract=read_contract(source)
    if contract['status']=='invalid':raise ValueError('nopilot.json mới không hợp lệ: '+contract['error'])
    changes,text=diff(workspace.source(pid),source)
    value={'id':token,'projectId':pid,'projectName':workspace.projects[pid]['name'],'sourceDirectory':str(workspace.source(pid)),'baseRevision':base['revision'],'candidateId':candidate['id'],'candidateRevision':candidate['revision'],'zipSha256':candidate['zipSha256'],'commitMessage':suggested(source) or '', 'changes':changes,'diff':text,'expiresAt':time.time()+900,'contractStatus':contract['status']}
    save_json(workspace.folder(pid)/'updates'/token/'review.json',value);return value

def apply(workspace,pid,token,revision,text):
    if not isinstance(token,str) or len(token)!=32 or any(c not in '0123456789abcdef' for c in token):raise ValueError('Invalid update review')
    text=message(text)
    with workspace.lock:
        workspace.idle(pid);folder=workspace.folder(pid)/'updates'/token
        value=json.loads((folder/'review.json').read_text(encoding='utf-8'))
        if value.get('applied') or time.time()>value['expiresAt']:raise ValueError('Review đã dùng hoặc hết hạn; xem diff lại')
        if revision!=value['baseRevision'] or workspace.current(pid)['revision']!=revision:raise ValueError('Source đã đổi; xem diff lại trước khi apply')
        staging=Workspace(folder);source=staging.source(value['candidateId'])
        if manifest(source)['revision']!=value['candidateRevision']:raise ValueError('Staged ZIP changed; preview again')
        commit(workspace,pid,'chore: checkpoint local source before Copilot update')
        checkpoint=workspace.checkpoint(pid,'Before Copilot ZIP update')
        target=workspace.source(pid)
        try:
            replace_source(workspace,pid,source)
            result=commit(workspace,pid,text)
        except Exception:
            replace_source(workspace,pid,workspace.folder(pid)/'checkpoints'/checkpoint['id']/'files')
            # Restore the private mirror/index to the source checkpoint as well.
            try:sync(target,repo(workspace,pid));git(repo(workspace,pid),'add','--force','--all','--','.')
            except Exception:pass
            raise
        value.update(applied=True,commit=result.get('head'));save_json(folder/'review.json',value)
        return {'project':workspace.describe(pid),'checkpoint':checkpoint['id'],'git':result,'changes':value['changes']}
