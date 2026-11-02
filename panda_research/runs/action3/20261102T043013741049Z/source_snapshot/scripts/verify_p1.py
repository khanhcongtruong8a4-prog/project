"""Retain engineering reproductions; never runs a P1 prehold or official A2."""
from pathlib import Path
import sys
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
import importlib.metadata
import json
import os
import platform
import shutil
import subprocess
from datetime import datetime,timezone
from panda_closed_loop.config import digest


def snapshot():
    return {str(p.relative_to(ROOT)):digest(p) for folder in ['src','tests','scripts','policy','inputs/p1_v1.2.2']
        for p in (ROOT/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts}


def main():
    out=ROOT/'runs/p1_verification'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    out.mkdir(parents=True,exist_ok=False)
    before=snapshot()
    record={'scope':'ENGINEERING_REPRODUCTION_NOT_INDEPENDENT_REVIEW_NOT_A2',
        'start_utc':datetime.now(timezone.utc).isoformat(),'python':sys.version,'platform':platform.platform(),
        'packages':{d.metadata['Name']:d.version for d in importlib.metadata.distributions()},
        'source_hashes':before,'commands':[],'official_A2_executed':False,'P1_physical_prehold_executed':False,
        'independent_reviewer_signature':None,'overall_pass':False,'status':'RUNNING'}
    def checkpoint():
        (out/'verification.json').write_text(json.dumps(record,indent=2)+'\n')
    checkpoint()
    env=os.environ.copy();env['PYTHONDONTWRITEBYTECODE']='1'
    commands=[('screen_tests',[sys.executable,'tests/test_p1_feasibility.py','--report',str(out/'screen_tests.json')]),
        ('draft_completeness',[sys.executable,'scripts/check_a2_plan.py','--output',str(out/'checklist')]),
        ('preserved_action3_validation',[sys.executable,'scripts/action3.py','validate'])]
    ok=True
    for name,command in commands:
        start=datetime.now(timezone.utc).isoformat()
        r=subprocess.run(command,cwd=ROOT,env=env,capture_output=True,text=True)
        (out/(name+'.log')).write_text(r.stdout+r.stderr)
        record['commands'].append({'name':name,'command':command,'cwd':str(ROOT),'start_utc':start,
            'finish_utc':datetime.now(timezone.utc).isoformat(),'exit_code':r.returncode,'expected_exit_code':0,'log':name+'.log'})
        ok=ok and r.returncode==0
        checkpoint()
        try:print(name+(': PASS' if r.returncode==0 else ': FAIL'),flush=True)
        except BrokenPipeError:pass
    record['action3_pointer']=json.loads((ROOT/'reports/action3_latest.json').read_text())
    record['protected_files_unchanged']=before==snapshot()
    record['overall_pass']=ok and record['protected_files_unchanged']
    record['status']='PASS' if record['overall_pass'] else 'FAIL'
    record['finish_utc']=datetime.now(timezone.utc).isoformat()
    checkpoint()
    (ROOT/'reports/p1_verification_latest.json').write_text(json.dumps({'run_directory':str(out.relative_to(ROOT)),
        'verification_sha256':digest(out/'verification.json'),'overall_pass':record['overall_pass']},indent=2)+'\n')
    print(json.dumps({'run_directory':str(out.relative_to(ROOT)),'overall_pass':record['overall_pass']},indent=2))
    return 0 if record['overall_pass'] else 1


if __name__=='__main__':raise SystemExit(main())
