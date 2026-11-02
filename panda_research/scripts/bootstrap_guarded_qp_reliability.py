"""Restore exact evidence and reproduce the versioned solver remediation."""
from pathlib import Path
import sys
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];REPO=ROOT.parent
sys.path.insert(0,str(ROOT/'scripts'))
import argparse,hashlib,json,re,subprocess
from datetime import datetime,timezone

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',action='store_true')
    p.add_argument('--verify-only',action='store_true');p.add_argument('--qp-only',action='store_true')
    p.add_argument('--prefix',default='remediation_replay_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    p.add_argument('--scratch',type=Path);a=p.parse_args()
    if sum([a.run,a.verify_only,a.qp_only])>1:p.error('Choose one mode')
    if not re.fullmatch('[A-Za-z0-9_-]+',a.prefix):raise ValueError('Unsafe exclusive run prefix')
    subset=REPO/'QP_SUBSET_MANIFEST.json'
    if subset.exists():
        if not a.qp_only:raise ValueError('Small QP package: use --qp-only. Full trajectory replay needs the complete evidence ZIP.')
        files=json.loads(subset.read_text())['files']
        for n,r in files.items():
            if sha(REPO/n)!=r['sha256']:raise ValueError('QP subset checksum differs: '+n)
    if a.qp_only:
        output=ROOT/f'reports/guarded_qp_reliability_v1/{a.prefix}_strict_T27'
        return subprocess.call([sys.executable,str(ROOT/'scripts/qualify_guarded_qp_strict_v1_1.py'),'--output',str(output)],cwd=ROOT)
    if (REPO/'evidence').is_dir():
        from archive_regular_evidence import restore as restore_regular
        from archive_evidence import restore as restore_ctz
        regular=restore_regular(REPO/'evidence',REPO,a.scratch);traces=restore_ctz(REPO/'evidence',REPO,a.scratch)
        print('Restored exact regular files',len(regular['files']),'CTZ files',len(traces['files']),flush=True)
        manifest=json.loads((REPO/'SOURCE_MANIFEST_GUARDED_QP.json').read_text())
        bad=[n for n,r in manifest['logical_files'].items() if sha(REPO/n)!=r['sha256']]
        if bad:raise ValueError('Restored source checksum differs: '+str(bad[:10]))
    if not (REPO/'.git').exists():
        subprocess.run(['git','init','-q','--initial-branch=local-guarded-qp-reproduction'],cwd=REPO,check=True)
        for key,value in [('user.name','Local QP Reproduction'),('user.email','local-reproduction@invalid')]:
            subprocess.run(['git','config',key,value],cwd=REPO,check=True)
        frozen=['policy/v1.2.2-r4/FROZEN_INPUTS.json','policy/a2_extended_v4/FROZEN_INPUTS.json',
            'policy/a2_acceptance_v1/PREDECLARATION.json','policy/guarded_qp_reliability_v1/PREDECLARATION.json',
            'policy/guarded_qp_reliability_v1/CLASSIFICATION_EXTENSION_V1_1.json']
        subprocess.run(['git','add','-f','--',*['panda_research/'+n for n in frozen]],cwd=REPO,check=True)
        subprocess.run(['git','commit','-q','-m','LOCAL reproduction staging only; not historical provenance or independent verification'],cwd=REPO,check=True)
        print('Created explicitly labeled LOCAL input-staging metadata; no historical commit/signature reconstructed.',flush=True)
    command=[sys.executable,str(ROOT/'scripts/replay_guarded_qp_reliability.py'),'--prefix',a.prefix]
    if not a.run:command.append('--verify-only')
    return subprocess.call(command,cwd=ROOT)

if __name__=='__main__':raise SystemExit(main())
