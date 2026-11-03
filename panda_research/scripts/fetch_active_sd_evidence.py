"""Fetch small exact evidence parts into an extracted numerical package.

Use an immutable artifact-commit raw URL as --base-url. SHA256 pins every
download; existing changed files are never replaced. No simulation is run.
"""
from pathlib import Path,PurePosixPath
import argparse,hashlib,json,time,urllib.request,urllib.error

def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--base-url',required=True)
    p.add_argument('--destination',type=Path,default=Path(__file__).resolve().parents[2]);a=p.parse_args()
    root=a.destination.resolve();manifest=json.loads((root/'EVIDENCE_DOWNLOAD_MANIFEST.json').read_text())
    if not a.base_url.startswith('https://'):raise ValueError('Use an HTTPS artifact URL')
    for name,record in manifest['files'].items():
        logical=PurePosixPath(name)
        if logical.is_absolute() or '..' in logical.parts or logical.parts[0]!='evidence':raise ValueError('Unsafe manifest path')
        target=root.joinpath(*logical.parts)
        if not target.resolve().is_relative_to(root):raise ValueError('Unsafe destination')
        target.parent.mkdir(parents=True,exist_ok=True)
        if target.exists():
            if sha(target)!=record['sha256']:raise ValueError('Existing file changed; preserving it: '+name)
            print('verified existing',name,flush=True);continue
        partial=target.with_name(target.name+'.partial');last=None
        for attempt in range(3):
            try:
                offset=partial.stat().st_size if partial.exists() else 0
                request=urllib.request.Request(a.base_url.rstrip('/')+'/'+name,headers={'Range':f'bytes={offset}-'} if offset else {})
                with urllib.request.urlopen(request,timeout=30) as response:
                    append=offset>0 and response.status==206
                    with partial.open('ab' if append else 'wb') as f:
                        while True:
                            block=response.read(1<<20)
                            if not block:break
                            f.write(block)
                            if f.tell()>record['size']:raise ValueError('Download exceeds declared size')
                if partial.stat().st_size!=record['size'] or sha(partial)!=record['sha256']:
                    raise ValueError('Incomplete or changed bytes; preserving partial: '+name)
                partial.rename(target);print('downloaded and verified',name,record['size'],flush=True);last=None;break
            except (urllib.error.URLError,TimeoutError,OSError) as error:
                last=error;time.sleep(1)
        if last is not None:raise last
    print('All exact evidence parts ready; run RUN_ACTIVE_FILTER.py --restore --verify-only',flush=True)

if __name__=='__main__':main()
