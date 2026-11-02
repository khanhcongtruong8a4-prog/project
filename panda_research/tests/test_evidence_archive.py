"""Delivery encoding must reconstruct exact original containers or refuse."""
from pathlib import Path
import sys
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'));sys.path.insert(0,str(ROOT/'src'))
import argparse,json,tempfile,unittest,zipfile
from archive_evidence import pack,restore,safe,sha
from panda_closed_loop.config import digest
from test_p1_r3 import Results


class EvidenceArchiveTests(unittest.TestCase):
    def fixture(self,root,name,extra=b''):
        path=root/name;path.parent.mkdir(parents=True,exist_ok=True)
        with zipfile.ZipFile(path,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
            z.comment=b'original scientific container'
            info=zipfile.ZipInfo('arrays/00000.npy',(2026,11,2,1,2,4))
            info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o640<<16
            info.comment=b'entry comment';z.writestr(info,bytes(range(256))*100+extra,compresslevel=6)
            z.writestr('schema.json',json.dumps({'root':{'file':'arrays/00000.npy','raw_sha256':'fixture'}}))
        return path

    def test_exact_container_metadata_comments_and_data(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);p=self.fixture(root,'run/a.ctz');out=root/'delivery'
            pack(root,[p],out,'one',root/'cache')
            result=restore(out,root/'restored')
            self.assertTrue(result['all_original_CTZ_bytes_reconstructed'])
            self.assertEqual(p.read_bytes(),(root/'restored/run/a.ctz').read_bytes())

    def test_global_dedup_across_segments_preserves_both_containers(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);a=self.fixture(root,'a.ctz');b=self.fixture(root,'b.ctz');out=root/'delivery'
            first=pack(root,[a],out,'one',root/'cache');second=pack(root,[b],out,'two',root/'cache')
            self.assertGreater(len(first['new_blocks']),0);self.assertEqual(len(second['new_blocks']),0)
            r=restore(out,root/'restored');self.assertEqual(len(r['files']),2)

    def test_corrupt_packed_part_rejected_before_restore(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);p=self.fixture(root,'a.ctz');out=root/'delivery'
            record=pack(root,[p],out,'one',root/'cache');part=out/record['parts'][0]['file']
            data=bytearray(part.read_bytes());data[12]^=1;part.write_bytes(data)
            with self.assertRaisesRegex(ValueError,'checksum'):restore(out,root/'restored')

    def test_existing_different_evidence_never_overwritten(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);p=self.fixture(root,'a.ctz');out=root/'delivery'
            pack(root,[p],out,'one',root/'cache');dest=root/'restored';dest.mkdir();bad=dest/'a.ctz';bad.write_bytes(b'preserve me')
            with self.assertRaisesRegex(ValueError,'overwrite'):restore(out,dest)
            self.assertEqual(bad.read_bytes(),b'preserve me')

    def test_paths_cannot_escape_root(self):
        with tempfile.TemporaryDirectory() as td:
            for p in ['../outside','/absolute','a/../../outside']:
                with self.assertRaises(ValueError):safe(td,p)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--report',type=Path,required=True);args=parser.parse_args()
    result=unittest.TextTestRunner(verbosity=2,resultclass=Results).run(unittest.defaultTestLoader.loadTestsFromTestCase(EvidenceArchiveTests))
    with args.report.open('x') as f:
        json.dump({'scope':'LOSSLESS_DELIVERY_ENCODING_ONLY_NO_SCIENTIFIC_CHANGE','tests_run':result.testsRun,
            'overall_pass':result.wasSuccessful(),'checks':result.rows,'source_hashes':{n:digest(ROOT/n) for n in
            ['scripts/archive_evidence.py','tests/test_evidence_archive.py']}},f,indent=2);f.write('\n')
    raise SystemExit(0 if result.wasSuccessful() else 1)
