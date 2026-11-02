"""peak_exact.py -- closed-form two-eigenmode post-shutoff solution for Coda's nonliving two-node
RC model T0-LUMP2-1 (validation/thermal_transient/rc_transient.py).

Red/Claude contribution for thermal-peak-exact-001, written without execution.  Standard library
only, deterministic, no network; writes only to a caller-supplied output path.  Lumped computational
reference only: not measured hardware, not a contact-safety assessment, not a design recommendation.

Phase equations (t measured from the start of the phase, ambient = reservoir = A):
    C_H dH/dt = -g (H - S) - gr (H - A) + p
    C_S dS/dt =  g (H - S) + j  - gb (S - A)
g = 1/a (series conductance H->S), gb = 1/(a + rconv) (front branch), gr rear conductance
(0.5 W/K intact, 0 after rear loss), p body power, j sensor power.
Reconstructed surface: T_o = A + rconv * gb * (S - A), as in rc_transient.simulate().
"""
from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict, dataclass

AMBIENT_C = 25.0
RCONV_K_PER_W = 12.5
AREA_M2 = 0.01
BODY_CAPACITY_J_PER_K = 20.0
REAR_CONDUCTANCE_W_PER_K = 0.5
THICKNESS_M = {"H1": 0.0005, "H2": 0.001, "H3": 0.002}
SHUTOFF_S = 900.0
REAR_LOSS_S = 600.0
HORIZON_S = 3600.0
BODY_POWER_W = 5.0
SENSOR_POWER_W = 0.1

# Report order.  ASSUMPTION: this schedule reconstructs Coda's "Executed scenarios" paragraph.
SCENARIOS = [("H1", "intact", 0.1), ("H1", "rear_loss", 0.1), ("H1", "rear_loss", 0.0),
             ("H2", "intact", 0.1), ("H2", "rear_loss", 0.1), ("H2", "rear_loss", 0.0),
             ("H3", "intact", 0.1), ("H3", "rear_loss", 0.1), ("H3", "rear_loss", 0.0)]


class DegenerateCase(ValueError):
    """Raised instead of silently evaluating sqrt/log on invalid values."""


def front_resistance(thickness_m: float, area_m2: float = AREA_M2) -> float:
    """Series resistance a (K/W) between H and S; identical expression to rc_transient.nominal()."""
    return thickness_m / (0.27 * area_m2) + 0.00005 / (2 * 0.20 * area_m2) + 0.0002 / area_m2


def surface_node_capacity(thickness_m: float, area_m2: float = AREA_M2) -> float:
    """C_S (J/K) as in rc_transient.nominal(): silicone (cp 1500 assumed) plus film."""
    return 1030 * area_m2 * (2 * thickness_m) * 1500 + 1420 * area_m2 * 0.00005 * 1090


@dataclass(frozen=True)
class Phase:
    ch: float
    cs: float
    g: float
    gb: float
    gr: float
    p: float
    j: float
    ambient: float = AMBIENT_C
    rconv: float = RCONV_K_PER_W

    def surface(self, s: float) -> float:
        return self.ambient + self.rconv * self.gb * (s - self.ambient)


def stack_phase(stack: str, rear_intact: bool, body_w: float, sensor_w: float) -> Phase:
    a = front_resistance(THICKNESS_M[stack])
    return Phase(ch=BODY_CAPACITY_J_PER_K, cs=surface_node_capacity(THICKNESS_M[stack]),
                 g=1.0 / a, gb=1.0 / (a + RCONV_K_PER_W),
                 gr=REAR_CONDUCTANCE_W_PER_K if rear_intact else 0.0, p=body_w, j=sensor_w)


def manufactured_phase() -> Phase:
    """Coda's manufactured post-shutoff case: H1 resistances/capacity, no rear path, J = 0.1 W."""
    return stack_phase("H1", rear_intact=False, body_w=0.0, sensor_w=0.1)


@dataclass(frozen=True)
class Modes:
    lam_slow: float
    lam_fast: float
    r_slow: float
    r_fast: float
    x_inf: float  # H_inf - ambient
    y_inf: float  # S_inf - ambient


