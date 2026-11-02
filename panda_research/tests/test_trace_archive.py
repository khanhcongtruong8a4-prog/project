"""Exact CTZ round trips, corruption rejection and real baseline trace coverage."""
from pathlib import Path
import sys
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
import argparse
import gzip
import hashlib
from io import BytesIO
import json
import math
import tempfile
import time
import unittest
import zipfile
import numpy as np
from panda_closed_loop.logging import json_values
from panda_closed_loop.trace_archive import CODEC, canonical_json, read_trace, write_trace

REPRESENTATIVE = None
MEASUREMENTS = {}


def rewrite(path, changed_name, changed_bytes, target):
    with zipfile.ZipFile(path) as src, zipfile.ZipFile(target, 'x', zipfile.ZIP_DEFLATED) as dst:
        for name in src.namelist():
            dst.writestr(name, changed_bytes if name == changed_name else src.read(name))


class TraceArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.folder = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def roundtrip(self, value, name='value.ctz'):
        path = self.folder/name
        record = write_trace(path, value)
        restored = read_trace(path, record)
        normal = json_values(value)
        self.assertEqual(canonical_json(restored), canonical_json(normal))
        # This additionally checks dictionary order, not covered by sort_keys.
        self.assertEqual(json.dumps(restored, separators=(',', ':'), allow_nan=False),
                         json.dumps(normal, separators=(',', ':'), allow_nan=False))
        self.assertEqual(record['canonical_json_sha256'], hashlib.sha256(canonical_json(normal)).hexdigest())
        return restored, path, record

    def test_ragged_lists_missing_keys_none_and_dictionary_order(self):
        value = {'z': [{'q': [1., 2.], 'failure': None}, {'q': [], 'other': True},
                       {'failure': None, 'q': [[1], [2, 3]]}, {}],
                 'a': [[[], [1, 'one', None]], []]}
        restored, _, _ = self.roundtrip(value)
        self.assertEqual(list(restored), ['z', 'a'])
        self.assertEqual(list(restored['z'][2]), ['failure', 'q'])
        self.assertNotIn('failure', restored['z'][1])
        self.assertIsNone(restored['z'][0]['failure'])

    def test_mixed_scalar_types_large_integers_and_signed_zero(self):
        value = [True, 1, 1., False, 0, 0., -0., 2**63+3, -(2**85), 2**130,
                 None, '', 'Panda 🐼', 1e-300, -1e300]
        restored, _, _ = self.roundtrip(value)
        self.assertEqual([type(x) for x in restored], [type(x) for x in value])
        self.assertEqual(math.copysign(1., restored[6]), -1.)
        self.assertEqual(restored[7:10], value[7:10])

    def test_uniform_integer_float_boolean_and_empty_matrices(self):
        value = {'float': [[-0., .25, 1e200], [1e-200, -.5, 8.]],
                 'int': [[0, 2**53+3], [-(2**63), 4]],
                 'bool': [[True, False], [False, True]], 'empty': [[], [], []]}
        restored, path, _ = self.roundtrip(value)
        self.assertEqual(type(restored['int'][0][1]), int)
        self.assertEqual(type(restored['bool'][0][0]), bool)
        self.assertEqual(math.copysign(1., restored['float'][0][0]), -1.)
        with zipfile.ZipFile(path) as z:
            for name in z.namelist():
                if name.endswith('.npy'):
                    a = np.load(BytesIO(z.read(name)), allow_pickle=False)
                    self.assertEqual(a.dtype, np.uint8)
                    self.assertEqual(a.ndim, 2)

    def test_numpy_values_and_tuples_normalize_without_precision_loss(self):
        value = {'array': np.array([[1., -0.], [1e-200, 2.3]], order='F'),
                 'single': np.float32(1.2), 'integer': np.int64(2**53+7),
                 'tuple': (np.bool_(True), np.array([2., 3.]))}
        restored, _, _ = self.roundtrip(value)
        self.assertEqual(restored['single'], float(np.float32(1.2)))
        self.assertEqual(restored['integer'], 2**53+7)

    def test_root_scalars_empty_lists_and_empty_dicts(self):
        for i, value in enumerate([None, [], {}, True, 0, 0., -0., '', 'constant']):
            with self.subTest(value=value):
                restored, _, _ = self.roundtrip(value, f'root_{i}.ctz')
                self.assertIs(type(restored), type(value))

    def test_repeated_string_enums_and_mixed_dictionary_schemas(self):
        values = [{'status': ['PASS', 'FAIL', 'PASS'][i % 3],
                   'optional': None, 'v': [float(i), float(i+1)]} for i in range(30)]
        values.extend([{'v': [1.], 'status': 'PASS'}, {'status': 'PASS'}, {'optional': []}])
        self.roundtrip(values)

    def test_rectangular_float_tensors_and_identical_columns(self):
        values = [{'G': [[1., 2.], [3., -0.]], 'copy': [[1., 2.], [3., -0.]]},
                  {'G': [[1.1, 2.1], [3.1, -0.]], 'copy': [[1.1, 2.1], [3.1, -0.]]}]
        _, path, _ = self.roundtrip(values)
        with zipfile.ZipFile(path) as z:
            schema = json.loads(z.read('schema.json'))
            descriptors = []
            def visit(v):
                if isinstance(v, dict):
                    if 'raw_sha256' in v:
                        descriptors.append(v)
                    for x in v.values():visit(x)
                elif isinstance(v, list):
                    for x in v:visit(x)
            visit(schema)
            tensors = [d for d in descriptors if d['shape'] == [2, 2, 2]]
            self.assertEqual(len(tensors), 2)
            self.assertEqual(tensors[0]['file'], tensors[1]['file'])

    def test_exclusive_creation_does_not_replace_existing_evidence(self):
        _, path, _ = self.roundtrip({'x': [1., 2.]})
        previous = path.read_bytes()
        with self.assertRaises(FileExistsError):
            write_trace(path, {'changed': True})
        self.assertEqual(path.read_bytes(), previous)

    def test_nonfinite_values_are_rejected_before_archive_creation(self):
        for i, value in enumerate([float('nan'), float('inf'), -float('inf')]):
            path = self.folder/f'bad_{i}.ctz'
            with self.assertRaises(ValueError):
                write_trace(path, {'x': value})
            self.assertFalse(path.exists())

    def test_expected_file_or_canonical_hash_mismatch_is_rejected(self):
        _, path, record = self.roundtrip({'x': [1., 2.]})
        wrong = {**record, 'sha256': 'bad'}
        with self.assertRaises(ValueError): read_trace(path, wrong)
        wrong = {**record, 'canonical_json_sha256': 'bad'}
        with self.assertRaises(ValueError): read_trace(path, wrong)

    def test_changed_numeric_block_is_rejected_even_with_rewritten_ZIP_CRC(self):
        _, path, _ = self.roundtrip({'x': [1., 2.]})
        with zipfile.ZipFile(path) as z:
            name = next(n for n in z.namelist() if n.endswith('.npy'))
            payload = bytearray(z.read(name));payload[-1] ^= 1
        changed = self.folder/'changed.ctz'
        rewrite(path, name, bytes(payload), changed)
        with self.assertRaises(ValueError): read_trace(changed)

    def test_changed_schema_canonical_checksum_is_rejected(self):
        _, path, _ = self.roundtrip({'x': [1., 2.]})
        with zipfile.ZipFile(path) as z: schema = json.loads(z.read('schema.json'))
        schema['canonical_json_sha256'] = 'bad'
        changed = self.folder/'changed_schema.ctz'
        rewrite(path, 'schema.json', json.dumps(schema).encode(), changed)
        with self.assertRaises(ValueError): read_trace(changed)

    def test_pickle_object_array_is_never_loaded(self):
        _, path, _ = self.roundtrip({'x': [1., 2.]})
        with zipfile.ZipFile(path) as z:
            name = next(n for n in z.namelist() if n.endswith('.npy'))
        buffer = BytesIO();np.save(buffer, np.array([{'not': 'numeric'}], dtype=object), allow_pickle=True)
        changed = self.folder/'object.ctz'
        rewrite(path, name, buffer.getvalue(), changed)
        with self.assertRaises(ValueError): read_trace(changed)

    def test_representative_full_baseline_cell_zero_trace_roundtrip(self):
        if REPRESENTATIVE is None:
            self.skipTest('Pass --representative-gzip to test a full retained baseline trace')
        original_gzip = REPRESENTATIVE.read_bytes()
        original_json = gzip.decompress(original_gzip)
        value = json.loads(original_json)
        start = time.perf_counter()
        restored, path, record = self.roundtrip(value, 'baseline_cell_0.ctz')
        elapsed = time.perf_counter()-start
        restored_original_order = json.dumps(restored, separators=(',', ':'), allow_nan=False).encode()
        self.assertEqual(restored_original_order, original_json)
        self.assertEqual(REPRESENTATIVE.read_bytes(), original_gzip)
        MEASUREMENTS.update(source=str(REPRESENTATIVE), original_gzip_bytes=len(original_gzip),
                            original_JSON_bytes=len(original_json), CTZ_bytes=path.stat().st_size,
                            ratio_vs_original_gzip=path.stat().st_size/len(original_gzip),
                            encode_plus_verified_reads_s=elapsed,
                            original_gzip_sha256=hashlib.sha256(original_gzip).hexdigest(),
                            original_JSON_sha256=hashlib.sha256(original_json).hexdigest(),
                            canonical_json_sha256=record['canonical_json_sha256'],
                            exact_original_JSON_byte_reconstruction=True)


