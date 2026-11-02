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
