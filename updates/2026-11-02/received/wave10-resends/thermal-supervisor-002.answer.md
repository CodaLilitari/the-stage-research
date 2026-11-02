# Thermal supervisor study — deliverable (Red / Claude, for The Stage)

Credits: plant algebra and all executed reference numbers are Coda's (Codex Lily) `rc_transient.py` / REPORT.md; the steady rational references are Coda's `validation/thermal` work. The supervisory layer, detectability analysis, harness, scenario matrix and tests below are Red's new, **unexecuted** contribution. Nothing below has been run; Red will execute in the sandbox and return results for correction. All temperatures are model outputs of T0‑LUMP2‑1; 40/45/60 °C are study comparators only.

Static-reasoning note: every numeric estimate in the README (detection delays, margins, energy costs) is a hand estimate from the linear model and is labelled `estimate`; the harness prints the actual model values.

---

FILE: thermal_supervisor/README.md
```markdown
# Failure-aware supervisory thermal protection on the T0-LUMP2-1 two-node plant

Red (Claude, Anthropic) continuing The Stage with Andrei; plant = Coda's executed
`rc_transient.py` (Codex Lily). Model study only: not empirical validation, not a safety
certification, not a hardware design recommendation, no biological content. 45 C trip,
40 C surface and 60 C internal are arbitrary study comparators.

Status: WRITTEN, NOT EXECUTED by Red. Red has no execution tools; Red (the coordinator)
runs `python -m unittest -v` and `python run_matrix.py --out results.json` inside
`thermal_supervisor/` and returns results. Expectations below are predeclared estimates.

## 0. Files

| file | content |
|---|---|
| plant.py | two-node backward-Euler plant; algebra copied from Coda's rc_transient.py so the controller can sit inside the time loop; exact steady state |
| detectability.py | rear-loss signature, step/probe responses, Gaussian false-alarm bounds, per-stack detectability summary |
| supervisor.py | the formal state machine, residual detectors, probe excitation, dual-sensor option, latching; plus `NaiveTrip` (F4) and `OpenLoop` |
| harness.py | deterministic closed loop: sensors (noise/bias/freeze/bias-step/dropout), actuator (delay/stuck-on), rear-loss injection, predeclared matrix (60 runs), JSON report |
| run_matrix.py | CLI; writes JSON only to `--out` |
| test_supervisor.py | unittest suite incl. counterexamples; cross-checks Coda's executed table |

Run from inside `thermal_supervisor/` (modules are flat, no package). Optional:
`RC_TRANSIENT_PATH=/path/to/rc_transient.py` enables a bit-level cross-check test.

## 1. Signals the supervisor may use (observability contract)

Allowed: `y1[k]` reported primary temperature at integer seconds (may be None),
optionally `y2[k]` an assumed independent second channel, the supervisor's own commanded
body power history, elapsed time, the mission demand. Hidden: true S, H, surface, applied
power, conductances, fault flags. Sensor self-heat J = 0.1 W is assumed known and
uncontrollable (it is the sensor's own dissipation per the T0-HYP-1 contract).

Second-sensor cost (stated, qualitative): a second channel (element, wiring, conditioning,
power, data) with an *independent* failure mechanism; common-mode faults (shared supply,
shared ADC, same adhesive failure) defeat it; with two channels and no third there is no
voting, so any disagreement > tau_pair forces a trip (availability loss on single-channel
drift); in this lumped model both channels see the same node S, so no spatial coverage is
implied. In the matrix the dual configuration runs with probes OFF, so its energy cost is
zero and the comparison with the single-sensor probe scheme is clean.

## 2. Formal state machine

States Q = {INIT, RUN, TRIP_LIMIT, TRIP_SENSOR, TRIP_MODEL}. TRIP_* are absorbing (latched);
there is no reset input and no automatic restart. Output: P_cmd. In INIT and all TRIP_* states
P_cmd = 0.

Per sample k (time t = k s), guards are evaluated in priority order LIMIT > SENSOR > MODEL;
any true guard moves to the corresponding trip state at this sample and P_cmd(k) = 0.

| from | guard | to |
|---|---|---|
| INIT | valid(y1) | RUN (model initialised Hhat = Shat = y1; assumes plant at rest) |
| INIT | consecutive invalid y1 >= n_dropout (3) | TRIP_SENSOR |
| RUN | (valid(y1) and y1 >= T_trip) or (dual and valid(y2) and y2 >= T_trip), T_trip = 45 C comparator | TRIP_LIMIT |
| RUN | consecutive invalid y1 >= n_dropout; or y1 outside [-20, 150] C; or |y1[k]-y1[k-1]| > 8 K/s | TRIP_SENSOR |
| RUN | dual: consecutive invalid y2 >= n_dropout; or |y1-y2| > tau_pair (0.8 K) for m_pair (3) consecutive samples | TRIP_SENSOR |
| RUN | probe check fails: an informative probe (|dYhat| >= 0.6 K) ends and |dY - dYhat| > 0.2 + 0.6|dYhat| | TRIP_SENSOR |
| RUN | liveness watchdog: more than 360 powered seconds since the last passed informative probe | TRIP_SENSOR |
| RUN | level residual |y1 - Shat| > 0.8 + 0.4|Shat - T_amb| for m_level (3) consecutive samples | TRIP_MODEL |
| RUN | increment residual |dY_W - dYhat_W| > 0.3 + 0.5|dYhat_W| for m_inc (3) consecutive samples, W = 10 s, 5-sample means | TRIP_MODEL |
| TRIP_* | true | same (absorbing) |

RUN output law: P_cmd = min(demand, P_max); while a probe is active, P_cmd = max(0, demand -
probe_depth). Probes start at t = 60 + n*150 s if demand > 0, last 60 s, depth 3 W (defaults;
all configurable). The supervisor's internal model is Coda's nominal stack driven by its own
P_cmd (optionally delayed by a known actuator delay) and J = 0.1 W, one backward-Euler step
per sample, identical algebra to the plant. Shat is the predicted reported temperature.

## 3. Residual-based detection, assumptions and analysis

Assumed ranges (A1-A7, all labelled assumptions):
A1 noise: iid Gaussian, sigma <= 0.1 K per 1 s sample; A2 constant bias |b| <= 0.2 K per
channel; A3 ambient and reservoir exactly 25 C (real ambient drift is unmodeled and would be
a false-alarm source); A4 design box the supervisor tolerates without tripping:
k_sil [0.22,0.32], k_film [0.16,0.24], r_c [1e-4,4e-4] m2K/W, h [6,10], R_rej [1.6,2.5] K/W,
C_H [15,25] J/K, cp_sil [1200,1800]. The contract's sensitivity ranges are wider; a plant
outside the box (e.g. R_rej = 10 K/W, internal node ~54 C at 5 W) is *expected* to trip and
is not counted as a false alarm. A5 exact 1 s sampling, supervisor acts at the sample instant;
A6 ideal actuator unless injected; A7 plant at rest at ambient at t = 0.

### 3.1 Rear-path loss (proved detectable iff the rear path carries heat)
Let (H_i,S_i) be the intact trajectory and (H_b,S_b) the trajectory with gr -> 0 at t_f from
the same state under identical inputs; e = (h,s) = (H_b-H_i, S_b-S_i) obeys
  C_H h' = -g(h-s) + q_r(t),   C_S s' = g(h-s) - ga s,   e(t_f) = 0,
with q_r(t) = gr (H_i(t) - T_res) the rear flux the intact plant would export. The matrix is
Metzler and Hurwitz (ga > 0), so (i) q_r == 0 on [t_f,T] implies e == 0: the fault is
unobservable from ANY signal, not only from y (idle plant at ambient with J = 0: latent
fault); (ii) q_r >= q_min > 0 implies s(t) >= q_min * k_S(t - t_f), k_S the nonnegative
increasing unit-step response of S to power at H in the blocked network (comparison principle
for positive systems). The residual therefore exceeds any threshold tau in finite time once
q_min k_S exceeds tau plus the model-error bound. With J = 0.1 W the idle signature is
only ~1 K with a time constant of several hundred seconds (weak). `detectability.py` prints
the noise-free increment and level detection-time estimates per stack (estimate: 10-30 s
after loss at 5 W steady state, increment test; H3 slowest).

### 3.2 Sensor freeze (disproved detectable without excitation; proved detectable with it)
Indistinguishability: take two situations with the same causal controller K: (A) healthy
sensor, plant in steady state under constant P; (B) sensor frozen at c = y(t_f) at t_f plus
rear loss at t_f. In (B) y_k = c for k >= k_f; in (A) y_k = S_i(t_k) + nu_k with
|S_i(t_k) - c| <= eps (eps -> 0 near steady state). Any K whose output is unchanged by input
perturbations of size eps (every controller with a nonzero noise tolerance) emits the same
P in (A) and (B), so (B)'s true plant follows the open-loop F1 trajectory. Verified by two
counterexample runs: F4-frozen naive trip and the no-probe supervisor variant (residual
stays within ~0.01 K for H1, < 0.3 K for H3 while the true S climbs ~26 K).
Remedies: (a) excitation: if a commanded power change produces |dYhat| over the probe window
with |dYhat| > tau_abs_p / (1 - tau_rel_p) = 0.5 K (and >= 0.6 K informative floor), a
noise-free frozen channel gives dY = 0 and the probe check fires deterministically at probe
end; worst-case latency = probe_period + probe_duration (+5 s window) = 215 s while powered.
A frozen channel that still carries ADC noise is detected per probe with margin
(|dYhat| - threshold)/(sigma sqrt(2/5)); estimate >= 2.5 sigma for H3 with the defaults, so
a miss is caught at the next probe with high probability. If probes are uninformative
(demand < depth), the watchdog trips after 360 powered seconds. (b) a second channel:
disagreement appears as soon as the true temperature moves (rear loss: estimate 10-40 s).

### 3.3 Bias, drift, dropout, actuator
Constant bias at start is absorbed by initialisation (the trip comparator shifts by b).
A bias step |db| > 0.3 K is caught by the increment test; slow drift inside the level band
is not: the blind band at 5 W steady state is 0.8 + 0.4*8.7 ~ 4.3 K, so the effective
comparator is T_trip +/- 4.3 K. Dropout: <= n_dropout samples. Actuator delay unmodeled by the
supervisor shows up as residual; estimate: a 5 s delay stays inside thresholds (reported, not
asserted). Actuator stuck-on: detected (residual after the command drops) but NOT protectable
with body power as the only actuator.

### 3.4 False alarms
Deterministic part: bounded by the design box; demonstrated only at two corners (HOT: low k,
high r_c, low h, high R_rej, low capacities; COLD: the opposite) per stack. Two corners of a
7-dimensional box are a check, not a proof (transient responses are not monotone in every
parameter). Hand estimates: HOT steady residual ~2.3 K vs threshold ~4.3 K; worst transient
margin ~1 K around t = 30-60 s for H1.
Stochastic part (noise only, deterministic residual assumed zero, union bound):
level test per-sample exceedance 2Phi(-(0.8-0.2)/0.1) = 2Phi(-6) ~ 2e-9, persistence 3 ->
negligible; increment test: sd of difference of two 5-sample means = 0.1*sqrt(2/5) = 0.063 K,
threshold 0.3 K = 4.7 sd -> 2.6e-6 per sample; the 3-sample persistence power is optimistic
for overlapping windows (labelled approximate). `run_matrix.py` prints these numbers.

## 4. Predeclared scenario matrix (60 runs) and expectations
Per stack H1/H2/H3 (19 each): ol_intact (F0 ref), ol_rearloss600 (F1 ref, must reproduce
Coda's table), naive45_truthful_rearloss600, naive45_frozen600_rearloss600 (counterexample:
never trips, equals F1), sup1_intact_ideal (zero residual, probe energy cost 1080 J of 4500 J
before 900 s), sup1_intact_noise, sup1_hotcorner_noise, sup1_coldcorner_noise (no trip),
sup1_rearloss600_noise (TRIP_MODEL <= 660 s, peak H < 45), sup1_rearloss100_noise,
sup1_freeze600_rearloss600_noise (trip <= 830 s, peak below F1 by >= 5 K),
sup1_freeze600_only_noise (sensor trip, no hazard), sup1_biasstep600_rearloss600_noise
(trip <= 620), sup1_dropout600_noise (TRIP_SENSOR at 602), sup1_actdelay5_intact_noise
(report only), sup1_stuckon600_rearloss600_noise (detected, unprotected, final H > 60),
sup2_freeze600_rearloss600_noise (TRIP_SENSOR <= 700, peak H < 45), sup2_intact_noise
(no trip), sup1_idle_rearloss1500_redemand2400_noise (latent; trip <= 2600, peak H < 50).
H1 extras: probe period 240 variant, out-of-box R_rej = 10 (expected trip, not a false alarm),
no-probe no-watchdog variant with freeze+rear loss (counterexample).
Noise seeds: crc32 of the scenario name (deterministic). All runs: 3600 s horizon, demand
5 W until 900 s then 0 (plus a second 5 W block 2400-3300 s in the idle case), J = 0.1 W.

## 5. What the scheme can and cannot guarantee (model scale only)
CAN (under A1-A7, in T0-LUMP2-1): G1 any trip latches P_cmd = 0 for the rest of the horizon;
G2 rear-path loss while the rear path carries >= q_min W with a live sensor is detected
within a finite, computable delay (table from execution), so the body energy delivered after
the fault is <= P_max * delay; G3 a stuck primary channel during powered operation is
detected within probe_period + probe_duration + 5 s (deterministic for a noise-free stuck
value), or within 360 powered seconds if probes are uninformative; G4 dropout within 3
samples, implausible values within 1 sample; G5 with a second channel, disagreement beyond
0.8 K for 3 samples trips.
CANNOT: C1 detect a rear loss while no heat crosses the rear path (latent until the next
power-on, which then acts as the self-test); C2 distinguish rear degradation from loss or
tolerate plants outside the design box (availability cost); C3 protect against actuator
stuck-on (detect only); C4 see bias/drift inside the ~4.3 K level band (comparator shifts);
C5 handle common-mode faults (both channels frozen, ambient drift) except via probes;
C6 say anything about a real panel: single lumped node, no hot spots, no contact physics,
no real sensor behaviour; detection is not protection - the post-trip peak depends on stored
energy and the blocked front path (sensor power 0.1 W continues).

## 6. Not implemented / left open
No ambient disturbance or quantisation model; no observer-based reconstruction of H (open-loop
model prediction only); no full design-box sweep (two corners only); no adaptive thresholds;
no reset/arming logic (by requirement); second-sensor hardware cost is qualitative; no
inter-sample (continuous-time) analysis; no spatial model.
```

