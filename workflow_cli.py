"""Human-reviewed local dev and interactive resumable explorer commands for CMD."""
import argparse
import json
import pathlib
from data_lock import default_directory
import time
from dev_workspace import Workspace,inspect_zip
from execution import Runner

def emit(value):print(json.dumps(value,ensure_ascii=False,indent=2),flush=True)
def review(approval,workspace):
    print('\nHUMAN REVIEW — approval '+approval['id'],flush=True)
    emit({key:approval[key] for key in ('kind','revision','cwd','commands','timeout')})
    print('Container: no network, read-only project, temporary writes and stdout only.' if approval.get('executionMode')=='container' else 'Runs with your Windows user privileges. A venv is not a security sandbox.',flush=True)
    if approval.get('requirements'):print(approval['requirements'])
    else:
        try:print(workspace.read(approval['projectId'],approval['entrypoint'])['content'][:16000])
        except (ValueError,UnicodeError):pass
    answer=input('Review the full source if needed. Type RUN '+approval['id'][:8]+' to approve once, anything else rejects: ').strip()
    return answer=='RUN '+approval['id'][:8]
def follow(runner,rid):
    offset=0
    try:
        while True:
            result=runner.log(rid,offset);offset=result['offset'];print(result['text'],end='',flush=True)
            if result['run']['status'] not in ('starting','running'):emit(result['run']);return result['run']
            time.sleep(.2)
    except KeyboardInterrupt:
        runner.stop(rid);print('\nStop requested for the entire process tree.',flush=True);raise

def paused_command(app,cid,item,line):
    """Keep the executor/browser alive while a CLI user supplies human input."""
    line=line.strip()
    if line in ('','/quit'):return False
    if line=='/resume':
        app.explorers.control(cid,item['id'],'resume');app.queue(cid,'explorer',task_id=item['id']);return True
    if line.startswith('/iterate '):
        app.explorers.control(cid,item['id'],'iterate',{'task':line[len('/iterate '):]});app.queue(cid,'explorer',task_id=item['id']);return True
    if line.startswith('/upload '):
        from cli import words
        parts=words(line)
        if len(parts)!=2:raise ValueError('Use /upload "absolute path"')
        path=pathlib.Path(parts[1]).resolve()
        if not path.is_file():raise ValueError('File not found')
        def attach():app.ensure(cid);return app.harness.upload(path)
        emit(app.executor.submit(attach).result(timeout=120));return True
    raise ValueError('Use /upload "path", /resume, /iterate text, or /quit')

def dev_main(argv):
    p=argparse.ArgumentParser(description='Offline Python project workspaces; install/run require an interactive human review')
    p.add_argument('--data-dir',type=pathlib.Path,default=default_directory('work/nopilot-cli/dev'))
    sub=p.add_subparsers(dest='command',required=True)
    a=sub.add_parser('inspect');a.add_argument('zip',type=pathlib.Path)
    a=sub.add_parser('extract');a.add_argument('zip',type=pathlib.Path)
    sub.add_parser('list')
    a=sub.add_parser('read');a.add_argument('project');a.add_argument('path')
    a=sub.add_parser('diff');a.add_argument('project');a.add_argument('checkpoint')
    a=sub.add_parser('rollback');a.add_argument('project');a.add_argument('checkpoint')
    a=sub.add_parser('plan');a.add_argument('project')
    a=sub.add_parser('task');a.add_argument('project');a.add_argument('task',choices=('install','start','check'))
    for name in ('run','install'):
        a=sub.add_parser(name);a.add_argument('project');a.add_argument('entrypoint',nargs='?',default='run.py' if name=='run' else 'requirements.txt');a.add_argument('--arg',action='append',default=[]);a.add_argument('--timeout',type=int,default=120)
        a.add_argument('--execution-mode',choices=('host','container'),default='host')
    args=p.parse_args(argv)
    if args.command=='inspect':emit(inspect_zip(args.zip));return 0
    from data_lock import DataLock
    data_lock=DataLock(args.data_dir);workspace=Workspace(args.data_dir);runner=Runner(workspace,args.data_dir/'artifacts'/'runs')
    try:
        if args.command=='extract':emit(workspace.extract(args.zip))
        elif args.command=='list':emit(workspace.list())
        elif args.command=='read':emit(workspace.read(args.project,args.path))
        elif args.command=='diff':emit(workspace.diff(args.project,args.checkpoint))
        elif args.command=='rollback':emit(workspace.rollback(args.project,args.checkpoint))
        elif args.command=='plan':
            from project_contract import read_contract
            emit(read_contract(workspace.source(args.project)))
        else:
            if args.command=='task':
                from project_contract import propose_task
                approval=propose_task(workspace,args.project,args.task,workspace.current(args.project)['revision'])
            else:approval=workspace.propose(args.project,kind='install' if args.command=='install' else 'run',entrypoint=args.entrypoint,arguments=args.arg,timeout=args.timeout,execution_mode=args.execution_mode)
            if review(approval,workspace):
                result=follow(runner,runner.start(approval['id'])['id']);return 0 if result['status']=='succeeded' else 1
            workspace.reject(approval['id']);print('Rejected. No process started.')
        return 0
    finally:runner.close();data_lock.close()

