"""Small reproducible code -> local execution -> log feedback demonstration.

Only AST-equivalent print(17 * 19) is executable. This is not a sandbox.
"""
import argparse
import ast
import datetime
import json
import pathlib
import subprocess
import sys
from bridge import Bridge

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--result-dir',type=pathlib.Path,default=pathlib.Path('work/loop-demo'))
    args=parser.parse_args()
    run_id=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    folder=args.result_dir.resolve()/run_id
    folder.mkdir(parents=True,exist_ok=False)
    report={'runId':run_id,'status':'started'}
    def save():
        (folder/'result.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
    save()
    try:
        with Bridge() as bridge:
            prompt=f'Local harness demonstration {run_id}. Return exactly one Python code block containing only print(17 * 19). No imports, file operations, or explanation.'
            report['request']=prompt
            report['status']='submitting-code-request'
            save()
            generated=bridge.ask(prompt)
            report['generated']=generated
            save()
            if len(generated['code'])!=1:raise RuntimeError('Expected one complete code block')
            code=generated['code'][0]
            if ast.dump(ast.parse(code))!=ast.dump(ast.parse('print(17 * 19)')):
                raise RuntimeError('Code is outside this demonstration allowlist; refusing execution')
            program=folder/'generated.py'
            program.write_text(code+'\n',encoding='utf-8')
            result=subprocess.run([sys.executable,'-I','-S',str(program)],cwd=folder,capture_output=True,text=True,timeout=5)
            report['execution']={'exitCode':result.returncode,'stdout':result.stdout,'stderr':result.stderr}
            save()
            if result.returncode or result.stdout.strip()!='323':raise RuntimeError('Unexpected local execution result')
            marker='LOCAL_LOOP_OK_'+run_id
            report['status']='submitting-execution-log'
            save()
            report['acknowledgement']=bridge.ask('Local execution log:\n'+json.dumps(report['execution'])+'\nIf the calculation succeeded, reply exactly '+marker+' and nothing else.')
            report['passed']=report['acknowledgement']['answer'].strip()==marker
            report['status']='complete'
            save()
    except Exception as error:
        report.update(status='needs-attention',error=str(error))
        save()
        raise
    print(json.dumps({'result':str(folder/'result.json'),'passed':report['passed']},indent=2))

if __name__=='__main__':main()
