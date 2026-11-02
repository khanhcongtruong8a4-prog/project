"""Complete standalone source/evidence ZIP tree, with exact lossless restoration.

Every tracked original input is included, unlike the earlier overlay. Original
scientific bytes are represented as regular files or checksum-bound lossless
payloads. No Git history, virtual environment, cache or duplicate project ZIP
is silently used as scientific evidence.
"""
from pathlib import Path
import sys
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];REPO=ROOT.parent
sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'scripts'))
import argparse,hashlib,json,shutil,subprocess,zipfile
from datetime import datetime,timezone
from archive_evidence import pack as pack_ctz,sha,dump
from archive_regular_evidence import pack as pack_regular


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--payload',type=Path,required=True)
    parser.add_argument('--ctz-cache',type=Path,required=True)
    parser.add_argument('--regular-cache',type=Path,required=True)
    parser.add_argument('--combined-work',type=Path,required=True)
    args=parser.parse_args();payload=args.payload.resolve();evidence=payload/'evidence'
    if not evidence.is_dir():raise ValueError('Previous exact CTZ payloads must be staged first')
    files=subprocess.check_output(['git','ls-tree','-r','--name-only','HEAD'],cwd=REPO,text=True).splitlines()
    policy=json.loads((ROOT/'policy/a2_verified_v1/FINAL_A2_POLICY.json').read_text())
    if policy['numerical_gate']!='GO':raise ValueError('Cannot package an accepted GO without passing technical evidence')
    existing={r['path'] for p in evidence.glob('*.index.json') for r in json.loads(p.read_text())['traces']}
    new_ctz=[REPO/n for n in files if n.endswith('.ctz') and n not in existing]
    if new_ctz:pack_ctz(REPO,new_ctz,evidence,'verified_replay',args.ctz_cache)
    binary=[REPO/n for n in files if not n.endswith('.ctz') and
            (Path(n).suffix.lower() in ['.gz','.zip','.rar','.npy','.npz'] or (REPO/n).stat().st_size>4*(1<<20))]
    # Joint solid compression keeps almost-identical old/replay JSON close;
    # no numeric delta/rounding or semantic interpretation is required.
    args.combined_work.mkdir(exist_ok=False)
    pack_regular(REPO,binary,args.combined_work,'all_original_and_replay',args.regular_cache)
    prototype=payload.parent/'a2-regular-prototype-preserved';prototype.mkdir(exist_ok=False)
    for p in list(evidence.glob('*.regular.*'))+list(evidence.glob('*.regular.json')):
        if p.exists():shutil.move(str(p),prototype/p.name)
    for p in args.combined_work.iterdir():shutil.copy2(p,evidence/p.name)
    encoded={}
    for p in evidence.glob('*.index.json'):
        for r in json.loads(p.read_text())['traces']:encoded[r['path']]={'sha256':r['sha256'],'size':r['size'],'encoding':'EXACT_CTZ_CONTAINER_IN_SHARED_XZ'}
    for p in evidence.glob('*.regular.json'):
        for n,r in json.loads(p.read_text())['files'].items():encoded[n]={'sha256':r['sha256'],'size':r['size'],'encoding':r['encoding']+'_IN_SHARED_XZ'}
    if set(encoded)-set(files):raise ValueError('Encoded source files are missing from the committed complete source tree')
    logical={}
    for n in files:
        src=REPO/n;digest=sha(src);logical[n]={'sha256':digest,'size':src.stat().st_size,'encoding':encoded.get(n,{}).get('encoding','REGULAR_FILE')}
        if n in encoded:
            if encoded[n]['sha256']!=digest:raise ValueError('Encoded original differs: '+n)
        else:
            dest=payload/n;dest.parent.mkdir(parents=True,exist_ok=True)
            if dest.exists():raise ValueError('Refuse to overwrite staged package source: '+n)
            shutil.copy2(src,dest)
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip()
    dump(payload/'SOURCE_MANIFEST_A2_VERIFIED.json',{'format':'IC2AI_A2_COMPLETE_VERIFIED_SOURCE_AND_EVIDENCE_V1',
        'source_commit':head,'logical_files':logical,'complete_original_protected_source_files':2018,
        'all_original_and_failed_data_included':True,'new_physical_replay_cells':19,
        'logical_CTZ_files':sum(n.endswith('.ctz') for n in logical),
        'archive_file_encodings':encoded,'dependency_lock':'panda_research/requirements.lock.txt',
        'git_history_not_included':'The standalone bootstrap creates labeled local metadata for original runner checks; historical commit IDs remain recorded.'})
    start='''# Verified IC2AI 2027 A2 package

Read panda_research/reports/a2_acceptance_v1/A2_READINESS_DECISION.md first.
The versioned policy is panda_research/policy/a2_verified_v1/FINAL_A2_POLICY.json.
Original r4 seven cells and v4 twelve cells were freshly replayed in a clean
checkout / pinned environment, with exact full scientific data agreement.
This is local technical evidence on the same host, not independent signatures.

One additional legacy-alpha5/guarded-solver probe FAILS despite an exact
represented-QP optimum. It is preserved and blocks broader solver/T27 claims.
The selected original alpha5 protocol uses its original solver; v4 uses
alpha10 and the guarded solver. Scope and known failure were declared before
the fresh replays. No gain, model, reference, guard or pass tolerance was changed.

This complete ZIP includes ALL prior protected source/input/failed-experiment
files and the new replay evidence. Large/raw files are LOSSLESSLY encoded in
evidence/, not omitted. Code and ordinary reports can be read immediately.
Restoration verifies every original file byte SHA-256 and refuses overwrites.

Use the recorded Python3.12.14 / Linux environment, zlib1.3.2 for identical
compressed containers, and the unchanged numerical version lock:

    python -m venv .venv
    .venv/bin/python -m pip install -r panda_research/requirements.lock.txt setuptools==80.9.0
    .venv/bin/python RUN_REPRODUCTION.py --verify-only

To execute another complete 19-cell replay with fresh exclusive outputs:

    .venv/bin/python RUN_REPRODUCTION.py --run --prefix my_fresh_replay

Use the matching virtual-environment Python path on your platform; the exact
reproduction claim is for the recorded Linux/pinned environment. Allow several
GB of temporary disk space for restored originals and shared decompression.
The supplied dependency lock pins versions without distribution hashes.

The original frozen CLI runners and all their SHA/Git checks remain enabled.
Because source ZIPs contain no .git history, the bootstrap creates a clearly
labeled LOCAL input-staging commit. It is not a historical commit reconstruction
or external reviewer signature. In a full checkout this step is unnecessary.

REVIEW.zip is an optional SMALL code/policy/report subset with no raw payloads.
It cannot substitute for complete replay or recovery. The outer complete ZIP
contains all payloads and manifests. Earlier historical pending-approval text
is preserved; direct user consultation/authorization governs this technical
release. No further administrative approval is requested.

Official A3 comparisons were not started. Level1 is not established. Numerical
GO applies only to the precisely frozen A2 experiments; it is not a general
solver-domain, all-time, hardware, optimized-planner or publication theorem.
'''
    (payload/'START_HERE_A2_VERIFIED.md').write_text(start)
    review=payload/'REVIEW.zip'
    with zipfile.ZipFile(review,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        z.writestr('REVIEW_SCOPE.md','Small code/policy/table subset only. Raw traces and prior protected input archives are in the complete package evidence/ payload. This subset cannot run full reproduction.\n')
        for p in sorted(payload.rglob('*')):
            if not p.is_file() or p==review:continue
            n=str(p.relative_to(payload))
            selected=(n=='START_HERE_A2_VERIFIED.md' or n.startswith('panda_research/policy/a2_verified_v1/')
                or n.startswith('panda_research/policy/a2_acceptance_v1/')
                or n.startswith('panda_research/reports/a2_acceptance_v1/')
                or n.startswith('panda_research/src/') or n.startswith('panda_research/scripts/')
                or n.startswith('panda_research/tests/') or n in ['panda_research/requirements.lock.txt','panda_research/pyproject.toml'])
            if selected and p.stat().st_size<3*(1<<20) and p.suffix not in ['.ctz','.gz','.rar','.zip']:
                z.write(p,n)
    physical={str(p.relative_to(payload)):{'sha256':sha(p),'size':p.stat().st_size}
              for p in sorted(payload.rglob('*')) if p.is_file()}
    dump(payload/'PACKAGE_MANIFEST.json',{'files':physical,'excludes_self_hash':True,'source_manifest':'SOURCE_MANIFEST_A2_VERIFIED.json',
           'complete_logical_source_files':len(logical),'logical_CTZ_files':sum(n.endswith('.ctz') for n in logical)})
    print('Complete source files',len(logical),'CTZ',sum(n.endswith('.ctz') for n in logical),
        'payload bytes',sum(x['size'] for x in physical.values()),'review bytes',review.stat().st_size,flush=True)


if __name__=='__main__':main()
