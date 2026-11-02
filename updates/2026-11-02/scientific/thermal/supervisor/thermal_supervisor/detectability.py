"""Static detectability helpers (model computations, no empirical content).

Red (Claude, Anthropic) for The Stage / Andrei; plant algebra credited to Coda (Codex Lily).
fix-003: adds eigen time constants and the periodic probe signature used to derive the
per-stack probe schedule (README section B). Nothing here is a measurement.
"""
from dataclasses import replace
import math

from plant import nominal, step, steady_state, blocked


def _mean(values):
    return math.fsum(values) / len(values)


def time_constants(p):
    """Eigen time constants (tau_slow, tau_fast) in seconds of the continuous linear model
        C_H H' = -(g+gr) H + g S + ...,   C_S S' = g H - (g+ga) S + ...
    Returns math.inf for a mode without finite time constant (both exits blocked)."""
    a11 = -(p.g + p.gr) / p.ch
    a12 = p.g / p.ch
    a21 = p.g / p.cs
    a22 = -(p.g + p.ga) / p.cs
    tr = a11 + a22
    det = a11 * a22 - a12 * a21
    disc = max(tr * tr - 4.0 * det, 0.0)
    root = math.sqrt(disc)
    lam_slow = (tr + root) / 2.0
    lam_fast = (tr - root) / 2.0
    tau_slow = -1.0 / lam_slow if lam_slow < 0 else math.inf
    tau_fast = -1.0 / lam_fast if lam_fast < 0 else math.inf
    return tau_slow, tau_fast


def periodic_probe_signature(p, P, J, depth, duration, period, mean_n, cycles=12):
    """Model-predicted probe statistic (mean of the last mean_n S samples of a probe minus the
    mean of the mean_n samples before the probe start) once periodic probing has settled.
    Mirrors Supervisor._evaluate_probe exactly (backward Euler, dt = 1 s). For this linear
    plant the value depends on depth, duration, period and the plant, not on P (P >= depth)."""
    duration = int(duration)
    period = int(period)
    mean_n = int(mean_n)
    if period <= duration or duration < 1 or mean_n < 1:
        raise ValueError("need period > duration >= 1 and mean_n >= 1")
    H, S = steady_state(p, P, J)
    hist = [S] * (mean_n + 1)
    stat = 0.0
    for _ in range(int(cycles)):
        pre = hist[-(mean_n + 1):-1]          # samples start-mean_n .. start-1
        for _k in range(duration):
            H, S = step(p, H, S, max(0.0, P - depth), J, 1.0)
            hist.append(S)
        post = hist[-mean_n:]                 # samples start+D-mean_n+1 .. start+D
        stat = _mean(post) - _mean(pre)
        for _k in range(period - duration):
            H, S = step(p, H, S, P, J, 1.0)
            hist.append(S)
        hist = hist[-(mean_n + 1):]
    return stat


def step_response(p, dP, duration, dt=1.0):
    """Deviation (t, h, s) from rest for a body-power step dP (linear system, baths at 0)."""
    q = replace(p, ambient=0.0, reservoir=0.0)
    H = S = 0.0
    out = [(0.0, 0.0, 0.0)]
    for k in range(int(duration)):
        H, S = step(q, H, S, dP, 0.0, dt)
        out.append(((k + 1) * dt, H, S))
    return out


def rear_loss_signature(p, H0, S0, P, J, duration, fraction=0.0):
    """(t, S_blocked - S_intact) from a common state under identical inputs."""
    pb = blocked(p, fraction)
    Hi, Si, Hb, Sb = H0, S0, H0, S0
    out = [(0, 0.0)]
    for k in range(int(duration)):
        Hi, Si = step(p, Hi, Si, P, J, 1.0)
        Hb, Sb = step(pb, Hb, Sb, P, J, 1.0)
        out.append((k + 1, Sb - Si))
    return out


def probe_response(p, P_base, J, depth, duration, mean_n):
    """Predicted change of S (mean of last mean_n samples minus steady pre-window) for a probe."""
    H, S = steady_state(p, P_base, J)
    values = []
    for _ in range(int(duration)):
        H, S = step(p, H, S, max(0.0, P_base - depth), J, 1.0)
        values.append(S)
    post = values[-mean_n:]
    return math.fsum(post) / len(post) - steady_state(p, P_base, J)[1]


def gaussian_two_sided_tail(k):
    """P(|N(0,1)| > k) = 2 Phi(-k)."""
    return math.erfc(k / math.sqrt(2.0))


def noise_false_alarm_bound(sigma, tau_abs, persistence, samples, mean_n=1, differencing=False):
    """Union bound on P(any false alarm within `samples`) from iid Gaussian noise alone.
    Assumes the deterministic residual is zero. For differencing with overlapping windows the
    persistence power is optimistic (labelled approximate by the caller)."""
    if sigma <= 0:
        return 0.0
    sd = sigma / math.sqrt(mean_n) * (math.sqrt(2.0) if differencing else 1.0)
    p_single = gaussian_two_sided_tail(tau_abs / sd)
    return min(1.0, samples * p_single ** persistence)


def summary_for_stack(stack, cfg, P=5.0, J=0.1):
    """Noise-free model estimates used in the README analysis; cfg is a SupervisorConfig."""
    p = nominal(stack)
    H, S = steady_state(p, P, J)
    q_rear = p.gr * (H - p.reservoir)
    sig = rear_loss_signature(p, H, S, P, J, 400)
    W = cfg.inc_window
    t_inc = next((t for t, d in sig if t >= W and d - sig[t - W][1] > cfg.tau_abs_inc), None)
    level_threshold = cfg.tau_abs_level + cfg.tau_rel_level * abs(S - p.ambient)
    t_lvl = next((t for t, d in sig if d > level_threshold), None)
    probe = probe_response(p, P, J, cfg.probe_depth, cfg.probe_duration, cfg.probe_mean_n)
    informative = abs(probe) >= cfg.probe_min_predicted
    frozen_detected = informative and abs(probe) > cfg.tau_abs_probe + cfg.tau_rel_probe * abs(probe)
    H_idle, S_idle = steady_state(p, 0.0, J)
    S_idle_blocked = steady_state(blocked(p), 0.0, J)[1]
    tau_slow, tau_fast = time_constants(p)
    tau_slow_blocked, _ = time_constants(blocked(p))
    periodic = periodic_probe_signature(p, P, J, cfg.probe_depth, cfg.probe_duration,
                                        cfg.probe_period, cfg.probe_mean_n)
    return dict(stack=stack, steady_H_5W=H, steady_S_5W=S, rear_flux_W=q_rear,
                tau_slow_s=tau_slow, tau_fast_s=tau_fast, tau_slow_blocked_s=tau_slow_blocked,
                probe_duration_s=cfg.probe_duration, probe_period_s=cfg.probe_period,
                watchdog_powered_s=cfg.watchdog_powered_s,
                increment_detection_time_estimate_s=t_inc, level_detection_time_estimate_s=t_lvl,
                level_threshold_K=level_threshold, probe_predicted_dS_K=probe,
                periodic_probe_signature_K=periodic,
                probe_informative=informative, frozen_channel_detected_by_probe=frozen_detected,
                idle_rear_flux_W=p.gr * (H_idle - p.reservoir), idle_S_intact=S_idle,
                idle_S_blocked=S_idle_blocked, label="noise-free model estimate, not a measurement")
