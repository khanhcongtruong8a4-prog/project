"""Paths for generated evidence, isolated from preserved source and reviews."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def evidence_dir():
    path = Path(os.environ.get('PANDA_EVIDENCE_DIR', ROOT / 'runs' / 'manual')).resolve()
    path.mkdir(parents=True, exist_ok=True)
    (path / 'review_sheets').mkdir(exist_ok=True)
    return path
