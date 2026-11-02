"""Lossless shared-XZ storage for original gzip/ZIP/RAR and other large files.

Gzip JSON is inflated without parsing or rounding and repacked only when its
EXACT original deflate stream is reproducible. Otherwise raw bytes are kept.
Each reconstructed file must match its original SHA-256 before it is written.
This is storage instrumentation, not a numerical or experimental amendment.
"""
from pathlib import Path
import sys
sys.dont_write_bytecode=True
import argparse,base64,gzip,hashlib,json,lzma,shutil,tarfile,tempfile,zlib
from archive_evidence import PartsReader,safe,sha,dump


def gzip_header_length(data):
    if data[:3]!=b'\x1f\x8b\x08' or len(data)<18:raise ValueError('Not gzip')
    flags=data[3];i=10
    if flags&4:
        n=int.from_bytes(data[i:i+2],'little');i+=2+n
    for flag in [8,16]:
        if flags&flag:i=data.index(b'\0',i)+1
    if flags&2:i+=2
    return i


def deflate(payload,level):
    obj=zlib.compressobj(level,zlib.DEFLATED,-15)
    return obj.compress(payload)+obj.flush()


def file_encoding(path):
    raw=path.read_bytes();record={'size':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),
                               'mode':path.stat().st_mode&0o777,'encoding':'RAW'}
    payload=raw
    if path.suffix=='.gz':
        try:
            start=gzip_header_length(raw);inflated=gzip.decompress(raw)
            level={2:9,4:1}.get(raw[8],6)
            if deflate(inflated,level)==raw[start:-8]:
                payload=inflated;record.update(encoding='EXACT_GZIP_REPACK',level=level,
                    header=base64.b64encode(raw[:start]).decode(),trailer=base64.b64encode(raw[-8:]).decode())
        except (ValueError,OSError,EOFError,zlib.error):
            pass # Preserve unusual/partial historical files as exact raw bytes.
    record['block_sha256']=hashlib.sha256(payload).hexdigest()
    return payload,record


def pack(root,paths,out,segment,cache):
    root=Path(root).resolve();out=Path(out);out.mkdir(parents=True,exist_ok=True)
    cache=Path(cache);cache.mkdir(parents=True,exist_ok=True);existing=set()
    for p in out.glob('*.regular.json'):existing.update(json.loads(p.read_text())['new_blocks'])
    records={};blocks={}
    for p in paths:
        p=Path(p).resolve();name=str(p.relative_to(root));payload,record=file_encoding(p);records[name]=record
        key=record['block_sha256']
        if key not in existing and key not in blocks:
            target=cache/key
            if not target.exists():
                with target.open('xb') as f:f.write(payload)
            if sha(target)!=key:raise ValueError('Corrupt shared file block')
            blocks[key]={'size':len(payload),'encoding':record['encoding']}
        print('indexed original bytes',name,record['encoding'],flush=True)
    stream=out/(segment+'.regular.tar.xz')
    with stream.open('xb') as raw:
        with lzma.LZMAFile(raw,'w',format=lzma.FORMAT_XZ,
                    filters=[{'id':lzma.FILTER_LZMA2,'preset':3,'dict_size':1<<28}]) as xz:
            with tarfile.open(fileobj=xz,mode='w|') as tar:
                for key,rec in sorted(blocks.items(),key=lambda item:(item[1]['encoding'],item[1]['size'],item[0])):
                    info=tarfile.TarInfo(key);info.size=rec['size'];info.mode=0o644;info.mtime=0
                    with (cache/key).open('rb') as f:tar.addfile(info,f)
    parts=[]
    with stream.open('rb') as f:
        i=1
        while True:
            data=f.read(80*(1<<20))
            if not data:break
            p=out/(segment+f'.regular.tar.xz.{i:03d}')
            with p.open('xb') as dest:dest.write(data)
            parts.append({'file':p.name,'size':len(data),'sha256':sha(p)});i+=1
    stream.unlink()
    result={'format':'A2_EXACT_REGULAR_FILES_XZ_V1','segment':segment,'files':records,'new_blocks':blocks,
            'parts':parts,'python':sys.version,'zlib':zlib.ZLIB_RUNTIME_VERSION,
            'numeric_parsing_or_rounding_performed':False}
    dump(out/(segment+'.regular.json'),result)
    print('packed',segment,'files',len(records),'original_bytes',sum(r['size'] for r in records.values()),
          'unique_inflated_bytes',sum(r['size'] for r in blocks.values()),'compressed_bytes',sum(r['size'] for r in parts),flush=True)
    return result


