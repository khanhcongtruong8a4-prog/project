"""Compute final gates and original-file preservation from executed evidence."""
from pathlib import Path
import sys
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];REPO=ROOT.parent
sys.path.insert(0,str(ROOT/'src'))
import csv,hashlib,io,json,subprocess
from datetime import datetime,timezone
from panda_closed_loop.config import digest
from panda_closed_loop.p1_r3 import compare_refinement

BASE='45d1adae85f4f2484202792041e080fa54e23962'
OUT=ROOT/'reports/a2_extended_delivery'


def write(name,value):
    path=OUT/name
    with path.open('x') as f:
        if isinstance(value,str):f.write(value.rstrip()+'\n')
        else:json.dump(value,f,indent=2,allow_nan=False);f.write('\n')


def git(*args,cwd=REPO):return subprocess.check_output(['git',*args],cwd=cwd)


def main():
    baseline=json.loads((ROOT/'reports/a2_extended_v1/baseline_reproduction/BASELINE_REPRODUCTION_RESULTS.json').read_text())
    all_versions={v:json.loads((ROOT/f'reports/a2_extended_{v}/A2_EXTENDED_SUITE.json').read_text()) for v in ['v1','v2','v3','v4']}
    current=all_versions['v4'];plan=json.loads((ROOT/'policy/a2_extended_v4/A2_EXTENDED_PREDECLARATION.json').read_text())
    checks={};cells=[]
    for ref in ['E1','E2','E3']:
        folder=ROOT/f'runs/a2_extended_v4/{ref}_c02f908';s=json.loads((folder/'summary.json').read_text())
        done=json.loads((folder/'run_completed.json').read_text());c=s['cells'];cells.extend(c)
        refinement=compare_refinement(c,plan['fixed_acceptance_thresholds'])
        checks[ref+'_four_cells']=len(c)==4 and all(x['a2']['completed'] and x['a2']['passed'] and x['audit']['passed'] for x in c)
        checks[ref+'_all_six_refinements']=refinement==s['refinement'] and len(refinement['comparisons'])==6 and all(x['status']=='PASS' for x in refinement['comparisons'])
        checks[ref+'_no_actual_negative']=all(x['negative_slacks']['negative_count']==0 for x in c)
        checks[ref+'_actual_entrance']=all(x['prehold']['completed'] and x['endpoint']['entrance_passed'] and x['endpoint']['q_qd_z_transfer_exact'] and not x['endpoint']['observer_reset'] and not x['endpoint']['clock_reset'] for x in c)
        checks[ref+'_inputs_and_exit']=done['frozen_inputs_unchanged'] and done['engineering_error'] is None and done['exit_code']==0
    original=[]
    for row in git('ls-tree','-r','-z',BASE).split(b'\0'):
        if not row:continue
        header,name=row.split(b'\t',1);mode,kind,blob=header.decode().split();name=name.decode();p=REPO/name
        if kind!='blob':raise ValueError('Unexpected original Git type')
        data=p.read_bytes();actual=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
        original.append({'path':name,'original_git_blob':blob,'current_git_blob':actual,'sha256':hashlib.sha256(data).hexdigest(),'size':len(data),'unchanged':actual==blob})
    checks['all_original_tracked_files_unchanged']=all(r['unchanged'] for r in original)
    checks['original_checkout_still_clean']=not git('status','--porcelain',cwd=Path('/workspace/project')).strip() and git('rev-parse','HEAD',cwd=Path('/workspace/project')).decode().strip()==BASE
    for v in ['v1','v2','v3','v4']:
        freeze=json.loads((ROOT/f'policy/a2_extended_{v}/FROZEN_INPUTS.json').read_text())
        checks[v+'_all_frozen_inputs_unchanged']=all(digest(ROOT/n)==h for n,h in freeze['files'].items())
    write('ORIGINAL_TRACKED_FILE_INTEGRITY.json',{'baseline_commit':BASE,'tracked_files':len(original),'all_unchanged':checks['all_original_tracked_files_unchanged'],'files':original})
    checks['baseline_exact_reproduction']=baseline['all_seven_exact_reproductions'] and baseline['fresh_numerical_gate']=='GO' and baseline['contract_tests_passed']
    checks['current_report_agrees']=current['suite_outcome']=='PASS' and current['passing_cells']==12 and current['completed_cells']==12
    gate='GO' if all(checks.values()) else 'NO-GO'
    output={'created_utc':datetime.now(timezone.utc).isoformat(),'gate':gate,'scope':'LOCAL_NUMERICAL_A2_EXTENDED_V4_FIXED_THREE_CASES_ORIGINAL_C4; NOT_ALL_TIME_CERTIFICATION',
        'version':'v4','freeze_commit':git('log','-1','--format=%H','--','panda_research/policy/a2_extended_v4/FROZEN_INPUTS.json').decode().strip(),
        'checks':checks,'motion_cells':12,'complete_audited_cells':sum(c['a2']['completed'] and c['audit']['passed'] for c in cells),
        'required_refinement_pairs':18,'required_metric_comparisons':72,
        'maximum_terminal_error_mm':1000*max(c['a2']['metrics']['actual_terminal_error_m'] for c in cells),
        'minimum_actual_normalized_raw_slack':min(c['a2']['metrics']['minimum_normalized_raw_slack'] for c in cells),
        'maximum_normalized_primal':max(c['a2']['metrics']['max_normalized_primal'] for c in cells),
        'maximum_scaled_stationarity':max(c['a2']['metrics']['max_scaled_stationarity'] for c in cells),
        'velocity_CBF_gain_change':{'old_s_inverse':5.,'new_s_inverse':10.,'versioned_amendment':True},
        'old_alpha5_shadow_negative_count':sum(c['audit']['barrier_gain_amendment']['old_alpha5_shadow_negative_count'] for c in cells),
        'old_alpha5_policy_satisfaction_claimed':False,'all_prior_suite_outcomes_preserved':{v:x['suite_outcome'] for v,x in all_versions.items()},
        'baseline_narrow_numerical':'GO' if checks['baseline_exact_reproduction'] else 'NO-GO',
        'independent_acceptance':'USER_REPORTED_ACCEPTANCE_OF_PRIOR_WORK; ATTRIBUTABLE_EXTERNAL_SIGNATURE_ARTIFACT_NOT_SUPPLIED',
        'A3':'NO-GO','Level1':'NO-GO','independent_controls_signature':None,'independent_theory_signature':None,
        'builder_sha256':digest(Path(__file__))}
    write('NUMERICAL_GO.json',output)
    authority={'recorded_utc':datetime.now(timezone.utc).isoformat(),'source':'DIRECT_USER_MESSAGES_IN_THIS_SESSION',
      'authorization':['I authorize simulation development, versioned policy changes, and P1/A2 numerical testing.',
       'continue, I want E1, E2 and E3 all passes, make A2 a solid GO.'],
      'acceptance_statement':'We need a numerical GO for A2 which requires every cell and refinement check to pass, you have the independent acceptance up till now.',
      'interpretation':'User-provided acceptance retained. No reviewer identity, dated signature or external review artifact is invented. Numerical work continued within this authority.',
      'external_reviewer_identity':None,'external_signature_artifact':None,'new_human_theory_proof_claimed':False}
    write('USER_ACCEPTANCE_RECORD.json',authority)
    write('A3_STAGE_GATE.md',f'''# A3 stage gate — NO-GO

Existing narrow A2 numerical: {output['baseline_narrow_numerical']}, exact fresh seven-cell local reproduction.
A2-Extended v4 numerical: {gate}; computed from 12 full cells, 18 pairs / 72 metric checks.
The original physical model is unchanged. The new filter uses explicit alpha_v 5→10;
v1/v2/v3 failures remain intact. A numerical tracking result does not validate a planner.

| Gate | Executed status | Needed before an official A3 study |
| --- | --- | --- |
| Independent A2 acceptance | User reports prior acceptance; external artifacts not supplied | Attributable acceptance scope including new filter design, source and evidence; signatures cannot be self-issued |
| Sampler / theory interpretation | Measurements and concrete unsigned review request complete | Real controls/theory disposition of nominal AB2, v4 gain and Section IV claim scope |
| T27 | 18 original-setting diagnostic fixtures, 15 API contracts; separate new solver qualification and complete numerical trajectory KKT audits | Reviewed full conditioning/precision/active-set protocol, failures retained, official acceptance; no fixture-count sign-off |
| Positive G2.5 | Original-policy 20-point filter screen: 15 pass / 3 fail / 2 unknown; planner M1 missing | A new frozen screen for the chosen final policy, both filter and factor-two planner conditions, torque/manipulability and valid common-domain margins |
| M1 common-domain bounds | Inventory/API implemented; no certified numbers invented | Frozen q/qd/qdd/tube domains; traceable inertia/inverse/derivative/barrier bounds and usable margin envelopes |
| Stage 1 structure | Free-time quintic/B-spline, energy, terminal/physical/margin residuals and symbolic adapter; 14 final tests pass | Dynamic real M1 symbolic provider; synthetic fixtures cannot supply production constants |
| Stage 1 numerical solver | Scaffold only; official solve hard-blocked | Validated derivatives, feasibility/KKT, solver settings/budget, quadrature/grid refinement and failure handling |
| T22 tasks | Not frozen executable tasks | Reviewed common targets, feasibility/terminal rules and task/config hashes |
| Scenario B method-independent suite | Proposed source inputs retained, no comparison run | Same target manifest and objective/failure aggregation for both methods |
| Equal initialization | Not frozen executable protocol | Ten COMMON cold starts, exact stored inputs/seeds/budgets; cross seeds separately labeled |
| Final comparison manifest | Missing | Signed/hashed final model, final gain/policy, domain, margins, tasks, methods, solver/budget and reporting manifest |
| Official A3 authority | Not granted in this task | Explicit later authority after the gates above are met |
| Level 1 | NO-GO | Continuous-domain bounds, theorem assumptions and justified sampled implementation/intersample enclosures |

No official Scenario A/B/C comparison or optimized planner result was executed.
The earlier preparation report is preserved at `../a2_extended_v1/A3_STAGE_GATE.md`;
its pending rows reflect its earlier snapshot. This is the final consolidated gate.
The alpha5 G2.5 results are not silently reinterpreted as alpha10 results.

Independent controls/theory signatures: null. User acceptance source: USER_ACCEPTANCE_RECORD.json.
''')
    write('CHANGELOG.md',f'''# Additive change record

- Baseline 45d1ada: all {len(original)} tracked files preserved; seven original cells exactly reproduced in a clean checkout and new pinned venv on the same machine. No independent human signature was created.
- e4267be: three one-second measured-endpoint references and original C4/criteria frozen before v1 motion. Outcome PARTIAL: E1/E3 failed, E2 passed. Protective stops and full prefix audits retained.
- 0391c5b: v2 solver scaling/roundoff tightening and stricter solver settings frozen. All individual cells passed; E3 energy/intervention refinement failed. Physics/model/gains unchanged.
- aec8e86: v3 causal interval-QP amendment frozen. All individual cells passed; E3 peak intervention/current-minimum-slack refinement failed. Complete evidence retained.
- c02f908: v4 explicit velocity-CBF design gain 5→10 frozen. Current-state v2 QP restored; physical model/limits, other gains, references, grid and pass tolerances unchanged. Computed final numerical gate: {gate}. Old alpha5 shadow negatives are retained separately.
- A3 preparation: additive QP fixtures, feasibility screens, M1 domain/bound provenance APIs and modular Stage 1 scaffold. Official comparisons and production optimization remain blocked.
- Reporting/archival: original raw fields retained, aborted distances separated from terminal accuracy; r/u/tau differences reported independently. Lossless CTZ plus shared XZ delivery reconstructs exact original CTZ bytes. This changes storage/instrumentation only.

Original signed policy, Gaz primary sources, manuscript .tex and research XLSX were not edited. No failed scientific or development log was replaced.
''')
    write('REVIEWER_INPUT_CHECKLIST.md','''# Reviewer-input checklist

- Original checkout/policy/Gaz provenance, pinned environment and exact seven-cell baseline comparison with full new raw traces.
- Each pre-motion source commit, policy hash, exact reference construction from actual post-P1 state and unchanged C4/thresholds.
- Full failed/aborted v1 traces and prefix audits; false infeasibility/boundary diagnostics; v2/v3 failed refinements.
- v4 explicit alpha_v 5→10 design change, original alpha5 shadow negatives, actual 43-row entrance/update data and both dual scalings.
- Every scheduled update / retained RK4 stage/endpoint, physical/observer/dense-interpolant checks, terminal errors and 72 refinement metrics.
- Separate u-r, tau-u and tau-r max/RMS/component data, sampler limitations and concrete unsigned theory request.
- User-provided acceptance record; provide attributable review decision/artifact if claiming independent acceptance. Do not invent sign-offs.
- T27/G2.5/M1/Stage 1 evidence and blockers; require final policy/domain/task/solver/margin/10-start manifest before official A3.
- SOURCE_MANIFEST.json plus encoding indices/checksums and byte-exact reconstruction proof; use fresh output paths for reruns.
''')
    write('THREE_PRIORITY_ACTIONS.md','''# Exactly three priority remaining actions

| Purpose | Owner | Artifact | Pass criterion |
| --- | --- | --- | --- |
| Independent A2 acceptance provenance / new-design interpretation | Controls and theory reviewers | Attributable decision linked to the v4 source/policy/evidence hashes and user acceptance record | Scope explicitly accepts or restricts alpha_v10 and the AB2 sampled realization; real reviewer identity/decision, with no fabricated theorem/signature |
| Expanded A2 evaluation reproducibility | Separate reproduction engineer | A fresh-machine replay of the SAME frozen 12-cell v4 suite, raw traces and comparison report | All 12 cells, full audits and 18 pairs / 72 metrics pass unchanged criteria; no case replacement or threshold tuning |
| Subsequent A3 readiness | Numerical/optimization lead with responsible reviewers | Common-domain M1 registry, positive final-policy G2.5, official T27 disposition, validated Stage 1 solver and signed final task/10-start manifest | Every A3_STAGE_GATE.md prerequisite has usable evidence and required decisions before any official comparison |
''')
    write('REPRODUCTION_COMMANDS.md','''# Reproduction commands and scope

Actual commands, timestamps, source/package/machine hashes and failed logs are retained in each run/report directory. Use NEW exclusive output paths; original records must not be overwritten.

On a full checkout of the source branch with the pinned Python 3.12.14 environment:

```bash
cd panda_research
python -m pip install -r requirements.lock.txt
python -m pip install setuptools==80.9.0
python -m pip install --no-deps --no-build-isolation -e .
python tests/test_a2_policy_v4.py --report /tmp/new-v4-contracts.json
python scripts/a2_extended_v4.py --reference E1 --contracts /tmp/new-v4-contracts.json --output runs/a2_extended_v4/new_E1
python scripts/a2_extended_v4.py --reference E2 --contracts /tmp/new-v4-contracts.json --output runs/a2_extended_v4/new_E2
python scripts/a2_extended_v4.py --reference E3 --contracts /tmp/new-v4-contracts.json --output runs/a2_extended_v4/new_E3
```

Python/NumPy/CasADi/SciPy/ProxQP/pin/MuJoCo versions are pinned by the recorded runtime, lock and package inventories. The supplied dependency lock pins versions without distribution hashes; it is not a hashed supply-chain lock. Source configuration/model hashes are separately verified by every runner. Runtime setup/reproduction details are in BASELINE_REPRODUCTION.md and its install logs.

The ZIP is a complete NEW-evidence/code overlay plus unchanged runtime context, not a duplicate of every old baseline archive. Strict full-run freeze verification also requires the immutable original checkout at 45d1ada with its older archival files. The source branch retains that ancestry/data. Baseline old failures were not deleted to shrink the ZIP.

Restore the shared compressed evidence using the top-level standard-library helper:

```bash
python archive_evidence.py restore --evidence evidence --destination . --report restored-proof.json
```

It reconstructs all original CTZ files at their recorded paths and verifies byte SHA-256, schemas, arrays and original container metadata. A differing existing file is never overwritten. Exact container rebuilding was tested on Python3.12.14 / zlib1.3.2. The scientific bytes are losslessly archived; recreating identical compressed containers requires compatible zlib. The pinned numerical environment is also needed for exact numerical replay.

Use `src/panda_closed_loop/trace_archive.py:read_trace` for retained native records, and `runs/a2_extended_baseline_clean_ctz/restore_json.py` when original baseline JSON/gzip bytes are needed. No raw-trace subset is represented as a complete reproduction.
''')
    write('GATE_SUMMARY.md',f'''# Evidence-based gates

| Scope | Gate | Basis |
| --- | --- | --- |
| Existing narrow A2 numerical | {output['baseline_narrow_numerical']} | Exact fresh seven-cell same-machine clean-checkout reproduction; original record unchanged |
| A2 independent acceptance | CONDITIONAL GO — user-reported prior acceptance | Direct user statement retained; external signature artifacts / new v4 theory disposition not supplied or invented |
| A2-Extended v4 numerical | {gate} | All required evidence checks in NUMERICAL_GO.json; earlier versions remain PARTIAL/NO-GO |
| A3 readiness | NO-GO | M1/G2.5/T27/production solver/task/10-start/review/authority gates incomplete |
| Level 1 certification | NO-GO | No continuous-domain/intersample proof |

Verification level: SOURCE VERIFIED / EXECUTED LOCALLY for the actual numerical evidence. A separate machine/human reproduction is not self-issued. A new simulation GO is not a hardware-safety or optimized planner/filter certificate.
''')
    print('Computed numerical gate',gate,'checks',len(checks),'original files',len(original),flush=True)
    return 0 if gate=='GO' else 3


if __name__=='__main__':raise SystemExit(main())
