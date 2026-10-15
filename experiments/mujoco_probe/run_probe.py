"""Finite, headless MuJoCo system-identification baseline; no model endpoint or hardware."""
from pathlib import Path
import argparse, hashlib, importlib.metadata, json, math, random, statistics
from datetime import datetime, timezone
import mujoco

ROOT = Path(__file__).resolve().parent
CONFIG = {
    "name": "MP0 mass-and-motor-change calibration baseline",
    "seeds": list(range(7000, 7064)), "dt": 0.002, "steps_per_pulse": 25,
    "calibration_commands": [-0.8, -0.4, 0.4, 0.8], "test_commands_per_seed": 16,
    "mass_range_kg": [0.5, 3.5], "velocity_noise_sd": 0.001,
    "primary_metric": "mean squared velocity-change prediction error per seed",
    "comparison": "fresh noisy calibration versus stale pre-change calibration",
    "controls": ["analytic oracle", "zero prediction", "permuted receipt calibration"],
    "scope": "Synthetic idealized frictionless 1-DOF simulator; no embodied-model or identity claim",
}

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def write(path, obj):
    path.write_text(json.dumps(obj, indent=2) + "\n", encoding="utf-8")

class Body:
    def __init__(self, mass, motor_sign):
        self.mass, self.motor_sign = mass, motor_sign
        self.model = mujoco.MjModel.from_xml_string(f'''<mujoco>
          <option timestep="{CONFIG['dt']}" gravity="0 0 0" integrator="Euler"/>
          <worldbody><body name="body"><joint type="slide" axis="1 0 0" damping="0"/>
          <geom type="sphere" size="0.05" mass="{mass}"/></body></worldbody>
          <actuator><motor joint="0" gear="{motor_sign}" ctrllimited="true" ctrlrange="-1 1"/></actuator>
        </mujoco>'''.replace('joint="0"', 'joint="slider"').replace('<joint type=', '<joint name="slider" type='))
        self.data = mujoco.MjData(self.model)

    def pulse(self, command):
        if not math.isfinite(command) or abs(command) > 1:
            raise ValueError("bounded finite command required")
        mujoco.mj_resetData(self.model, self.data)
        self.data.ctrl[0] = command
        mujoco.mj_step(self.model, self.data, nstep=CONFIG['steps_per_pulse'])
        return float(self.data.qvel[0])

def fit(commands, observations):
    return sum(x*y for x, y in zip(commands, observations)) / sum(x*x for x in commands)

def run():
    frozen = json.loads((ROOT / 'freeze.json').read_text())
    if frozen['source_sha256'] != sha(__file__) or frozen['config'] != CONFIG:
        raise RuntimeError('Frozen source/config mismatch')
    results, receipts = [], []
    duration = CONFIG['dt'] * CONFIG['steps_per_pulse']
    calibrate = CONFIG['calibration_commands']
    checks = {"bounded_command_rejected": False, "repeat_reset_equal": True,
              "oracle_matches_integrator": True, "finite_predictions": True}
    base = Body(1.0, 1)
    try:
        base.pulse(1.01)
    except ValueError:
        checks['bounded_command_rejected'] = True
    for seed in CONFIG['seeds']:
        rng = random.Random(seed)
        old_obs = [base.pulse(c)+rng.gauss(0, CONFIG['velocity_noise_sd']) for c in calibrate]
        stale = fit(calibrate, old_obs)
        mass = rng.uniform(*CONFIG['mass_range_kg'])
        sign = rng.choice([-1, 1])
        changed = Body(mass, sign)
        new_obs = [changed.pulse(c)+rng.gauss(0, CONFIG['velocity_noise_sd']) for c in calibrate]
        fresh = fit(calibrate, new_obs)
        shuffled = list(new_obs)
        rng.shuffle(shuffled)
        wrong_receipts = fit(calibrate, shuffled)
        slopes = {"fresh": fresh, "stale": stale, "zero": 0.0,
                  "permuted_receipts": wrong_receipts, "oracle": duration*sign/mass}
        errors = {name: [] for name in slopes}
        for j in range(CONFIG['test_commands_per_seed']):
            command = rng.uniform(-1, 1)
            observed = changed.pulse(command)
            checks['repeat_reset_equal'] &= observed == changed.pulse(command)
            checks['oracle_matches_integrator'] &= abs(observed-slopes['oracle']*command) < 1e-12
            preds = {name: slope*command for name, slope in slopes.items()}
            checks['finite_predictions'] &= all(math.isfinite(x) for x in preds.values())
            for name, pred in preds.items():
                errors[name].append((pred-observed)**2)
            receipts.append({"seed": seed, "probe": j, "requested_command": command,
                "dispatched_command": command, "motor_sign": sign, "observed_dv": observed,
                "predictions": preds, "note": "truth available only to benchmark evaluator"})
        results.append({"seed": seed, "mass_kg": mass, "motor_sign": sign,
            "mse": {name: statistics.mean(e) for name, e in errors.items()}})
    summary = {"mse_by_controller": {name: statistics.mean(r['mse'][name] for r in results) for name in slopes},
        "fresh_beats_stale_seed_count": sum(r['mse']['fresh'] < r['mse']['stale'] for r in results),
        "seed_count": len(results), "probes": len(receipts), "checks": checks,
        "interpretation": "Fresh calibration uses post-change observations; stale calibration does not. This is a system-identification baseline under the declared model, not a test of AI adaptation.",
        "limitations": ["One uncoupled frictionless degree of freedom; no contact or latency.",
            "Predetermined calibration actions, not autonomous exploration.",
            "Gaussian measurement noise only in calibration; test targets are noiseless simulator velocities.",
            "Local freeze is not independently witnessed preregistration; no parameter tuning after freeze.",
            "No LLM, biology, physical robot, personal identity or subjective experience was tested."]}
    write(ROOT / 'per_seed.json', results)
    write(ROOT / 'receipts.json', receipts)
    write(ROOT / 'results.json', summary)
    write(ROOT / 'manifest.json', {p.name: sha(p) for p in sorted(ROOT.iterdir()) if p.is_file() and p.name != 'manifest.json'})
    print(json.dumps(summary, indent=2))
    if not all(checks.values()):
        raise SystemExit('Probe integrity check failed')

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--freeze', action='store_true')
    args = parser.parse_args()
    if args.freeze:
        target = ROOT / 'freeze.json'
        if target.exists():
            raise SystemExit('Freeze exists; will not overwrite it')
        write(target, {"timestamp_utc": datetime.now(timezone.utc).isoformat(), "config": CONFIG,
            "source_sha256": sha(__file__), "packages": {p: importlib.metadata.version(p) for p in ['mujoco', 'gymnasium', 'numpy']}})
        print('Frozen configuration and source before execution')
    else:
        run()
