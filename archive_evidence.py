"""Losslessly pack CTZ members into shared solid XZ streams; restore exact CTZ.

Standard-library-only delivery helper, separate from scientific trace encoding.
All ZIP metadata and original file checksums are retained. Every restored CTZ
must match its ORIGINAL bytes. No numeric decoding/rounding or pickle occurs.
"""
from pathlib import Path,PurePosixPath
import argparse,base64,hashlib,io,json,lzma,shutil,tarfile,tempfile,zipfile,zlib,sys


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1<<20),b''):h.update(block)
    return h.hexdigest()


def safe(base,name):
    p=PurePosixPath(name)
    if p.is_absolute() or '..' in p.parts or not p.parts:raise ValueError('Unsafe archive path')
    target=Path(base).joinpath(*p.parts)
    if not target.resolve().is_relative_to(Path(base).resolve()):raise ValueError('Path escapes destination')
    return target


def dump(path,value):
    with Path(path).open('x') as f:json.dump(value,f,indent=2);f.write('\n')


def roles(node,path='',result=None):
    result={} if result is None else result
    if isinstance(node,dict):
        if 'file' in node and 'raw_sha256' in node:result[node['file']]=path
        if node.get('kind')=='dicts':
            for key,value in zip(node['keys'],node['columns']):roles(value,path+'/'+key,result)
        else:
            for key,value in node.items():roles(value,path+'/'+key,result)
    elif isinstance(node,list):
        for i,value in enumerate(node):roles(value,path+'/'+str(i),result)
    return result


INFO_FIELDS=['filename','date_time','compress_type','create_system','create_version',
             'extract_version','reserved','flag_bits','volume','internal_attr','external_attr']


def pack(root,paths,out,segment,cache):
    root=Path(root).resolve();out=Path(out);out.mkdir(parents=True,exist_ok=True)
    cache=Path(cache);cache.mkdir(parents=True,exist_ok=True)
    existing=set()
    for index in out.glob('*.index.json'):
        existing.update(json.loads(index.read_text())['new_blocks'])
    traces=[];new={}
    for path in paths:
        path=Path(path).resolve();logical=str(path.relative_to(root));entries=[]
        with zipfile.ZipFile(path) as archive:
            schema=json.loads(archive.read('schema.json'));names=roles(schema)
            for info in archive.infolist():
                payload=archive.read(info);key=hashlib.sha256(payload).hexdigest()
                record={k:getattr(info,k) for k in INFO_FIELDS}
                record.update(comment=base64.b64encode(info.comment).decode(),extra=base64.b64encode(info.extra).decode(),
                              block_sha256=key,uncompressed_size=len(payload))
                entries.append(record)
                if key not in existing and key not in new:
                    block=cache/key
                    if not block.exists():
                        with block.open('xb') as f:f.write(payload)
                    if sha(block)!=key:raise ValueError('Cached block corruption')
                    new[key]={'size':len(payload),'role':names.get(info.filename,'/schema')}
            traces.append({'path':logical,'size':path.stat().st_size,'sha256':sha(path),
                           'comment':base64.b64encode(archive.comment).decode(),'entries':entries})
        print('indexed',logical,flush=True)
    packed=out/(segment+'.tar.xz')
    with packed.open('xb') as raw:
        # Moderate encoder effort, long dictionary for shared shuffled floats.
        with lzma.LZMAFile(raw,'w',format=lzma.FORMAT_XZ,
                          filters=[{'id':lzma.FILTER_LZMA2,'preset':3,'dict_size':1<<26}]) as xz:
            with tarfile.open(fileobj=xz,mode='w|') as tar:
                for key,d in sorted(new.items(),key=lambda v:(v[1]['role'],v[1]['size'],v[0])):
                    info=tarfile.TarInfo(key);info.size=d['size'];info.mode=0o644;info.mtime=0
                    with (cache/key).open('rb') as f:tar.addfile(info,f)
    # Individual GitHub blobs remain below 100 MiB; the outer ZIP is one file.
    parts=[]
    with packed.open('rb') as f:
        i=1
        while True:
            block=f.read(80*(1<<20))
            if not block:break
            part=out/(segment+f'.tar.xz.{i:03d}')
            with part.open('xb') as dest:dest.write(block)
            parts.append({'file':part.name,'size':len(block),'sha256':sha(part)});i+=1
    packed.unlink()
    record={'format':'CTZ_EXACT_CONTAINER_SHARED_XZ_V1','segment':segment,'traces':traces,
            'new_blocks':new,'parts':parts,'python':sys.version,'zlib':zlib.ZLIB_RUNTIME_VERSION,
            'no_numeric_values_changed':True,'restore_requires_exact_original_CTZ_sha256':True}
    dump(out/(segment+'.index.json'),record)
    print('packed',segment,'traces',len(traces),'unique_new_bytes',sum(d['size'] for d in new.values()),
          'compressed_bytes',sum(p['size'] for p in parts),flush=True)
    return record


