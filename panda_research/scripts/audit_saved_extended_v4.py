"""Read-only full v4 audit from restored ZIP evidence; no new motion or QP."""
from pathlib import Path
import sys
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
import argparse,json
from panda_closed_loop.a2_extended import audit_extended
from panda_closed_loop.a2_qp_v2 import audit_qp_numerics
from panda_closed_loop.a2_policy_v4 import build_amended_system,audit_gain_amendment
from panda_closed_loop.config import digest
from panda_closed_loop.trace_archive import read_trace
from panda_closed_loop.p1_r3 import compare_refinement
from panda_closed_loop.logging import json_values


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    plan=json.loads((ROOT/'policy/a2_extended_v4/A2_EXTENDED_PREDECLARATION.json').read_text())
    frozen=json.loads((ROOT/'policy/a2_extended_v4/FROZEN_INPUTS.json').read_text())
    runtime=[n for n in frozen['files'] if n.startswith('src/') or n.startswith('policy/a2_extended_v4/')]
    if not all(digest(ROOT/n)==frozen['files'][n] for n in runtime):raise ValueError('Frozen runtime source differs')
    system=build_amended_system();system.geometry.function=system.geometry.function.expand()
    def forbidden(*a,**k):raise AssertionError('Saved-evidence audit must never resolve or actuate')
    system.qp.solve=forbidden
    results={}
    for ref in ['E1','E2','E3']:
        folder=ROOT/f'runs/a2_extended_v4/{ref}_c02f908';cells=[];audits=[]
        for i in range(4):
            c=json.loads((folder/f'cell_{i}.json').read_text());updates=read_trace(folder/c['a2']['trace']['file'],c['a2']['trace'])['updates']
            a=audit_extended(c,folder,system,plan);kkt=audit_qp_numerics(updates,system.barriers.taumax);gain=audit_gain_amendment(updates,system)
            audits.append({'cell':i,'full_trace':a,'dual_KKT':kkt,'declared_gain_and_old_policy_shadow':gain,
                           'passed':a['passed'] and kkt['passed'] and gain['passed']});cells.append(c)
        refinement=compare_refinement(cells,plan['fixed_acceptance_thresholds'])
        results[ref]={'cells':audits,'refinement':refinement,'passed':all(a['passed'] for a in audits) and all(r['status']=='PASS' for r in refinement['comparisons'])}
        print(ref,results[ref]['passed'],flush=True)
    report={'scope':'READ_ONLY_RESTORED_V4_EVIDENCE_AUDIT_NO_QP_NO_NEW_MOTION','all_pass':all(r['passed'] for r in results.values()),
            'results':results,'runtime_source_hashes_checked':runtime,
            'original_baseline_archival_integrity':'Not rechecked from overlay; use full-source preservation report and full checkout for that separate check',
            'independent_signature':None}
    with args.output.open('x') as f:json.dump(json_values(report),f,indent=2,allow_nan=False);f.write('\n')
    return 0 if report['all_pass'] else 3


if __name__=='__main__':raise SystemExit(main())