def modes(ph: Phase) -> Modes:
    """Eigenvalues (both negative, distinct), eigenvector second components, and steady state."""
    if min(ph.ch, ph.cs) <= 0.0:
        raise DegenerateCase("capacities must be positive")
    if min(ph.g, ph.gb, ph.gr) < 0.0:
        raise DegenerateCase("negative conductance")
    if ph.g == 0.0:
        raise DegenerateCase("g = 0: nodes decoupled; S(t) is a single exponential with no interior "
                             "extremum (the only configuration allowing a repeated eigenvalue)")
    det_num = ph.g * ph.gb + ph.g * ph.gr + ph.gr * ph.gb
    if det_num == 0.0:
        raise DegenerateCase("gb = gr = 0: zero eigenvalue; no finite steady state for a positive "
                             "source, peak formula not applicable")
    pcoef = (ph.g + ph.gr) / ph.ch
    qcoef = (ph.g + ph.gb) / ph.cs
    disc = (pcoef - qcoef) ** 2 + 4.0 * ph.g * ph.g / (ph.ch * ph.cs)  # = trace^2 - 4 det > 0
    root = math.sqrt(disc)
    lam_fast = -0.5 * (pcoef + qcoef + root)
    det = det_num / (ph.ch * ph.cs)
    lam_slow = det / lam_fast  # product of eigenvalues = det; avoids cancellation
    r_slow = 1.0 + (ph.gr + lam_slow * ph.ch) / ph.g
    r_fast = 1.0 + (ph.gr + lam_fast * ph.ch) / ph.g
    y_inf = (ph.g * (ph.p + ph.j) + ph.gr * ph.j) / det_num
    x_inf = ((ph.g + ph.gb) * y_inf - ph.j) / ph.g
    return Modes(lam_slow, lam_fast, r_slow, r_fast, x_inf, y_inf)


@dataclass(frozen=True)
class Amplitudes:
    a_slow: float
    a_fast: float


def amplitudes(ph: Phase, md: Modes, h0: float, s0: float) -> Amplitudes:
    u0 = h0 - ph.ambient - md.x_inf
    v0 = s0 - ph.ambient - md.y_inf
    denom = md.r_slow - md.r_fast  # > 0
    return Amplitudes((v0 - md.r_fast * u0) / denom, (md.r_slow * u0 - v0) / denom)


def state(ph: Phase, md: Modes, amp: Amplitudes, t: float) -> dict:
    """Exact H, S, surface and time derivatives at time t (from phase start)."""
    e_slow = math.exp(md.lam_slow * t)
    e_fast = math.exp(md.lam_fast * t)
    u = amp.a_slow * e_slow + amp.a_fast * e_fast
    v = amp.a_slow * md.r_slow * e_slow + amp.a_fast * md.r_fast * e_fast
    du = amp.a_slow * md.lam_slow * e_slow + amp.a_fast * md.lam_fast * e_fast
    dv = amp.a_slow * md.r_slow * md.lam_slow * e_slow + amp.a_fast * md.r_fast * md.lam_fast * e_fast
    h = ph.ambient + md.x_inf + u
    s = ph.ambient + md.y_inf + v
    return dict(t=t, H=h, S=s, surface=ph.surface(s), dH=du, dS=dv)


@dataclass(frozen=True)
class SurfaceExtremum:
    status: str
    t_star: float | None
    ratio: float | None
    initial_slope: float
    slow_velocity: float
    fast_velocity: float


def surface_extremum(md: Modes, amp: Amplitudes) -> SurfaceExtremum:
    """Stationary point of S (and of the affine surface); explicit limiting cases."""
    c_slow = amp.a_slow * md.r_slow * md.lam_slow
    c_fast = amp.a_fast * md.r_fast * md.lam_fast
    slope0 = c_slow + c_fast
    if c_slow == 0.0 and c_fast == 0.0:
        return SurfaceExtremum("constant", None, None, slope0, c_slow, c_fast)
    if c_slow == 0.0 or c_fast == 0.0:
        return SurfaceExtremum("single_mode_monotone", None, None, slope0, c_slow, c_fast)
    ratio = -c_fast / c_slow
    if ratio <= 0.0:
        return SurfaceExtremum("monotone_no_stationary_point", None, ratio, slope0, c_slow, c_fast)
    t_star = math.log(ratio) / (md.lam_slow - md.lam_fast)
    if t_star <= 0.0:
        return SurfaceExtremum("stationary_at_or_before_zero", t_star, ratio, slope0, c_slow, c_fast)
    status = "post_shutoff_maximum" if c_slow < 0.0 else "post_shutoff_minimum"
    return SurfaceExtremum(status, t_star, ratio, slope0, c_slow, c_fast)


