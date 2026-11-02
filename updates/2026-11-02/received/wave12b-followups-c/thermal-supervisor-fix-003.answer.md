# Thermal supervisor fix-003 — diagnosis, re-derivation, minimal diffs, updated tests

**Credits.** Plant algebra and the six executed reference rows: Coda (Codex Lily), `rc_transient.py` / REPORT.md. Supervisor, harness, matrix, tests (wave 10): Red (Claude, Anthropic). All executed numbers quoted below (receipts, matrix stdout) were produced by Red's sandbox run of the wave-10 code. This revision (fix-003) is Red's new, **unexecuted** static work; Red will execute and return results. Model study only (T0-LUMP2-1); 40/45/60 °C remain arbitrary study comparators; nothing here is a hardware design recommendation or a safety certification.

Static-reasoning note: every number marked `estimate` is hand-derived from the linear model; the code recomputes the exact discrete values at run time, and the updated tests derive their bounds from the configuration the code actually produces (not from my estimates).

---

## A. Diagnosis of the 9 failures (design defect vs test expectation)

| # | receipt | diagnosis | class |
|---|---|---|---|
| 1 | H3 `sup1_intact_noise`, `hotcorner`, `coldcorner` → TRIP_SENSOR at 481 "liveness watchdog" | **D1 + D2.** The watchdog counts powered seconds since the last *passed informative probe* (only). For H3 the 2nd and 3rd probes (210–270, 360–420) were *uninformative*: the probe statistic is the predicted **net** change over the 60 s window, and during H3's long heating transient (τ_slow ≈ 169 s) the heating rise (+0.76 K over 210–270, estimate) cancels the probe-induced drop (≈ −1.07 K), so \|dŷ\| ≈ 0.3 < 0.6. The first probe passed (net +0.7, heating-dominated), resetting the counter at 120; 120 + 361 = 481. The 360 s budget assumed every probe informative. | design defect |
| 2 | H3 dropout trip 481 ≠ 602 | consequence of #1 (tripped 119 s before the fault) | design (test right) |
| 3 | H3 rear-loss final TRIP_SENSOR ≠ TRIP_MODEL (delay −119) | consequence of #1 | design (test right) |
| 4 | H3 stuck-on final_H 26.46 ≯ 60 | consequence of #1: supervisor de-energised at 481, the actuator stuck at 600 held its *last applied* value 0 W → no hazard | design (test right) |
| 5 | H3 freeze gap −0.347 ≯ 1.0 | consequence of #1: trip at 481 preceded the freeze; the gap is just −bias −noise | design (test right) |
| 6 | `probes_ok` 5 ≠ 6 (H1 or H2; from the receipts it is H2 — see §B.3) | **T2.** Informativeness is a property of the predicted net change of the window, not of the probe. During the heating transient of a slow stack the first probe's net change can be ≈ 0 (H2: heating +2.3 K vs probe −2.2 K over 55→120 s, estimate). All 6 probes *were executed* (energy 3420 J). The test must count probes evaluated, the energy cost, and require only the *late* (quasi-steady) probes to be informative and passed. | test expectation (plus doc fix) |
| 7 | `test_rear_loss_unobservable_without_rear_flux` tuple mismatch at 1e-14 | **T1.** Exact float equality was asserted between two backward-Euler trajectories computed with different coefficient sets (gr = 0.5 vs 0). The mathematical identity (both stay at ambient) holds; rounding differs. Assert within 1e-9. | test expectation |

