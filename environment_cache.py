"""Project-local dependency receipts; source edits do not invalidate a matching venv."""
import hashlib,json,pathlib,sys

def sha(path):return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()
def dependency_key(source):
    req=pathlib.Path(source)/'requirements.txt'
    pins=sorted(line.strip() for line in req.read_text(encoding='utf-8').splitlines() if line.strip() and not line.lstrip().startswith('#')) if req.is_file() else None
    value={'pinnedRequirements':pins,'pythonSha256':sha(sys.executable),'pythonVersion':sys.version,'registry':'https://pypi.org/simple'}
    return hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()

def state(workspace,pid,source=None):
    folder=workspace.folder(pid);exe=folder/'venv/Scripts/python.exe';receipt=folder/'environment.json'
    try:
        from dev_workspace import plain
        for path in (receipt,folder/'venv',exe.parent,exe):plain(path)
        value=json.loads(receipt.read_text(encoding='utf-8'))
        ready=exe.is_file() and value['key']==dependency_key(source or workspace.source(pid)) and value['runtimeSha256']==sha(exe)
        return {'ready':bool(ready),'reason':'Requirements và Python khớp; dùng lại venv.' if ready else 'Requirements/Python/runtime đã đổi; cần cài lại.','installedAt':value.get('installedAt')}
    except (OSError,ValueError,KeyError,TypeError):return {'ready':False,'reason':'Chưa có receipt cài dependency thành công.'}

def record(workspace,approval):
    if approval['kind']!='install' or approval['entrypoint']!='requirements.txt':return
    from dev_workspace import save_json,stamp
    pid=approval['projectId'];exe=workspace.folder(pid)/'venv/Scripts/python.exe'
    save_json(workspace.folder(pid)/'environment.json',{'key':dependency_key(approval['cwd']),'runtimeSha256':sha(exe),'installedAt':stamp(),'approvalId':approval['id']})