def post_shutoff_peak(ph: Phase, h0: float, s0: float, shutoff_time: float = 0.0) -> dict:
    """Closed-form post-shutoff surface peak from the state (h0, s0) at shutoff."""
    md = modes(ph)
    amp = amplitudes(ph, md, h0, s0)
    ext = surface_extremum(md, amp)
    at0 = state(ph, md, amp, 0.0)
    result = dict(H0=h0, S0=s0, surface0=at0["surface"], dH0=at0["dH"], dS0=at0["dS"],
                  H_inf=ph.ambient + md.x_inf, S_inf=ph.ambient + md.y_inf,
                  surface_inf=ph.surface(ph.ambient + md.y_inf),
                  modes=asdict(md), amplitudes=asdict(amp), extremum=asdict(ext),
                  rising_criterion_met=at0["dS"] > 0.0, shutoff_time=shutoff_time)
    if ext.status == "post_shutoff_maximum":
        pk = state(ph, md, amp, ext.t_star)
        result.update(peak_kind="interior_maximum", peak_time=shutoff_time + ext.t_star,
                      peak_surface=pk["surface"], peak_S=pk["S"], H_at_peak=pk["H"])
        return result
    late_sign = ext.slow_velocity if ext.slow_velocity != 0.0 else ext.fast_velocity
    if late_sign <= 0.0 and ext.initial_slope <= 0.0:
        result.update(peak_kind="at_shutoff", peak_time=shutoff_time, peak_surface=at0["surface"],
                      peak_S=s0, H_at_peak=h0)
    else:
        s_sup = max(s0, ph.ambient + md.y_inf)
        result.update(peak_kind="supremum_not_attained_or_at_shutoff", peak_time=None,
                      peak_surface=ph.surface(s_sup), peak_S=s_sup, H_at_peak=None)
    return result


def mode_energy_identity_residuals(ph: Phase, md: Modes) -> list:
    """Per-mode form of d(C_H H + C_S S)/dt = j - gb (S-A) - gr (H-A): (C_H + C_S r) lam + gr + gb r = 0.
    Holds for every solution of the ODE; it does not test amplitudes or the peak algebra."""
    return [(ph.ch + ph.cs * r) * lam + ph.gr + ph.gb * r
            for lam, r in ((md.lam_slow, md.r_slow), (md.lam_fast, md.r_fast))]


def rk4_integrate(ph: Phase, h0: float, s0: float, t_end: float, dt: float) -> list:
    """Independent classical RK4 integration of the two ODEs (shape check, not used in the formula)."""
    def rhs(h, s):
        dh = (-ph.g * (h - s) - ph.gr * (h - ph.ambient) + ph.p) / ph.ch
        ds = (ph.g * (h - s) + ph.j - ph.gb * (s - ph.ambient)) / ph.cs
        return dh, ds
    n = int(round(t_end / dt))
    h, s = h0, s0
    samples = [(0.0, h, s)]
    for i in range(n):
        k1 = rhs(h, s)
        k2 = rhs(h + 0.5 * dt * k1[0], s + 0.5 * dt * k1[1])
        k3 = rhs(h + 0.5 * dt * k2[0], s + 0.5 * dt * k2[1])
        k4 = rhs(h + dt * k3[0], s + dt * k3[1])
        h += dt * (k1[0] + 2 * k2[0] + 2 * k3[0] + k4[0]) / 6.0
        s += dt * (k1[1] + 2 * k2[1] + 2 * k3[1] + k4[1]) / 6.0
        samples.append(((i + 1) * dt, h, s))
    return samples


def scenario_segments(case: str, sensor_w: float) -> list:
    """ASSUMED reconstruction of Coda's schedule (REPORT.md 'Executed scenarios')."""
    if case == "intact":
        return [dict(duration=SHUTOFF_S, p=BODY_POWER_W, j=sensor_w),
                dict(duration=HORIZON_S - SHUTOFF_S, p=0.0, j=sensor_w)]
    if case == "rear_loss":
        return [dict(duration=REAR_LOSS_S, p=BODY_POWER_W, j=sensor_w),
                dict(duration=SHUTOFF_S - REAR_LOSS_S, p=BODY_POWER_W, j=sensor_w, gr=0.0),
                dict(duration=HORIZON_S - SHUTOFF_S, p=0.0, j=sensor_w)]
    raise ValueError("case must be 'intact' or 'rear_loss'")


