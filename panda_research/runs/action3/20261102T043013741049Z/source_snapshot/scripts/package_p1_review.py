"""Create a clean source/report/draft overlay on the immutable accepted r2 ZIP."""
from pathlib import Path
import sys
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from datetime import datetime,timezone
import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
import zipfile
from panda_closed_loop.config import digest

BASE='cea93d667350d56df7f7de2426f3679ee6eacce0'
NAME='IC2AI_Panda_P1_Protocol_v1.2.2_DRAFT_2026-11-01'
REPORT=ROOT/'reports/p1_v1.2.2'
SOURCES=['README.md','src/panda_closed_loop/config.py','src/panda_closed_loop/readiness.py',
    'src/panda_closed_loop/feasibility.py','src/panda_closed_loop/a2_plan.py',
    'tests/test_action3.py','tests/test_p1_feasibility.py',
    'scripts/action3.py','scripts/p1_feasibility.py','scripts/check_a2_plan.py',
    'scripts/build_p1_review.py','scripts/verify_p1.py','scripts/package_p1_review.py','scripts/p1_overlay_install.py',
    'provenance/p1_input_and_predeclaration_hashes.json']


def write_json(p,data):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(data,indent=2)+'\n')


def copy_reports(source,target):
    target.mkdir(parents=True,exist_ok=True)
    for p in source.iterdir():
        if p.is_file() and p.suffix in ['.json','.log','.md','.txt']:
            shutil.copy2(p,target/p.name)


