"""Lossless columnar trace archive for nested JSON-normalized scientific data.

CTZ v1 keeps dictionaries' key order and missing keys, ragged lists, scalar
types, arbitrary-size integers and IEEE float64 bits (including signed zero).
Homogeneous numeric columns are stored as byte-shuffled Fortran-order arrays
in ordinary, non-pickled .npy entries inside a ZIP. Repeated strings use enums.
Canonical JSON checksums describe semantic values; callers may separately retain
the original JSON/gzip byte hashes when transcoding immutable prior evidence.
"""
from io import BytesIO
from pathlib import Path
import hashlib
import json
import zipfile
import numpy as np
from .logging import json_values

CODEC = 'CTZ_COLUMNAR_SHUFFLED_NPY_V1'
_DTYPES = {'<f8', '<i8', '<u8', '<u4', '<u2', '|u1', '|b1'}


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def canonical_json(value):
    """Stable checksum representation; not a claim about original JSON order."""
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def _tag(value):
    kind = type(value)
    if value is None:
        return 'none'
    if kind is bool:
        return 'bool'
    if kind is int:
        return 'int'
    if kind is float:
        return 'float'
    if kind is str:
        return 'str'
    if kind is list:
        return 'list'
    if kind is dict:
        if not all(type(k) is str for k in value):
            raise TypeError('CTZ dictionaries must have string JSON keys')
        return 'dict'
    raise TypeError('Unsupported normalized JSON type: '+kind.__name__)


def _integer_dtype(values):
    lower, upper = min(values), max(values)
    if -(2**63) <= lower and upper < 2**63:
        return '<i8'
    if 0 <= lower and upper < 2**64:
        return '<u8'
    return None


def _index_dtype(count):
    return '|u1' if count <= 256 else '<u2' if count <= 65536 else '<u4'


def _numeric_shape(value, scalar_type):
    """Strict rectangular shape; never promote mixed scalar types to float."""
    if type(value) is scalar_type:
        return ()
    if type(value) is not list or not value:
        return None
    child = _numeric_shape(value[0], scalar_type)
    if child is None or any(_numeric_shape(v, scalar_type) != child for v in value[1:]):
        return None
    return (len(value),)+child