def analytic_shutoff_state(stack: str, case: str, sensor_w: float) -> tuple:
    """Exact (H, S) at 900 s by chaining the closed form over the pre-shutoff phases (cross-check)."""
    h = s = AMBIENT_C
    if case == "intact":
        phases = [(stack_phase(stack, True, BODY_POWER_W, sensor_w), SHUTOFF_S)]
    else:
        phases = [(stack_phase(stack, True, BODY_POWER_W, sensor_w), REAR_LOSS_S),
                  (stack_phase(stack, False, BODY_POWER_W, sensor_w), SHUTOFF_S - REAR_LOSS_S)]
    for ph, duration in phases:
        md = modes(ph)
        st = state(ph, md, amplitudes(ph, md, h, s), duration)
        h, s = st["H"], st["S"]
    return h, s


def verify_trace(trace: list, ph: Phase, shutoff_time: float = SHUTOFF_S,
                 time_tol_s: float = 2.0, temp_tol_k: float = 0.1) -> dict:
    """Compare an rc_transient.simulate() trace with the closed form started from its shutoff row.
    Shape check (pointwise H/S deviation, peak) is separate from the discrete energy identity check."""
    rows = [r for r in trace if r["time"] >= shutoff_time - 1e-9]
    if not rows or abs(rows[0]["time"] - shutoff_time) > 1e-9:
        raise ValueError("trace has no sample exactly at the shutoff time")
    for r in rows[1:]:
        if r["p"] != 0.0 or r["j"] != ph.j:
            raise ValueError("post-shutoff trace sources differ from the supplied phase")
    first = rows[0]
    h0, s0 = first["H"], first["S"]
    exact = post_shutoff_peak(ph, h0, s0, shutoff_time)
    md = modes(ph)
    amp = amplitudes(ph, md, h0, s0)
    best = max(rows, key=lambda r: r["surface"])  # first maximal sample
    dev_h = dev_s = dev_t = 0.0
    for r in rows:
        ex = state(ph, md, amp, r["time"] - shutoff_time)
        dev_h = max(dev_h, abs(r["H"] - ex["H"]))
        dev_s = max(dev_s, abs(r["S"] - ex["S"]))
        dev_t = max(dev_t, abs(r["surface"] - ex["surface"]))
    injected = sum(r["dt"] * r["j"] for r in rows[1:])
    exported = sum(r["dt"] * (r["front"] + r["rear"]) for r in rows[1:])
    stored = ph.ch * (rows[-1]["H"] - h0) + ph.cs * (rows[-1]["S"] - s0)
    exact_peak_time = exact["peak_time"] if exact["peak_time"] is not None else shutoff_time
    dt_peak = best["time"] - exact_peak_time
    d_surface = best["surface"] - exact["peak_surface"]
    within = (abs(dt_peak) <= time_tol_s and abs(d_surface) <= temp_tol_k and dev_s <= temp_tol_k
              and dev_h <= temp_tol_k)
    return dict(H900=h0, S900=s0, surface900=first["surface"],
                surface900_reconstruction_error=abs(first["surface"] - ph.surface(s0)),
                exact=exact, discrete_peak_time=best["time"], discrete_peak_surface=best["surface"],
                peak_time_difference_s=dt_peak, peak_surface_difference_K=d_surface,
                max_abs_dev_H=dev_h, max_abs_dev_S=dev_s, max_abs_dev_surface=dev_t,
                discrete_energy_residual_J=stored - injected + exported,
                mode_energy_identity_residuals=mode_energy_identity_residuals(ph, md),
                final_time=rows[-1]["time"], final_H_executed=rows[-1]["H"],
                final_H_exact=state(ph, md, amp, rows[-1]["time"] - shutoff_time)["H"],
                within_tolerance=within, time_tol_s=time_tol_s, temp_tol_k=temp_tol_k)


def manufactured_case_report() -> dict:
    ph = manufactured_phase()
    res = post_shutoff_peak(ph, 60.0, 58.0, 0.0)
    md = modes(ph)
    res.update(a_K_per_W=1.0 / ph.g, b_K_per_W=1.0 / ph.gb, C_S=ph.cs,
               energy_identity_residuals=mode_energy_identity_residuals(ph, md),
               initial_energy_above_ambient_J=ph.ch * 35.0 + ph.cs * 33.0,
               exported_after_shutoff_J=ph.ch * (35.0 - md.x_inf) + ph.cs * (33.0 - md.y_inf))
    return res