def explorer_main(argv):
    from web_server import Application
    p=argparse.ArgumentParser(description='Resumable explorer with human turn grants and approved dev execution')
    p.add_argument('--data-dir',type=pathlib.Path,default=default_directory('work/nopilot-workflow'))
    sub=p.add_subparsers(dest='command',required=True)
    a=sub.add_parser('start');a.add_argument('url');a.add_argument('-q','--question',required=True)
    sub.add_parser('list')
    a=sub.add_parser('resume');a.add_argument('task_id')
    args=p.parse_args(argv)
    from data_lock import DataLock
    data_lock=DataLock(args.data_dir);app=Application(args.data_dir)
    try:
        if args.command=='list':
            for cid in app.conversations:
                for item in app.explorers.list(cid):emit(item)
            return 0
        if args.command=='start':
            cid=app.create(args.question[:52])['id'];item=app.explorers.create(cid,args.url,args.question)
            app.queue(cid,'explorer',task_id=item['id'])
        else:
            item=app.explorers.tasks.get(args.task_id)
            if not item:raise ValueError('Explorer not found')
            cid=item['conversationId']
            print('Recovery opens a fresh browser at the last URL; no previous mutations are replayed. Inspect any interrupted Teams response first.')
            if input('Type RECOVER '+item['id'][:8]+' after reviewing Teams: ').strip()!='RECOVER '+item['id'][:8]:return 0
            app.explorers.control(cid,item['id'],'recover',{'acknowledge':True});app.queue(cid,'explorer',task_id=item['id'])
        print('Explorer ID: '+item['id'],flush=True);last=None;reviewed=set()
        while True:
            marker=(item['status'],item['turns'])
            if marker!=last:print(f'{item["status"]}: {item["turns"]}/{item["budget"]} turns',flush=True);last=marker
            if item['status']=='waiting_turns':
                if input('Budget exhausted. Grant 20 more turns? [y/N] ').strip().lower()!='y':break
                app.explorers.control(cid,item['id'],'grant',{'turns':20});app.queue(cid,'explorer',task_id=item['id'])
            elif item['status']=='awaiting_approval' and item.get('approvalId') not in reviewed:
                aid=item['approvalId'];reviewed.add(aid);approval=app.workspace(cid).approvals[aid]
                if review(approval,app.workspace(cid)):
                    run=app.dev_action(cid,'approve',{'approvalId':aid});follow(app.runner(cid),run['id'])
                else:app.dev_action(cid,'reject',{'approvalId':aid})
            elif item['status']=='completed':
                print(item.get('answer',''),flush=True);task=input('Iterate in the same browser/workspace (blank to exit): ').strip()
                if not task:break
                app.explorers.control(cid,item['id'],'iterate',{'task':task});app.queue(cid,'explorer',task_id=item['id'])
            elif item['status']=='paused':
                try:
                    if not paused_command(app,cid,item,input('Paused: /upload "path", /resume, /iterate task, or /quit: ')):break
                except ValueError as error:print(str(error),flush=True)
            elif item['status'] in ('needs_recovery','closed'):
                emit({k:item.get(k) for k in ('id','status','error','recoveryReason')});break
            time.sleep(.2)
        return 0
    except KeyboardInterrupt:
        for task in app.explorers.tasks.values():task['pauseRequested']=True
        print('\nPause requested; any submitted prompt is not automatically resent.');return 130
    finally:app.shutdown();data_lock.close()
