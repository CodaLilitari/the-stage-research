#!/usr/bin/env python3
"""UNEXECUTED MuJoCo parity specification supplied for a local follow-up.

Checks an independently implemented simulator against a frozen FL1 witness.
The analytic equivalence assumes MuJoCo Euler's implicit joint damping.
A failed tolerance check is an informative bridge failure, not permission to
silently alter the original FL1 experiment or its results.
"""
from __future__ import annotations
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from first_leaf import body_vectors, fixture, load_protocol


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed', type=int, default=10000)
    parser.add_argument('--algorithm', default='window')
    parser.add_argument('--trace', type=Path, default=ROOT / 'results/evaluation_primary_window_witness.jsonl.gz')
    parser.add_argument('--out', type=Path, default=ROOT / 'results/mujoco_parity_local.json')
    args = parser.parse_args()
    try:
        import mujoco
        import numpy as np
    except ImportError as exc:
        raise SystemExit('MuJoCo runtime unavailable. No parity result was produced. Install optional/requirements.txt locally. ' + str(exc))
    cfg, fx = load_protocol(), fixture(args.seed, load_protocol())
    xml = ROOT / 'optional/planar_point.xml'
    model = mujoco.MjModel.from_xml_path(str(xml))
    data = mujoco.MjData(model)
    with gzip.open(args.trace, 'rt') as f:
        rows = [json.loads(line) for line in f]
    current_ep, max_error, count = -1, 0., 0
    restore_state, restore_row = None, None
    signature = mujoco.mjtState.mjSTATE_INTEGRATION
    for index, r in enumerate(rows):
        if r['ep'] != current_ep:
            mujoco.mj_resetData(model, data)
            current_ep = r['ep']
        b = body_vectors(cfg, fx, current_ep, cfg['profiles']['primary'])
        # For unit mass: v_next=(v+dt*force)/(1+dt*damping).
        data.ctrl[:] = np.array(b[r['executed']]) / (cfg['dynamics']['alpha'] * cfg['dynamics']['dt'])
        mujoco.mj_step(model, data)
        error = max(np.max(np.abs(data.qpos - r['true_p'])), np.max(np.abs(data.qvel - r['true_v'])))
        max_error = max(max_error, float(error))
        count += 1
        if r['ep'] == 4 and r['tick'] == 30:
            restore_state = np.empty(mujoco.mj_stateSize(model, signature))
            mujoco.mj_getState(model, data, restore_state, signature)
            restore_row = index
    if restore_state is None:
        raise ValueError('Trace did not include the checkpoint position')
    restored = mujoco.MjData(model)
    mujoco.mj_setState(model, restored, restore_state, signature)
    restore_max_error = 0.
    for r in rows[restore_row + 1:]:
        if r['ep'] != 4:
            break
        b = body_vectors(cfg, fx, 4, cfg['profiles']['primary'])
        restored.ctrl[:] = np.array(b[r['executed']]) / (.75 * .1)
        mujoco.mj_step(model, restored)
        restore_max_error = max(restore_max_error, float(np.max(np.abs(restored.qpos - r['true_p']))),
                                float(np.max(np.abs(restored.qvel - r['true_v']))))
    result = {'status': 'executed', 'engine': 'MuJoCo', 'version': mujoco.__version__, 'seed': args.seed,
              'supplied_algorithm_label': args.algorithm, 'trace_file_sha256': hashlib.sha256(args.trace.read_bytes()).hexdigest(),
              'xml_sha256': hashlib.sha256(xml.read_bytes()).hexdigest(), 'steps': count,
              'max_position_or_velocity_error': max_error, 'restore_max_error': restore_max_error,
              'acceptance_tolerance': 1e-10, 'passed': max_error <= 1e-10 and restore_max_error <= 1e-10,
              'limits': 'State-transition parity for this planar body and supplied trace, not a new adaptation study or physical validation.'}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
    if not result['passed']:
        raise SystemExit(1)

if __name__ == '__main__':
    main()
