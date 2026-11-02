"""Build complete NEW-code/evidence overlay and a clearly labeled small review ZIP.

CTZ logical files are losslessly encoded by archive_evidence.py, not omitted.
Packaging outputs live outside the research worktree and never replace inputs.
"""
from pathlib import Path
import sys
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];REPO=ROOT.parent
sys.path.insert(0,str(ROOT/'src'))
import argparse,hashlib,json,shutil,subprocess,zipfile
from datetime import datetime,timezone
from panda_closed_loop.config import digest


def git(*args):return subprocess.check_output(['git',*args],cwd=REPO).decode()


def write(path,value):
    with path.open('x') as f:
        if isinstance(value,str):f.write(value.rstrip()+'\n')
        else:json.dump(value,f,indent=2);f.write('\n')


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--payload',type=Path,required=True);args=parser.parse_args();payload=args.payload
    evidence=payload/'evidence'
    if not evidence.is_dir():raise ValueError('Complete encoded evidence required first')
    indices=[json.loads(p.read_text()) for p in sorted(evidence.glob('*.index.json'))]
    encoded={r['path']:r for idx in indices for r in idx['traces']}
    changed=git('diff','--name-status','45d1ada','HEAD').splitlines()
    if any(not line.startswith('A\t') for line in changed):raise ValueError('Original tracked source modified')
    new={line.split('\t',1)[1] for line in changed}|set(git('ls-files','--others','--exclude-standard').splitlines())
    new={n for n in new if n.startswith('panda_research/') and not n.endswith('/SOURCE_MANIFEST.json')}
    missing=[]
    for n in sorted(new):
        p=REPO/n
        if p.suffix=='.ctz':
            if n not in encoded or encoded[n]['sha256']!=digest(p):missing.append(n)
    if missing:raise ValueError('New raw evidence not losslessly represented: '+str(missing))
    for n,r in encoded.items():
        if digest(REPO/n)!=r['sha256']:raise ValueError('Encoded input differs')
    context=set()
    for folder in ['src','tests','scripts','policy','baseline','sources','manifests']:
        base=ROOT/folder
        if base.exists():context.update(str(p.relative_to(REPO)) for p in base.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc')
    for name in ['requirements.lock.txt','pyproject.toml','README.md','inputs/action3/Project.rar']:
        if (ROOT/name).is_file():context.add('panda_research/'+name)
    selected=new|context
    for n in sorted(selected):
        p=REPO/n
        if p.suffix=='.ctz':continue
        target=payload/n;target.parent.mkdir(parents=True,exist_ok=True)
        if target.exists():raise ValueError('Refuse to overwrite packaging output: '+n)
        shutil.copy2(p,target)
    manifest={'schema':'A2_EXTENDED_NEW_SOURCE_AND_EVIDENCE_V1','created_utc':datetime.now(timezone.utc).isoformat(),
      'baseline_commit':'45d1adae85f4f2484202792041e080fa54e23962','source_commit':git('rev-parse','HEAD').strip(),
      'all_new_files':{n:{'sha256':digest(REPO/n),'size':(REPO/n).stat().st_size,'delivery':'LOSSLESS_CTZ_IN_SHARED_XZ' if n in encoded else 'REGULAR_FILE'} for n in sorted(new)},
      'unchanged_runtime_context':{n:{'sha256':digest(REPO/n),'size':(REPO/n).stat().st_size} for n in sorted(context-new)},
      'encoding_indices':{p.name:{'sha256':digest(p),'size':p.stat().st_size} for p in sorted(evidence.glob('*.index.json'))},
      'logical_CTZ_file_count':len(encoded),'every_new_CTZ_represented':True,'excludes_self_hash':True,
      'original_archived_failures':'Unchanged in full source ancestry; new v1-v3 failures fully included in this overlay',
      'external_signature_artifacts_supplied':False}
    srcmanifest=ROOT/'reports/a2_extended_delivery/SOURCE_MANIFEST.json'
    write(srcmanifest,manifest);shutil.copy2(srcmanifest,payload/'panda_research/reports/a2_extended_delivery/SOURCE_MANIFEST.json')
    shutil.copy2(ROOT/'scripts/archive_evidence.py',payload/'archive_evidence.py')
    write(payload/'SOURCE_COMMIT.txt',git('rev-parse','HEAD').strip())
    write(payload/'README.md','''# A2-Extended v4 complete handoff

Start with panda_research/reports/a2_extended_delivery/GATE_SUMMARY.md and
panda_research/reports/a2_extended_v4/A2_EXTENDED_RESULTS.md.

This ZIP contains ALL new code and evidence, including every failed v1/v2/v3
run, the clean original seven-cell reproduction and the complete v4 campaign.
The physical model and limits are unchanged. v4 explicitly changes the
velocity-CBF design gain 5→10; other gains/references/pass thresholds stay fixed.
Earlier failures are not relabeled. Source/policy/trace hashes are provided.

Full raw traces are losslessly encoded together in evidence/ to reduce download
size. They are NOT silently omitted. After extraction, reconstruct their exact
original files with the standard-library helper (no extra archive program):

    python archive_evidence.py restore --evidence evidence --destination . --report restored-proof.json

Every original CTZ byte SHA-256 is checked. A different existing file is never
overwritten. Exact reconstruction was verified on Python3.12.14/zlib1.3.2;
compatible compression versions are needed for identical outer CTZ bytes.
Original numeric arrays/schema bytes are stored losslessly without rounding.
Allow several GB of temporary disk space. Numerical replay uses the pinned
environment; do not infer safety/theorems from the archive format.

For a read-only mathematical audit after restoring and installing the pinned
research environment:

    cd panda_research
    python scripts/audit_saved_extended_v4.py --output /tmp/new-saved-v4-audit.json

There is no QP resolve or new motion in that audit. To rerun strict full source
freeze checks/motion, use the full source branch a2-extended-v4, which retains
the immutable original archived files. This ZIP supplies the complete NEW
overlay and unchanged runtime context, without duplicating all older archives
and Git history.

REVIEW.zip is an OPTIONAL small code/table/report subset for convenient review.
It explicitly omits raw payloads and cannot substitute for full reproduction.
The outer complete ZIP includes every encoded raw file, with reconstruction
proof and manifest. No independent reviewer identity/signature is fabricated.
Official A3 comparisons and Level 1 certification remain NO-GO.
''')
    # A small usable download alongside the complete archive, clearly scoped.
    review=payload/'REVIEW.zip'
    with zipfile.ZipFile(review,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        z.writestr('REVIEW_SCOPE.txt','CODE/TABLE/REPORT SUBSET ONLY. Full raw traces are in the complete ZIP evidence/ payload. This review subset cannot establish complete raw-trace reproduction.\n')
        for p in sorted(payload.rglob('*')):
            if not p.is_file() or p==review or 'evidence' in p.relative_to(payload).parts:continue
            if p.stat().st_size>4*(1<<20):continue
            z.write(p,str(p.relative_to(payload)))
    package={str(p.relative_to(payload)):{'sha256':digest(p),'size':p.stat().st_size} for p in sorted(payload.rglob('*')) if p.is_file()}
    write(payload/'PACKAGE_MANIFEST.json',{'files':package,'excludes_self_hash':True,'logical_CTZ_file_count':len(encoded)})
    print('New logical files',len(new),'CTZ',len(encoded),'payload bytes',sum(r['size'] for r in package.values()),'review bytes',review.stat().st_size,flush=True)


if __name__=='__main__':main()
