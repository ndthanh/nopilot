"""Opt-in Linux container execution. No silent fallback to host privileges."""
import json
import shutil
import subprocess

HOST='npipe:////./pipe/dockerDesktopLinuxEngine'

def docker_command():
    exe=shutil.which('docker')
    if not exe:raise ValueError('Container mode requires Docker Desktop Linux engine')
    return [exe,'--host',HOST]

def container_runtime(image='python:3.14-slim'):
    docker=docker_command()
    try:
        version=subprocess.run([*docker,'info','--format','{{.OSType}}'],capture_output=True,text=True,timeout=8,creationflags=subprocess.CREATE_NO_WINDOW)
        if version.returncode or version.stdout.strip()!='linux':raise ValueError('Docker Linux engine is unavailable. Start it explicitly; no host fallback was performed.')
        result=subprocess.run([*docker,'image','inspect','--format','{{.Id}}',image],capture_output=True,text=True,timeout=8,creationflags=subprocess.CREATE_NO_WINDOW)
        image_id=result.stdout.strip()
        if result.returncode or not image_id.startswith('sha256:') or len(image_id)!=71:raise ValueError('Container image is not installed. Prepare python:3.14-slim explicitly before proposing a container run.')
    except (OSError,subprocess.TimeoutExpired) as error:raise ValueError('Docker preflight failed; no host fallback: '+str(error)) from error
    return docker,image_id

def plan(docker,image_id,name,source,entrypoint,arguments):
    # Only the immutable approved source is mounted, read-only. No host outputs,
    # home/profile, environment credentials, socket, or network are forwarded.
    if ',' in str(source):raise ValueError('Container source paths cannot contain commas')
    bootstrap='import runpy,sys;sys.path.insert(0,"/workspace");sys.argv='+repr([entrypoint,*arguments])+';runpy.run_path('+repr('/workspace/'+entrypoint)+',run_name="__main__")'
    return [*docker,'run','--rm','--pull=never','--name',name,'--network=none','--read-only',
      '--cap-drop=ALL','--security-opt=no-new-privileges','--pids-limit=64','--memory=512m','--cpus=1',
      '--user=65534:65534','--tmpfs=/tmp:rw,nosuid,nodev,size=128m','--workdir=/tmp',
      '--mount','type=bind,source='+str(source)+',target=/workspace,readonly',image_id,'python','-I','-B','-u','-c',bootstrap]

def cleanup(command,name):
    try:
        result=subprocess.run([*command,'rm','-f',name],capture_output=True,text=True,timeout=10,creationflags=subprocess.CREATE_NO_WINDOW)
        return {'ok':result.returncode==0 or 'No such container' in result.stderr,'message':result.stderr[-800:]}
    except (OSError,subprocess.TimeoutExpired) as error:return {'ok':False,'message':'Container cleanup could not be confirmed: '+str(error)}
