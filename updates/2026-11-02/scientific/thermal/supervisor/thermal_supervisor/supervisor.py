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
