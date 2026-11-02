"""Losslessly transcode new baseline evidence; never change original gzip files."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'src'))
import gzip,hashlib,json,platform,shutil,time,zlib
from panda_closed_loop.trace_archive import write_trace,read_trace
SOURCE=Path('/workspace/a2-baseline-clean/panda_research/runs/p1_r4/baseline_clean_reproduction_v1')
TARGET=ROOT/'runs/a2_extended_baseline_clean_ctz'

def sha(b):return hashlib.sha256(b).hexdigest()
def write(p,v):
    with p.open('x') as f:json.dump(v,f,indent=2);f.write('\n')

def main():
    TARGET.mkdir(parents=True,exist_ok=True)
    index=[]
    for path in sorted(SOURCE.rglob('*')):
        if not path.is_file():continue
        relative=path.relative_to(SOURCE)
        if path.suffixes[-2:]==['.json','.gz']:
            original=path.read_bytes();raw=gzip.decompress(original);value=json.loads(raw)
            destination=TARGET/(str(relative)[:-len('.json.gz')]+'.ctz')
            started=time.perf_counter();record=write_trace(destination,value)
            restored=read_trace(destination,record)
            restored_raw=json.dumps(restored,separators=(',',':'),allow_nan=False).encode()
            assert restored_raw==raw,path
            regenerated=gzip.compress(restored_raw,mtime=0)
            assert regenerated==original,path
            assert path.read_bytes()==original,path
            index.append({'source_gzip_file':str(relative),'source_gzip_bytes':len(original),'source_gzip_sha256':sha(original),
                'source_JSON_bytes':len(raw),'source_JSON_sha256':sha(raw),'ctz':record,'ctz_bytes':destination.stat().st_size,
                'original_JSON_byte_reconstruction_verified':True,'original_gzip_reconstruction_verified_on_recorded_runtime':True,
                'encode_and_checks_s':time.perf_counter()-started})
            print(path.name,'->',destination.name,round(destination.stat().st_size/len(original),3),flush=True)
        else:
            target=TARGET/relative;target.parent.mkdir(parents=True,exist_ok=True)
            if target.exists():raise FileExistsError(target)
            shutil.copy2(path,target)
    summary={'scope':'LOSSLESS_ARCHIVAL_ONLY_NOT_A_NEW_NUMERICAL_EXPERIMENT','source_run':str(SOURCE),
        'source_commit':'45d1ada','python':platform.python_version(),'zlib_version':zlib.ZLIB_RUNTIME_VERSION,
        'records':index,'gzip_bytes':sum(r['source_gzip_bytes'] for r in index),'ctz_bytes':sum(r['ctz_bytes'] for r in index),
        'all_originals_unchanged':True,'raw_JSON_and_current_runtime_gzip_reconstruction_exact':True,
        'independent_reviewer_signature':None}
    write(TARGET/'TRANSCODE_INDEX.json',summary)
    print(json.dumps({k:v for k,v in summary.items() if k!='records'},indent=2),flush=True)
if __name__=='__main__':main()
