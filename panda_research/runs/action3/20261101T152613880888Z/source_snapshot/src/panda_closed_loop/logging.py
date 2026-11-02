"""Immutable JSON trace output retaining raw negative samples and diagnostics."""
from pathlib import Path
import json
import numpy as np
from .contracts import scalar


def json_values(value):
    if isinstance(value, np.ndarray): return value.tolist()
    if isinstance(value, np.generic): return value.item()
    if isinstance(value, dict): return {k: json_values(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)): return [json_values(v) for v in value]
    return value


class TraceLogger:
    def __init__(self, metadata):
        self.metadata = json.loads(json.dumps(json_values(metadata), allow_nan=False))
        self.samples = []

    def append(self, record):
        start, end = scalar(record['t0'], 'trace start', nonnegative=True), scalar(record['t1'], 'trace end', nonnegative=True)
        if end <= start or (self.samples and abs(start-self.samples[-1]['t1']) > 1e-12):
            raise ValueError('Trace must contain contiguous positive-duration periods')
        self.samples.append(json.loads(json.dumps(json_values(record), allow_nan=False)))

    def write(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        # Exclusive creation: earlier traces, including failed runs, are retained.
        with path.open('x') as stream:
            json.dump({'metadata': self.metadata, 'scope': 'COMPONENT_FIXTURE_NOT_A2', 'samples': self.samples}, stream,
                      indent=2, allow_nan=False)
            stream.write('\n')