def run_executed_scenarios(rc, dt: float) -> list:
    out = []
    for stack, case, sensor_w in SCENARIOS:
        sim = rc.simulate(rc.nominal(stack), (AMBIENT_C, AMBIENT_C), scenario_segments(case, sensor_w), dt)
        ph = stack_phase(stack, case == "intact", 0.0, sensor_w)
        ver = verify_trace(sim["trace"], ph)
        h_an, s_an = analytic_shutoff_state(stack, case, sensor_w)
        an = post_shutoff_peak(ph, h_an, s_an, SHUTOFF_S)
        md = modes(ph)
        h_final_an = state(ph, md, amplitudes(ph, md, h_an, s_an), HORIZON_S - SHUTOFF_S)["H"]
        out.append(dict(stack=stack, case=case, sensor_w=sensor_w, dt=dt, executed=ver,
                        analytic_900s=dict(H=h_an, S=s_an, peak_time=an["peak_time"],
                                           peak_surface=an["peak_surface"], final_H=h_final_an),
                        max_energy_residual_program_J=sim["max_energy_residual_abs_J"]))
    return out


def _fmt(x) -> str:
    return "None" if x is None else f"{x:.6f}"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Closed-form post-shutoff surface peak (T0-LUMP2-1).")
    parser.add_argument("--dt", type=float, default=1.0, help="backward-Euler step for scenario runs")
    parser.add_argument("--out", default=None, help="optional JSON output path (only file written)")
    parser.add_argument("--no-rc", action="store_true", help="skip rc_transient scenario execution")
    parser.add_argument("--state", nargs=5, metavar=("STACK", "CASE", "SENSOR_W", "H900", "S900"),
                        help="compute the exact peak from a supplied 900 s state")
    args = parser.parse_args(argv)
    report = dict(manufactured=manufactured_case_report())
    m = report["manufactured"]
    print("Manufactured case (H0=60, S0=58, J=0.1 W, no rear path):")
    print(f"  a={m['a_K_per_W']:.7f} K/W b={m['b_K_per_W']:.7f} K/W lam_slow={m['modes']['lam_slow']:.7f}"
          f" lam_fast={m['modes']['lam_fast']:.7f} r_slow={m['modes']['r_slow']:.6f} r_fast={m['modes']['r_fast']:.6f}")
    print(f"  dS/dt(0+)={m['dS0']:.6f} K/s dH/dt(0+)={m['dH0']:.6f} K/s status={m['extremum']['status']}"
          f" ratio={_fmt(m['extremum']['ratio'])} t*={_fmt(m['extremum']['t_star'])} s")
    print(f"  surface(0)={m['surface0']:.6f} peak surface={_fmt(m['peak_surface'])} peak S={_fmt(m['peak_S'])}"
          f" H at peak={_fmt(m['H_at_peak'])} asymptotes H=S={m['S_inf']:.6f} surface={m['surface_inf']:.6f}")
    print(f"  per-mode energy identity residuals={m['energy_identity_residuals']}")
    if args.state:
        stack, case, sensor_w, h900, s900 = args.state
        ph = stack_phase(stack, case == "intact", 0.0, float(sensor_w))
        res = post_shutoff_peak(ph, float(h900), float(s900), SHUTOFF_S)
        report["supplied_state"] = dict(stack=stack, case=case, sensor_w=float(sensor_w), result=res)
        print(f"Supplied state {stack}/{case}/J={sensor_w}: peak time={_fmt(res['peak_time'])} s"
              f" peak surface={_fmt(res['peak_surface'])} C status={res['extremum']['status']}")
    if not args.no_rc:
        try:
            import rc_transient as rc
        except ImportError:
            rc = None
            print("rc_transient not importable: executed-scenario verification skipped")
        if rc is not None:
            rows = run_executed_scenarios(rc, args.dt)
            report["scenarios"] = rows
            print(f"Executed scenarios (dt={args.dt}); exact = closed form from executed 900 s state;"
                  " analytic = closed form chained from 25 C")
            print("stack case     J    H900       S900       exact_tpk  exact_pk   disc_tpk  disc_pk    "
                  "dev_S    an_tpk     an_pk      ok")
            for row in rows:
                v = row["executed"]
                e = v["exact"]
                a = row["analytic_900s"]
                print(f"{row['stack']}  {row['case']:9s}{row['sensor_w']:.1f}  {v['H900']:.6f} {v['S900']:.6f}"
                      f"  {_fmt(e['peak_time']):>10s} {_fmt(e['peak_surface'])} {v['discrete_peak_time']:8.1f}"
                      f"  {v['discrete_peak_surface']:.6f} {v['max_abs_dev_S']:.5f} {_fmt(a['peak_time']):>10s}"
                      f" {_fmt(a['peak_surface'])} {v['within_tolerance']}")
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=1, sort_keys=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