FILE: thermal_supervisor/plant.py
```python
"""Two-node plant for the supervisory study.

Algebra reproduced from Coda's executed rc_transient.py (T0-LUMP2-1, Codex Lily) so that a
controller can be placed inside the time loop; this file is not a replacement for Coda's
module and test_supervisor.py cross-checks against it when RC_TRANSIENT_PATH is set.
  C_H H' = P - g (H - S) - gr (H - T_res)
  C_S S' = J + g (H - S) - ga (S - T_amb)
  surface = T_amb + Rconv * ga * (S - T_amb)   (quasi-steady algebraic reconstruction)
Model study only; no physical validation is implied.
"""
from dataclasses import dataclass, replace
import math

AREA_M2 = 0.01
FILM_THICKNESS_M = 0.00005
SILICONE_DENSITY = 1030.0
FILM_DENSITY = 1420.0
FILM_CP = 1090.0
THICKNESS_M = {"H1": 0.0005, "H2": 0.001, "H3": 0.002}
P_MAX_W = 10.0
J_MAX_W = 0.2
NOMINAL_PROPERTIES = dict(k_sil=0.27, k_film=0.20, r_c=0.0002, h=8.0, r_rej=2.0, c_h=20.0, cp_sil=1500.0)


def _finite(value, name):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(name + " must be a finite non-Boolean number")
    return float(value)


@dataclass(frozen=True)
class Params:
    ch: float
    cs: float
    g: float
    ga: float
    gr: float
    ambient: float
    reservoir: float
    rconv: float

    def __post_init__(self):
        for name in ("ch", "cs", "g", "ga", "gr", "ambient", "reservoir", "rconv"):
            object.__setattr__(self, name, _finite(getattr(self, name), name))
        if self.ch <= 0 or self.cs <= 0:
            raise ValueError("Capacities must be positive")
        if min(self.g, self.ga, self.gr, self.rconv) < 0:
            raise ValueError("Negative passive parameter")


def build(stack, k_sil=0.27, k_film=0.20, r_c=0.0002, h=8.0, r_rej=2.0, c_h=20.0, cp_sil=1500.0,
          ambient=25.0, reservoir=25.0):
    """Stack parameters; with defaults this is bit-for-bit Coda's nominal()."""
    if stack not in THICKNESS_M:
        raise ValueError("Unknown reference stack")
    thick = THICKNESS_M[stack]
    area = AREA_M2
    a = thick / (k_sil * area) + FILM_THICKNESS_M / (2 * k_film * area) + r_c / area
    c = 1 / (h * area)
    cs = SILICONE_DENSITY * area * (2 * thick) * cp_sil + FILM_DENSITY * area * FILM_THICKNESS_M * FILM_CP
    gr = 0.0 if r_rej == math.inf else 1 / r_rej
    return Params(ch=c_h, cs=cs, g=1 / a, ga=1 / (a + c), gr=gr, ambient=ambient, reservoir=reservoir, rconv=c)


def nominal(stack):
    return build(stack)


def step(p, H, S, P, J, dt):
    """One backward-Euler step; same algebra as rc_transient.simulate (Coda)."""
    A = p.ch / dt + p.gr
    B = p.cs / dt + p.ga
    determinant = A * B + p.g * (A + B)
    bh = p.ch * H / dt + P + p.gr * p.reservoir
    bs = p.cs * S / dt + J + p.ga * p.ambient
    new_H = (bh * (B + p.g) + p.g * bs) / determinant
    new_S = (bs * (A + p.g) + p.g * bh) / determinant
    if not (math.isfinite(new_H) and math.isfinite(new_S)):
        raise ValueError("Nonfinite numerical state")
    return new_H, new_S


def surface(p, S):
    front = p.ga * (S - p.ambient)
    return p.ambient + p.rconv * front


def steady_state(p, P, J):
    """Exact linear steady state (H, S); raises if both exits are blocked."""
    a11 = p.g + p.gr
    a12 = -p.g
    a21 = -p.g
    a22 = p.g + p.ga
    b1 = P + p.gr * p.reservoir
    b2 = J + p.ga * p.ambient
    det = a11 * a22 - a12 * a21
    if det <= 0:
        raise ValueError("No finite steady state: both environmental exits blocked")
    return (b1 * a22 - a12 * b2) / det, (a11 * b2 - a21 * b1) / det


def blocked(p, fraction=0.0):
    return replace(p, gr=p.gr * fraction)
```

