"""Shared test INPUTS only; never used to build an external robot reference."""
from pathlib import Path
import json
import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def limits():
    manifest = json.loads((ROOT / 'baseline/model_manifest_v1.json').read_text())
    return tuple(np.array(manifest[key], dtype=float) for key in
                 ['joint_limits_qmin_rad', 'joint_limits_qmax_rad', 'joint_speed_max_rad_s'])


def protocol_cases():
    lower, upper, _ = limits()
    rng = np.random.default_rng(20261101)
    q = np.vstack([np.zeros(7), (lower + upper) / 2,
                   lower + .05 * (upper - lower) + rng.random((20, 7)) * .9 * (upper - lower)])
    return q, rng.normal(0, .35, (22, 7)), rng.normal(0, .4, (22, 7))


def expanded_cases():
    lower, upper, speed = limits()
    rng = np.random.default_rng(20261101)
    q = np.vstack([np.zeros(7), (lower + upper) / 2, lower, upper,
                   rng.uniform(lower, upper, size=(128, 7))])
    return q, rng.uniform(-speed, speed, size=(132, 7)), rng.uniform(-3, 3, size=(132, 7))


def all_cases():
    expanded, protocol = expanded_cases(), protocol_cases()
    return tuple(np.vstack([a, b]) for a, b in zip(expanded, protocol))


def case_labels(index):
    if index < 132:
        local = index
        kind = ['zero_algebraic', 'midpoint', 'lower_corner', 'upper_corner'][local] if local < 4 else 'seeded_full_box'
        return 'expanded132', local, kind
    local = index - 132
    return 'protocol22', local, 'zero_algebraic' if local == 0 else 'midpoint' if local == 1 else 'seeded_5pct_interior'