Root-cause split: one real design defect with two parts (D1: wrong evidence source for the liveness watchdog; D2: probe schedule not derived from τ_slow, so H3's probe signature is too small and its probes are marginal/uninformative), and two wrong test expectations (T1, T2). Five of the nine receipt lines are consequences of D1.

Observations from the receipts that were not test failures (recorded, acted on where cheap):
- H1 `actdelay5` tripped TRIP_MODEL at 71 (dy 0.410 vs dŷ −0.021): an unmodelled 5 s actuator delay at the first probe onset is equivalent to ≈ 0.4 K of 10 s-increment residual for the fast H1 stack; the README's "estimate: stays inside thresholds" was wrong for H1. The supervisor supports `actuator_delay_model`; a new test checks the modelled case (prediction: no trip).
- The "latent" idle rear loss (C1) is in fact detected during idle for H1/H2 (1838 s, 2050 s) because the 0.1 W sensor self-heat crosses the rear path; the blocked idle plant warms ≈ 1.1 K, which with the +0.2 K bias exceeds the idle level threshold (≈ 0.89 K) after ≈ τ_slow,blocked (463 s / 670 s / 1100 s). For H3 the re-demand at 2400 is predicted to win. C1 is amended: *weakly detectable, latency ~τ_blocked*.
- "Constant bias is absorbed by initialisation" was imprecise: the initial-state offset decays with τ_slow; the steady residual converges to +b (0.2 K here), which is inside the 0.8 K band. Corrected below.
- Period-240 variant and the no-probe counterexample tripped TRIP_MODEL via the increment test at a probe onset / power-off with a frozen channel (dy = 0). Consistent with the design: increment mismatches are labelled TRIP_MODEL regardless of origin (the test cannot attribute).

## B. Re-derivation from the plant's time constants

### B.1 Eigen time constants (nominal, hand-derived; `detectability.time_constants` computes them)
Linear matrix A = [[−(g+gr)/C_H, g/C_H], [g/C_S, −(g+ga)/C_S]].

| stack | g (W/K) | ga (W/K) | C_S (J/K) | τ_slow (s) | τ_fast (s) | τ_slow blocked (gr→0) | K_S = g/(g·ga + gr·g + gr·ga) (K/W) |
|---|---|---|---|---|---|---|---|
| H1 | 4.594 | 0.0786 | 16.22 | **63.4** | 1.9 | 463 | 1.703 |
| H2 | 2.482 | 0.0775 | 31.67 | **94.4** | 4.6 | 670 | 1.686 |
| H3 | 1.293 | 0.0753 | 62.57 | **169.1** | 9.5 | 1100 | 1.654 |

H3 stores 3.9× the surface heat of H1 behind 3.5× the resistance: its slow mode is 2.7× slower, while the probe schedule (D = 60 s, period 150 s) was the same for all stacks.

### B.2 Probe signature vs schedule (continuous-time, slow/fast mode weights A1, A2; `estimate`)
Single shot from steady state: ΔS(D) = K_S·d·[1 − A1 e^{−D/τ1} − A2 e^{−D/τ2}]. Periodic probing (D on, R = T − D off): per mode z_e = −d(1−e^{−D/τi})/(1−e^{−T/τi}), Δz_i = z_e(1−e^{−R/τi}), signature = K_S Σ A_i Δz_i (d = 3 W).

| stack | (D, T) | continuous estimate (K) | executed discrete value (receipt) |
|---|---|---|---|
| H1 | (60,150) | −2.54 | −2.425 (dŷ at 720) |
| H2 | (60,150) | −1.67 | −1.576 |
| H3 | (60,150) | **−0.81** | not reached (watchdog) |
| H3 | (90,180) | −1.07 | — |
| H3 | (90,210) | −1.26 | — |
| H3 | (120,210) / (120,240) | −1.26 / −1.50 | — |

The discrete statistic (5-sample means, dt = 1 s) is 4–6 % smaller than the continuous value. H3 with the old schedule has a periodic signature ≈ 0.8 K: above the deterministic frozen-detection boundary τ_abs/(1−τ_rel) = 0.5 K and the 0.6 K floor, but with only 0.4·0.8 − 0.2 = 0.12 K margin (≈ 1.1 σ of a noise-straddled window) — and during the heating transient it is cancelled outright (§A #1).

### B.3 Design rules (study choices, applied per stack by `supervisor.derive_config`)
- R0 (floor, noise-derived, stack-independent): `probe_min_predicted` = 0.6 K > 0.5 K boundary; unchanged.
- R1 (duration from τ_slow): D = max(60, ceil₁₀(0.5·τ_slow)) capped at 120 s → H1 60, H2 60, **H3 90**.
- R2 (period): T = D + 90 s (the H1/H2 recovery), extended in 30 s steps until the model's **periodic** signature ≥ target = floor + 0.4 K = 1.0 K (0.4 K ≈ 6 σ of the clean dy statistic; ≈ 1.8 σ for a window straddling the freeze instant). Predicted: H1/H2 stay (60,150); H3 → (90,180) if the discrete value of −1.07 survives the 4–6 % discretisation loss, else (90,210). Both are acceptable; tests use the derived value.
- R3 (watchdog from the schedule, not a constant): watchdog = 2·T + D, i.e. tolerate exactly one uninformative probe → H1/H2 360 s (the old default, now justified), H3 450 or 510 s.
- R4 (evidence source — the D1 fix): liveness evidence is *any confirmed, informative movement* over the probe-length window, evaluated every sample: \|dŷ_W\| ≥ floor and \|dy_W − dŷ_W\| ≤ τ_abs + τ_rel\|dŷ_W\|. The heating transient and the recovery after each probe therefore count as evidence (a frozen channel never confirms: dy = 0 vs \|dŷ\| ≥ 0.6 gives mismatch ≥ 0.6 > 0.56). Probes only need to *create* movement when the plant is quiet. This check never trips (no new false-alarm surface); trips still come only from the probe-end check, the increment/level tests and the watchdog.

Why #6 happened (H2, not H1, per estimate): first-probe net change = heating(55→120) + probe: H1 +2.2 − 2.9 = −0.7 (informative), H2 +2.3 − 2.2 = +0.1 (uninformative), H3 +1.9 − 1.2 = +0.7 (informative, heating-dominated).

Predicted H3 trajectory of evidence with (90,180) (`estimate`): probe 1 (60–150) net +0.7 ok; movement windows confirm through ≈ 241; probe 2 (240–330) net ≈ −0.45 uninformative; window 300→391 (+0.76) confirms; probe 3 (420–510) −0.86 ok; probes 4/5 ≈ −1.1 ok. Longest evidence gap ≈ 150 s ≪ 450 s.

## C. Changes (minimal diffs; full files below for mechanical extraction)
- `detectability.py`: + `time_constants(p)`, + `periodic_probe_signature(...)` (mirrors `_evaluate_probe` exactly), `summary_for_stack` reports τ's and the periodic signature. Existing functions unchanged.
- `supervisor.py`: + `derive_config(model, base, overrides)` (R1–R3, returns cfg and a derivation record); `Supervisor.update` + liveness-evidence block (R4) and `live_windows` counter; `SupervisorConfig.__post_init__` + guard `watchdog_powered_s ≥ probe_period + probe_duration` when probes and watchdog are enabled. No threshold constants changed; the 360 s default is now the R3 value for the base schedule.
- `harness.py`: `make_controller` uses `derive_config` (scenario overrides still win); results gain `probe_log`, `live_windows`, `supervisor_config`; report gains `derived_configs`; H3-dependent `expected` strings made schedule-relative.
- `run_matrix.py`: prints the derived configurations.
- `test_supervisor.py`: T1/T2 fixed; bounds derived from the config in force; new tests for time constants, derived configs, evidence semantics, config guard, modelled actuator delay, and a regression test pinning H1/H2 to the executed receipts (their derived config equals the base, so they must reproduce bit-for-bit).
- `plant.py`: **unchanged, not re-sent.**

## D. Updated predeclared expectations (unexecuted; H1/H2 unchanged from receipts)
| H3 run | expectation (`estimate`) |
|---|---|
| sup1_intact_* (ideal, noise, hot, cold) | RUN to horizon; 5 probes (T=180: 60,240,420,600,780; cost 1350 J) or 4 (T=210: 1080 J); probe 2 uninformative; all probes ending ≥ 500 s "ok" |
| sup1_rearloss600_noise | TRIP_MODEL ≈ 620–635 (increment test), peak H ≈ 34–37 |
| sup1_freeze600_rearloss600_noise | TRIP_SENSOR at 690 (T=180; probe 4 starts at 600, pre-window straddles the freeze: ≈ 2 % chance of a miss → 870) or 780 (T=210, dy = 0 exactly); peak H ≈ 36–43 < 45.17 either way; bound in test: 600 + T + D + 5 |
| sup1_freeze600_only_noise | TRIP_SENSOR same instants, peak H < 34 |
| biasstep / dropout | 602 / 602 |
| stuckon600_rearloss600 | tripped ≈ 620–635; final H ≈ 90 (blocked 5 W steady 96.6, τ 1100 s) |
| idle_rearloss1500_redemand2400 | trip ≈ 2425 via increment after re-demand (level crossing would be ≈ 2590); peak < 50 |
| actdelay5 | report only; estimate RUN |

Fragile points to watch in execution: (i) whether H3 resolves to T = 180 or 210; (ii) H3 `rearloss600` ≤ 660 if a probe is active at 600 (T = 180) — the rear flux is reduced during the probe; estimate ≈ 630; (iii) H3 `rearloss100` ≤ 250 (was 216 with the old schedule).

## E. Guarantees restated (model scale only)
G3 becomes: a stuck primary channel during powered operation is detected within probe_period + probe_duration + 5 s of the stack's derived schedule (deterministic for a noise-free stuck value, H3: ≤ 275/305 s), or within 2·probe_period + probe_duration powered seconds otherwise. C1 amended as in §A. C4 amended: steady residual under constant bias is +b.

## F. Not implemented / open
Adaptive probe depth (model look-ahead at probe start would make heating-transient probes informative; deliberately not added — minimal diff); per-sample movement check as a trip path (rejected: correlated-window noise exposure); full design-box sweep; ambient drift; quantisation; H-observer; reset logic; continuous-time analysis; quantitative second-sensor cost.

---

FILE: thermal_supervisor/detectability.py
```python
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
```

FILE: thermal_supervisor/supervisor.py
```python
"""Failure-aware supervisory thermal-protection layer (model study only).

Red (Claude, Anthropic) for The Stage / Andrei; plant algebra credited to Coda (Codex Lily).
Observable inputs: reported y1 (may be None), optional y2, own commanded power, elapsed time,
mission demand. Everything else is hidden. No reset, no automatic restart.

fix-003 changes (README sections A-C): liveness evidence comes from any confirmed informative
movement over the probe-length window (not only probe ends); derive_config() sets the probe
duration/period and the watchdog budget per stack from the plant's slow time constant and the
model's periodic probe signature; a config guard rejects watchdog budgets shorter than one
probe cycle. Thresholds (tau_*) are unchanged.
"""
from collections import deque
from dataclasses import dataclass, replace
import math

from plant import step, blocked
from detectability import time_constants, periodic_probe_signature

INIT = "INIT"
RUN = "RUN"
TRIP_LIMIT = "TRIP_LIMIT"
TRIP_SENSOR = "TRIP_SENSOR"
TRIP_MODEL = "TRIP_MODEL"
TRIPPED = frozenset({TRIP_LIMIT, TRIP_SENSOR, TRIP_MODEL})
STATES = (INIT, RUN, TRIP_LIMIT, TRIP_SENSOR, TRIP_MODEL)


def valid_reading(y):
    return y is not None and type(y) in (int, float) and math.isfinite(y)


def _mean(values):
    return math.fsum(values) / len(values)


@dataclass(frozen=True)
class SupervisorConfig:
    sample_dt: float = 1.0
    p_max: float = 10.0
    j_assumed: float = 0.1
    t_trip: float = 45.0            # study comparator only
    t_lo: float = -20.0
    t_hi: float = 150.0
    rate_max: float = 8.0           # K/s plausibility
    n_dropout: int = 3
    tau_abs_level: float = 0.8
    tau_rel_level: float = 0.4
    m_level: int = 3
    inc_window: int = 10
    inc_mean_n: int = 5
    tau_abs_inc: float = 0.3
    tau_rel_inc: float = 0.5
    m_inc: int = 3
    probe_enabled: bool = True
    probe_depth: float = 3.0
    probe_duration: int = 60
    probe_period: int = 150
    probe_first: int = 60
    probe_mean_n: int = 5
    tau_abs_probe: float = 0.2
    tau_rel_probe: float = 0.6
    probe_min_predicted: float = 0.6
    watchdog_enabled: bool = True
    watchdog_powered_s: int = 360   # = 2*probe_period + probe_duration for the base schedule (rule R3)
    dual_sensor: bool = False
    tau_pair: float = 0.8
    m_pair: int = 3
    actuator_delay_model: int = 0

    def __post_init__(self):
        if self.probe_period <= self.probe_duration:
            raise ValueError("probe_period must exceed probe_duration")
        for name in ("n_dropout", "m_level", "m_inc", "m_pair", "inc_window", "inc_mean_n",
                     "probe_mean_n", "probe_duration", "probe_period"):
            if int(getattr(self, name)) < 1:
                raise ValueError(name + " must be >= 1")
        if self.actuator_delay_model < 0 or self.probe_first < 0:
            raise ValueError("delays must be nonnegative")
        if self.tau_rel_probe >= 1.0 or self.tau_rel_inc < 0 or self.tau_rel_level < 0:
            raise ValueError("relative thresholds out of range")
        if (self.probe_enabled and self.watchdog_enabled
                and self.watchdog_powered_s < self.probe_period + self.probe_duration):
            raise ValueError("watchdog_powered_s must cover at least one full probe cycle "
                             "(probe_period + probe_duration)")


def derive_config(model, base=None, overrides=None, signature_margin=0.4, p_ref=5.0,
                  duration_cap=120, period_step=30, period_extension_max=300):
    """Per-stack schedule from the plant's slow time constant (README B.3, rules R1-R3).

    R1 probe_duration = max(base, ceil10(0.5 * tau_slow)), capped at duration_cap.
    R2 probe_period = duration + base recovery, extended in period_step increments until the
       model's periodic probe signature reaches probe_min_predicted + signature_margin.
    R3 watchdog_powered_s = 2 * probe_period + probe_duration (tolerates one uninformative probe).
    `overrides` (SupervisorConfig field values) always win; a field given in overrides is not
    derived. Returns (config, derivation_record). Study derivation for the model, nothing more."""
    base = base or SupervisorConfig()
    overrides = dict(overrides or {})
    tau_slow, tau_fast = time_constants(model)
    tau_slow_blocked = time_constants(blocked(model))[0]
    recovery = int(base.probe_period - base.probe_duration)
    if "probe_duration" in overrides:
        duration = int(overrides["probe_duration"])
    elif math.isfinite(tau_slow):
        duration = max(int(base.probe_duration),
                       min(int(duration_cap), 10 * int(math.ceil(0.5 * tau_slow / 10.0))))
    else:
        duration = int(base.probe_duration)
    depth = float(overrides.get("probe_depth", base.probe_depth))
    mean_n = int(overrides.get("probe_mean_n", base.probe_mean_n))
    j = float(overrides.get("j_assumed", base.j_assumed))
    target = float(overrides.get("probe_min_predicted", base.probe_min_predicted)) + signature_margin
    period = int(overrides.get("probe_period", duration + recovery))
    sig = periodic_probe_signature(model, p_ref, j, depth, duration, period, mean_n)
    candidates = [(duration, period, sig)]
    if "probe_period" not in overrides:
        while abs(sig) < target and period < duration + recovery + period_extension_max:
            period += int(period_step)
            sig = periodic_probe_signature(model, p_ref, j, depth, duration, period, mean_n)
            candidates.append((duration, period, sig))
    watchdog = int(overrides.get("watchdog_powered_s", 2 * period + duration))
    fields = dict(probe_duration=duration, probe_period=period, watchdog_powered_s=watchdog)
    fields.update(overrides)
    cfg = replace(base, **fields)
    info = dict(tau_slow_s=tau_slow, tau_fast_s=tau_fast, tau_slow_blocked_s=tau_slow_blocked,
                probe_duration_rule="max(base, ceil10(0.5*tau_slow)) capped at %d s" % duration_cap,
                period_rule=("duration + base recovery (%d s), extended in %d s steps until "
                             "|periodic signature| >= target" % (recovery, period_step)),
                watchdog_rule="2*probe_period + probe_duration (tolerates one uninformative probe)",
                signature_target_K=target, periodic_signature_K=sig,
                candidates=[dict(duration=d, period=t, signature_K=s) for d, t, s in candidates],
                derivation_ok=bool(abs(sig) >= target), overrides=dict(overrides),
                label="model derivation for the study plant; not a hardware design recommendation")
    return cfg, info


class Supervisor:
    """State machine + residual detectors; see README section 2."""

    def __init__(self, model, cfg=None):
        self.model = model
        self.cfg = cfg or SupervisorConfig()
        c = self.cfg
        self.state = INIT
        self.trip_time = None
        self.trip_cause = None
        self.Hhat = None
        self.Shat = None
        self.prev_y1 = None
        self.invalid1 = 0
        self.invalid2 = 0
        self.disagree = 0
        self.level_run = 0
        self.inc_run = 0
        self.last_residual = None
        self.active_probe_start = None
        self.probes_ok = 0
        self.probes_uninformative = 0
        self.probe_log = []
        self.powered_since_evidence = 0
        self.live_windows = 0          # fix-003: confirmed informative movement windows
        n = max(c.inc_window + c.inc_mean_n, c.probe_duration + 1 + c.probe_mean_n) + 8
        self.ybuf = deque(maxlen=n)
        self.sbuf = deque(maxlen=n)
        self.p_hist = deque([0.0] * (c.actuator_delay_model + 1), maxlen=c.actuator_delay_model + 1)
        self.history = []   # (t, y1, y2, Shat, state, p_cmd, probe_active)

    # ---- helpers -------------------------------------------------------------------
    def _trip(self, state, t, cause):
        if self.state in TRIPPED:
            return
        self.state = state
        self.trip_time = t
        self.trip_cause = cause

    def _record(self, t, y1, y2, p_cmd, probe_active):
        self.history.append((t, y1, y2, self.Shat, self.state, p_cmd, probe_active))

    def _increment(self, W, n):
        buf = list(self.ybuf)
        L = len(buf)
        if L < W + n:
            return None
        post = buf[L - n:]
        pre = buf[L - W - n:L - W]
        if any(v is None for v in post) or any(v is None for v in pre):
            return None
        sb = list(self.sbuf)
        return _mean(post) - _mean(pre), _mean(sb[L - n:]) - _mean(sb[L - W - n:L - W])

    def _evaluate_probe(self, t):
        c = self.cfg
        D, n = c.probe_duration, c.probe_mean_n
        buf = list(self.ybuf)
        sb = list(self.sbuf)
        L = len(buf)
        if L < D + 1 + n:
            self.probes_uninformative += 1
            self.probe_log.append((t, None, None, "short buffer"))
            return
        post = buf[L - n:]
        pre = buf[L - D - 1 - n:L - D - 1]
        dyh = _mean(sb[L - n:]) - _mean(sb[L - D - 1 - n:L - D - 1])
        if any(v is None for v in post) or any(v is None for v in pre):
            self.probes_uninformative += 1
            self.probe_log.append((t, None, dyh, "invalid samples in window"))
            return
        if abs(dyh) < c.probe_min_predicted:
            self.probes_uninformative += 1
            self.probe_log.append((t, _mean(post) - _mean(pre), dyh, "uninformative"))
            return
        dy = _mean(post) - _mean(pre)
        mismatch = abs(dy - dyh)
        if mismatch > c.tau_abs_probe + c.tau_rel_probe * abs(dyh):
            self.probe_log.append((t, dy, dyh, "FAIL"))
            self._trip(TRIP_SENSOR, t, "probe no-response: dy=%.3f dyhat=%.3f" % (dy, dyh))
        else:
            self.probe_log.append((t, dy, dyh, "ok"))
            self.probes_ok += 1
            self.powered_since_evidence = 0

    # ---- main entry -----------------------------------------------------------------
    def update(self, t, y1, y2, demand):
        """One sample at integer time t. Returns commanded body power for [t, t+1)."""
        c = self.cfg
        v1 = valid_reading(y1)
        v2 = c.dual_sensor and valid_reading(y2)
        if self.state in TRIPPED:
            self._record(t, y1, y2, 0.0, False)
            return 0.0
        if self.state == INIT:
            if not v1:
                self.invalid1 += 1
                if self.invalid1 >= c.n_dropout:
                    self._trip(TRIP_SENSOR, t, "startup dropout")
                self._record(t, y1, y2, 0.0, False)
                return 0.0
            self.Hhat = self.Shat = float(y1)
            self.state = RUN
            self.invalid1 = 0
            self.powered_since_evidence = 0
        # ---- guards: LIMIT > SENSOR > MODEL ----
        if (v1 and y1 >= c.t_trip) or (v2 and y2 >= c.t_trip):
            self._trip(TRIP_LIMIT, t, "reported temperature >= study comparator %.1f C" % c.t_trip)
        if self.state == RUN:
            if not v1:
                self.invalid1 += 1
                if self.invalid1 >= c.n_dropout:
                    self._trip(TRIP_SENSOR, t, "primary sensor dropout")
            else:
                self.invalid1 = 0
                if y1 < c.t_lo or y1 > c.t_hi:
                    self._trip(TRIP_SENSOR, t, "implausible primary value")
                elif self.prev_y1 is not None and abs(y1 - self.prev_y1) > c.rate_max * c.sample_dt:
                    self._trip(TRIP_SENSOR, t, "implausible primary rate")
        if self.state == RUN and c.dual_sensor:
            if not v2:
                self.invalid2 += 1
                if self.invalid2 >= c.n_dropout:
                    self._trip(TRIP_SENSOR, t, "second sensor dropout")
            else:
                self.invalid2 = 0
                if v1:
                    if abs(y1 - y2) > c.tau_pair:
                        self.disagree += 1
                    else:
                        self.disagree = 0
                    if self.disagree >= c.m_pair:
                        self._trip(TRIP_SENSOR, t, "sensor disagreement > %.2f K" % c.tau_pair)
        # ---- residual bookkeeping (kept aligned even when invalid) ----
        self.ybuf.append(float(y1) if v1 else None)
        self.sbuf.append(self.Shat)
        if self.state == RUN and v1:
            r = y1 - self.Shat
            self.last_residual = r
            if abs(r) > c.tau_abs_level + c.tau_rel_level * abs(self.Shat - self.model.ambient):
                self.level_run += 1
            else:
                self.level_run = 0
            if self.level_run >= c.m_level:
                self._trip(TRIP_MODEL, t, "level residual %.3f K" % r)
        if self.state == RUN:
            inc = self._increment(c.inc_window, c.inc_mean_n)
            if inc is None:
                self.inc_run = 0
            else:
                dy, dyh = inc
                if abs(dy - dyh) > c.tau_abs_inc + c.tau_rel_inc * abs(dyh):
                    self.inc_run += 1
                else:
                    self.inc_run = 0
                if self.inc_run >= c.m_inc:
                    self._trip(TRIP_MODEL, t, "increment residual dy=%.3f dyhat=%.3f" % (dy, dyh))
        # ---- liveness evidence (fix-003, rule R4): any confirmed informative movement over the
        #      probe-length window resets the watchdog; a stuck channel never confirms ----
        if self.state == RUN:
            mv = self._increment(c.probe_duration + 1, c.probe_mean_n)
            if mv is not None:
                dy_w, dyh_w = mv
                if (abs(dyh_w) >= c.probe_min_predicted
                        and abs(dy_w - dyh_w) <= c.tau_abs_probe + c.tau_rel_probe * abs(dyh_w)):
                    self.powered_since_evidence = 0
                    self.live_windows += 1
        # ---- probe completion check ----
        if (self.state == RUN and self.active_probe_start is not None
                and t == self.active_probe_start + c.probe_duration):
            self._evaluate_probe(t)
            self.active_probe_start = None
        # ---- liveness watchdog ----
        if self.state == RUN and c.watchdog_enabled and self.powered_since_evidence > c.watchdog_powered_s:
            self._trip(TRIP_SENSOR, t, "liveness watchdog: no confirmed movement within %d powered s"
                       % c.watchdog_powered_s)
        # ---- command law ----
        p_cmd = 0.0
        probe_active = False
        if self.state == RUN:
            p_cmd = min(max(float(demand), 0.0), c.p_max)
            if c.probe_enabled and p_cmd > 0:
                phase = t - c.probe_first
                if phase >= 0:
                    if phase % c.probe_period == 0 and self.active_probe_start is None:
                        self.active_probe_start = t
                    if self.active_probe_start is not None and t < self.active_probe_start + c.probe_duration:
                        probe_active = True
                        p_cmd = max(0.0, p_cmd - c.probe_depth)
            if p_cmd > 0:
                self.powered_since_evidence += 1
        if v1:
            self.prev_y1 = float(y1)
        self._record(t, y1, y2, p_cmd, probe_active)
        if self.state == RUN:
            self.p_hist.append(p_cmd)
            self.Hhat, self.Shat = step(self.model, self.Hhat, self.Shat, self.p_hist[0],
                                        c.j_assumed, c.sample_dt)
        return p_cmd


class OpenLoop:
    """Demand passthrough; reference behaviour (F0/F1)."""
    state = "OPEN_LOOP"
    trip_time = None
    trip_cause = None

    def update(self, t, y1, y2, demand):
        return float(demand)


class NaiveTrip:
    """F4 illustration: latch body power to zero at the first reported value >= t_trip."""

    def __init__(self, t_trip=45.0):
        self.t_trip = t_trip
        self.state = RUN
        self.trip_time = None
        self.trip_cause = None

    def update(self, t, y1, y2, demand):
        if self.state == TRIP_LIMIT:
            return 0.0
        if valid_reading(y1) and y1 >= self.t_trip:
            self.state = TRIP_LIMIT
            self.trip_time = t
            self.trip_cause = "naive: reported >= %.1f C" % self.t_trip
            return 0.0
        return float(demand)
```

FILE: thermal_supervisor/harness.py
```python
"""Deterministic closed-loop harness, fault injection, predeclared matrix and report.

Plant: Coda's two-node algebra (plant.py). Everything here is synthetic computation.
fix-003: supervisor runs use the per-stack derived configuration (supervisor.derive_config);
scenario overrides still win. Results carry the probe log, liveness-window count and the
configuration in force; the report carries the derivation records.
"""
from dataclasses import dataclass, field, asdict, replace
import math
import random
import zlib

from plant import (Params, build, nominal, step, surface, steady_state, blocked,
                   NOMINAL_PROPERTIES, P_MAX_W)
from supervisor import (Supervisor, SupervisorConfig, NaiveTrip, OpenLoop, TRIPPED,
                        derive_config)
import detectability

DESIGN_BOX = dict(k_sil=(0.22, 0.32), k_film=(0.16, 0.24), r_c=(1e-4, 4e-4), h=(6.0, 10.0),
                  r_rej=(1.6, 2.5), c_h=(15.0, 25.0), cp_sil=(1200.0, 1800.0))
CONTRACT_RANGES = dict(k_sil=(0.18, 0.35), k_film=(0.12, 0.25), r_c=(0.0, 2e-3), h=(3.0, 15.0),
                       r_rej=(1.0, 10.0), c_h=(5.0, 100.0), cp_sil=(1000.0, 2000.0))
HOT_CORNER = dict(k_sil=0.22, k_film=0.16, r_c=4e-4, h=6.0, r_rej=2.5, c_h=15.0, cp_sil=1200.0)
COLD_CORNER = dict(k_sil=0.32, k_film=0.24, r_c=1e-4, h=10.0, r_rej=1.6, c_h=25.0, cp_sil=1800.0)
MISSION = ((0, 900, 5.0),)
MISSION_REDEMAND = ((0, 900, 5.0), (2400, 3300, 5.0))
NOISE_SIGMA = 0.1
NOISE_BIAS_1 = 0.2
NOISE_BIAS_2 = -0.1


def in_design_box(props):
    return all(lo <= props[k] <= hi for k, (lo, hi) in DESIGN_BOX.items())


def seed_for(name):
    return zlib.crc32(name.encode("utf-8")) & 0xFFFF


@dataclass(frozen=True)
class SensorSpec:
    sigma: float = 0.0
    bias: float = 0.0
    seed: int = 0
    freeze_time: int | None = None       # reported value held at the sample before this time
    freeze_adds_noise: bool = False      # True: channel stuck upstream of ADC noise
    bias_step_time: int | None = None
    bias_step: float = 0.0
    dropout_start: int | None = None
    dropout_end: int | None = None       # exclusive; None with start = permanent


class SensorChannel:
    def __init__(self, spec):
        self.spec = spec
        self.rng = random.Random(spec.seed)
        self.last = None
        self.frozen_value = None
        self.frozen_set = False

    def read(self, k, true_S):
        sp = self.spec
        n = self.rng.gauss(0.0, 1.0) if sp.sigma > 0 else 0.0
        frozen = sp.freeze_time is not None and k >= sp.freeze_time
        if sp.dropout_start is not None and k >= sp.dropout_start and (sp.dropout_end is None or k < sp.dropout_end):
            reported = None
        elif frozen:
            if not self.frozen_set:
                self.frozen_value = self.last
                self.frozen_set = True
            reported = self.frozen_value
            if reported is not None and sp.freeze_adds_noise:
                reported = reported + sp.sigma * n
        else:
            value = true_S + sp.bias + sp.sigma * n
            if sp.bias_step_time is not None and k >= sp.bias_step_time:
                value += sp.bias_step
            reported = value
        if not frozen:
            self.last = reported
        return reported


@dataclass(frozen=True)
class ActuatorSpec:
    delay: int = 0                       # samples of pure transport delay (unknown to supervisor unless modelled)
    stuck_time: int | None = None        # from this sample the applied power is frozen at its last value


class Actuator:
    def __init__(self, spec):
        self.spec = spec
        self.hist = [0.0] * spec.delay
        self.last_applied = 0.0
        self.stuck_value = None

    def apply(self, k, p_cmd):
        self.hist.append(float(p_cmd))
        p = self.hist[-1 - self.spec.delay]
        if self.spec.stuck_time is not None and k >= self.spec.stuck_time:
            if self.stuck_value is None:
                self.stuck_value = self.last_applied
            p = self.stuck_value
        self.last_applied = p
        return p


def demand_at(schedule, k):
    for start, end, power in schedule:
        if start <= k < end:
            return float(power)
    return 0.0


@dataclass(frozen=True)
class Scenario:
    name: str
    stack: str
    controller: str                                  # open_loop | naive | supervisor
    plant_props: dict = field(default_factory=lambda: dict(NOMINAL_PROPERTIES))
    demand: tuple = MISSION
    rear_loss_time: int | None = None
    rear_fraction: float = 0.0
    sensor1: SensorSpec = field(default_factory=SensorSpec)
    sensor2: SensorSpec | None = None
    actuator: ActuatorSpec = field(default_factory=ActuatorSpec)
    supervisor: dict = field(default_factory=dict)   # SupervisorConfig overrides (win over derivation)
    horizon: int = 3600
    sensor_power: float = 0.1
    purpose: str = ""
    expected: str = ""

    def faults(self):
        out = []
        if self.rear_loss_time is not None:
            out.append(("rear_loss", self.rear_loss_time))
        s = self.sensor1
        if s.freeze_time is not None:
            out.append(("sensor1_freeze", s.freeze_time))
        if s.bias_step_time is not None:
            out.append(("sensor1_bias_step", s.bias_step_time))
        if s.dropout_start is not None:
            out.append(("sensor1_dropout", s.dropout_start))
        if self.sensor2 is not None:
            s2 = self.sensor2
            if s2.freeze_time is not None:
                out.append(("sensor2_freeze", s2.freeze_time))
            if s2.dropout_start is not None:
                out.append(("sensor2_dropout", s2.dropout_start))
        if self.actuator.delay:
            out.append(("actuator_delay", 0))
        if self.actuator.stuck_time is not None:
            out.append(("actuator_stuck_on", self.actuator.stuck_time))
        return out


def supervisor_config_for(sc):
    """Derived per-stack configuration with the scenario's overrides applied (fix-003)."""
    cfg, info = derive_config(nominal(sc.stack), SupervisorConfig(), sc.supervisor)
    return cfg, info


def make_controller(sc):
    if sc.controller == "open_loop":
        return OpenLoop()
    if sc.controller == "naive":
        return NaiveTrip(45.0)
    if sc.controller == "supervisor":
        cfg, _info = supervisor_config_for(sc)
        return Supervisor(nominal(sc.stack), cfg)
    raise ValueError("unknown controller " + sc.controller)


def run_scenario_detailed(sc):
    """Returns (result dict, controller). Deterministic."""
    params = build(sc.stack, **sc.plant_props)
    faulted = blocked(params, sc.rear_fraction)
    controller = make_controller(sc)
    s1 = SensorChannel(sc.sensor1)
    s2 = SensorChannel(sc.sensor2) if sc.sensor2 is not None else None
    act = Actuator(sc.actuator)
    H = S = params.ambient
    peak = {"H": (-math.inf, None), "S": (-math.inf, None), "surface": (-math.inf, None)}
    cross = {"surface_ge_40C": None, "internal_ge_60C": None}
    energy_applied = 0.0
    energy_demanded = 0.0
    trace = []
    at_trip = None
    for k in range(sc.horizon + 1):
        surf = surface(params, S)
        y1 = s1.read(k, S)
        y2 = s2.read(k, S) if s2 is not None else None
        d = demand_at(sc.demand, k)
        p_cmd = controller.update(k, y1, y2, d)
        for key, val in (("H", H), ("S", S), ("surface", surf)):
            if val > peak[key][0]:
                peak[key] = (val, k)
        if cross["surface_ge_40C"] is None and surf >= 40.0:
            cross["surface_ge_40C"] = k
        if cross["internal_ge_60C"] is None and H >= 60.0:
            cross["internal_ge_60C"] = k
        if at_trip is None and controller.state in TRIPPED:
            at_trip = dict(time=k, true_H=H, true_S=S, true_surface=surf, reported_y1=y1, reported_y2=y2)
        if k % 60 == 0:
            trace.append(dict(t=k, H=round(H, 6), S=round(S, 6), surface=round(surf, 6),
                              y1=None if y1 is None else round(y1, 6), p_cmd=p_cmd, state=controller.state))
        if k == sc.horizon:
            break
        p_app = act.apply(k, p_cmd)
        if not 0.0 <= p_app <= P_MAX_W:
            raise ValueError("applied power outside study envelope")
        p = faulted if (sc.rear_loss_time is not None and k >= sc.rear_loss_time) else params
        H, S = step(p, H, S, p_app, sc.sensor_power, 1.0)
        energy_applied += p_app
        energy_demanded += d
    faults = sc.faults()
    first_fault = min((t for _, t in faults), default=None)
    trip_time = getattr(controller, "trip_time", None)
    tripped = controller.state in TRIPPED
    box = in_design_box(sc.plant_props)
    result = dict(
        name=sc.name, stack=sc.stack, controller=sc.controller, purpose=sc.purpose, expected=sc.expected,
        plant_props=dict(sc.plant_props), in_design_box=box, demand=list(sc.demand),
        faults=[list(f) for f in faults], first_fault_time=first_fault,
        peak_H=peak["H"][0], peak_H_time=peak["H"][1], peak_S=peak["S"][0], peak_S_time=peak["S"][1],
        peak_surface=peak["surface"][0], peak_surface_time=peak["surface"][1],
        final_H=H, final_S=S, final_state=controller.state, tripped=tripped,
        trip_time=trip_time, trip_cause=getattr(controller, "trip_cause", None),
        detection_delay_s=(trip_time - first_fault) if (trip_time is not None and first_fault is not None) else None,
        state_at_trip=at_trip,
        energy_demanded_J=energy_demanded, energy_applied_J=energy_applied,
        energy_withheld_J=energy_demanded - energy_applied,
        probes_ok=getattr(controller, "probes_ok", None),
        probes_uninformative=getattr(controller, "probes_uninformative", None),
        probe_log=[list(e) for e in getattr(controller, "probe_log", [])],
        live_windows=getattr(controller, "live_windows", None),
        supervisor_config=(asdict(controller.cfg) if isinstance(controller, Supervisor) else None),
        false_alarm=bool(tripped and not faults and box),
        comparator_crossings={k: (v if v is not None else "not_crossed_in_horizon") for k, v in cross.items()},
        comparator_label="study_comparator_only",
        trace_60s=trace, model="T0-LUMP2-1 (Coda) + Red supervisor", physical_validation=False)
    return result, controller


def run_scenario(sc):
    return run_scenario_detailed(sc)[0]


def scenario_matrix():
    """Predeclared, deterministic, <= 60 runs. Supervisor runs use the per-stack derived
    schedule (H1/H2 predicted identical to the base; H3 longer probes and period)."""
    runs = []

    def noisy(name, bias=NOISE_BIAS_1, offset=0, **kw):
        return SensorSpec(sigma=NOISE_SIGMA, bias=bias, seed=seed_for(name) + offset, **kw)

    for stack in ("H1", "H2", "H3"):
        def add(short, **kw):
            name = stack + "_" + short
            kw.setdefault("controller", "supervisor")
            runs.append(Scenario(name=name, stack=stack, **kw))
            return name
        add("ol_intact", controller="open_loop", purpose="F0 reference",
            expected="no trip; matches Coda's intact row")
        add("ol_rearloss600", controller="open_loop", rear_loss_time=600, purpose="F1 reference",
            expected="matches Coda's rear-loss row")
        add("naive45_truthful_rearloss600", controller="naive", rear_loss_time=600,
            purpose="F4 truthful", expected="trips at first reported >= 45 C before 900 s")
        add("naive45_frozen600_rearloss600", controller="naive", rear_loss_time=600,
            sensor1=SensorSpec(freeze_time=600), purpose="F4 frozen counterexample",
            expected="never trips; true trajectory equals F1")
        add("sup1_intact_ideal", purpose="probe cost, zero residual",
            expected="RUN to horizon; all scheduled probes evaluated; probes ending >= 500 s ok; residual ~0")
        n = stack + "_sup1_intact_noise"
        add("sup1_intact_noise", sensor1=noisy(n), purpose="false alarm (noise+bias)", expected="no trip")
        n = stack + "_sup1_hotcorner_noise"
        add("sup1_hotcorner_noise", plant_props=dict(HOT_CORNER), sensor1=noisy(n),
            purpose="false alarm at hot design-box corner", expected="no trip")
        n = stack + "_sup1_coldcorner_noise"
        add("sup1_coldcorner_noise", plant_props=dict(COLD_CORNER), sensor1=noisy(n),
            purpose="false alarm at cold design-box corner", expected="no trip")
        n = stack + "_sup1_rearloss600_noise"
        add("sup1_rearloss600_noise", rear_loss_time=600, sensor1=noisy(n),
            purpose="rear loss, live sensor", expected="TRIP_MODEL within 60 s; peak H < 45")
        n = stack + "_sup1_rearloss100_noise"
        add("sup1_rearloss100_noise", rear_loss_time=100, sensor1=noisy(n),
            purpose="rear loss during heating transient", expected="TRIP_MODEL within 150 s")
        n = stack + "_sup1_freeze600_rearloss600_noise"
        add("sup1_freeze600_rearloss600_noise", rear_loss_time=600, sensor1=noisy(n, freeze_time=600),
            purpose="F3 with probe scheme",
            expected="trip by fault + probe_period + probe_duration + 5 s; peak below F1 by >= 5 K")
        n = stack + "_sup1_freeze600_only_noise"
        add("sup1_freeze600_only_noise", sensor1=noisy(n, freeze_time=600),
            purpose="freeze without hazard (availability cost)",
            expected="TRIP_SENSOR by fault + probe_period + probe_duration + 5 s")
        n = stack + "_sup1_biasstep600_rearloss600_noise"
        add("sup1_biasstep600_rearloss600_noise", rear_loss_time=600,
            sensor1=noisy(n, bias_step_time=600, bias_step=-5.0),
            purpose="sensor reads 5 K low from 600 s", expected="trip within 20 s")
        n = stack + "_sup1_dropout600_noise"
        add("sup1_dropout600_noise", sensor1=noisy(n, dropout_start=600, dropout_end=615),
            purpose="15 s dropout", expected="TRIP_SENSOR at 602")
        n = stack + "_sup1_actdelay5_intact_noise"
        add("sup1_actdelay5_intact_noise", actuator=ActuatorSpec(delay=5), sensor1=noisy(n),
            purpose="unmodelled 5 s actuator delay", expected="report only (H1 tripped at 71 in wave 10)")
        n = stack + "_sup1_stuckon600_rearloss600_noise"
        add("sup1_stuckon600_rearloss600_noise", rear_loss_time=600, actuator=ActuatorSpec(stuck_time=600),
            sensor1=noisy(n), purpose="actuator stuck on: detect but cannot protect",
            expected="tripped; final H > 60 C (comparator only)")
        n = stack + "_sup2_freeze600_rearloss600_noise"
        add("sup2_freeze600_rearloss600_noise", rear_loss_time=600, sensor1=noisy(n, freeze_time=600),
            sensor2=noisy(n, bias=NOISE_BIAS_2, offset=1),
            supervisor=dict(dual_sensor=True, probe_enabled=False, watchdog_enabled=False),
            purpose="dual channel, no probes", expected="TRIP_SENSOR (disagreement) within 100 s")
        n = stack + "_sup2_intact_noise"
        add("sup2_intact_noise", sensor1=noisy(n), sensor2=noisy(n, bias=NOISE_BIAS_2, offset=1),
            supervisor=dict(dual_sensor=True, probe_enabled=False, watchdog_enabled=False),
            purpose="dual channel false alarm", expected="no trip")
        n = stack + "_sup1_idle_rearloss1500_redemand2400_noise"
        add("sup1_idle_rearloss1500_redemand2400_noise", rear_loss_time=1500, demand=MISSION_REDEMAND,
            sensor1=noisy(n), purpose="rear loss during idle (J-driven slow signature), re-demand at 2400",
            expected="slow level detection (~tau_blocked) or trip within 200 s after 2400; peak H < 50")
    n = "H1_sup1_freeze600_rearloss600_period240_noise"
    runs.append(Scenario(name=n, stack="H1", controller="supervisor", rear_loss_time=600,
                         sensor1=noisy(n, freeze_time=600), supervisor=dict(probe_period=240),
                         purpose="probe period 240 s: latency/cost trade", expected="later trip, higher peak"))
    n = "H1_sup1_outofbox_rrej10_intact_noise"
    runs.append(Scenario(name=n, stack="H1", controller="supervisor",
                         plant_props={**NOMINAL_PROPERTIES, "r_rej": 10.0}, sensor1=noisy(n),
                         purpose="plant outside design box (contract range)",
                         expected="trips; not a false alarm by definition"))
    n = "H1_sup1_noprobe_freeze600_rearloss600_ideal"
    runs.append(Scenario(name=n, stack="H1", controller="supervisor", rear_loss_time=600,
                         sensor1=SensorSpec(freeze_time=600),
                         supervisor=dict(probe_enabled=False, watchdog_enabled=False),
                         purpose="single sensor, no excitation: counterexample",
                         expected="no trip before 900; peak equals F1"))
    if len(runs) > 60:
        raise ValueError("matrix exceeds 60 runs")
    if len({r.name for r in runs}) != len(runs):
        raise ValueError("duplicate scenario names")
    return runs


def summarize(results):
    lines = ["%-50s %-11s %6s %6s %8s %8s %9s %s" % ("scenario", "final", "trip", "delay", "peakH", "peakSurf", "E_app/dem", "cause")]
    for r in results:
        lines.append("%-50s %-11s %6s %6s %8.3f %8.3f %4.0f/%4.0f %s" % (
            r["name"], r["final_state"], str(r["trip_time"]), str(r["detection_delay_s"]),
            r["peak_H"], r["peak_surface"], r["energy_applied_J"], r["energy_demanded_J"], r["trip_cause"] or ""))
    false_alarms = [r["name"] for r in results if r["false_alarm"]]
    lines.append("false alarms inside design box: %s" % (false_alarms or "none"))
    return lines


def build_report(results):
    cfg = SupervisorConfig()
    noise = dict(
        assumptions="iid Gaussian sigma=0.1 K, |bias|<=0.2 K, deterministic residual assumed zero",
        level_test_union_bound_3600s=detectability.noise_false_alarm_bound(
            NOISE_SIGMA, cfg.tau_abs_level - NOISE_BIAS_1, cfg.m_level, 3600),
        increment_test_union_bound_3600s_approx=detectability.noise_false_alarm_bound(
            NOISE_SIGMA, cfg.tau_abs_inc, cfg.m_inc, 3600, mean_n=cfg.inc_mean_n, differencing=True),
        probe_test_per_probe=detectability.noise_false_alarm_bound(
            NOISE_SIGMA, cfg.tau_abs_probe, 1, 1, mean_n=cfg.probe_mean_n, differencing=True),
        label="noise-only bounds; overlapping-window persistence power is approximate")
    derived = []
    summaries = []
    for s in ("H1", "H2", "H3"):
        cfg_s, info = derive_config(nominal(s), cfg)
        derived.append(dict(stack=s, config=asdict(cfg_s), **info))
        summaries.append(detectability.summary_for_stack(s, cfg_s))
    return dict(model="T0-LUMP2-1 (Coda, Codex Lily) plant; supervisor by Red (Claude, Anthropic)",
                physical_validation=False, comparators="40/45/60 C study_comparator_only",
                supervisor_base_defaults=asdict(cfg), derived_configs=derived,
                design_box=DESIGN_BOX, contract_ranges=CONTRACT_RANGES,
                noise_false_alarm_bounds=noise, detectability=summaries, results=results)
```

FILE: thermal_supervisor/run_matrix.py
```python
"""Run the predeclared matrix; write JSON only to --out. Deterministic, stdlib only."""
import argparse
import json
from pathlib import Path
import sys

from harness import scenario_matrix, run_scenario, summarize, build_report


def main(argv=None):
    ap = argparse.ArgumentParser(description="Thermal supervisor scenario matrix (model study only)")
    ap.add_argument("--out", default=None, help="caller-supplied JSON output path (optional)")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)
    runs = scenario_matrix()
    results = [run_scenario(s) for s in runs]
    report = build_report(results)
    if not args.quiet:
        for line in summarize(results):
            print(line)
        print(json.dumps(report["noise_false_alarm_bounds"], indent=1))
        for d in report["derived_configs"]:
            print(json.dumps(d, indent=1, sort_keys=True))
        for d in report["detectability"]:
            print(json.dumps(d, indent=1))
    if args.out:
        Path(args.out).write_text(json.dumps(report, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        if not args.quiet:
            print("wrote", args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

FILE: thermal_supervisor/test_supervisor.py
```python
"""Unit tests: plant fidelity to Coda's executed numbers, state machine, detectors,
counterexamples where any controller using only the reported sensor must fail.
fix-003: T1/T2 expectation fixes, bounds derived from the configuration in force, new tests for
time constants / derived schedules / liveness evidence, and a regression test pinning H1/H2 to
Red's executed wave-10 receipts (their derived schedule equals the base schedule)."""
import importlib.util
import json
import os
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from plant import nominal, build, step, surface, steady_state, blocked, Params  # noqa: E402
from supervisor import (Supervisor, SupervisorConfig, RUN, TRIP_LIMIT, TRIP_SENSOR,  # noqa: E402
                        TRIP_MODEL, TRIPPED, derive_config)
from harness import (scenario_matrix, run_scenario, run_scenario_detailed, Scenario, SensorSpec,  # noqa: E402
                     ActuatorSpec, in_design_box, HOT_CORNER, COLD_CORNER, NOMINAL_PROPERTIES)
import detectability  # noqa: E402
from dataclasses import replace  # noqa: E402

MATRIX = {s.name: s for s in scenario_matrix()}
CODA_TABLE = {  # Coda's executed REPORT.md values (dt = 1 s, 1 s sample peaks)
    "H1": dict(intact=(33.831193, 900, 33.554994, 900, 25.170303), loss=(61.143480, 900, 59.747155, 901, 26.374204)),
    "H2": dict(intact=(33.861287, 900, 33.362444, 900, 25.168602), loss=(55.545063, 900, 53.153638, 904, 26.798252)),
    "H3": dict(intact=(33.884652, 900, 32.963939, 900, 25.165436), loss=(50.169875, 900, 45.881263, 914, 28.187988)),
}
# Red's executed wave-10 receipts for H1/H2 supervisor runs (base schedule; must reproduce).
RECEIPTS_H1_H2 = {
    "H1_sup1_rearloss600_noise": (TRIP_MODEL, 611), "H2_sup1_rearloss600_noise": (TRIP_MODEL, 614),
    "H1_sup1_rearloss100_noise": (TRIP_MODEL, 111), "H2_sup1_rearloss100_noise": (TRIP_MODEL, 115),
    "H1_sup1_freeze600_rearloss600_noise": (TRIP_SENSOR, 720), "H2_sup1_freeze600_rearloss600_noise": (TRIP_SENSOR, 720),
    "H1_sup1_biasstep600_rearloss600_noise": (TRIP_MODEL, 602), "H2_sup1_biasstep600_rearloss600_noise": (TRIP_MODEL, 602),
    "H1_sup1_dropout600_noise": (TRIP_SENSOR, 602), "H2_sup1_dropout600_noise": (TRIP_SENSOR, 602),
    "H1_sup2_freeze600_rearloss600_noise": (TRIP_SENSOR, 613), "H2_sup2_freeze600_rearloss600_noise": (TRIP_SENSOR, 620),
    "H1_sup1_idle_rearloss1500_redemand2400_noise": (TRIP_MODEL, 1838),
    "H2_sup1_idle_rearloss1500_redemand2400_noise": (TRIP_MODEL, 2050),
    "H1_sup1_freeze600_rearloss600_period240_noise": (TRIP_MODEL, 795),
    "H1_sup1_noprobe_freeze600_rearloss600_ideal": (TRIP_MODEL, 911),
    "H1_sup1_outofbox_rrej10_intact_noise": (TRIP_MODEL, 67),
    "H1_sup1_actdelay5_intact_noise": (TRIP_MODEL, 71), "H2_sup1_actdelay5_intact_noise": (RUN, None),
    "H1_sup1_intact_noise": (RUN, None), "H2_sup1_intact_noise": (RUN, None),
}
_CACHE = {}


def run(name):
    if name not in _CACHE:
        _CACHE[name] = run_scenario(MATRIX[name])
    return _CACHE[name]


def f1_peak(stack):
    return run(stack + "_ol_rearloss600")["peak_H"]


def freeze_bound(result, fault_time=600):
    """G3 worst case: probe_period + probe_duration + 5 s after the fault (config in force)."""
    c = result["supervisor_config"]
    return fault_time + c["probe_period"] + c["probe_duration"] + 5


class PlantFidelity(unittest.TestCase):
    def test_capacities_and_steady_state_match_coda(self):
        for stack, cs, H, S in (("H1", 16.2239, 33.8311998611, 33.7039846238),
                                ("H2", 31.6739, 33.8619024573, 33.6326495681),
                                ("H3", 62.5739, 33.9190557524, 33.5011406870)):
            p = nominal(stack)
            self.assertAlmostEqual(p.cs, cs, delta=1e-10)
            h, s = steady_state(p, 5.0, 0.1)
            self.assertAlmostEqual(h, H, delta=1e-8)
            self.assertAlmostEqual(s, S, delta=1e-8)
        for stack, Hb in (("H1", 90.9486203704), ("H2", 92.8189907407), ("H3", 96.5597314815)):
            h, s = steady_state(blocked(nominal(stack)), 5.0, 0.1)
            self.assertAlmostEqual(h, Hb, delta=1e-8)
            self.assertAlmostEqual(surface(nominal(stack), s), 88.75, delta=1e-8)

    def test_open_loop_reproduces_coda_executed_table(self):
        for stack, rows in CODA_TABLE.items():
            for case, name in (("intact", "_ol_intact"), ("loss", "_ol_rearloss600")):
                r = run(stack + name)
                pH, tH, pSu, tSu, fH = rows[case]
                with self.subTest(stack=stack, case=case):
                    self.assertAlmostEqual(r["peak_H"], pH, delta=2e-5)
                    self.assertEqual(r["peak_H_time"], tH)
                    self.assertAlmostEqual(r["peak_surface"], pSu, delta=2e-5)
                    self.assertEqual(r["peak_surface_time"], tSu)
                    self.assertAlmostEqual(r["final_H"], fH, delta=2e-5)
                    self.assertAlmostEqual(r["energy_applied_J"], 4500.0, delta=1e-9)

    def test_crosscheck_rc_transient_when_available(self):
        here = Path(__file__).resolve().parent
        candidates = [os.environ.get("RC_TRANSIENT_PATH"), str(here / "rc_transient.py"),
                      str(here.parent / "validation" / "thermal_transient" / "rc_transient.py")]
        path = next((c for c in candidates if c and Path(c).exists()), None)
        if path is None:
            self.skipTest("rc_transient.py not available; set RC_TRANSIENT_PATH to enable")
        spec = importlib.util.spec_from_file_location("rc_transient", path)
        rc = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(rc)
        for stack in ("H1", "H2", "H3"):
            cp = rc.nominal(stack)
            p = nominal(stack)
            ref = rc.simulate(cp, (25.0, 25.0), [dict(duration=600.0, p=5.0, j=0.1),
                                                 dict(duration=300.0, p=5.0, j=0.1, gr=0.0),
                                                 dict(duration=2700.0, p=0.0, j=0.1, gr=0.0)], 1.0)["trace"]
            H = S = 25.0
            for k in range(3600):
                q = blocked(p) if k >= 600 else p
                H, S = step(q, H, S, 5.0 if k < 900 else 0.0, 0.1, 1.0)
                self.assertAlmostEqual(H, ref[k + 1]["H"], delta=1e-9)
                self.assertAlmostEqual(S, ref[k + 1]["S"], delta=1e-9)

    def test_rear_loss_unobservable_without_rear_flux(self):
        # T1 fix: the identity holds mathematically; the two Euler coefficient sets round
        # differently at 1e-14, so compare within 1e-9 instead of exact float equality.
        p = nominal("H1")
        Hi = Si = Hb = Sb = 25.0
        for _ in range(600):
            Hi, Si = step(p, Hi, Si, 0.0, 0.0, 1.0)
            Hb, Sb = step(blocked(p), Hb, Sb, 0.0, 0.0, 1.0)
        for v in (Hi, Si, Hb, Sb):
            self.assertAlmostEqual(v, 25.0, delta=1e-9)
        self.assertAlmostEqual(Si, Sb, delta=1e-9)
        self.assertAlmostEqual(Hi, Hb, delta=1e-9)

    def test_rear_loss_signature_positive_and_growing_under_load(self):
        for stack in ("H1", "H2", "H3"):
            p = nominal(stack)
            H, S = steady_state(p, 5.0, 0.1)
            sig = detectability.rear_loss_signature(p, H, S, 5.0, 0.1, 120)
            values = [d for _, d in sig]
            self.assertTrue(all(b >= a for a, b in zip(values, values[1:])))
            self.assertGreater(values[60], 1.0)
            self.assertGreater(p.gr * (H - p.reservoir), 4.0)

    def test_design_box_membership(self):
        self.assertTrue(in_design_box(NOMINAL_PROPERTIES))
        self.assertTrue(in_design_box(HOT_CORNER) and in_design_box(COLD_CORNER))
        self.assertFalse(in_design_box({**NOMINAL_PROPERTIES, "r_rej": 10.0}))

    def test_time_constants_hand_values(self):
        # hand-derived from the 2x2 eigenproblem (README B.1); tolerance covers rounding
        for stack, tau_slow, tau_fast, tau_blocked in (("H1", 63.4, 1.9, 463.0),
                                                       ("H2", 94.4, 4.6, 670.0),
                                                       ("H3", 169.1, 9.5, 1100.0)):
            p = nominal(stack)
            ts, tf = detectability.time_constants(p)
            with self.subTest(stack=stack):
                self.assertAlmostEqual(ts, tau_slow, delta=1.5)
                self.assertAlmostEqual(tf, tau_fast, delta=0.3)
                self.assertAlmostEqual(detectability.time_constants(blocked(p))[0], tau_blocked,
                                       delta=0.03 * tau_blocked)
        self.assertEqual(detectability.time_constants(replace(nominal("H1"), gr=0.0, ga=0.0))[0],
                         float("inf"))


class Derivation(unittest.TestCase):
    def test_periodic_signature_orders_stacks_and_h3_base_schedule_is_small(self):
        sig = {s: detectability.periodic_probe_signature(nominal(s), 5.0, 0.1, 3.0, 60, 150, 5)
               for s in ("H1", "H2", "H3")}
        self.assertLess(sig["H1"], sig["H2"])          # all negative: H1 largest magnitude
        self.assertLess(sig["H2"], sig["H3"])
        self.assertGreaterEqual(abs(sig["H1"]), 1.0)
        self.assertGreaterEqual(abs(sig["H2"]), 1.0)
        self.assertGreater(abs(sig["H3"]), 0.6)       # above the floor ...
        self.assertLess(abs(sig["H3"]), 1.0)          # ... but below the margin target (D2)
        # executed wave-10 probe statistics in the periodic regime (H1/H2 freeze runs, t = 720)
        self.assertAlmostEqual(sig["H1"], -2.425, delta=0.03)
        self.assertAlmostEqual(sig["H2"], -1.576, delta=0.03)

    def test_derived_configs(self):
        base = SupervisorConfig()
        for s in ("H1", "H2"):
            cfg, info = derive_config(nominal(s), base)
            with self.subTest(stack=s):
                self.assertEqual((cfg.probe_duration, cfg.probe_period, cfg.watchdog_powered_s), (60, 150, 360))
                self.assertTrue(info["derivation_ok"])
                self.assertEqual(cfg, base)
        cfg3, info3 = derive_config(nominal("H3"), base)
        self.assertEqual(cfg3.probe_duration, 90)
        self.assertIn(cfg3.probe_period, (180, 210, 240))
        self.assertEqual(cfg3.watchdog_powered_s, 2 * cfg3.probe_period + cfg3.probe_duration)
        self.assertGreaterEqual(abs(info3["periodic_signature_K"]), info3["signature_target_K"])
        self.assertTrue(info3["derivation_ok"])
        self.assertGreater(info3["tau_slow_s"], 150.0)
        # overrides win and are not derived
        cfg_o, _ = derive_config(nominal("H1"), base, dict(probe_period=240))
        self.assertEqual((cfg_o.probe_period, cfg_o.watchdog_powered_s), (240, 540))
        cfg_o2, _ = derive_config(nominal("H1"), base, dict(probe_period=240, watchdog_powered_s=360))
        self.assertEqual(cfg_o2.watchdog_powered_s, 360)
        cfg_o3, _ = derive_config(nominal("H3"), base, dict(probe_enabled=False, watchdog_enabled=False))
        self.assertFalse(cfg_o3.probe_enabled)


class StateMachine(unittest.TestCase):
    def test_latches_and_never_restarts(self):
        sup = Supervisor(nominal("H1"))
        self.assertEqual(sup.update(0, 25.0, None, 5.0), 5.0)
        self.assertEqual(sup.state, RUN)
        self.assertEqual(sup.update(1, 80.0, None, 5.0), 0.0)
        self.assertEqual(sup.state, TRIP_LIMIT)
        for t in range(2, 50):
            self.assertEqual(sup.update(t, 25.0, None, 5.0), 0.0)
            self.assertEqual(sup.state, TRIP_LIMIT)
        self.assertEqual(sup.trip_time, 1)

    def test_dropout_implausible_and_second_sensor_limit(self):
        sup = Supervisor(nominal("H1"))
        sup.update(0, 25.0, None, 5.0)
        for t in (1, 2):
            sup.update(t, None, None, 5.0)
            self.assertEqual(sup.state, RUN)
        sup.update(3, None, None, 5.0)
        self.assertEqual(sup.state, TRIP_SENSOR)
        sup = Supervisor(nominal("H1"))
        sup.update(0, 25.0, None, 5.0)
        sup.update(1, -50.0, None, 5.0)
        self.assertEqual(sup.state, TRIP_SENSOR)
        sup = Supervisor(nominal("H1"), SupervisorConfig(dual_sensor=True))
        sup.update(0, 25.0, 25.0, 5.0)
        sup.update(1, 25.0, 50.0, 5.0)
        self.assertEqual(sup.state, TRIP_LIMIT)
        sup = Supervisor(nominal("H1"))
        for t in range(3):
            sup.update(t, None, None, 5.0)
        self.assertEqual(sup.state, TRIP_SENSOR)

    def test_disagreement_guard(self):
        sup = Supervisor(nominal("H1"), SupervisorConfig(dual_sensor=True))
        sup.update(0, 25.0, 25.0, 5.0)
        for t in (1, 2):
            sup.update(t, 25.0, 27.0, 5.0)
            self.assertEqual(sup.state, RUN)
        sup.update(3, 25.0, 27.0, 5.0)
        self.assertEqual(sup.state, TRIP_SENSOR)
        self.assertIn("disagreement", sup.trip_cause)

    def test_liveness_watchdog(self):
        cfg = SupervisorConfig(probe_enabled=False, watchdog_enabled=True, watchdog_powered_s=20)
        sup = Supervisor(nominal("H1"), cfg)
        y = 25.0
        for t in range(40):
            sup.update(t, y, None, 5.0)
            if sup.state != RUN:
                break
            y = sup.Shat  # perfect agreement with the model; window too short for movement evidence
        self.assertEqual(sup.state, TRIP_SENSOR)
        self.assertEqual(sup.trip_time, 21)
        self.assertIn("watchdog", sup.trip_cause)

    def test_transient_is_liveness_evidence_but_stuck_channel_is_not(self):
        # R4: a healthy channel tracking the heating transient refreshes the watchdog without any
        # probe; a channel stuck at its initial value never does (it is tripped by the level test).
        cfg = SupervisorConfig(probe_enabled=False, watchdog_enabled=False)
        sup = Supervisor(nominal("H3"), cfg)
        y = 25.0
        for t in range(251):
            sup.update(t, y, None, 5.0)
            y = sup.Shat
        self.assertEqual(sup.state, RUN)
        self.assertGreater(sup.live_windows, 50)
        self.assertLessEqual(sup.powered_since_evidence, 5)
        sup = Supervisor(nominal("H3"), cfg)
        for t in range(251):
            sup.update(t, 25.0, None, 5.0)
            if sup.state != RUN:
                break
        self.assertEqual(sup.state, TRIP_MODEL)
        self.assertEqual(sup.live_windows, 0)

    def test_config_validation(self):
        with self.assertRaises(ValueError):
            SupervisorConfig(probe_period=30, probe_duration=60)
        with self.assertRaises(ValueError):
            SupervisorConfig(tau_rel_probe=1.0)
        with self.assertRaises(ValueError):
            SupervisorConfig(watchdog_powered_s=100)          # < probe_period + probe_duration
        SupervisorConfig(watchdog_powered_s=100, probe_enabled=False)   # allowed without probes


class ClosedLoop(unittest.TestCase):
    def test_intact_ideal_zero_residual_and_probe_cost(self):
        # T2 fix: informativeness is a property of the predicted net window change; the first
        # probe(s) during the heating transient may be uninformative. Assert what the design
        # guarantees: every scheduled probe is executed and evaluated, the energy cost follows
        # the derived schedule, probes ending in the quasi-steady regime are informative and
        # pass, the residual is zero, and the heating transient supplies liveness evidence.
        for stack in ("H1", "H2", "H3"):
            r, sup = run_scenario_detailed(MATRIX[stack + "_sup1_intact_ideal"])
            c = sup.cfg
            starts = [t for t in range(c.probe_first, 900, c.probe_period)]
            withheld = sum(c.probe_depth * max(0, min(s + c.probe_duration, 900) - s) for s in starts)
            with self.subTest(stack=stack):
                self.assertEqual(r["final_state"], RUN)
                self.assertEqual(r["probes_ok"] + r["probes_uninformative"], len(starts))
                self.assertEqual([e[0] for e in r["probe_log"]], [s + c.probe_duration for s in starts])
                late = [e for e in r["probe_log"] if e[0] >= 500]
                self.assertTrue(late)
                self.assertTrue(all(e[3] == "ok" for e in late), r["probe_log"])
                self.assertGreaterEqual(r["probes_ok"], len(starts) - 2)
                self.assertAlmostEqual(r["energy_applied_J"], 4500.0 - withheld, delta=1e-6)
                self.assertGreater(r["live_windows"], 0)
                residual = max(abs(h[1] - h[3]) for h in sup.history if h[1] is not None and h[3] is not None)
                self.assertLess(residual, 1e-9)

    def test_no_false_alarm_inside_design_box(self):
        for stack in ("H1", "H2", "H3"):
            for short in ("sup1_intact_noise", "sup1_hotcorner_noise", "sup1_coldcorner_noise", "sup2_intact_noise"):
                r = run(stack + "_" + short)
                with self.subTest(run=r["name"]):
                    self.assertEqual(r["final_state"], RUN, r["trip_cause"])
                    self.assertFalse(r["false_alarm"])

    def test_f4_naive_counterexample(self):
        for stack in ("H1", "H2", "H3"):
            frozen = run(stack + "_naive45_frozen600_rearloss600")
            truthful = run(stack + "_naive45_truthful_rearloss600")
            with self.subTest(stack=stack):
                self.assertFalse(frozen["tripped"])
                self.assertAlmostEqual(frozen["peak_H"], f1_peak(stack), delta=1e-9)
                self.assertTrue(truthful["tripped"])
                self.assertLess(truthful["trip_time"], 900)
                self.assertLess(truthful["peak_H"], frozen["peak_H"])

    def test_single_sensor_without_excitation_must_fail(self):
        base = MATRIX["H1_sup1_noprobe_freeze600_rearloss600_ideal"]
        for stack, bound in (("H1", 0.01), ("H2", 0.1), ("H3", 0.3)):
            sc = replace(base, stack=stack, name=stack + "_noprobe_counterexample")
            r, sup = run_scenario_detailed(sc)
            with self.subTest(stack=stack):
                self.assertTrue(r["trip_time"] is None or r["trip_time"] >= 900)
                self.assertAlmostEqual(r["peak_H"], f1_peak(stack), delta=1e-6)
                gap = max(abs(h[1] - h[3]) for h in sup.history if 600 <= h[0] < 900)
                self.assertLess(gap, bound)          # reported history indistinguishable from healthy
                self.assertGreater(r["state_at_trip"]["true_S"] if r["state_at_trip"] else r["peak_S"], 45.0)

    def test_rear_loss_with_live_sensor_detected(self):
        for stack in ("H1", "H2", "H3"):
            r = run(stack + "_sup1_rearloss600_noise")
            with self.subTest(stack=stack):
                self.assertEqual(r["final_state"], TRIP_MODEL, r["trip_cause"])
                self.assertLessEqual(r["trip_time"], 660)
                self.assertLess(r["peak_H"], 45.0)
                self.assertLess(r["peak_H"], f1_peak(stack) - 5.0)
            r = run(stack + "_sup1_rearloss100_noise")
            with self.subTest(stack=stack, early=True):
                self.assertTrue(r["tripped"])
                self.assertLessEqual(r["trip_time"], 250)
                self.assertLess(r["peak_H"], 45.0)

    def test_freeze_detected_with_bounded_latency_by_probe_scheme(self):
        for stack in ("H1", "H2", "H3"):
            r = run(stack + "_sup1_freeze600_rearloss600_noise")
            with self.subTest(stack=stack):
                self.assertTrue(r["tripped"])
                self.assertLessEqual(r["trip_time"], freeze_bound(r))
                self.assertLess(r["peak_H"], f1_peak(stack) - 5.0)
                st = r["state_at_trip"]
                self.assertGreater(st["true_S"] - st["reported_y1"], 1.0)   # observability gap at trip
            r = run(stack + "_sup1_freeze600_only_noise")
            with self.subTest(stack=stack, hazard=False):
                self.assertEqual(r["final_state"], TRIP_SENSOR, r["trip_cause"])
                self.assertLessEqual(r["trip_time"], freeze_bound(r))
                self.assertLess(r["peak_H"], 36.0)

    def test_dual_sensor_detects_freeze_quickly(self):
        for stack in ("H1", "H2", "H3"):
            r = run(stack + "_sup2_freeze600_rearloss600_noise")
            with self.subTest(stack=stack):
                self.assertEqual(r["final_state"], TRIP_SENSOR)
                self.assertLessEqual(r["trip_time"], 700)
                self.assertLess(r["peak_H"], 45.0)
                self.assertEqual(r["energy_withheld_J"] > 0, True)

    def test_bias_step_and_dropout(self):
        for stack in ("H1", "H2", "H3"):
            r = run(stack + "_sup1_biasstep600_rearloss600_noise")
            with self.subTest(stack=stack, fault="bias"):
                self.assertTrue(r["tripped"])
                self.assertLessEqual(r["trip_time"], 620)
            r = run(stack + "_sup1_dropout600_noise")
            with self.subTest(stack=stack, fault="dropout"):
                self.assertEqual(r["final_state"], TRIP_SENSOR)
                self.assertEqual(r["trip_time"], 602)

    def test_stuck_on_actuator_detected_but_not_protected(self):
        for stack in ("H1", "H2", "H3"):
            r = run(stack + "_sup1_stuckon600_rearloss600_noise")
            with self.subTest(stack=stack):
                self.assertTrue(r["tripped"])
                self.assertGreaterEqual(r["trip_time"], 600)      # the trip must follow the fault
                self.assertGreater(r["final_H"], 60.0)   # study comparator only

    def test_idle_rear_loss_latent_then_detected_on_redemand(self):
        for stack in ("H1", "H2", "H3"):
            r = run(stack + "_sup1_idle_rearloss1500_redemand2400_noise")
            with self.subTest(stack=stack):
                self.assertTrue(r["tripped"])
                self.assertGreaterEqual(r["trip_time"], 1500)
                self.assertLessEqual(r["trip_time"], 2600)
                self.assertLess(r["peak_H"], 50.0)

    def test_modelled_actuator_delay_does_not_trip(self):
        # wave-10 receipt: H1 unmodelled 5 s delay tripped at 71. With the delay modelled, the
        # supervisor's p_hist aligns with the actuator's transport delay sample for sample.
        base = MATRIX["H1_sup1_actdelay5_intact_noise"]
        sc = replace(base, name="H1_actdelay5_modelled", supervisor=dict(actuator_delay_model=5))
        r = run_scenario(sc)
        self.assertEqual(r["final_state"], RUN, r["trip_cause"])
        sc0 = replace(base, name="H1_actdelay5_ideal_modelled", sensor1=SensorSpec(),
                      supervisor=dict(actuator_delay_model=5))
        r0, sup0 = run_scenario_detailed(sc0)
        residual = max(abs(h[1] - h[3]) for h in sup0.history if h[1] is not None and h[3] is not None)
        self.assertLess(residual, 1e-9)

    def test_h1_h2_reproduce_wave10_receipts(self):
        # The derived schedule for H1/H2 equals the base schedule and the only behavioural change
        # (evidence source of the watchdog) never fired for them: results must be unchanged.
        for name, (state, trip) in RECEIPTS_H1_H2.items():
            r = run(name)
            with self.subTest(run=name):
                self.assertEqual(r["final_state"], state, r["trip_cause"])
                self.assertEqual(r["trip_time"], trip)
        self.assertAlmostEqual(run("H1_sup1_freeze600_rearloss600_noise")["peak_H"], 40.497, delta=2e-3)
        self.assertAlmostEqual(run("H2_sup1_freeze600_rearloss600_noise")["peak_H"], 38.393, delta=2e-3)
        self.assertAlmostEqual(run("H1_sup1_intact_ideal")["energy_applied_J"], 3420.0, delta=1e-6)

    def test_h3_schedule_in_force_and_no_watchdog_trips_in_matrix(self):
        for name, sc in MATRIX.items():
            if sc.controller != "supervisor":
                continue
            r = run(name)
            with self.subTest(run=name):
                if r["trip_cause"]:
                    self.assertNotIn("watchdog", r["trip_cause"])
                if sc.stack == "H3" and sc.supervisor.get("probe_enabled", True):
                    self.assertEqual(r["supervisor_config"]["probe_duration"], 90)
                    self.assertGreater(r["supervisor_config"]["probe_period"], 150)

    def test_matrix_predeclared_and_deterministic(self):
        runs = scenario_matrix()
        self.assertLessEqual(len(runs), 60)
        self.assertEqual(len({s.name for s in runs}), len(runs))
        a = json.dumps(run_scenario(MATRIX["H1_sup1_rearloss600_noise"]), sort_keys=True)
        b = json.dumps(run_scenario(MATRIX["H1_sup1_rearloss600_noise"]), sort_keys=True)
        self.assertEqual(a, b)

    def test_detectability_summary(self):
        for stack in ("H1", "H2", "H3"):
            cfg, _ = derive_config(nominal(stack), SupervisorConfig())
            d = detectability.summary_for_stack(stack, cfg)
            self.assertTrue(d["probe_informative"] and d["frozen_channel_detected_by_probe"])
            self.assertIsNotNone(d["increment_detection_time_estimate_s"])
            self.assertLess(d["idle_rear_flux_W"], 0.1)
            self.assertGreater(d["idle_S_blocked"], d["idle_S_intact"])
            self.assertGreaterEqual(abs(d["periodic_probe_signature_K"]), 1.0)
            self.assertGreater(d["tau_slow_blocked_s"], d["tau_slow_s"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
```

---

## Notes for Red's execution and review

1. **Nothing in fix-003 has been executed.** Run inside `thermal_supervisor/`: `python -m unittest -v` and `python run_matrix.py --out results.json` (plant.py unchanged from wave 10). Please return the full test receipt, the matrix stdout, and the `derived_configs` block (it tells us whether H3 resolved to period 180 or 210 — see README §B.3; both satisfy the tests).
2. Highest-risk assertions (predeclared): `test_derived_configs` H3 period ∈ {180,210,240} (if the discrete signature of (90,180) lands exactly near 1.00 the search may step to 210 — allowed); `test_rear_loss_with_live_sensor_detected` H3 ≤ 660 (estimate 620–635; a probe active at 600 under period 180 weakens the signature slightly) and the early case ≤ 250; `test_intact_ideal...` requires every probe ending ≥ 500 s to be "ok" for H3 (estimate −0.86 … −1.1 K, floor 0.6); `test_transient_is_liveness_evidence...` thresholds (live_windows > 50, counter ≤ 5 at t = 250) are estimates from the H3 heating transient. If any fails, send the actual values; do not loosen thresholds silently.
3. `test_h1_h2_reproduce_wave10_receipts` is a true regression anchor: H1/H2 must be bit-identical to the wave-10 run because their derived schedule equals the base and the watchdog never fired for them. A difference there means an unintended behavioural change in fix-003.
4. Unimplemented/open items are listed in README §F; the adaptive-depth probe and a trip-capable movement check were considered and deliberately excluded (minimal diff; correlated-window false-alarm exposure).