def base_hash(relative):
    r=subprocess.run(['git','show',BASE+':panda_research/'+relative],cwd=ROOT.parent,capture_output=True)
    return hashlib.sha256(r.stdout).hexdigest() if r.returncode==0 else None


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,default=ROOT.parent/'downloads')
    args=parser.parse_args()
    pp=json.loads((ROOT/'reports/p1_latest.json').read_text());sp=ROOT/pp['run_directory']
    vp=json.loads((ROOT/'reports/p1_verification_latest.json').read_text());vr=ROOT/vp['run_directory']
    verification=json.loads((vr/'verification.json').read_text())
    if not verification['overall_pass']:raise ValueError('Passing engineering verification is required')
    if digest(vr/'verification.json')!=vp['verification_sha256']:raise ValueError('Verification record changed')
    if digest(sp/'screen.json')!=pp['screen_sha256']:raise ValueError('Static screen changed')
    for relative,expected in verification['source_hashes'].items():
        if relative.endswith('.py') or relative.endswith('PREDECLARED_P1_DESIGN.json') or relative.endswith('PROPOSED_POLICY_CONFIGURATION_v1.2.2.json'):
            if digest(ROOT/relative)!=expected:raise ValueError('Tested source/configuration changed: '+relative)
    copy_reports(sp,REPORT/'evidence/static_screen')
    copy_reports(vr,REPORT/'evidence/verification')
    copy_reports(vr/'checklist',REPORT/'evidence/verification/checklist')
    action=ROOT/verification['action3_pointer']['run_directory']
    copy_reports(action,REPORT/'evidence/action3_engineering')
    legacy_pointer=json.loads((action/'legacy_run_pointer.json').read_text())
    legacy=ROOT/legacy_pointer['run_directory']
    copy_reports(legacy,REPORT/'evidence/legacy_engineering')
    # Keep initial screen evidence; the later rerun adds strict raw-slack acceptance
    # and diagnostic fields only, with the identical predeclared design/duration.
    initial=ROOT/'runs/p1/20261101T170654977412Z'
    if initial.exists():copy_reports(initial,REPORT/'evidence/initial_static_screen')
    references=REPORT/'reviewer_sources';references.mkdir(exist_ok=True)
    for p in (ROOT/'inputs/p1_v1.2.2').iterdir():
        if p.is_file():shutil.copy2(p,references/p.name)
    patch=subprocess.run(['git','diff',BASE,'--',*[f'panda_research/{p}' for p in SOURCES]],cwd=ROOT.parent,capture_output=True,text=True,check=True)
    (REPORT/'TRACKED_BASE_TO_DRAFT_SOURCE.diff').write_text(patch.stdout)
    write_json(REPORT/'EVIDENCE_PACKAGING_NOTE.json',{'scope':'SOURCE_AND_REPORT_OVERLAY_NOT_A2',
        'static_screen':pp,'verification':vp,'accepted_base_commit':BASE,
        'source_files_not_changed_after_verification':True,
        'later_bookkeeping':'Review/report files, checksum manifest and portable report pointers are generated after verification. They are not tested controller parameters.',
        'initial_to_final_screen':'Same frozen design and 0.156 s duration; strict raw-slack acceptance and extra planner diagnostic fields, no tuning',
        'omitted':'No baseline model/source archive, old cumulative releases, virtualenv, caches or run-local disposable copies in this clean ZIP'})
    manifest_paths=[p for folder in [ROOT/'policy/v1.2.2-draft',REPORT] for p in folder.rglob('*')
        if p.is_file() and p.name!='SHA256_MANIFEST.json']
    write_json(ROOT/'policy/v1.2.2-draft/SHA256_MANIFEST.json',{str(p.relative_to(ROOT)):digest(p) for p in sorted(manifest_paths)})
    args.output_dir.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='p1-package-',dir='/tmp') as temp:
        package=Path(temp)/NAME;overlay=package/'overlay/panda_research';overlay.mkdir(parents=True)
        paths=[ROOT/p for p in SOURCES]
        paths.extend(p for folder in [ROOT/'policy/v1.2.2-draft',REPORT] for p in folder.rglob('*') if p.is_file())
        install=[]
        for source in sorted(set(paths)):
            relative=str(source.relative_to(ROOT));target=overlay/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
            install.append({'package_path':str(target.relative_to(package)),'target':relative,
                'baseline_sha256':base_hash(relative),'new_sha256':digest(target)})
        # Preserve portable pointers without requiring the original /workspace/runs paths.
        for relative,data in [('reports/p1_latest.json',{'run_directory':'reports/p1_v1.2.2/evidence/static_screen','screen_sha256':pp['screen_sha256']}),
            ('reports/p1_verification_latest.json',{'run_directory':'reports/p1_v1.2.2/evidence/verification',
                'verification_sha256':vp['verification_sha256'],'overall_pass':True})]:
            target=overlay/relative;write_json(target,data)
            install.append({'package_path':str(target.relative_to(package)),'target':relative,
                'baseline_sha256':base_hash(relative),'new_sha256':digest(target)})
        # Reviewer documents are report-source evidence. Install exact source bytes
        # at the input locations expected by the frozen predeclaration hash map.
        for source in references.iterdir():
            relative='inputs/p1_v1.2.2/'+source.name
            install.append({'package_path':'overlay/panda_research/'+str(source.relative_to(ROOT)),
                'target':relative,'baseline_sha256':None,'new_sha256':digest(source)})
        shutil.copy2(ROOT/'scripts/p1_overlay_install.py',package/'APPLY_OVERLAY.py')
        readme='''# IC2AI Panda P1 / Protocol v1.2.2 — DRAFT / OWNER APPROVAL PENDING

This is a clean additive review overlay on accepted Action 3 r2, not a replacement
simulation release. A1 GO; P1 BLOCKED; official A2/A3/Level 1/publication NO-GO.
The static proposal chooses T_pre=0.156 s analytically. Both online pairs pass
at 129 declared nodes, and 129 full 43-row QP midpoint fixtures pass. Physical
holding dynamics and actual endpoints are unverified. No prehold/A2 was run.

Start with overlay/panda_research/reports/p1_v1.2.2/REVIEWER_ISSUE_RESPONSE.md,
P1_FEASIBILITY_MEMORANDUM.md, A2_ENTRY_CHECKLIST.md and NEXT_THREE_ACTIONS.md.
All new approval/signature fields are null. Follow REPRODUCTION.md to apply the
overlay to a disposable copy; original replaced source files are backed up.
The accepted r2 ZIP, model, original manuscript/workbook and old logs are unchanged.
'''
        (package/'README.md').write_text(readme)
        repro='''# Reproduction and limits

Use Linux x86-64 and Python 3.12. Preserve the accepted Action 3 r2 ZIP unchanged:
IC2AI_Panda_Action3_v1.2.1_2026-11-01_r2.zip
SHA-256: 7b96c24e6a56dfbde805ba610d1564b4128c20fe291b01dce4663e2696122292
Base Git commit: cea93d667350d56df7f7de2426f3679ee6eacce0.
The accepted archive remains in the repository's action3-v1.2.1 branch under downloads/.

1. Unpack that ZIP into a fresh disposable directory. It contains panda_research/.
2. Unpack this overlay separately. Run the standard-library installer:

   python APPLY_OVERLAY.py --baseline /path/to/fresh/panda_research

   All package/base/conflict checks complete before writes. Modified original
   files are copied to historical/p1_overlay_baseline/. The installer refuses
   unexpected local edits and supports an idempotent second call.
3. Change to the resulting panda_research directory. Install pinned dependencies:

   python3.12 -m venv .venv
   .venv/bin/python -m pip install -r requirements.lock.txt
   .venv/bin/python -m pip install --no-deps -e .

   Full baseline verification also requires pdftotext (poppler-utils). No GUI,
   ROS, GPU, external credentials or network access is needed after installation.
4. Reproduce only the authorized engineering checks:

   .venv/bin/python scripts/p1_feasibility.py
   .venv/bin/python scripts/check_a2_plan.py
   .venv/bin/python scripts/verify_p1.py

   verify_p1 includes the exact existing command `python scripts/action3.py validate`
   with the current interpreter. It is engineering evidence. An independent reviewer
   must do a separate clean-environment reproduction and sign their own record.
   Exit 0 from check_a2_plan means proposed fields are complete; its official_A2
   output remains NO-GO. It never grants approval.

Each screen/test/check command creates a new runs/ directory. The existing
action3 validate includes its original development tests, model comparisons
and an expected exit-2 A2-entry refusal. These are not a P1 hold or official A2.
Numerical values may vary at roundoff across platforms. Match the same physical
inputs, pair failures, fixed duration, strict QP acceptance, counts and gates;
do not compare timestamped report file hashes as if the execution times matched.

The screen has no plant integration or disturbance-truth query. Negative physical
time is used only in its analytic envelope map. A signed prehold execution adapter
and actual torque-hold validation are absent; no physical startup should be inferred.
Do not run an optimizer, new prehold or official A2 under this draft.

To regenerate unsigned review artifacts after a new screen:

   .venv/bin/python scripts/build_p1_review.py

Keep prior immutable run directories. This changes current report pointers and
checksum bookkeeping, never the approved v1.2.1 policy or predeclaration bytes.
The archive includes report copies of run records and original reviewer inputs;
portable report pointers replace local run paths only. Absolute historical command
paths inside evidence are provenance, not paths you must recreate.
'''
        (package/'REPRODUCTION.md').write_text(repro)
        immutable={p:base_hash(p) for p in ['src/panda_dynamics.py','baseline/model_manifest_v1.json',
            'policy/v1.2.1/APPROVED_POLICY_CONFIGURATION_v1.2.1.json','sources/manuscript_v1.2.1/02_mm&nc.tex','sources/manuscript_v1.2.1/03_contribution.tex']}
        file_hashes={str(p.relative_to(package)):digest(p) for p in sorted(package.rglob('*')) if p.is_file()}
        write_json(package/'PACKAGE_MANIFEST.json',{'status':'DRAFT_OWNER_APPROVAL_PENDING','base_commit':BASE,
            'immutable_base_files':immutable,'package_files':file_hashes,'install_files':install})
        output=args.output_dir/(NAME+'.zip')
        with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
            for p in sorted(package.rglob('*')):
                if p.is_file():archive.write(p,NAME+'/'+str(p.relative_to(package)))
        with zipfile.ZipFile(output) as archive:
            if archive.testzip() is not None:raise ValueError('ZIP CRC failure')
            count=len(archive.infolist())
        checksum=digest(output)
        output.with_suffix('.zip.sha256').write_text(checksum+'  '+output.name+'\n')
        print(json.dumps({'zip':str(output),'bytes':output.stat().st_size,'files':count,'sha256':checksum,
            'A2':'NO-GO','P1':'BLOCKED'},indent=2))


if __name__=='__main__':main()
