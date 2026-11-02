"""Complete lossless package plus a small, independently runnable QP subset."""
from pathlib import Path
import sys
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];REPO=ROOT.parent
sys.path.insert(0,str(ROOT/'scripts'))
import argparse,hashlib,json,shutil,subprocess,zipfile
from archive_evidence import pack as pack_ctz,sha,dump
from archive_regular_evidence import pack as pack_regular

WRAPPER='''from pathlib import Path
import sys
sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).resolve().parent/'panda_research/scripts'))
from bootstrap_guarded_qp_reliability import main
raise SystemExit(main())
'''

def zip_tree(root,target):
    with zipfile.ZipFile(target,'x',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for p in sorted(root.rglob('*')):
            if p.is_file():z.write(p,str(p.relative_to(root)))

def main():
    p=argparse.ArgumentParser();p.add_argument('--previous',type=Path,required=True)
    p.add_argument('--staged-evidence',type=Path)
    p.add_argument('--payload',type=Path,required=True);p.add_argument('--subset',type=Path,required=True)
    p.add_argument('--ctz-cache',type=Path,required=True);p.add_argument('--regular-cache',type=Path,required=True)
    p.add_argument('--combined-work',type=Path,required=True);a=p.parse_args()
    payload=a.payload.resolve();payload.mkdir(exist_ok=False);evidence=payload/'evidence';evidence.mkdir()
    source_evidence=a.staged_evidence if a.staged_evidence else a.previous/'evidence'
    for path in source_evidence.iterdir():
        if a.staged_evidence or '.regular.' not in path.name:shutil.copy2(path,evidence/path.name)
    files=subprocess.check_output(['git','ls-tree','-r','--name-only','HEAD'],cwd=REPO,text=True).splitlines()
    decision=json.loads((ROOT/'policy/guarded_qp_reliability_v1/ACCEPTANCE_DECISIONS.json').read_text())
    existing={r['path'] for p in evidence.glob('*.index.json') for r in json.loads(p.read_text())['traces']}
    new=[REPO/n for n in files if n.endswith('.ctz') and n not in existing]
    if new:pack_ctz(REPO,new,evidence,'guarded_qp_remediation',a.ctz_cache)
    binary=[REPO/n for n in files if not n.endswith('.ctz') and
        (Path(n).suffix.lower() in ['.gz','.zip','.rar','.npy','.npz'] or (REPO/n).stat().st_size>4*(1<<20))]
    staged_regular={n:r for p in evidence.glob('*.regular.json') for n,r in json.loads(p.read_text())['files'].items()}
    if staged_regular:
        current={str(p.relative_to(REPO)):sha(p) for p in binary}
        if current!={n:r['sha256'] for n,r in staged_regular.items()}:raise ValueError('Staged regular-file set or hashes differ')
    else:
        a.combined_work.mkdir(exist_ok=False);pack_regular(REPO,binary,a.combined_work,'all_original_and_remediation',a.regular_cache)
        for p in a.combined_work.iterdir():shutil.copy2(p,evidence/p.name)
    encoded={}
    for index in evidence.glob('*.index.json'):
        for r in json.loads(index.read_text())['traces']:encoded[r['path']]={'sha256':r['sha256'],'size':r['size'],'encoding':'EXACT_CTZ_CONTAINER_SHARED_XZ'}
    for index in evidence.glob('*.regular.json'):
        for n,r in json.loads(index.read_text())['files'].items():encoded[n]={'sha256':r['sha256'],'size':r['size'],'encoding':r['encoding']+'_SHARED_XZ'}
    if set(encoded)-set(files):raise ValueError('Encoded evidence outside complete committed source')
    logical={}
    for n in files:
        src=REPO/n;digest=sha(src);logical[n]={'sha256':digest,'size':src.stat().st_size,'encoding':encoded.get(n,{}).get('encoding','REGULAR_FILE')}
        if n in encoded:
            if encoded[n]['sha256']!=digest:raise ValueError('Encoded source differs: '+n)
        else:
            dest=payload/n;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dest)
    dump(payload/'SOURCE_MANIFEST_GUARDED_QP.json',{'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip(),
        'logical_files':logical,'protected_previous_files':2262,'all_original_and_failed_files_included':True,
        'new_physical_motion_cells':23,'new_QP_regression_passes':39,'prior_v1_regression_history_preserved':True})
    (payload/'RUN_REMEDIATION.py').write_text(WRAPPER)
    start='''# IC2AI 2027 guarded-QP remediation

Read panda_research/reports/guarded_qp_reliability_v1/READINESS_DECISION.md.
The scoped decisions and known failures are separate and machine readable in
panda_research/policy/guarded_qp_reliability_v1/ACCEPTANCE_DECISIONS.json.
No independent reviewer signatures, official A3 experiments or Level 1 claims.

This COMPLETE package contains every previous protected source/input/failure
file, full new 23-cell motion evidence, both 39-fixture regressions, exact
certificates, corrected source, build recipe and the tested Linux x86_64 backend.
Large original files use exact reversible encodings in evidence/. Nothing is
rounded or replaced with a numerical witness. Restore checks original byte SHA.

Use the recorded Linux / Python 3.12.14, zlib 1.3.2 and pinned versions:

    python -m venv .venv
    .venv/bin/python -m pip install -r panda_research/requirements.lock.txt setuptools==80.9.0
    .venv/bin/python RUN_REMEDIATION.py --verify-only
    .venv/bin/python RUN_REMEDIATION.py --qp-only --prefix my_qp_check
    .venv/bin/python RUN_REMEDIATION.py --run --prefix my_motion_replay

The last command runs all 19 selected A2 cells AND the four separately labeled
legacy active-filter cells. A failure of their original refinement criteria
remains a failure and produces a nonzero aggregate process exit code.

The ZIP has no Git history. Full restoration creates explicitly labeled LOCAL
input-staging metadata to keep the ORIGINAL runners' committed-input checks
enabled. This is not a reconstruction of historical commits or signatures.
Full restoration needs several GB of temporary disk; QP-only needs no raw-trace
restoration. The tested backend is bundled with its SHA and source hashes.

To rebuild from pinned installed headers (g++17 required):

    .venv/bin/python panda_research/scripts/build_guarded_qp_reliability.py --output my_local_build

Use PANDA_GUARDED_QP_BUILD to select that build and rerun the 39 strict fixtures.
A rebuilt binary is a separate build unless its SHA matches the frozen tested
binary; the motion verifier intentionally rejects silently substituted builds.
Do not overwrite the frozen policies or earlier failed results.

QP_REPRODUCTION.zip is a SMALL extra package containing source, policies,
reports and every fixture needed for the 39-case solver reproduction. It is
not the complete trajectory evidence archive; its --qp-only command is usable
without downloading or restoring the large raw-history payloads.
'''
    (payload/'START_HERE.md').write_text(start)
    subset=a.subset.resolve();subset.mkdir(exist_ok=False)
    for src in sorted(payload.rglob('*')):
        if not src.is_file():continue
        n=str(src.relative_to(payload))
        if n.startswith('evidence/') or src.suffix in ['.ctz','.gz','.rar','.zip','.xz','.npy','.npz']:continue
        if '/runs/' in n and n!='panda_research/runs/a2_extended_v4/E3_c02f908/cell_0.json':continue
        if src.stat().st_size>4*(1<<20):continue
        dest=subset/n;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dest)
    # The complete source manifest describes files intentionally outside this
    # small package and is not its integrity manifest.
    (subset/'SOURCE_MANIFEST_GUARDED_QP.json').unlink(missing_ok=True)
    (subset/'START_HERE.md').write_text('''# Small runnable guarded-QP reproduction

This subset contains corrected source, the tested Linux x86_64 native backend,
its build recipe, policies, read-only reports and all 39 qualification fixtures.
Full original/extended trajectory traces and large historical archives are in
the separate COMPLETE evidence ZIP. This subset cannot replay the 23 motions.

With the recorded Linux/Python 3.12.14 environment:

    python -m venv .venv
    .venv/bin/python -m pip install -r panda_research/requirements.lock.txt setuptools==80.9.0
    .venv/bin/python RUN_REMEDIATION.py --qp-only --prefix my_solver_check

Read panda_research/reports/guarded_qp_reliability_v1/READINESS_DECISION.md for
the separate A2, solver-qualification, T27 and A3 decisions. No external review
signatures or Level 1 certification are claimed. Every included byte is covered
by QP_SUBSET_MANIFEST.json; the subset manifest itself excludes its own hash.
''')
    dump(subset/'QP_SUBSET_MANIFEST.json',{'scope':'RUNNABLE_39_FIXTURE_QP_SUBSET_NOT_COMPLETE_MOTION_EVIDENCE',
        'files':{str(p.relative_to(subset)):{'sha256':sha(p),'size':p.stat().st_size} for p in sorted(subset.rglob('*')) if p.is_file()}})
    zip_tree(subset,payload/'QP_REPRODUCTION.zip')
    physical={str(p.relative_to(payload)):{'sha256':sha(p),'size':p.stat().st_size} for p in sorted(payload.rglob('*')) if p.is_file()}
    dump(payload/'PACKAGE_MANIFEST.json',{'files':physical,'excludes_self_hash':True,'source_manifest':'SOURCE_MANIFEST_GUARDED_QP.json',
        'logical_source_files':len(logical),'decisions':decision['decisions']})
    print('Logical files',len(logical),'payload bytes',sum(r['size'] for r in physical.values()),'QP subset bytes',(payload/'QP_REPRODUCTION.zip').stat().st_size,flush=True)

if __name__=='__main__':main()