FILE: thermal_supervisor/detectability.py
```python
"""Static detectability helpers (model computations, no empirical content)."""
from dataclasses import replace
import math

from plant import nominal, step, steady_state, blocked


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
    return dict(stack=stack, steady_H_5W=H, steady_S_5W=S, rear_flux_W=q_rear,
                increment_detection_time_estimate_s=t_inc, level_detection_time_estimate_s=t_lvl,
                level_threshold_K=level_threshold, probe_predicted_dS_K=probe,
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
"""
from collections import deque
from dataclasses import dataclass
import math

from plant import step

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
    watchdog_powered_s: int = 360
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
        # ---- probe completion check ----
        if (self.state == RUN and self.active_probe_start is not None
                and t == self.active_probe_start + c.probe_duration):
            self._evaluate_probe(t)
            self.active_probe_start = None
        # ---- liveness watchdog ----
        if self.state == RUN and c.watchdog_enabled and self.powered_since_evidence > c.watchdog_powered_s:
            self._trip(TRIP_SENSOR, t, "liveness watchdog: no informative probe within %d powered s"
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
"""
from dataclasses import dataclass, field, asdict, replace
import math
import random
import zlib

from plant import (Params, build, nominal, step, surface, steady_state, blocked,
                   NOMINAL_PROPERTIES, P_MAX_W)
from supervisor import Supervisor, SupervisorConfig, NaiveTrip, OpenLoop, TRIPPED
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
    supervisor: dict = field(default_factory=dict)   # SupervisorConfig overrides
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


def make_controller(sc):
    if sc.controller == "open_loop":
        return OpenLoop()
    if sc.controller == "naive":
        return NaiveTrip(45.0)
    if sc.controller == "supervisor":
        return Supervisor(nominal(sc.stack), SupervisorConfig(**sc.supervisor))
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
        false_alarm=bool(tripped and not faults and box),
        comparator_crossings={k: (v if v is not None else "not_crossed_in_horizon") for k, v in cross.items()},
        comparator_label="study_comparator_only",
        trace_60s=trace, model="T0-LUMP2-1 (Coda) + Red supervisor", physical_validation=False)
    return result, controller


def run_scenario(sc):
    return run_scenario_detailed(sc)[0]


def scenario_matrix():
    """Predeclared, deterministic, <= 60 runs."""
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
            expected="RUN to horizon; 6 probes ok; residual ~0")
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
            purpose="F3 with probe scheme", expected="trip by 830 s via probe/increment; peak below F1")
        n = stack + "_sup1_freeze600_only_noise"
        add("sup1_freeze600_only_noise", sensor1=noisy(n, freeze_time=600),
            purpose="freeze without hazard (availability cost)", expected="TRIP_SENSOR by 830 s")
        n = stack + "_sup1_biasstep600_rearloss600_noise"
        add("sup1_biasstep600_rearloss600_noise", rear_loss_time=600,
            sensor1=noisy(n, bias_step_time=600, bias_step=-5.0),
            purpose="sensor reads 5 K low from 600 s", expected="trip within 20 s")
        n = stack + "_sup1_dropout600_noise"
        add("sup1_dropout600_noise", sensor1=noisy(n, dropout_start=600, dropout_end=615),
            purpose="15 s dropout", expected="TRIP_SENSOR at 602")
        n = stack + "_sup1_actdelay5_intact_noise"
        add("sup1_actdelay5_intact_noise", actuator=ActuatorSpec(delay=5), sensor1=noisy(n),
            purpose="unmodelled 5 s actuator delay", expected="report; estimate no trip")
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
            sensor1=noisy(n), purpose="latent rear loss during idle, revealed by re-demand",
            expected="weak or no detection before 2400; trip within 200 s after 2400; peak H < 50")
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
    return dict(model="T0-LUMP2-1 (Coda, Codex Lily) plant; supervisor by Red (Claude, Anthropic)",
                physical_validation=False, comparators="40/45/60 C study_comparator_only",
                supervisor_defaults=asdict(cfg), design_box=DESIGN_BOX, contract_ranges=CONTRACT_RANGES,
                noise_false_alarm_bounds=noise,
                detectability=[detectability.summary_for_stack(s, cfg) for s in ("H1", "H2", "H3")],
                results=results)
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
counterexamples where any controller using only the reported sensor must fail."""
import importlib.util
import json
import os
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from plant import nominal, build, step, surface, steady_state, blocked, Params  # noqa: E402
from supervisor import (Supervisor, SupervisorConfig, RUN, TRIP_LIMIT, TRIP_SENSOR,  # noqa: E402
                        TRIP_MODEL, TRIPPED)
from harness import (scenario_matrix, run_scenario, run_scenario_detailed, Scenario, SensorSpec,  # noqa: E402
                     in_design_box, HOT_CORNER, COLD_CORNER, NOMINAL_PROPERTIES)
import detectability  # noqa: E402
from dataclasses import replace  # noqa: E402

MATRIX = {s.name: s for s in scenario_matrix()}
CODA_TABLE = {  # Coda's executed REPORT.md values (dt = 1 s, 1 s sample peaks)
    "H1": dict(intact=(33.831193, 900, 33.554994, 900, 25.170303), loss=(61.143480, 900, 59.747155, 901, 26.374204)),
    "H2": dict(intact=(33.861287, 900, 33.362444, 900, 25.168602), loss=(55.545063, 900, 53.153638, 904, 26.798252)),
    "H3": dict(intact=(33.884652, 900, 32.963939, 900, 25.165436), loss=(50.169875, 900, 45.881263, 914, 28.187988)),
}
_CACHE = {}


def run(name):
    if name not in _CACHE:
        _CACHE[name] = run_scenario(MATRIX[name])
    return _CACHE[name]


def f1_peak(stack):
    return run(stack + "_ol_rearloss600")["peak_H"]


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
        p = nominal("H1")
        Hi = Si = Hb = Sb = 25.0
        for _ in range(600):
            Hi, Si = step(p, Hi, Si, 0.0, 0.0, 1.0)
            Hb, Sb = step(blocked(p), Hb, Sb, 0.0, 0.0, 1.0)
        self.assertEqual((Hi, Si), (Hb, Sb))
        self.assertAlmostEqual(Si, 25.0, delta=1e-12)

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
            y = sup.Shat  # perfect agreement with the model: only the watchdog can fire
        self.assertEqual(sup.state, TRIP_SENSOR)
        self.assertEqual(sup.trip_time, 21)
        self.assertIn("watchdog", sup.trip_cause)

    def test_config_validation(self):
        with self.assertRaises(ValueError):
            SupervisorConfig(probe_period=30, probe_duration=60)
        with self.assertRaises(ValueError):
            SupervisorConfig(tau_rel_probe=1.0)


class ClosedLoop(unittest.TestCase):
    def test_intact_ideal_zero_residual_and_probe_cost(self):
        for stack in ("H1", "H2", "H3"):
            r, sup = run_scenario_detailed(MATRIX[stack + "_sup1_intact_ideal"])
            self.assertEqual(r["final_state"], RUN)
            self.assertEqual(r["probes_ok"], 6)
            self.assertAlmostEqual(r["energy_applied_J"], 4500.0 - 6 * 60 * 3.0, delta=1e-6)
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
                self.assertEqual(r["final_state"], TRIP_MODEL)
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
                self.assertLessEqual(r["trip_time"], 830)
                self.assertLess(r["peak_H"], f1_peak(stack) - 5.0)
                st = r["state_at_trip"]
                self.assertGreater(st["true_S"] - st["reported_y1"], 1.0)   # observability gap at trip
            r = run(stack + "_sup1_freeze600_only_noise")
            with self.subTest(stack=stack, hazard=False):
                self.assertEqual(r["final_state"], TRIP_SENSOR)
                self.assertLessEqual(r["trip_time"], 830)
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
                self.assertGreater(r["final_H"], 60.0)   # study comparator only

    def test_idle_rear_loss_latent_then_detected_on_redemand(self):
        for stack in ("H1", "H2", "H3"):
            r = run(stack + "_sup1_idle_rearloss1500_redemand2400_noise")
            with self.subTest(stack=stack):
                self.assertTrue(r["tripped"])
                self.assertLessEqual(r["trip_time"], 2600)
                self.assertLess(r["peak_H"], 50.0)

    def test_matrix_predeclared_and_deterministic(self):
        runs = scenario_matrix()
        self.assertLessEqual(len(runs), 60)
        self.assertEqual(len({s.name for s in runs}), len(runs))
        a = json.dumps(run_scenario(MATRIX["H1_sup1_rearloss600_noise"]), sort_keys=True)
        b = json.dumps(run_scenario(MATRIX["H1_sup1_rearloss600_noise"]), sort_keys=True)
        self.assertEqual(a, b)

    def test_detectability_summary(self):
        cfg = SupervisorConfig()
        for stack in ("H1", "H2", "H3"):
            d = detectability.summary_for_stack(stack, cfg)
            self.assertTrue(d["probe_informative"] and d["frozen_channel_detected_by_probe"])
            self.assertIsNotNone(d["increment_detection_time_estimate_s"])
            self.assertLess(d["idle_rear_flux_W"], 0.1)
            self.assertGreater(d["idle_S_blocked"], d["idle_S_intact"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
```

---

## Notes for Red's execution and review

1. **Nothing above was executed.** Predicted outcomes in README §4 and the test bounds are static estimates; if a bound fails, preserve the failed run and send it back rather than loosening thresholds — the most likely fragile points are (i) HOT‑corner transient margins (estimate ~1 K) in `test_no_false_alarm_inside_design_box`, (ii) H3 probe margin (~0.2 K) in the freeze tests, (iii) the `≤ 2600 s` / `< 50 °C` bounds in the idle case.
2. The plant reimplementation must reproduce Coda's six executed table rows (`test_open_loop_reproduces_coda_executed_table`); a failure there means a semantic mismatch and everything downstream is suspect. The optional `RC_TRANSIENT_PATH` cross‑check compares every second to 1e‑9.
3. The two deliberate counterexamples (`naive45_frozen`, `sup1_noprobe_*`) are expected to show *no trip and the F1 peak* — that is the result, not a bug.
4. Left unimplemented (listed in README §6): ambient disturbance, quantisation, H‑observer, full box sweep, adaptive thresholds, reset logic, quantitative second‑sensor cost, continuous‑time inter‑sample analysis, spatial model.