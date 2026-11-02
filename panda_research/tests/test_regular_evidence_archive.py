"""Exact archival preservation for old gzip, arbitrary bytes and corruption."""
from pathlib import Path
import sys
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'));sys.path.insert(0,str(ROOT/'src'))
import argparse,gzip,io,json,tempfile,unittest
from archive_regular_evidence import pack,restore
from panda_closed_loop.config import digest
from test_p1_r3 import Results


class RegularArchive(unittest.TestCase):
    def test_gzip_header_name_time_and_original_bytes_are_reconstructed(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);p=root/'old.gz';stream=io.BytesIO()
            with gzip.GzipFile(filename='original_name.json',fileobj=stream,mode='wb',mtime=123,compresslevel=9) as g:g.write(b'{"original_float":1.2345678901234567}'*300)
            p.write_bytes(stream.getvalue());out=root/'encoded'
            index=pack(root,[p],out,'first',root/'cache');self.assertEqual(index['files']['old.gz']['encoding'],'EXACT_GZIP_REPACK')
            restore(out,root/'restored');self.assertEqual(p.read_bytes(),(root/'restored/old.gz').read_bytes())

    def test_identical_inflated_payload_is_shared_with_different_gzip_headers(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);out=root/'encoded';a=root/'a.gz';b=root/'b.gz'
            a.write_bytes(gzip.compress(b'same original data'*100,compresslevel=6,mtime=1))
            b.write_bytes(gzip.compress(b'same original data'*100,compresslevel=6,mtime=2))
            index=pack(root,[a,b],out,'shared',root/'cache');self.assertEqual(len(index['new_blocks']),1)
            restore(out,root/'restored')
            for p in [a,b]:self.assertEqual(p.read_bytes(),(root/'restored'/p.name).read_bytes())

    def test_arbitrary_and_partial_gzip_bytes_preserved_as_raw(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);a=root/'source.zip';a.write_bytes(bytes(range(256))*100);b=root/'partial.gz';b.write_bytes(b'\x1f\x8b\x08truncated old failure')
            index=pack(root,[a,b],root/'encoded','raw',root/'cache');self.assertTrue(all(r['encoding']=='RAW' for r in index['files'].values()))
            restore(root/'encoded',root/'restored')
            for p in [a,b]:self.assertEqual(p.read_bytes(),(root/'restored'/p.name).read_bytes())

    def test_corrupt_packed_part_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);p=root/'data.gz';p.write_bytes(gzip.compress(b'original'*100,mtime=0));out=root/'encoded'
            index=pack(root,[p],out,'bad',root/'cache');part=out/index['parts'][0]['file'];data=bytearray(part.read_bytes());data[15]^=1;part.write_bytes(data)
            with self.assertRaisesRegex(ValueError,'checksum'):restore(out,root/'restored')

    def test_existing_different_source_is_never_replaced(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);p=root/'source.bin';p.write_bytes(b'original');out=root/'encoded'
            pack(root,[p],out,'safe',root/'cache');dest=root/'restored';dest.mkdir();other=dest/'source.bin';other.write_bytes(b'user change')
            with self.assertRaisesRegex(ValueError,'Refuse'):restore(out,dest)
            self.assertEqual(other.read_bytes(),b'user change')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--report',type=Path,required=True);args=parser.parse_args()
    result=unittest.TextTestRunner(verbosity=2,resultclass=Results).run(unittest.defaultTestLoader.loadTestsFromTestCase(RegularArchive))
    with args.report.open('x') as f:json.dump({'scope':'STORAGE_ONLY_NO_EXPERIMENTAL_CHANGE','tests_run':result.testsRun,
        'overall_pass':result.wasSuccessful(),'checks':result.rows,'source_hashes':{n:digest(ROOT/n) for n in
        ['scripts/archive_regular_evidence.py','tests/test_regular_evidence_archive.py']}},f,indent=2);f.write('\n')
    raise SystemExit(0 if result.wasSuccessful() else 1)
