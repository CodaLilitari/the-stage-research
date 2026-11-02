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
