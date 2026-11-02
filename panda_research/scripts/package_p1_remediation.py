"""Cumulative clean r2 overlay; accepted r1 ZIP and Action 3 r2 stay immutable."""
from pathlib import Path
import sys
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
import argparse,hashlib,json,shutil,subprocess,tempfile,zipfile
from panda_closed_loop.config import digest

NAME='IC2AI_Panda_P1_Review_Remediation_v1.2.2_DRAFT_2026-11-02_r2'
BASE='cea93d667350d56df7f7de2426f3679ee6eacce0'
R1_SHA='ff17fcac4e865825512d321350260b169d4b12065c5af10fcc40a82a91139f05'
R1=ROOT.parent/'downloads/IC2AI_Panda_P1_Protocol_v1.2.2_DRAFT_2026-11-01.zip'


def write(p,data):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(data,indent=2)+'\n')


def base_hash(path):
    p=subprocess.run(['git','show',BASE+':panda_research/'+path],cwd=ROOT.parent,capture_output=True)
    return hashlib.sha256(p.stdout).hexdigest() if p.returncode==0 else None


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage-dir',type=Path,help='Optional new package staging directory for clean engineering reproduction')
    parser.add_argument('--output-dir',type=Path,default=ROOT.parent/'downloads')
    args=parser.parse_args()
    if digest(R1)!=R1_SHA:raise ValueError('Accepted r1 archive changed')
    if args.stage_dir:
        stage=args.stage_dir.resolve()
        if stage.exists():raise ValueError('Stage path must be new')
        if not any(stage.is_relative_to(Path(p)) for p in ['/workspace','/tmp']):raise ValueError('Stage outside writable roots')
        stage.mkdir(parents=True)
        cleanup=None
    else:
        cleanup=tempfile.TemporaryDirectory(prefix='p1-r2-package-',dir='/tmp');stage=Path(cleanup.name)
    try:
        with zipfile.ZipFile(R1) as z:
            for name in z.namelist():
                if not (stage/name).resolve().is_relative_to(stage):raise ValueError('Unsafe accepted archive path')
            z.extractall(stage)
        old_root=next(p for p in stage.iterdir() if p.is_dir());package=stage/NAME;old_root.rename(package)
        old_manifest=json.loads((package/'PACKAGE_MANIFEST.json').read_text())
        previous={r['target']:r['new_sha256'] for r in old_manifest['install_files']}
        overlay=package/'overlay/panda_research'
        paths=[p for folder in ['src','scripts','tests'] for p in (ROOT/folder).rglob('*.py') if '__pycache__' not in p.parts]
        paths+=[ROOT/'README.md',ROOT/'provenance/p1_r2_prehold_input_hashes.json']
        paths += [p for folder in ['policy/v1.2.2-r2-draft','reports/p1_v1.2.2_r2'] for p in (ROOT/folder).rglob('*') if p.is_file()]
        for p in paths:
            target=overlay/p.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,target)
        pp=json.loads((ROOT/'reports/p1_prehold_latest.json').read_text())
        write(overlay/'reports/p1_prehold_latest.json',{'run_directory':'reports/p1_v1.2.2_r2/evidence/prehold',
            'summary_sha256':pp['summary_sha256'],'P1_numerical_hold':'FAIL','A2':'NO-GO'})
        install=[]
        for p in sorted(overlay.rglob('*')):
            if p.is_file():
                relative=str(p.relative_to(overlay))
                install.append({'package_path':str(p.relative_to(package)),'target':relative,
                    'baseline_sha256':base_hash(relative),'accepted_previous_sha256':[previous[relative]] if relative in previous else [],
                    'new_sha256':digest(p)})
        for r in old_manifest['install_files']:
            if r['target'].startswith('inputs/'):
                r=dict(r);r['accepted_previous_sha256']=[r['new_sha256']];install.append(r)
        review='IC2AI_2027_P1_Independent_Review_Decision_2026-11-02.txt'
        rp=overlay/'reports/p1_v1.2.2_r2/reviewer_sources'/review
        install.append({'package_path':str(rp.relative_to(package)),
            'target':'inputs/p1_review_2026_11_02/'+review,'baseline_sha256':None,'accepted_previous_sha256':[],
            'new_sha256':digest(rp)})
        shutil.copy2(ROOT/'scripts/p1_overlay_install.py',package/'APPLY_OVERLAY.py')
        (package/'README.md').write_text('''# P1 independent-review remediation — v1.2.2 r2 DRAFT

The frozen applied-torque hold FAILS: joints 3 and 7 exceed 0.02 rad/s by
elapsed 1.25 ms in every C4 preparation cell. Each run stops there; all full
43-row QPs at the actual abort states are infeasible. No valid t=0 endpoint
or A2 motion is produced. No duration, gain, disturbance or tolerance is retuned.

Signed negative-time execution, observer/applied-torque continuity, numerical
cubic extrema checks, measured-state transfer guards and actual-state QP checks
are implemented and tested. This is development evidence, not verified startup.

A1 GO; P1 frozen candidate FAIL / startup NOT APPROVED;
official A2, A3, Level 1 and publication NO-GO. All human approvals remain null.

Read overlay/panda_research/reports/p1_v1.2.2_r2/REVIEW_REMEDIATION.md,
A2_ENTRY_CHECKLIST.md and NEXT_THREE_ACTIONS.md. Previous r1 reports are included
unchanged as historical analytical evidence; r2 reports give current status.
''')
        (package/'REPRODUCTION.md').write_text('''# Apply and reproduce the cumulative r2 review overlay

Preserve accepted archives. Use a disposable copy of either accepted Action 3 r2
(ZIP SHA-256 7b96c24e6a56dfbde805ba610d1564b4128c20fe291b01dce4663e2696122292)
or that baseline with the accepted P1 r1 overlay already applied
(overlay ZIP SHA-256 ff17fcac4e865825512d321350260b169d4b12065c5af10fcc40a82a91139f05).
Both are available under downloads/ in the repository. Then run:

    python APPLY_OVERLAY.py --baseline /path/to/disposable/panda_research

Checks complete before writes. Only exact accepted base/r1 hashes or already
installed r2 hashes are accepted. Unexpected local edits are refused. Replaced
files are backed up under historical/p1_overlay_r2_baseline/, separately from r1.
Repeated application is idempotent. No cache, virtualenv or cumulative input
source archive is inside this clean overlay.

Use Linux x86-64/Python 3.12, install requirements.lock.txt, install the project
with `python -m pip install --no-deps -e .`, and provide pdftotext/poppler-utils
for full baseline validation. No GUI/ROS/GPU is required. From panda_research/:

    python tests/test_preparation.py --report runs/my_preparation_tests.json
    python scripts/action3.py validate
    python scripts/p1_prehold.py

Create a new directory below runs/ for your test report first. p1_prehold creates
a unique run directory and is EXPECTED TO EXIT 3: the frozen physical-model hold
fails. Exit 0 must never be forced. The first failure is retained for every
predeclared C4 cell. No official A2 or post-hold reference execution is available.
All parameter choices stay fixed; do not retry with a longer duration or easier
tolerance. Model integration is a development test authorized by the remediation
request, not owner/theory/controls approval of startup.

Inspect the actual abort-state diagnostics in each new cell JSON, including
q/qd/z, propagated varpi, h/psi1/speed/manipulability/torque and full QP result.
Physical time -0.15475 s has only 1.25 ms observer elapsed time; never substitute
the planned t=0 bound there. The cubic extension checks are numerical only and
do not certify a continuous ODE neighborhood or sampled observer theorem.

For the current evidence-aware checklist (EXPECTED EXIT 1 because P1 fails):

    python scripts/check_a2_plan.py --policy policy/v1.2.2-r2-draft/PROPOSED_POLICY_CONFIGURATION_v1.2.2_r2.json --preparation-summary reports/p1_v1.2.2_r2/evidence/prehold/summary.json --clock-tests reports/p1_v1.2.2_r2/evidence/signed_clock_and_hold_tests.json

Default older check/verify scripts can still reproduce the r1 analytical draft;
they do not override the newer r2 failure disposition. Fresh engineering
reproduction is not an independent reviewer's signature. The three human
actions and build-revision packet remain necessary before any future A2 GO.
''')
        manifest={'status':'DRAFT_OWNER_APPROVAL_PENDING_P1_FAILED','base_commit':BASE,
            'accepted_previous_overlay_sha256':R1_SHA,'backup_directory':'historical/p1_overlay_r2_baseline',
            'immutable_base_files':old_manifest['immutable_base_files'],
            'package_files':{str(p.relative_to(package)):digest(p) for p in sorted(package.rglob('*')) if p.is_file() and p.name!='PACKAGE_MANIFEST.json'},
            'install_files':install}
        write(package/'PACKAGE_MANIFEST.json',manifest)
        args.output_dir.mkdir(parents=True,exist_ok=True);output=args.output_dir/(NAME+'.zip')
        with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
            for p in sorted(package.rglob('*')):
                if p.is_file():z.write(p,NAME+'/'+str(p.relative_to(package)))
        with zipfile.ZipFile(output) as z:
            if z.testzip() is not None:raise ValueError('ZIP CRC failure')
            count=len(z.namelist())
        output.with_suffix('.zip.sha256').write_text(digest(output)+'  '+output.name+'\n')
        print(json.dumps({'archive':str(output),'bytes':output.stat().st_size,'members':count,'sha256':digest(output),
            'stage_directory':str(package) if args.stage_dir else None,'P1':'FAIL','A2':'NO-GO'},indent=2))
    finally:
        if cleanup:cleanup.cleanup()


if __name__=='__main__':main()
