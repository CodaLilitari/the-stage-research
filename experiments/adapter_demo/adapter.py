"""Continuous headless MuJoCo adapter. Engineering demonstration, no AI tested."""
import argparse, hashlib, json, math, sys
from pathlib import Path
import mujoco
import numpy as np

ROOT = Path(__file__).resolve().parent
STATE = mujoco.mjtState.mjSTATE_INTEGRATION


def finite(x):
    try: return type(x) in (int, float) and math.isfinite(x)
    except OverflowError: return False


def clean(x):
    if isinstance(x, float) and not math.isfinite(x): return repr(x)
    if isinstance(x, dict): return {k: clean(v) for k, v in x.items()}
    if isinstance(x, list): return [clean(v) for v in x]
    return x


def emit(x):
    return json.dumps(clean(x), sort_keys=True, allow_nan=False)


def unique_pairs(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError("Duplicate JSON object key")
        obj[key] = value
    return obj


class Adapter:
    def __init__(self, mass=1.0, gear=1.0):
        if not finite(mass) or mass <= 0 or not finite(gear) or gear == 0:
            raise ValueError("Invalid evaluator configuration")
        self.config = {"mass": mass, "gear": gear, "dt": .002, "substeps": 50}
        xml = f'''<mujoco><option timestep=".002" gravity="0 0 0" integrator="RK4"/>
        <worldbody><body><joint name="slide" type="slide" axis="1 0 0" damping=".1"/>
        <geom type="sphere" size=".05" mass="{mass}"/></body></worldbody>
        <actuator><motor joint="slide" gear="{gear}" ctrllimited="true" ctrlrange="-1 1"/></actuator></mujoco>'''
        self.model = mujoco.MjModel.from_xml_string(xml)
        self.data = mujoco.MjData(self.model)
        self.seq, self.used, self.stopped = 0, set(), False
        mujoco.mj_forward(self.model, self.data)

    def observe(self):
        # Deliberately no mass, gear, configuration, paths, keys, or model object.
        return {"position": float(self.data.qpos[0]), "velocity": float(self.data.qvel[0]),
                "logical_timestamp": float(self.data.time), "observation_id": f"obs-{self.seq}"}

    def apply(self, request):
        before, reason = self.observe(), None
        allowed = {"command_id", "observation_id", "motor", "deadline"}
        stop_fields = {"command_id", "observation_id", "stop", "deadline"}
        if not isinstance(request, dict) or set(request) not in (allowed, stop_fields):
            reason = "malformed_envelope"
        elif (not isinstance(request["command_id"], str) or not request["command_id"]
              or len(request["command_id"]) > 128 or not finite(request["deadline"])):
            reason = "malformed_envelope"
        elif "stop" in request and request["stop"] is not True:
            reason = "malformed_stop"
        elif "motor" in request and (not finite(request["motor"]) or abs(request["motor"]) > 1):
            reason = "invalid_motor"
        elif self.stopped: reason = "stop_latched"
        elif request["command_id"] in self.used: reason = "duplicate_command"
        elif request["observation_id"] != before["observation_id"]: reason = "stale_observation"
        elif request["deadline"] < before["logical_timestamp"]: reason = "expired_deadline"
        executed = None
        if reason is None:
            self.used.add(request["command_id"])
            self.seq += 1
            if "stop" in request:
                self.stopped = True
                self.data.ctrl[0] = 0
                executed = {"stop": True, "integration_steps": 0}
            else:
                self.data.ctrl[0] = request["motor"]
                for _ in range(self.config["substeps"]): mujoco.mj_step(self.model, self.data)
                executed = {"motor": float(request["motor"]), "integration_steps": self.config["substeps"]}
        return {"requested": clean(request), "admitted": reason is None, "reason": reason,
                "executed": executed, "before": before, "observed": self.observe()}

    def checkpoint(self):
        state = np.empty(mujoco.mj_stateSize(self.model, STATE))
        mujoco.mj_getState(self.model, self.data, state, STATE)
        return {"schema": 1, "mujoco_version": mujoco.__version__, "config": self.config,
                "integration_state": state.tolist(), "sequence": self.seq,
                "used_command_ids": sorted(self.used), "stopped": self.stopped}

    @classmethod
    def restore(cls, checkpoint):
        if checkpoint["schema"] != 1 or checkpoint["mujoco_version"] != mujoco.__version__:
            raise ValueError("Checkpoint schema/runtime mismatch")
        obj = cls(checkpoint["config"]["mass"], checkpoint["config"]["gear"])
        if obj.config != checkpoint["config"]: raise ValueError("Configuration mismatch")
        state = np.array(checkpoint["integration_state"], dtype=float)
        if len(state) != mujoco.mj_stateSize(obj.model, STATE) or not np.isfinite(state).all():
            raise ValueError("Invalid integration state")
        mujoco.mj_setState(obj.model, obj.data, state, STATE)
        obj.seq = checkpoint["sequence"]
        obj.used = set(checkpoint["used_command_ids"])
        obj.stopped = checkpoint["stopped"]
        return obj


def command(adapter, i, motor=0.6):
    obs = adapter.observe()
    return {"command_id": f"c-{i}", "observation_id": obs["observation_id"],
            "motor": motor, "deadline": obs["logical_timestamp"] + 1}


def demo():
    traces, checks = [], {}
    controls = [.6] * 8 + [-.4] * 6 + [0.] * 6
    baseline, interrupted = Adapter(), Adapter()
    baseline_receipts = []
    for i, motor in enumerate(controls):
        r = baseline.apply(command(baseline, i, motor)); baseline_receipts.append(r)
        traces.append({"rollout": "uninterrupted", "receipt": r})
    for i, motor in enumerate(controls[:7]):
        traces.append({"rollout": "before_checkpoint", "receipt": interrupted.apply(command(interrupted, i, motor))})
    cp_path = ROOT / "checkpoint.json"
    cp_path.write_text(emit(interrupted.checkpoint()) + "\n", encoding="utf-8")
    resumed = Adapter.restore(json.loads(cp_path.read_text(encoding="utf-8")))
    resumed_receipts = []
    for i, motor in enumerate(controls[7:], 7):
        r = resumed.apply(command(resumed, i, motor)); resumed_receipts.append(r)
        traces.append({"rollout": "resumed", "receipt": r})
    checks["resumed_receipts_exact_match"] = resumed_receipts == baseline_receipts[7:]
    checks["integration_state_exact_match"] = resumed.checkpoint() == baseline.checkpoint()
    second = baseline_receipts[1]
    checks["persistent_state_not_pulse_reset"] = second["before"] == baseline_receipts[0]["observed"] and second["before"]["velocity"] > 0
    heavy = Adapter(mass=2.0)
    for i, motor in enumerate(controls):
        traces.append({"rollout": "mass_2", "receipt": heavy.apply(command(heavy, i, motor))})
    checks["mass_perturbation_changes_motion"] = abs(heavy.data.qpos[0] - baseline.data.qpos[0]) > .05
    checks["observation_schema_excludes_evaluator_config"] = set(heavy.observe()) == {"position", "velocity", "logical_timestamp", "observation_id"}
    fault = Adapter.restore(json.loads(cp_path.read_text(encoding="utf-8")))
    bad_requests = [dict(command(fault, 90), motor=float("nan")), dict(command(fault, 90), motor=1.01),
                    dict(command(fault, 90), command_id=[]), dict(command(fault, 90), deadline=-1),
                    dict(command(fault, 90), observation_id="obs-0"), command(fault, 0), {"load_file": "private"}]
    for i, req in enumerate(bad_requests):
        before = fault.checkpoint(); r = fault.apply(req)
        checks[f"reject_fault_{i}_without_state_change"] = not r["admitted"] and fault.checkpoint() == before
        traces.append({"rollout": "fault", "receipt": r})
    stop = command(fault, 999); stop.pop("motor"); stop["stop"] = True
    traces.append({"rollout": "stop", "receipt": fault.apply(stop)})
    stopped = Adapter.restore(json.loads(emit(fault.checkpoint())))
    r = stopped.apply(command(stopped, 1000))
    checks["restored_stop_latches"] = not r["admitted"] and r["reason"] == "stop_latched" and stopped.checkpoint() == fault.checkpoint()
    traces.append({"rollout": "restored_stop", "receipt": r})
    checks = {name: bool(value) for name, value in checks.items()}
    if not all(checks.values()): raise AssertionError(checks)
    (ROOT / "trace.jsonl").write_text("\n".join(emit(t) for t in traces) + "\n", encoding="utf-8")
    result = {"status": "passed", "mujoco_version": mujoco.__version__, "checks": checks,
              "baseline_final": baseline.observe(), "mass2_final": heavy.observe(),
              "checkpoint_after_commands": 7, "uninterrupted_commands": 20, "resumed_commands": 13,
              "trace_records": len(traces), "scope": "Engineering adapter demo, no AI endpoint or physical body."}
    (ROOT / "results.json").write_text(emit(result) + "\n", encoding="utf-8")
    files = sorted(p for p in ROOT.iterdir() if p.is_file() and p.name != "manifest-sha256.txt")
    (ROOT / "manifest-sha256.txt").write_text("".join(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n" for p in files), encoding="utf-8")
    print(json.dumps(result, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["demo", "serve"])
    parser.add_argument("--mass", type=float, default=1.)
    parser.add_argument("--gear", type=float, default=1.)
    args = parser.parse_args()
    if args.mode == "demo": return demo()
    adapter = Adapter(args.mass, args.gear)
    print(emit({"observation": adapter.observe()}), flush=True)
    for line in sys.stdin:
        try:
            request = json.loads(line, object_pairs_hook=unique_pairs,
                                 parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))
            response = adapter.apply(request)
        except (ValueError, TypeError, OverflowError, RecursionError):
            response = {"requested": line.rstrip(), "admitted": False, "executed": None,
                        "reason": "malformed_json_or_envelope", "before": adapter.observe(), "observed": adapter.observe()}
        print(emit(response), flush=True)


if __name__ == "__main__": main()