class PartsReader:
    def __init__(self,paths):self.paths=iter(paths);self.current=None
    def read(self,n=-1):
        chunks=[];left=n
        while left!=0:
            if self.current is None:
                try:self.current=next(self.paths).open('rb')
                except StopIteration:break
            data=self.current.read(left)
            if data:
                chunks.append(data)
                if left>0:left-=len(data)
            else:self.current.close();self.current=None
        return b''.join(chunks)
    def close(self):
        if self.current is not None:self.current.close()


def restore(evidence,destination,scratch=None):
    evidence=Path(evidence);destination=Path(destination)
    indices=[json.loads(p.read_text()) for p in sorted(evidence.glob('*.index.json'))]
    if not indices:raise ValueError('No evidence indices')
    expected={k:v for idx in indices for k,v in idx['new_blocks'].items()}
    results=[]
    with tempfile.TemporaryDirectory(prefix='a2-exact-blocks-',dir=scratch) as tmp:
        cache=Path(tmp)
        for idx in indices:
            if idx['format']!='CTZ_EXACT_CONTAINER_SHARED_XZ_V1':raise ValueError('Unknown delivery encoding')
            paths=[safe(evidence,p['file']) for p in idx['parts']]
            for p,record in zip(paths,idx['parts']):
                if p.stat().st_size!=record['size'] or sha(p)!=record['sha256']:raise ValueError('Packed part checksum mismatch')
            reader=PartsReader(paths)
            try:
                with lzma.LZMAFile(reader,'r') as xz:
                    with tarfile.open(fileobj=xz,mode='r|') as tar:
                        for member in tar:
                            key=member.name
                            if key not in expected or not member.isfile() or member.size!=expected[key]['size']:
                                raise ValueError('Unexpected block member')
                            target=safe(cache,key)
                            if target.exists():raise ValueError('Duplicate archive block')
                            with target.open('xb') as f:shutil.copyfileobj(tar.extractfile(member),f)
                            if sha(target)!=key:raise ValueError('Uncompressed block checksum mismatch')
            finally:reader.close()
        for idx in indices:
            for record in idx['traces']:
                target=safe(destination,record['path']);target.parent.mkdir(parents=True,exist_ok=True)
                if target.exists():
                    if sha(target)!=record['sha256']:raise ValueError('Refusing to overwrite different existing evidence')
                else:
                    with zipfile.ZipFile(target,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
                        archive.comment=base64.b64decode(record['comment'])
                        for entry in record['entries']:
                            info=zipfile.ZipInfo(entry['filename'],tuple(entry['date_time']))
                            for k in INFO_FIELDS:
                                if k not in ['filename','date_time']:setattr(info,k,entry[k])
                            info.comment=base64.b64decode(entry['comment']);info.extra=base64.b64decode(entry['extra'])
                            block=cache/entry['block_sha256']
                            archive.writestr(info,block.read_bytes(),compresslevel=6)
                if target.stat().st_size!=record['size'] or sha(target)!=record['sha256']:
                    raise ValueError('Rebuilt CTZ differs from original bytes; keep original evidence and inspect zlib version')
                results.append({'path':record['path'],'sha256':record['sha256'],'byte_exact':True})
                print('restored exact',record['path'],flush=True)
    return {'format':'CTZ_EXACT_CONTAINER_SHARED_XZ_V1','all_original_CTZ_bytes_reconstructed':True,
            'files':results,'python':sys.version,'zlib':zlib.ZLIB_RUNTIME_VERSION}


def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('pack');p.add_argument('--root',type=Path,required=True);p.add_argument('--paths',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--segment',required=True);p.add_argument('--cache',type=Path,required=True)
    p=sub.add_parser('restore');p.add_argument('--evidence',type=Path,default=Path('evidence'));p.add_argument('--destination',type=Path,default=Path('.'))
    p.add_argument('--scratch',type=Path);p.add_argument('--report',type=Path)
    args=parser.parse_args()
    if args.command=='pack':pack(args.root,[args.root/p for p in args.paths.read_text().splitlines() if p],args.output,args.segment,args.cache)
    else:
        result=restore(args.evidence,args.destination,args.scratch)
        if args.report:dump(args.report,result)


if __name__=='__main__':main()
