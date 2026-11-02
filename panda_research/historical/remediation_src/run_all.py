"""Run the complete OFFLINE model-evidence workflow; no A2/A3 simulation."""
from pathlib import Path
from datetime import datetime, timezone
import ast
import hashlib
import importlib.metadata
import json
import platform
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


class RemoveDocstrings(ast.NodeTransformer):
    def strip(self,node):
        self.generic_visit(node)
        if node.body and isinstance(node.body[0],ast.Expr) and isinstance(node.body[0].value,ast.Constant) and isinstance(node.body[0].value.value,str):
            node.body=node.body[1:]
        return node
    visit_Module=strip
    visit_FunctionDef=strip
    visit_ClassDef=strip


def assert_integrity():
    hashes=json.loads((ROOT/'reports/baseline_hashes.json').read_text())
    checks=[]
    for row in hashes['zip_members']:
        checks.append({'file':'baseline/'+row['file'],'expected_sha256':row['sha256'],
                       'observed_sha256':sha(ROOT/'baseline'/row['file'])})
    for row in hashes['uploaded_inputs']:
        checks.append({'file':'inputs/'+row['name'],'expected_sha256':row['sha256'],
                       'observed_sha256':sha(ROOT/'inputs'/row['name'])})
    for row in json.loads((ROOT/'reports/source_git_verification.json').read_text())['checks']:
        checks.append({'file':'sources/'+row['file'],'expected_sha256':row['sha256'],
                       'observed_sha256':sha(ROOT/'sources'/row['file'])})
    for c in checks:c['result']='PASS' if c['expected_sha256']==c['observed_sha256'] else 'FAIL'
    result={'checks':checks,'overall_pass':all(x['result']=='PASS' for x in checks)}
    (ROOT/'reports/preservation_check.json').write_text(json.dumps(result,indent=2)+'\n')
    if not result['overall_pass']:raise RuntimeError('Input/baseline/source bytes changed')


def main():
    log={'start_utc':datetime.now(timezone.utc).isoformat(),'python':sys.version,
         'platform':platform.platform(),'executable':sys.executable,'commands':[]}
    log['packages']={d.metadata['Name']:d.version for d in importlib.metadata.distributions()}
    steps=['run_reproduction.py','prepare_corrected_tests.py','run_phase3a_tests.py',
           'verify_primary_sources.py','compare_external_dynamics.py','test_reference_sensitivity.py',
           'prepare_scenario_b_suite.py']
    status=0
    try:
        assert_integrity()
        command=['pdftotext','-layout',str(ROOT/'sources/supplement.pdf'),str(ROOT/'sources/supplement_layout.txt')]
        extraction=subprocess.run(command,cwd=ROOT,capture_output=True,text=True)
        log['commands'].append({'command':command,'cwd':str(ROOT),'exit_code':extraction.returncode,
                                'stdout':extraction.stdout,'stderr':extraction.stderr})
        if extraction.returncode:raise RuntimeError('Primary-source PDF extraction failed')
        version=subprocess.run(['pdftotext','-v'],capture_output=True,text=True)
        log['pdftotext_version']=version.stderr.strip()
        for name in steps:
            command=[sys.executable,str(ROOT/'src'/name)]
            started=datetime.now(timezone.utc).isoformat()
            r=subprocess.run(command,cwd=ROOT,capture_output=True,text=True)
            filename='logs/verified_'+name.removesuffix('.py')+'.log'
            (ROOT/filename).write_text(r.stdout+r.stderr)
            log['commands'].append({'command':command,'cwd':str(ROOT),'started_utc':started,
                'finished_utc':datetime.now(timezone.utc).isoformat(),'exit_code':r.returncode,'log':filename})
            print(name, 'PASS' if r.returncode==0 else 'FAIL')
            if r.returncode:
                print(r.stdout,r.stderr)
                raise RuntimeError(f'{name} failed')
        trees=[RemoveDocstrings().visit(ast.parse((ROOT/folder/'panda_dynamics.py').read_text()))
               for folder in ('baseline','src')]
        equivalent=ast.dump(trees[0])==ast.dump(trees[1])
        (ROOT/'reports/evaluator_semantics.json').write_text(json.dumps({
            'method':'AST comparison with docstrings removed; no other AST nodes removed',
            'same_executable_AST':equivalent,'baseline_sha256':sha(ROOT/'baseline/panda_dynamics.py'),
            'working_sha256':sha(ROOT/'src/panda_dynamics.py')},indent=2)+'\n')
        if not equivalent:raise RuntimeError('Evaluator executable semantics changed')
        # Independently confirm the exact seeded inputs match original script.
        code="""import sys, numpy as np
sys.path.insert(0,'src')
from compare_external_dynamics import sample_cases
sys.path.insert(0,'runs/original')
import run_phase3a_tests as original
for a,b in zip(sample_cases(),(original.Q_CASES,original.QD_CASES,original.QDD_CASES)):
    np.testing.assert_array_equal(a,np.asarray(b))
print('Exact original q/qd/qdd arrays match external 22 cases.')
"""
        command=[sys.executable,'-c',code]
        r=subprocess.run(command,cwd=ROOT,capture_output=True,text=True)
        log['commands'].append({'command':command,'cwd':str(ROOT),'exit_code':r.returncode,'stdout':r.stdout,'stderr':r.stderr})
        if r.returncode:raise RuntimeError('Original case arrays mismatch')
        check=subprocess.run([sys.executable,'-m','pip','check'],cwd=ROOT,capture_output=True,text=True)
        log['commands'].append({'command':[sys.executable,'-m','pip','check'],'cwd':str(ROOT),
                                'exit_code':check.returncode,'stdout':check.stdout,'stderr':check.stderr})
        if check.returncode:raise RuntimeError('Dependency check failed')
        assert_integrity()
        log['status']='PASS_MODEL_EVIDENCE_WORKFLOW_ONLY'
    except Exception as error:
        log.update(status='FAIL',error=str(error));status=1
    finally:
        log['finish_utc']=datetime.now(timezone.utc).isoformat()
        (ROOT/'reports/verification_run.json').write_text(json.dumps(log,indent=2)+'\n')
    raise SystemExit(status)


if __name__=='__main__':main()
