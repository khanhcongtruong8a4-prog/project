"""Verify/restore this release and reproduce its local numerical analysis.

No Git history or independent signatures are synthesized. Historical frozen
simulation CLIs retain all original provenance checks and require the linked
full checkout. The compact ZIP runs the analysis tests and exact T27 directly.
"""
from pathlib import Path
import sys
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];REPO=ROOT.parent
sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'scripts'))
import argparse,hashlib,importlib.metadata,json,re,subprocess
from datetime import datetime,timezone

def load(p):return json.loads(Path(p).read_text())
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def write(p,d):
    with Path(p).open('x') as f:json.dump(d,f,indent=2,allow_nan=False);f.write('\n')

def verify():
    if tuple(sys.version_info[:3])!=(3,12,14):raise ValueError('Exact reproduction requires recorded Python3.12.14')
    for line in (ROOT/'requirements.lock.txt').read_text().splitlines():
        if '==' in line:
            name,version=line.split('==',1)
            if importlib.metadata.version(name)!=version:raise ValueError('Pinned package differs: '+name)
    manifest=REPO/'ACTIVE_SD_PACKAGE_MANIFEST.json'
    if manifest.exists():
        bad=[n for n,r in load(manifest)['files'].items() if not (REPO/n).is_file() or sha(REPO/n)!=r['sha256']]
        if bad:raise ValueError('Package mismatch: '+str(bad[:10]))
    from panda_closed_loop.guarded_qp_final_v1 import verify_release
    from panda_closed_loop.a2_policy_v4 import build_amended_system
    release=verify_release();system=build_amended_system()
    import panda_closed_loop.active_sampled_analysis_v1 as analysis
    if not Path(analysis.__file__).is_relative_to(ROOT):raise ValueError('Imported a different working tree')
    return {'package_verified':True,'model_assembly_passed':True,'alpha_v':system.barriers.alpha_v,
            'native_library_sha256':release['backend']['library_sha256'],'new_motion':False,'A3':False,'Level1':False}

def restore(scratch):
    if not (REPO/'evidence').is_dir():raise ValueError('Raw restoration requires full evidence package')
    from archive_evidence import restore as restore_ctz
    from archive_regular_evidence import restore as restore_gzip
    ctz=restore_ctz(REPO/'evidence',REPO,scratch)
    regular=restore_gzip(REPO/'evidence',REPO,scratch)
    manifest=load(REPO/'ACTIVE_SD_SOURCE_MANIFEST.json')
    for name,r in manifest['encoded_files'].items():
        if sha(REPO/name)!=r['sha256']:raise ValueError('Restored bytes differ: '+name)
    return {'CTZ_restore':ctz,'gzip_restore':regular,'all_encoded_SHA256_verified':True}

def main():
    p=argparse.ArgumentParser(description=__doc__);g=p.add_mutually_exclusive_group()
    g.add_argument('--verify-only',action='store_true');g.add_argument('--run-numerics',action='store_true')
    g.add_argument('--analyze-traces',action='store_true');p.add_argument('--restore',action='store_true')
    p.add_argument('--scratch',type=Path);p.add_argument('--prefix',default='replay_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'));a=p.parse_args()
    if not re.fullmatch('[A-Za-z0-9_-]+',a.prefix):raise ValueError('Invalid exclusive prefix')
    proof=verify();print(json.dumps(proof,indent=2),flush=True)
    if a.restore:
        restored=restore(a.scratch);print('Restoration checks passed',flush=True)
    if not(a.run_numerics or a.analyze_traces):return 0
    out=ROOT/f'reports/active_sampled_data_v1/reproductions/{a.prefix}';out.mkdir(parents=True,exist_ok=False)
    write(out/'run_started.json',{'start_utc':datetime.now(timezone.utc).isoformat(),'python':sys.version,
        'command':[sys.executable,*sys.argv],'scope':'LOCAL_REPRODUCTION_NOT_EXTERNAL_OR_INDEPENDENT_VERIFICATION',
        'official_A3':False,'Level1':False,'signatures':None})
    def run(name,cmd):
        with (out/(name+'.log')).open('x') as f:return subprocess.run(cmd,cwd=ROOT,stdout=f,stderr=subprocess.STDOUT).returncode
    codes={}
    if a.run_numerics:
        codes['six_analysis_contracts']=run('six_analysis_contracts',[sys.executable,'tests/test_active_sampled_analysis_v1.py'])
        codes['three_clock_contracts']=run('three_clock_contracts',[sys.executable,'tests/test_active_sampled_clock_v1.py'])
        codes['T27_39']=run('T27_39',[sys.executable,'scripts/qualify_guarded_qp_strict_v1_1.py','--output',str(out/'T27')])
        fixtures=load(out/'T27/SUMMARY.json')
        passed=all(c==0 for c in codes.values()) and fixtures['overall_pass'] and fixtures['fixture_count']==39
    else:
        for label,folder,extra in [
            ('baseline',ROOT/'runs/guarded_qp_reliability_v1/sd_v1_fresh_active_E3',[]),
            ('alpha10',ROOT/'runs/active_sampled_data_v1/alpha10_active_challenge',['--alpha10'])]:
            codes[label]=run(label,[sys.executable,'scripts/analyze_active_sampled_v1_3.py','--input',str(folder),
                '--output',str(out/(label+'_operators')),*extra])
        if all(c==0 for c in codes.values()):
            codes['modified_equation']=run('modified_equation',[sys.executable,'scripts/attribute_modified_equation_v1.py',
                '--input',str(ROOT/'runs/guarded_qp_reliability_v1/sd_v1_fresh_active_E3'),
                '--operators',str(out/'baseline_operators'),'--output',str(out/'modified_equation')])
        passed=all(c==0 for c in codes.values())
    write(out/'SUMMARY.json',{'reproduction_passed':passed,'exit_codes':codes,
        'failed_active_refinement_remains_failed':True,'gate_promoted_by_reproduction':False,'A3':False,'Level1':False})
    return 0 if passed else 3

if __name__=='__main__':raise SystemExit(main())
