"""Restore immutable original JSON (or pinned-runtime gzip) from baseline CTZ."""
from pathlib import Path
import sys
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[1]/'src'))
import argparse,gzip,hashlib,json,shutil
from panda_closed_loop.trace_archive import read_trace


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--gzip',action='store_true',help='Restore original gzip bytes; requires compatible Python/zlib encoder')
    parser.add_argument('--only',help='Original gzip filename for a one-trace verification')
    args=parser.parse_args();output=args.output.resolve()
    if output==HERE:raise ValueError('Use a separate destination to preserve archival evidence')
    output.mkdir(parents=True,exist_ok=True)
    index=json.loads((HERE/'TRANSCODE_INDEX.json').read_text())
    records=[r for r in index['records'] if not args.only or r['source_gzip_file']==args.only]
    if not records:raise ValueError('No matching trace')
    for r in records:
        value=read_trace(HERE/r['ctz']['file'],r['ctz'])
        raw=json.dumps(value,separators=(',',':'),allow_nan=False).encode()
        if hashlib.sha256(raw).hexdigest()!=r['source_JSON_sha256']:raise ValueError('Original JSON bytes differ')
        payload=gzip.compress(raw,mtime=0) if args.gzip else raw
        target=output/(r['source_gzip_file'] if args.gzip else r['source_gzip_file'][:-3])
        if args.gzip and hashlib.sha256(payload).hexdigest()!=r['source_gzip_sha256']:
            raise ValueError('Gzip encoder differs; restore JSON without --gzip for portable exact raw JSON')
        target.parent.mkdir(parents=True,exist_ok=True)
        with target.open('xb') as f:f.write(payload)
        print(target,flush=True)
    if not args.only:
        for path in HERE.rglob('*'):
            if not path.is_file() or path.suffix=='.ctz' or path.name in ['restore_json.py','TRANSCODE_INDEX.json','CODEC_README.md']:continue
            target=output/path.relative_to(HERE);target.parent.mkdir(parents=True,exist_ok=True)
            if target.exists():raise FileExistsError(target)
            shutil.copy2(path,target)

if __name__=='__main__':main()