class _Encoder:
    def __init__(self, archive):
        self.archive = archive
        self.counter = 0
        self.blocks = {}

    def array(self, values, dtype):
        a = np.asarray(values, dtype=np.dtype(dtype))
        if a.dtype.str not in _DTYPES:
            raise TypeError('Unsupported numeric dtype')
        raw = a.tobytes(order='F')
        raw_sha = _sha(raw)
        key = (a.dtype.str, tuple(a.shape), raw_sha)
        if key in self.blocks:
            return self.blocks[key]
        shuffled = np.frombuffer(raw, dtype=np.uint8).reshape(-1, a.dtype.itemsize).T.copy()
        stream = BytesIO()
        np.save(stream, shuffled, allow_pickle=False)
        filename = f'arrays/{self.counter:05d}.npy'
        self.counter += 1
        self.archive.writestr(filename, stream.getvalue())
        descriptor = {'file': filename, 'dtype': a.dtype.str, 'shape': list(a.shape),
                      'order': 'F', 'raw_sha256': raw_sha}
        self.blocks[key] = descriptor
        return descriptor

    def variants(self, values, labels):
        catalog, groups, lookup, indices = [], [], {}, []
        for value, label in zip(values, labels):
            if label not in lookup:
                lookup[label] = len(catalog)
                catalog.append(label)
                groups.append([])
            index = lookup[label]
            groups[index].append(value)
            indices.append(index)
        return {'kind': 'variants', 'count': len(values),
                'tags': self.array(indices, _index_dtype(len(groups))),
                'groups': [self.many(group) for group in groups]}

    def many(self, values):
        count = len(values)
        if not count:
            return {'kind': 'empty', 'count': 0}
        tags = [_tag(v) for v in values]
        if len(set(tags)) != 1:
            return self.variants(values, tags)
        tag = tags[0]
        if tag == 'none':
            return {'kind': 'none', 'count': count}
        if tag == 'str':
            catalog, lookup, indices = [], {}, []
            for value in values:
                if value not in lookup:
                    lookup[value] = len(catalog)
                    catalog.append(value)
                indices.append(lookup[value])
            if len(catalog) == 1:
                return {'kind': 'constant_string', 'count': count, 'value': catalog[0]}
            return {'kind': 'strings', 'count': count, 'catalog': catalog,
                    'indices': self.array(indices, _index_dtype(len(catalog)))}
        if tag in ['bool', 'int', 'float']:
            dtype = '|b1' if tag == 'bool' else '<f8' if tag == 'float' else _integer_dtype(values)
            if dtype is None:
                return {'kind': 'bigints', 'count': count,
                        'decimal_strings': self.many([str(v) for v in values])}
            return {'kind': 'numeric', 'count': count, 'data': self.array(values, dtype)}
        if tag == 'dict':
            shapes = [tuple(v) for v in values]
            if len(set(shapes)) != 1:
                return self.variants(values, shapes)
            keys = list(shapes[0])
            return {'kind': 'dicts', 'count': count, 'keys': keys,
                    'columns': [self.many([v[k] for v in values]) for k in keys]}
        if tag == 'list':
            lengths = [len(v) for v in values]
            total = sum(lengths)
            if total == 0:
                return {'kind': 'empty_lists', 'count': count}
            # Keep the time axis contiguous for full matrices/tensors as well
            # as vectors. In particular G[t,row,joint] must not interleave the
            # row index between adjacent samples of one coefficient.
            for scalar_type, dtype in [(float, '<f8'), (bool, '|b1')]:
                shape = _numeric_shape(values[0], scalar_type)
                if shape is not None and len(shape) > 1 and all(_numeric_shape(v, scalar_type) == shape for v in values[1:]):
                    return {'kind': 'numeric_rows', 'count': count,
                            'data': self.array(values, dtype)}
            flat = [item for row in values for item in row]
            # Uniform vectors form a matrix: Fortran storage puts the same
            # component at adjacent times together before byte shuffling.
            if len(set(lengths)) == 1:
                flat_tags = {_tag(v) for v in flat}
                if len(flat_tags) == 1 and next(iter(flat_tags)) in ['bool', 'int', 'float']:
                    subtype = next(iter(flat_tags))
                    dtype = '|b1' if subtype == 'bool' else '<f8' if subtype == 'float' else _integer_dtype(flat)
                    if dtype is not None:
                        return {'kind': 'numeric_rows', 'count': count,
                                'data': self.array(values, dtype)}
            return {'kind': 'lists', 'count': count,
                    'lengths': self.array(lengths, '<i8'), 'items': self.many(flat)}
        raise ValueError('Unhandled JSON type')