class Results(unittest.TextTestResult):
    def __init__(self, *a, **k):
        super().__init__(*a, **k);self.rows = []

    def addSuccess(self, test):
        super().addSuccess(test);self.rows.append({'test': test.id(), 'result': 'PASS'})

    def addFailure(self, test, error):
        super().addFailure(test, error);self.rows.append({'test': test.id(), 'result': 'FAIL', 'traceback': self._exc_info_to_string(error, test)})

    def addError(self, test, error):
        super().addError(test, error);self.rows.append({'test': test.id(), 'result': 'ERROR', 'traceback': self._exc_info_to_string(error, test)})

    def addSkip(self, test, reason):
        super().addSkip(test, reason);self.rows.append({'test': test.id(), 'result': 'SKIPPED', 'reason': reason})


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--representative-gzip', type=Path)
    args = parser.parse_args()
    REPRESENTATIVE = args.representative_gzip
    result = unittest.TextTestRunner(verbosity=2, resultclass=Results).run(unittest.defaultTestLoader.loadTestsFromTestCase(TraceArchiveTests))
    with args.report.open('x') as f:
        json.dump({'scope': 'LOSSLESS_ENGINEERING_CODEC_NOT_NEW_PHYSICS', 'codec': CODEC,
                   'tests_run': result.testsRun, 'overall_pass': result.wasSuccessful(), 'checks': result.rows,
                   'representative_measurements': MEASUREMENTS,
                   'source_sha256': hashlib.sha256((ROOT/'src/panda_closed_loop/trace_archive.py').read_bytes()).hexdigest(),
                   'test_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}, f, indent=2)
        f.write('\n')
    raise SystemExit(0 if result.wasSuccessful() else 1)
