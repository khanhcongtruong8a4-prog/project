"""Action 3 provenance, focused tests and an A2 command which refuses entry."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from panda_closed_loop.config import Policy, digest
from panda_closed_loop.readiness import equation_crosswalk, m1_registry, gates
from panda_closed_loop.stepper import HeldTorqueHarness
from datetime import datetime,timezone
import argparse
import hashlib
import importlib.metadata
import importlib.util
import json
import os
import platform
import shutil
import subprocess


def serial(value):
    if hasattr(value,'tolist'):return value.tolist()
    if isinstance(value,dict):return {k:serial(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [serial(v) for v in value]
    return value


def write(path, value):
    path.write_text(json.dumps(serial(value),indent=2,allow_nan=False)+'\n')


def protected():
    spec=importlib.util.spec_from_file_location('legacy_hash_contract',ROOT/'scripts/run_validation.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    result=module.protected_files()
    for p in (ROOT/'policy').rglob('*'):
        if p.is_file():result[str(p.relative_to(ROOT))]=digest(p)
    return result


def handoff(out, state):
    tests=json.loads((out/'component_tests.json').read_text()) if (out/'component_tests.json').exists() else None
    rawc=json.loads((out/'t28_raw_c.json').read_text()) if (out/'t28_raw_c.json').exists() else None
    point=tests.get('diagnostics',{}).get('PANDA_APPROVED_INITIAL_COMPONENT') if tests else None
    text=f'''# Action 3 review handoff — v1.2.1

Run: `{out.relative_to(ROOT)}`. Result: **{state['status']}**.
All source/code/policy hashes, exact commands, effective configuration and logs
are in this run. New source/test snapshots are retained. Original source
archives, LaTeX, workbook, v1.2.0 evidence and human signatures were not edited.

## Component status

| Item | Result |
| --- | --- |
| Policy bytes, equation-source hashes, workbook cells | See source_audit.json; canonical equation files match |
| Momentum observer, Slotine-Li, 43 robust rows, hard QP, RK4 and contracts | {str(tests['overall_pass'])+'; '+str(tests['tests_run'])+' tests executed' if tests else 'NOT_RUN'} |
| T28 independent raw-C convention check | {'PASS (22 poses x 3 FD steps)' if rawc and rawc['overall_pass'] else 'NOT_RUN/FAIL'} |
| Preserved source/Pinocchio/MuJoCo baseline regression | {state.get('legacy_status','NOT_RUN')} |
| Approved Panda initial midpoint hard-QP feasibility | {point['feasibility'] if point else 'NOT_RUN in this run'} |
| Official A2 / full A2 2x2 refinement | NOT_RUN / BLOCKED |
| Complete T27 / G2.5 | NOT_RUN; solver fixtures and static point check are not these experiments |
| A3 / Level 1 / publication experiments | NOT_RUN / NO-GO |

## Critical static component result

Current run contains point diagnostics: **{bool(point)}**. The numerical values
below describe the retained point fixture; consult the current component JSON
before attributing them to this run if a test was not executed.

At the approved q0 midpoint, qdot=0 and varpi0=0.02*tau_max, the paired speed
rows require `abs(M^-1)@varpi0 <= alpha_v*vmax`. This necessary condition fails
for joints 1,3,4,5,6,7. For joint 1 it is approximately 93.325 versus 10.875
rad/s^2. ProxQP returns PRIMAL_INFEASIBLE. No torque is applied and no plant
state is advanced. This is configuration/point-specific evidence, not a global
impossibility theorem or a completed G2.5 screen. No gain/disturbance/bound was
retuned or replaced to obtain a pass. The passing unit test verifies detection
and stop behavior; it does not label the infeasible configuration feasible.

## Numerical conventions and limitations

- Observer z is integrated with plant q/qd using coupled RK4, actual held torque
  and stage state measurements. This is a declared COMPONENT convention; the
  approved policy's observer-update field remains null. Its independent dhat-ODE
  comparison does not validate a real sampled/delayed observer envelope.
- Controller and safety QP update once per Delta; applied torque is held for
  all RK4 stages. True disturbance enters only the plant; truth is logged for
  diagnosis after control computation. Replanning preserves z, global time and
  the propagated envelope. The deterministic reference is a measured-state
  fixture, not an optimized Stage-1 solution.
- Dense ProxQP 0.7.2 uses the supplied settings. Each component solve is cold;
  this is not an approved future warm-start policy. Actual normalized primal,
  scaled stationarity, complementarity, duality gap and raw negative slacks are
  retained. Numerical acceptance is not a proof of invariance or solver error.
- T28 forms a Christoffel reference from five-point derivatives of independent
  source-built Pinocchio CRBA M, never target dM. Raw library C is diagnostic
  only; FD comparisons at 22 states are not a global convention proof.
- Recovery is DISABLED because K_b, gamma and discrete recovery semantics are
  not supplied. A hard-QP failure requests replan/protective stop and provides
  no fabricated safe torque. The torque-box projection alone is tested.
- M1 domains/constants, derivative/tube bounds, estimator policy and discrete
  observer justification remain OPEN in M1_requirements.json. No null was
  replaced by zero. Planner envelopes/reserves and energy comparisons are not
  fabricated or used to clear A2.
- The source archive and main.tex differ from policy hashes. The two canonical
  equation files match. Manuscript build-revision acceptance remains open.
- The T29 CSV's old NOT_APPROVED status is preserved; v1.2.1 C6 explicitly
  approves the protocol row-scale rule, not a nonexistent T29 worksheet.

## Reproduce

```bash
.venv/bin/python scripts/action3.py preflight
.venv/bin/python scripts/action3.py validate
.venv/bin/python scripts/action3.py a2  # intentionally exits 2 with blockers
```

The validate command includes all established dynamics/source/Pinocchio/MuJoCo
tests. Inspect per-test JSON and logs, not only aggregate counts. Every call
creates a new run directory, retaining failures and earlier outputs.

## Gates

A1 GO. A2 NO-GO/HOLD under current inputs and initial-QP result. A3, Level 1
and publication NO-GO. Owner design acceptance is recorded in the supplied
policy; it is not a second-person signature. No official A2, planner comparison
or certification run was executed.

## Exactly three prioritized next actions

| Priority | Owner | Artifact | Objective acceptance criterion |
| --- | --- | --- | --- |
| 1 | Controls lead + project owner | Versioned disposition of the midpoint speed-row contradiction | Show all paired robust speed rows admit an acceleration under an explicitly reviewed configuration, retaining valid initial observer bounds; no hidden retuning |
| 2 | Theory/model-bounds lead | Completed hashed M1 domain/constant registry | Every used bound has domain, formula, units, provenance, estimator grid/seed/budget and honest evidence level; discrete observer assumptions explicitly resolved |
| 3 | Numerical/experimental lead + independent reviewer | Approved execution conventions and complete A2/T27 entry plan | Inspect component/T28/regression evidence, resolve source revision and observer/hold/solver settings, record required reviews, then explicitly authorize the A2 refinement run; do not infer authorization from this package |
'''
    (out/'REVIEW_HANDOFF.md').write_text(text)
    (ROOT/'reports/ACTION3_REVIEW_HANDOFF.md').write_text(text)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=['preflight','validate','a2'])
    args=parser.parse_args()
    now=datetime.now(timezone.utc)
    out=ROOT/'runs/action3'/now.strftime('%Y%m%dT%H%M%S%fZ')
    out.mkdir(parents=True,exist_ok=False)
    record={'start_utc':now.isoformat(),'mode':args.mode,'scope':'ACTION3_COMPONENTS_NOT_OFFICIAL_A2',
            'python':sys.version,'platform':platform.platform(),'seed':20261101,'commands':[],'status':'PREFLIGHT'}
    before=protected();record['code_and_input_hashes']=before
    write(out/'source_hashes.json',before)
    for folder in ['src','tests','scripts']:
        for p in (ROOT/folder).rglob('*.py'):
            if '__pycache__' not in p.parts:
                target=out/'source_snapshot'/p.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,target)
    env=os.environ.copy();env['PANDA_EVIDENCE_DIR']=str(out);env['PYTHONDONTWRITEBYTECODE']='1'
    exit_code=0
    def execute(name,command,expected=0):
        started=datetime.now(timezone.utc).isoformat()
        result=subprocess.run(command,cwd=ROOT,env=env,capture_output=True,text=True)
        (out/(name+'.log')).write_text(result.stdout+result.stderr)
        record['commands'].append({'name':name,'command':command,'cwd':str(ROOT),'start_utc':started,
            'finish_utc':datetime.now(timezone.utc).isoformat(),'actual_exit_code':result.returncode,'expected_exit_code':expected,
            'matched_expected_exit':result.returncode==expected,'log':name+'.log'})
        print(name+': '+('PASS' if result.returncode==expected else 'FAIL'),flush=True)
        return result.returncode==expected
    try:
        policy=Policy.load()
        write(out/'effective_configuration.json',{'approved_policy_read_only':policy.raw,
            'policy_sha256':digest(policy.path),'observer_numerical_convention':HeldTorqueHarness.observer_semantics,
            'QP_initialization':'COLD_PER_COMPONENT_UPDATE; full warm-start policy not approved',
            'packages':{d.metadata['Name']:d.version for d in importlib.metadata.distributions()},
            'equations':{'02_mm&nc.tex':digest(ROOT/'sources/manuscript_v1.2.1/02_mm&nc.tex'),
                         '03_contribution.tex':digest(ROOT/'sources/manuscript_v1.2.1/03_contribution.tex')},
            'official_A2_authorized':False})
        write(out/'source_audit.json',policy.source_audit())
        write(out/'equation_to_code.json',equation_crosswalk())
        write(out/'M1_requirements.json',m1_registry(policy))
        if args.mode=='a2':
            record['status']='REFUSED_OFFICIAL_A2';exit_code=2
        elif args.mode=='preflight':
            record['status']='COMPONENT_INPUTS_AVAILABLE_A2_HOLD'
        else:
            ok=execute('component_tests',[sys.executable,str(ROOT/'tests/test_action3.py'),'--report',str(out/'component_tests.json')])
            ok=execute('T28_raw_C',[sys.executable,str(ROOT/'tests/test_t28_raw_c.py'),'--report',str(out/'t28_raw_c.json')]) and ok
            legacy=execute('preserved_v120_regression',[sys.executable,str(ROOT/'scripts/run_validation.py')])
            record['legacy_status']='PASS' if legacy else 'FAIL'
            if (ROOT/'reports/latest.json').exists():
                write(out/'legacy_run_pointer.json',json.loads((ROOT/'reports/latest.json').read_text()))
            guard=execute('A2_entry_refusal',[sys.executable,str(ROOT/'scripts/action3.py'),'a2'],expected=2)
            ok=execute('dependency_check',[sys.executable,'-m','pip','check']) and ok and legacy and guard
            record['status']='PASS_COMPONENTS_AND_REGRESSIONS_A2_HOLD' if ok else 'FAIL_COMPONENT_OR_REGRESSION'
            exit_code=0 if ok else 1
            if record['status']=='PASS_COMPONENTS_AND_REGRESSIONS_A2_HOLD':
                component=json.loads((out/'component_tests.json').read_text())
                if component['tests_run']<1 or not component['overall_pass']:
                    raise RuntimeError('No completed passing component tests')
        diagnostics=json.loads((out/'component_tests.json').read_text())['diagnostics'] if (out/'component_tests.json').exists() else None
        write(out/'stage_gates.json',gates(policy,diagnostics))
        if before!=protected():
            raise RuntimeError('Protected code/input/source/review files changed during run')
        record['protected_files_unchanged']=True
    except Exception as error:
        record.update(status='FAIL',error=str(error));exit_code=1
        print(error,file=sys.stderr)
    finally:
        record['finish_utc']=datetime.now(timezone.utc).isoformat()
        write(out/'run.json',record)
        write(ROOT/'reports/action3_latest.json',{'run_directory':str(out.relative_to(ROOT)),'status':record['status'],'run_sha256':digest(out/'run.json')})
        if args.mode=='validate':handoff(out,record)
    print(json.dumps({'status':record['status'],'run_directory':str(out.relative_to(ROOT))},indent=2))
    raise SystemExit(exit_code)


if __name__=='__main__':main()
