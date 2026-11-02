"""Thin wrapper that CALLS Coda's T0-LUMP2-1 two-node model (validation/thermal_transient/rc_transient.py)
for thermal-sensitivity-001. It does not reimplement the integrator. Author: Claude (Anthropic).

Capacity convention copied from Coda's PREDECLARED.md: C_H = 20 J/K; C_S = silicone rho 1030 * A *
(t_o + t_i) * cp 1500 + film rho 1420 * A * t_f * cp 1090 (assumed properties, fixed; not in any
sensitivity domain). Front surface is Coda's quasi-steady reconstruction T_amb + Rconv * q_front.
"""
import importlib.util
import os
from pathlib import Path

C_H_J_PER_K = 20.0
SILICONE_RHO_CP = 1030.0 * 1500.0
FILM_RHO_CP = 1420.0 * 1090.0
SCENARIOS = ("intact_sensor_on", "rear_loss_sensor_on", "rear_blocked_from_start")


def locate_rc_transient(path=None):
    candidates = []
    if path:
        candidates.append(Path(path))
    env = os.environ.get("THERMAL_TRANSIENT_DIR")
    if env:
        candidates.append(Path(env))
    here = Path(__file__).resolve().parent
    candidates.append(here.parent / "thermal_transient" / "rc_transient.py")
    candidates.append(here / "rc_transient.py")
    for cand in candidates:
        cand = cand / "rc_transient.py" if cand.is_dir() else cand
        if cand.is_file():
            return cand
    raise FileNotFoundError("rc_transient.py not found; set THERMAL_TRANSIENT_DIR")


def load_rc_transient(path=None):
    """Return (module, file path). The module is Coda's code, imported unchanged."""
    file = locate_rc_transient(path)
    spec = importlib.util.spec_from_file_location("coda_rc_transient", str(file))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, file


def cover_capacity(p):
    return SILICONE_RHO_CP * p["A"] * (p["t_o"] + p["t_i"]) + FILM_RHO_CP * p["A"] * p["t_f"]


def lump_parameters(rc, p):
    """rc.Parameters from a float parameter dict of steady_closed_form.make_params."""
    A = p["A"]
    half_film = p["t_f"] / (2 * p["k_f"] * A)
    contact = p["r_c"] / A
    a = p["t_i"] / (p["k_s"] * A) + half_film + contact
    c = 1 / (p["h"] * A)
    b = p["t_o"] / (p["k_s"] * A) + half_film + contact + c
    gr = 0.0 if p["r"] is None else 1.0 / float(p["r"])
    return rc.Parameters(ch=C_H_J_PER_K, cs=float(cover_capacity(p)), g=1.0 / a, ga=1.0 / b, gr=gr,
                         ambient=float(p["T_amb"]), reservoir=float(p["T_res"]), rconv=c)


def scenario_segments(name, body_power, sensor_power=0.1, horizon=1800.0, body_off=900.0, loss=600.0):
    """Segment lists for rc.simulate. Rear-loss schedule is Coda's fault suite: body on until body_off,
    sensor on throughout, rear conductance set to exactly zero at `loss`."""
    P, J = float(body_power), float(sensor_power)
    if not loss < body_off < horizon:
        raise ValueError("Require loss < body_off < horizon")
    if name == "intact_sensor_on":
        return [{"duration": body_off, "p": P, "j": J},
                {"duration": horizon - body_off, "p": 0.0, "j": J}]
    if name == "rear_loss_sensor_on":
        return [{"duration": loss, "p": P, "j": J},
                {"duration": body_off - loss, "p": P, "j": J, "gr": 0.0},
                {"duration": horizon - body_off, "p": 0.0, "j": J}]
    if name == "rear_blocked_from_start":
        return [{"duration": body_off, "p": P, "j": J, "gr": 0.0},
                {"duration": horizon - body_off, "p": 0.0, "j": J}]
    raise ValueError("Unknown scenario " + repr(name))


def run_case(rc, params, segments, dt, initial=(25.0, 25.0)):
    """Call rc.simulate and reduce the trace to peaks, endpoint and energy audit."""
    result = rc.simulate(params, tuple(initial), segments, dt)
    peak_H = t_H = peak_s = t_s = None
    for row in result["trace"]:
        if peak_H is None or row["H"] > peak_H:
            peak_H, t_H = row["H"], row["time"]
        s = row["surface"]
        if s is not None and (peak_s is None or s > peak_s):
            peak_s, t_s = s, row["time"]
    last = result["trace"][-1]
    return {"peak_H": peak_H, "t_peak_H": t_H, "peak_surface": peak_s, "t_peak_surface": t_s,
            "final_H": last["H"], "final_S": last["S"], "final_surface": last["surface"],
            "final_time": last["time"], "steps": result["steps"],
            "injected_J": result["injected_J"], "exported_front_J": result["exported_front_J"],
            "exported_rear_J": result["exported_rear_J"],
            "max_energy_residual_abs_J": result["max_energy_residual_abs_J"],
            "energy_tolerance_J": result["energy_tolerance_J"],
            "energy_ok": result["max_energy_residual_abs_J"] <= result["energy_tolerance_J"]}