def restore(evidence,destination,scratch=None):
    evidence=Path(evidence);destination=Path(destination)
    indices=[json.loads(p.read_text()) for p in sorted(evidence.glob('*.regular.json'))]
    expected={k:v for idx in indices for k,v in idx['new_blocks'].items()};results=[]
    with tempfile.TemporaryDirectory(prefix='a2-original-files-',dir=scratch) as tmp:
        cache=Path(tmp)
        for idx in indices:
            if idx['format']!='A2_EXACT_REGULAR_FILES_XZ_V1':raise ValueError('Unexpected file archive format')
            parts=[safe(evidence,r['file']) for r in idx['parts']]
            for p,r in zip(parts,idx['parts']):
                if p.stat().st_size!=r['size'] or sha(p)!=r['sha256']:raise ValueError('File payload checksum mismatch')
            reader=PartsReader(parts)
            try:
                with lzma.LZMAFile(reader,'r') as xz:
                    with tarfile.open(fileobj=xz,mode='r|') as tar:
                        for member in tar:
                            if member.name not in expected or not member.isfile() or member.size!=expected[member.name]['size']:
                                raise ValueError('Unexpected original-file block')
                            p=safe(cache,member.name)
                            if p.exists():raise ValueError('Duplicated original-file block')
                            with p.open('xb') as f:shutil.copyfileobj(tar.extractfile(member),f)
                            if sha(p)!=member.name:raise ValueError('Inflated original-file block checksum mismatch')
            finally:reader.close()
        for idx in indices:
            for name,r in idx['files'].items():
                target=safe(destination,name);target.parent.mkdir(parents=True,exist_ok=True)
                if target.exists():
                    if sha(target)!=r['sha256']:raise ValueError('Refuse to replace different original evidence: '+name)
                else:
                    data=(cache/r['block_sha256']).read_bytes()
                    if r['encoding']=='EXACT_GZIP_REPACK':
                        data=base64.b64decode(r['header'])+deflate(data,r['level'])+base64.b64decode(r['trailer'])
                    elif r['encoding']!='RAW':raise ValueError('Unknown regular-file encoding')
                    if len(data)!=r['size'] or hashlib.sha256(data).hexdigest()!=r['sha256']:
                        raise ValueError('Exact original-file reconstruction failed; inspect recorded zlib version')
                    with target.open('xb') as f:f.write(data)
                    target.chmod(r['mode'])
                if target.stat().st_size!=r['size'] or sha(target)!=r['sha256']:raise ValueError('Original-file checksum differs')
                results.append({'path':name,'sha256':r['sha256'],'byte_exact':True})
                print('restored exact original file',name,flush=True)
    return {'all_original_file_bytes_reconstructed':True,'files':results,'zlib':zlib.ZLIB_RUNTIME_VERSION}


def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('pack');p.add_argument('--root',type=Path,required=True);p.add_argument('--paths',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--segment',required=True);p.add_argument('--cache',type=Path,required=True)
    p=sub.add_parser('restore');p.add_argument('--evidence',type=Path,default=Path('evidence'))
    p.add_argument('--destination',type=Path,default=Path('.'));p.add_argument('--scratch',type=Path);p.add_argument('--report',type=Path)
    args=parser.parse_args()
    if args.command=='pack':pack(args.root,[args.root/n for n in args.paths.read_text().splitlines() if n],args.output,args.segment,args.cache)
    else:
        result=restore(args.evidence,args.destination,args.scratch)
        if args.report:dump(args.report,result)


if __name__=='__main__':main()