class _Decoder:
    def __init__(self, archive):
        self.archive = archive

    def array(self, descriptor):
        dtype = descriptor['dtype']
        if dtype not in _DTYPES or descriptor.get('order') != 'F':
            raise ValueError('Unsupported CTZ array layout')
        shape = descriptor['shape']
        if not all(type(n) is int and n >= 0 for n in shape):
            raise ValueError('Invalid CTZ numeric shape')
        a = np.load(BytesIO(self.archive.read(descriptor['file'])), allow_pickle=False)
        itemsize = np.dtype(dtype).itemsize
        size = int(np.prod(shape, dtype=np.int64))
        if a.dtype != np.uint8 or a.shape != (itemsize, size):
            raise ValueError('Invalid CTZ shuffled array shape/dtype')
        raw = np.ascontiguousarray(a.T).tobytes()
        if _sha(raw) != descriptor['raw_sha256']:
            raise ValueError('CTZ numeric block checksum mismatch')
        return np.frombuffer(raw, dtype=np.dtype(dtype)).reshape(shape, order='F')

    def many(self, node):
        count, kind = node['count'], node['kind']
        if type(count) is not int or count < 0:
            raise ValueError('Invalid CTZ item count')
        if kind == 'empty':
            result = []
        elif kind == 'none':
            result = [None]*count
        elif kind == 'constant_string':
            if type(node['value']) is not str:
                raise ValueError('Invalid CTZ string')
            result = [node['value']]*count
        elif kind == 'strings':
            indices = self.array(node['indices']).tolist()
            catalog = node['catalog']
            if not all(type(v) is str for v in catalog):
                raise ValueError('Invalid CTZ string catalog')
            if any(type(i) is not int or not 0 <= i < len(catalog) for i in indices):
                raise ValueError('Invalid CTZ string index')
            result = [catalog[i] for i in indices]
        elif kind in ['numeric', 'numeric_rows']:
            result = self.array(node['data']).tolist()
        elif kind == 'bigints':
            result = [int(v) for v in self.many(node['decimal_strings'])]
        elif kind == 'dicts':
            keys = node['keys']
            if len(set(keys)) != len(keys) or not all(type(k) is str for k in keys):
                raise ValueError('Invalid CTZ dictionary keys')
            columns = [self.many(n) for n in node['columns']]
            if len(columns) != len(keys) or any(len(c) != count for c in columns):
                raise ValueError('Invalid CTZ dictionary column count')
            result = [{k: column[i] for k, column in zip(keys, columns)} for i in range(count)]
        elif kind == 'empty_lists':
            result = [[] for _ in range(count)]
        elif kind == 'lists':
            lengths = self.array(node['lengths']).tolist()
            flat = self.many(node['items'])
            if len(lengths) != count or any(type(n) is not int or n < 0 for n in lengths) or sum(lengths) != len(flat):
                raise ValueError('Invalid CTZ ragged list lengths')
            result, offset = [], 0
            for n in lengths:
                result.append(flat[offset:offset+n])
                offset += n
        elif kind == 'variants':
            tags = self.array(node['tags']).tolist()
            groups = [self.many(n) for n in node['groups']]
            offsets = [0]*len(groups)
            result = []
            for tag in tags:
                if type(tag) is not int or not 0 <= tag < len(groups) or offsets[tag] >= len(groups[tag]):
                    raise ValueError('Invalid CTZ variant index')
                result.append(groups[tag][offsets[tag]])
                offsets[tag] += 1
            if offsets != [len(g) for g in groups]:
                raise ValueError('Unconsumed CTZ variant values')
        else:
            raise ValueError('Unknown CTZ schema node')
        if not isinstance(result, list) or len(result) != count:
            raise ValueError('CTZ decoded count mismatch')
        return result


def write_trace(path, value):
    """Exclusively write and verify a lossless normalized JSON trace archive."""
    path = Path(path)
    normalized = json_values(value)
    canonical_sha = _sha(canonical_json(normalized))
    path.parent.mkdir(parents=True, exist_ok=True)
    # Mode x preserves previous scientific evidence, including failed writes.
    with zipfile.ZipFile(path, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        encoder = _Encoder(archive)
        schema = {'codec': CODEC, 'canonical_json_sha256': canonical_sha,
                  'root': encoder.many([normalized])}
        archive.writestr('schema.json', json.dumps(schema, separators=(',', ':'), allow_nan=False))
    record = {'file': path.name, 'sha256': _sha(path.read_bytes()),
              'canonical_json_sha256': canonical_sha, 'codec': CODEC}
    read_trace(path, record)  # Verify the bytes actually written, not just inputs.
    return record


def read_trace(path, record=None):
    """Restore native JSON values, rejecting corruption or incompatible codecs."""
    path = Path(path)
    if record is not None:
        if record.get('codec') != CODEC or _sha(path.read_bytes()) != record.get('sha256'):
            raise ValueError('CTZ file checksum/codec mismatch')
    try:
        with zipfile.ZipFile(path) as archive:
            schema = json.loads(archive.read('schema.json'))
            if schema.get('codec') != CODEC:
                raise ValueError('Unsupported trace codec')
            values = _Decoder(archive).many(schema['root'])
            if len(values) != 1:
                raise ValueError('CTZ root must contain one value')
            result = values[0]
        actual = _sha(canonical_json(result))
        if actual != schema['canonical_json_sha256']:
            raise ValueError('CTZ canonical JSON checksum mismatch')
        if record is not None and actual != record.get('canonical_json_sha256'):
            raise ValueError('CTZ expected canonical JSON checksum mismatch')
        return result
    except (zipfile.BadZipFile, KeyError, IndexError, TypeError, EOFError, OverflowError) as error:
        raise ValueError('Invalid CTZ trace archive: '+str(error)) from error
