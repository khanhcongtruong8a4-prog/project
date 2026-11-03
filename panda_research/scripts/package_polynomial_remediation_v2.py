"""Deterministic, complete tracked-source/evidence ZIP; no history omission."""
from pathlib import Path
import sys
sys.dont_write_bytecode=True
REPO=Path(__file__).resolve().parents[2]
import argparse,hashlib,json,stat,subprocess,zipfile

README='''# IC2AI 2027 Panda A2 polynomial-hold remediation v2.4a

The requested unpublished checkpoint f9278f2 was not recovered. This is a new
versioned reconstruction from published 4e6335d, with every earlier source and
failure preserved. Read panda_research/reports/active_remediation_v2/final/
ACCEPTANCE.json and ALL_CANDIDATE_REFINEMENTS.csv for separate decisions.

Runtime v2.4 uses causal cubic torque holds, Gauss-Legendre execution, and
28-variable augmented completion QPs with constraint generation and full
finite-grid guarded/KKT verification. Dynamics, gains, disturbance, original
numerical thresholds and historical sources are unchanged. There is no stored
exact-witness runtime fallback. All new source versions and failed attempts
are included. See policy/active_remediation_v2/ for mathematical justification.

IMPORTANT VERIFICATION HISTORY: original result.json and logs retain the failed
bitwise implicit-fixed-point assertion. They are never overwritten. The frozen
v2.4a audit independently checks matching actual polynomial torque and complete
plant/DOB/power stage equations at the ORIGINAL predeclared 1e-13 residual.
AUDIT_V2_4A.json binds this correction to each original result and raw trace by
SHA256. The acceptance ledger explicitly records both verdicts. No physical
trajectory is changed or spliced, and no guard, KKT or refinement tolerance is
relaxed. Three negative-control/analytic tests qualify the corrected auditor.

The ZIP includes ALL tracked source, inputs, past failures, current raw traces,
original seven plus twelve extended replays, and 39 finite T27 fixtures. No
rounding/downsampling of evidence is used. MANIFEST_REPRODUCTION.json hashes
every delivered file except itself; the outer ZIP has a separate SHA256.
Git object history is not embedded. SOURCE_VERSION.json records source commit
and correction history. A standalone run creates explicitly LOCAL policy
staging metadata for the unchanged original Git-checking CLIs; it never forges
historic provenance, external reviewer signatures or checkpoint recovery.

Use Linux x86-64, Python 3.12.14, g++ and Poppler pdftotext. Tested native
libraries are included with build records, source and support-sign patch.
Dependencies are pinned; installation keeps TLS verification enabled.

    python VERIFY_PACKAGE.py
    python3.12 -m venv .venv
    .venv/bin/python -m pip install -r panda_research/requirements.lock.txt setuptools==80.9.0 wheel==0.48.0
    .venv/bin/python RUN_REPRODUCTION.py --verify-only
    .venv/bin/python RUN_REPRODUCTION.py --prefix fresh_local_full_replay

The full command reruns contract tests, all 39 T27 fixtures, all 19 frozen
regressions, and all eight new candidate cells with their corrected independent
audits and every refinement comparison. It is computationally substantial;
prefixes must be new. No previous summary is a substitute for a new run.
The extra historical active-AB2 campaign inside the frozen regression command
is EXPECTED to remain a refinement failure (exit3). Its preserved failure is
reported separately; the final source's acceptance is never based on that exit
alone. For candidate-only iteration use --candidate-only; it does not qualify
the omitted 19-cell/T27 gates. --workers 1 or 2 controls physical-run parallelism.

Read ALL_COEFFICIENT_COMPLETION_V2_4.md and the numerical audit policy before
interpreting results. Sampled trajectories, finite-grid guarded inequalities,
KKT tolerances and collocation extrema are NUMERICAL evidence, not certified
bounds on the true ODE between samples. A2 numerical acceptance is separate
from continuous-time certification, planner/M1/G2.5 readiness, official A3 and
Level1. No official A3 comparison or Level1 certification is performed.
'''
VERIFY='''from pathlib import Path
import hashlib,json
root=Path(__file__).resolve().parent
manifest=json.loads((root/'MANIFEST_REPRODUCTION.json').read_text())
for n,r in manifest['files'].items():
 p=root/n
 if not p.is_file() or p.stat().st_size!=r['size']:raise SystemExit('Missing/size mismatch: '+n)
 with p.open('rb') as f:actual=hashlib.file_digest(f,'sha256').hexdigest()
 if actual!=r['sha256']:raise SystemExit('SHA256 mismatch: '+n)
print('Verified',len(manifest['files']),'exact files; source',manifest['source_commit'])
'''
RUN='''from pathlib import Path
import sys
sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).resolve().parent/'panda_research/scripts'))
from reproduce_polynomial_remediation_v2 import main
raise SystemExit(main())
'''

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    decision=json.loads((REPO/'panda_research/reports/active_remediation_v2/final/ACCEPTANCE.json').read_text())
    if decision['separate_acceptance_decisions']['A2_full_requested_numerical_campaign']!='GO_NUMERICAL':raise ValueError('Final numerical acceptance is not GO')
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip()
    files=[x.decode() for x in subprocess.check_output(['git','ls-files','-z'],cwd=REPO).split(b'\0') if x]
    version={'source_commit':head,'published_reconstruction_base':'4e6335dbdfac4473ebd01f4d134da098a54fb563','runtime':'CAUSAL_CUBIC_GL2_COMPLETION_V2_4','verification':'GL_EXECUTION_VERIFICATION_V2_4A','checkpoint_f9278f2_recovered':False,
             'correction_history':subprocess.check_output(['git','log','--format=%H %s','4e6335d..HEAD'],cwd=REPO,text=True).splitlines()}
    virtual={'README_REPRODUCTION.md':README.encode(),'VERIFY_PACKAGE.py':VERIFY.encode(),'RUN_REPRODUCTION.py':RUN.encode(),'SOURCE_VERSION.json':(json.dumps(version,indent=2)+'\n').encode()}
    manifest={'source_commit':head,'self_hash_excluded':True,'files':{}}
    a.output.parent.mkdir(parents=True,exist_ok=True)
    def info(n,mode=0o644):
        i=zipfile.ZipInfo(n,(2026,11,3,0,0,0));i.create_system=3;i.external_attr=(stat.S_IFREG|mode)<<16;i.compress_type=zipfile.ZIP_DEFLATED;i._compresslevel=6;return i
    with zipfile.ZipFile(a.output,'x',allowZip64=True) as z:
        for n in sorted(files):
            src=REPO/n
            if src.is_symlink():raise ValueError('Handle source symlink explicitly before packaging: '+n)
            h=hashlib.sha256();size=0
            with src.open('rb') as f,z.open(info(n,0o755 if src.stat().st_mode&0o111 else 0o644),'w',force_zip64=True) as dst:
                while data:=f.read(1<<20):h.update(data);size+=len(data);dst.write(data)
            manifest['files'][n]={'sha256':h.hexdigest(),'size':size}
        for n,data in sorted(virtual.items()):z.writestr(info(n),data);manifest['files'][n]={'sha256':hashlib.sha256(data).hexdigest(),'size':len(data)}
        z.writestr(info('MANIFEST_REPRODUCTION.json'),json.dumps(manifest,indent=2,sort_keys=True)+'\n')
    with a.output.open('rb') as f:digest=hashlib.file_digest(f,'sha256').hexdigest()
    a.output.with_suffix(a.output.suffix+'.sha256').write_text(digest+'  '+a.output.name+'\n')
    print(json.dumps({'source_commit':head,'file_count':len(manifest['files']),'bytes':a.output.stat().st_size,'sha256':digest},indent=2))
if __name__=='__main__':main()
