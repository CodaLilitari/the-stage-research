# Thermal transient & fault packet — T0-FV1D-1 (distributed finite-volume model for T0-HYP-1)

Contributor role: Red's Claude contributor, bounded to task thermal-faults-fv-001. Everything below is **proposed and implemented as text**; **nothing was executed by me**. Red executes in the sandbox and returns results for correction. No code was run, no file read beyond the verbatim bundle, no numbers below are results. Coda (Codex Lily) authored the packet, the shared contract T0-HYP-1, the exact rational steady reference (validation/thermal) and the executed two-node T0-LUMP2-1 (validation/thermal_transient); those are used only as external cross-check targets. Earlier Claude Fable 5.1 steady-contract work is referenced in the packet and not reproduced. This is model research only: not validation, not a safety certificate, not a hardware design recommendation, not a public release.

---

## 1. Compact derivation

**Unknowns.** Dynamic nodes i = 0…N−1 ordered from ambient inward: outer silicone cells, film cells (odd count, centre cell holds the sensor sheet), inner silicone cells, then H (index N−1, capacitance C_H). Cell capacity C_i = ρ·A·Δx_i·cp (H: C_H). Ambient and reservoir are fixed external boundaries without capacity.

**Face conductances.** Between adjacent nodes i, i+1: R_i = Δx_i/(2k_iA) + r_c/A·[face is a material interface] + Δx_{i+1}/(2k_{i+1}A), g_i = 1/R_i. Contact resistance is added only at the two physical silicone–film faces (outer at depth t_s, inner at depth t_s+t_f), never on refined sub-faces. The inner-silicone→H face uses only the silicone half-cell (ideal attachment; listed as omitted uncertainty). Front: G_f = 1/(1/(hA) + Δx_0/(2k_sA)); h = 0 means G_f = 0 (adiabatic, "blocked exit"). Rear: G_r = 1/R_rej; R_rej = ∞ means G_r = 0.

**Nodal ODEs.** With face flux f_i = g_i(T_i − T_{i+1}) (positive toward H), q_f = G_f(T_0 − T_amb), q_r = G_r(T_H − T_res) (positive = exported):

C_i dT_i/dt = s_i + f_{i−1} − f_i − q_f·[i=0] − q_r·[i=N−1],  s_H = P_body, s_sensor = 0.10 W.

**Network sum.** Σ_i(f_{i−1} − f_i) telescopes to zero because each internal face appears once with + and once with −. Hence dE/dt = Σ s_i − q_f − q_r with E = Σ C_i T_i — no hidden sink; the reservoir's demand is q_r, reported separately.

**Backward Euler.** (C/Δt + K)T^{n+1} = (C/Δt)T^n + s + G_fT_amb e_0 + G_rT_res e_H, K the tridiagonal conductance matrix. Summing the rows gives the exact discrete balance Σ C_i(T_i^{n+1} − T_i^n) = Δt[Σ s − q_f^{n+1} − q_r^{n+1}], i.e. end-of-step (right-endpoint) flux quadrature is the scheme-consistent audit. C/Δt + K is an M-matrix, so the step is a convex combination of old nodal and boundary temperatures: discrete maximum principle, no spurious extrema, L-stability on the stiff thin-film cells. First-order in time; controlled by refinement, never by claiming instability is physical.

**Surface.** T_surf = T_0 − q_f·Δx_0/(2k_sA) (= T_amb + q_f/(hA) when h > 0; = T_0 when h = 0). Quasi-steady half-cell reconstruction, not a dynamic state.

**Events.** Conductance changes alter K only; the state vector is unchanged at the instant (continuous), fluxes jump algebraically. Steps end exactly on event times (event times must be integer multiples of Δt); the next step uses the new operator.

## 2. Node/face map (production mesh N_s = 2, N_f = 1; N = 6)

| node | layer | thickness | capacity | notes |
|---|---|---|---|---|
| 0 | outer silicone | t_s/2 | ρ_sA(t_s/2)cp_s | front face: 1/(hA) + half-cell |
| 1 | outer silicone | t_s/2 | same | face 1→2 carries r_c,outer/A |
| 2 | film (sensor cell) | t_f | ρ_fAt_fcp_f | source 0.10 W; centre = midplane |
| 3 | inner silicone | t_s/2 | ρ_sA(t_s/2)cp_s | face 2→3 carries r_c,inner/A |
| 4 | inner silicone | t_s/2 | same | face 4→5 = silicone half-cell only |
| 5 | H | — | C_H = 20 J/K | source P_body; rear G_r to T_res |

Series resistance from midplane to H equals the contract's a; from ambient to midplane equals b; so the steady solution is mesh-invariant and must reproduce Coda's rational reference exactly (test).

## 3. Exact event/scenario table

Common schedule (all stacks): t = 0 all nodes 25 °C; P_body = 5 W on [0, 900), 0 after; P_sensor = 0.10 W throughout; horizon 3600 s; faults at t = 600 s; integer-second sampling.

| case | fault at 600 s | observation | control |
|---|---|---|---|
| F0 | none | truthful | none |
| F1 | G_r → 0 permanently | truthful | none |
| F2 | r_c,inner 2e-4 → 2e-2 m²K/W (uniform) | truthful | none |
| F3 | as F1 | reported sensor frozen at 599 s sample from 600 s | none (open loop; physics ≡ F1) |
| F4T | as F1 | truthful | latch P_body=0 at first integer-second reported ≥ 45 °C; else 900 s shutdown |
| F4F | as F1 | frozen at 600 s (599 s value) | same controller |
| F5 | G_r → 0 and h → 0 | truthful | none |

Deterministic run list (51 ≤ 60): per stack, 7 nominal cases + 10 sensitivity runs: F1×{cp_s 1000, cp_s 2000, C_H 5, C_H 100, r_c 0 (both), r_c 2e-3 (both)}, F4T×{C_H 5, C_H 100}, F0×{cp_s 1000, cp_s 2000}. Verification refinements (outside the 51): time (Δt 1, 0.5, 0.25) on F1/F2; mesh ((1,1),(2,1),(4,1),(2,3)) on F1/F2; F4T trip grid at three Δt; F1/F3 identity; uniform hold; insulated inventory; long-time steady approach.

## 4. Predeclared acceptance plan (before any result exists)

| check | criterion | if unmet |
|---|---|---|
| Uniform hold | max deviation ≤ 1e-11 K | stop; solver defect |
| Insulated inventory | ΔE = ∫(P+J) within 1e-9 J, exports exactly 0 | stop |
| One-node exponential | errors at Δt 1/0.5/0.25 equal Coda's recorded values within 1e-9 K; ratios in (1.8, 2.1) | stop |
| Two-node insulated modes | successive error ratios in (1.8, 2.2); finest < 0.01 K; weighted energy exact to 1e-10 | stop |
| Steady match | FV steady = Coda rational reference within 1e-9 K / 1e-9 W, meshes (1,1),(2,1),(4,3); long-time hold reaches it within 1e-9 K | stop |
| Energy audit, every run | \|residual\| ≤ 1e-8 J + 1e-10·throughput; instantaneous power residual ≤ 1e-8 W; trace re-sum within 1e-8 J | preserve failed run; exclude from comparisons |
| F1≡F3 physical identity | ≤ 1e-12 K/W on all trace fields | stop F3/F4 interpretation |
| Event continuity | state_before == state_after; first post-event step change ≤ 1.0 K | preserve; investigate |
| Time refinement (F1, F2, open loop) | max diff at common integer seconds (Δt 0.5 vs 0.25) < 0.05 K for surface/sensor/H and smaller than the (1.0 vs 0.5) pair | keep Δt 0.5 results labelled failed; refine Δt (numerics change), do not loosen |
| Mesh refinement | (2,1) vs (4,1) and (2,1) vs (2,3) < 0.10 K; injected energy bitwise identical; steady targets within 1e-9; interface depths identical | adopt finer production mesh, re-run; do not loosen |
| Controller grid | F4T trip sample agrees across Δt within ±1 s | report as sample-grid limitation |
| Cross-check vs LUMP2 (expectation, not acceptance) | F0/F1 peak H, peak surface within 2.0 K; H(3600) within 1.0 K | flag both models for review; agreement validates nothing physical |

Criteria are engineering verification targets for the model; they say nothing about the real panel's accuracy.

## 5. Source/assumption ledger (also embedded in the module)

| quantity | value | status |
|---|---|---|
| k_silicone | 0.27 W/mK | W1 typical; conditions unstated |
| ρ_silicone | 1030 kg/m³ | approximate conversion of W1 SG 1.03 |
| cp_silicone | 1500 J/kgK | ASSUMED (not on W1); domain [1000, 2000] |
| k_film | 0.20 W/mK | W2/W3 indexed typical; HTTP 403 retrieval limit retained |
| ρ_film, cp_film | 1420 kg/m³, 1090 J/kgK | W2/W3 indexed typical |
| r_c | 2e-4 m²K/W | assumed; domain [0, 2e-3]; F2 impairment 2e-2 |
| h | 8 W/m²K | assumed, not derived from airflow |
| R_rej, T_res | 2 K/W, 25 °C | assumed ideal reservoir; demand reported, realization unmodeled |
| C_H | 20 J/K | assumed lump; domain [5, 100] |
| 40/60 °C, 45 °C trip | — | arbitrary study comparators |
| sensor sheet | zero added mass/thickness | simplifying assumption |
| omitted | lateral conduction, radiation, H attachment contact, traces/adhesive mass, human contact, localized delamination | delimit the question, not evidence of negligibility |

## 6. Output field schema (per run, JSON)

`run_id, model_id, contract_version, stack, case, case_description, perturbation, parameters{stack, materials, boundary_initial, boundary_final, mesh{…,capacities, face_resistances, interface_depths_m}, numerics, scenario, initial_temperatures_C}, events[{time_s, kind, detail, state_before_C, state_after_C, state_continuous, fluxes_before, fluxes_after, body_power_before_W, body_power_after_W}], body_power_end_s, peaks{surface_actual, sensor_actual, H, sensor_reported_at_samples}{value_C, time_s, after_body_power_end, delay_after_body_power_end_s}, comparators_study_comparator_only{surface_actual_40C, H_60C, sensor_actual_45C}{status ∈ crossed_detected_at_sample | not_crossed_in_horizon, first_sample_at_or_above_s, interpolated_crossing_estimate_s, peak_minus_comparator_K}, checkpoints{599,600,601,900,3600}, samples_60s[], energy{injected_J, exported_front_to_ambient_J, exported_rear_to_reservoir_J, stored_change_J, residual_J, tolerance_J, within_predeclared_tolerance, max_instantaneous_power_residual_W, reconstructed_from_trace_J, reconstructed_residual_J, peak_front_flux_W, peak_rear_flux_W, min_rear_flux_W}, controller, sensor_observability, long_time_target_if_final_conditions_held, final_state, labels`. Top level adds `verification`, `cross_check_against_lump2`, `acceptance`, `assumption_ledger`, `criteria`, `scenario_table`.

---

## 7. Files

FILE: thermal_fv_transient.py
```python
"""thermal_fv_transient.py -- T0-FV1D-1: one-dimensional finite-volume RC transient
for the shared synthetic reference T0-HYP-1 (task thermal-faults-fv-001, The Stage).

STATUS LABELS (keep distinct)
  proposed/implemented : this module, written as text by Red's Claude contributor
  executed             : only when Red runs it; the author executed nothing
  checked              : test_thermal_fv_transient.py, once executed
  source-supported     : W1/W2/W3 typical values; Coda's executed references
  empirically validated: NOTHING in this file

Credits.  Packet and shared contract T0-HYP-1: Coda (Codex Lily).  Exact rational
steady reference (validation/thermal/thermal_reference.py, reference_results.json)
and the executed two-node transient T0-LUMP2-1 (validation/thermal_transient):
Coda; used here only as external cross-check targets.  Coordination: Red (Claude)
with Richard (Andrei) Pemberton.  Earlier Claude Fable 5.1 steady-contract work is
referenced by the packet and not reproduced here.

Standard library only (Python 3.10+); deterministic; no network, threads or GPU;
the only file written is a caller-supplied output path.
"""
from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict, dataclass, field, is_dataclass, replace
from fractions import Fraction
from typing import Dict, List, NamedTuple, Optional, Sequence, Tuple

CONTRACT_VERSION = "T0-HYP-1"
MODEL_ID = "T0-FV1D-1"
MODULE_VERSION = "0.1.0"
MAX_STEPS = 2_000_000
P_BODY_MAX_W = 10.0
P_SENSOR_MAX_W = 0.2
GRID_TOLERANCE = 1e-9
STACK_NAMES = ("H1", "H2", "H3")
FAULT_KINDS = ("none", "rear_blocked", "inner_contact", "both_exits_blocked")

ASSUMPTION_LEDGER = {
    "geometry": {"value": "0.100 m x 0.100 m planar, 1-D through-thickness, adiabatic edges",
                 "status": "hypothetical study proxy (T0-HYP-1)"},
    "k_silicone_W_per_mK": {"value": 0.27, "status": "nominal manufacturer typical (W1); test conditions not stated"},
    "rho_silicone_kg_per_m3": {"value": 1030.0, "status": "approximate conversion of W1 specific gravity 1.03"},
    "cp_silicone_J_per_kgK": {"value": 1500.0, "status": "ASSUMED for the synthetic reference; not supplied by W1; sensitivity [1000, 2000]"},
    "k_film_W_per_mK": {"value": 0.20, "status": "nominal indexed typical (W2/W3); direct fetch returned HTTP 403"},
    "rho_film_kg_per_m3": {"value": 1420.0, "status": "nominal indexed typical (W2)"},
    "cp_film_J_per_kgK": {"value": 1090.0, "status": "nominal indexed typical (W3, DSC); retrieval limit retained"},
    "r_c_m2K_per_W": {"value": 2.0e-4, "status": "assumed; sensitivity [0, 2e-3]; F2 impairment 2e-2 uniform"},
    "h_W_per_m2K": {"value": 8.0, "status": "assumed convection coefficient; not measured, not derived from airflow"},
    "R_rej_K_per_W": {"value": 2.0, "status": "assumed finite path to an ideal isothermal reservoir; capacity not guaranteed"},
    "C_H_J_per_K": {"value": 20.0, "status": "assumed lump of robot structure; sensitivity [5, 100]"},
    "sensor_sheet": {"value": "0.10 W at film midplane, zero added mass/thickness", "status": "simplifying assumption"},
    "comparators_C": {"value": [40.0, 60.0, 45.0], "status": "arbitrary study comparators; no standard applied"},
    "omitted": {"value": ["lateral conduction", "radiation", "H attachment contact resistance", "trace/adhesive/component mass",
                          "human contact", "localized delamination", "strain-dependent resistance", "real sensor dynamics"],
                "status": "delimit the question; not evidence of negligibility"},
    "retained_prior_failure": {"value": "PF0 flow_wall_capacity_monotonic=false (6/7)", "status": "unchanged by this work"},
}

CRITERIA = {
    "energy_residual_abs_floor_J": 1e-8,
    "energy_residual_relative": 1e-10,
    "instantaneous_power_residual_W": 1e-8,
    "steady_match_K": 1e-9,
    "fixed_point_hold_K": 1e-10,
    "uniform_hold_K": 1e-11,
    "f1_f3_physical_identity_K": 1e-12,
    "time_refinement_K": 0.05,
    "time_refinement_dts_s": [1.0, 0.5, 0.25],
    "mesh_refinement_K": 0.10,
    "mesh_refinement_meshes": [[1, 1], [2, 1], [4, 1], [2, 3]],
    "controller_trip_grid_s": 1.0,
    "post_event_single_step_change_bound_K": 1.0,
    "cross_check_lump2_expectation_K": {"peak_H": 2.0, "peak_surface": 2.0, "H_at_3600": 1.0},
    "note": "engineering verification targets for the model; not statements about the real panel",
}


# ---------------------------------------------------------------------------
# validation helpers
# ---------------------------------------------------------------------------
def _number(value, name, *, minimum=None, strict_positive=False, allow_inf=False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a non-Boolean int or float, got {value!r}")
    x = float(value)
    if math.isnan(x):
        raise ValueError(f"{name} must not be NaN")
    if math.isinf(x) and not allow_inf:
        raise ValueError(f"{name} must be finite")
    if strict_positive and not x > 0.0:
        raise ValueError(f"{name} must be > 0, got {x!r}")
    if minimum is not None and x < minimum:
        raise ValueError(f"{name} must be >= {minimum}, got {x!r}")
    return x


def _count(value, name, *, minimum=1, odd=False) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an int, got {value!r}")
    if value < minimum:
        raise ValueError(f"{name} must be >= {minimum}, got {value}")
    if odd and value % 2 == 0:
        raise ValueError(f"{name} must be odd so one cell is centred on the film midplane")
    return value


def _jsonable(obj):
    if is_dataclass(obj) and not isinstance(obj, type):
        return _jsonable(asdict(obj))
    if isinstance(obj, dict):
        return {str(k): _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    if isinstance(obj, float):
        if math.isnan(obj):
            return "nan"
        if math.isinf(obj):
            return "inf" if obj > 0 else "-inf"
        return obj
    if isinstance(obj, (int, str, bool)) or obj is None:
        return obj
    if isinstance(obj, Fraction):
        return str(obj)
    return str(obj)


# ---------------------------------------------------------------------------
# reference data: materials, stacks, boundary
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Materials:
    k_silicone: float = 0.27
    k_film: float = 0.20
    rho_silicone: float = 1030.0
    cp_silicone: float = 1500.0
    rho_film: float = 1420.0
    cp_film: float = 1090.0

    def __post_init__(self) -> None:
        for name in ("k_silicone", "k_film", "rho_silicone", "cp_silicone", "rho_film", "cp_film"):
            object.__setattr__(self, name, _number(getattr(self, name), name, strict_positive=True))


@dataclass(frozen=True)
class StackSpec:
    name: str
    t_silicone_outer: float
    t_silicone_inner: float
    t_film: float = 5.0e-5
    area: float = 0.01

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name:
            raise ValueError("stack name must be a non-empty string")
        for name in ("t_silicone_outer", "t_silicone_inner", "t_film", "area"):
            object.__setattr__(self, name, _number(getattr(self, name), name, strict_positive=True))


STACKS: Dict[str, StackSpec] = {
    "H1": StackSpec("H1", 0.0005, 0.0005),
    "H2": StackSpec("H2", 0.0010, 0.0010),
    "H3": StackSpec("H3", 0.0020, 0.0020),
}


@dataclass(frozen=True)
class Boundary:
    """h=0.0 means an adiabatic (blocked) front exit; r_rej=math.inf means a blocked rear path
    (zero conductance).  Both are exact zero conductances, not large numeric resistances."""
    h: float = 8.0
    t_ambient: float = 25.0
    r_rej: float = 2.0
    t_reservoir: float = 25.0
    r_c_outer: float = 2.0e-4
    r_c_inner: float = 2.0e-4
    c_h: float = 20.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "h", _number(self.h, "h", minimum=0.0))
        object.__setattr__(self, "t_ambient", _number(self.t_ambient, "t_ambient"))
        object.__setattr__(self, "r_rej", _number(self.r_rej, "r_rej", strict_positive=True, allow_inf=True))
        object.__setattr__(self, "t_reservoir", _number(self.t_reservoir, "t_reservoir"))
        object.__setattr__(self, "r_c_outer", _number(self.r_c_outer, "r_c_outer", minimum=0.0))
        object.__setattr__(self, "r_c_inner", _number(self.r_c_inner, "r_c_inner", minimum=0.0))
        object.__setattr__(self, "c_h", _number(self.c_h, "c_h", strict_positive=True))


# ---------------------------------------------------------------------------
# mesh
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Mesh:
    n_silicone: int
    n_film: int
    layer_of_node: Tuple[str, ...]
    thickness_of_node_m: Tuple[float, ...]
    center_depth_m: Tuple[float, ...]
    face_depth_m: Tuple[float, ...]
    outer_film_face: int
    film_inner_face: int
    sensor_node: int
    h_node: int

    @property
    def node_count(self) -> int:
        return len(self.layer_of_node)

    @property
    def interface_depths_m(self) -> Tuple[float, float]:
        return (self.face_depth_m[self.outer_film_face], self.face_depth_m[self.film_inner_face])


def build_mesh(stack: StackSpec, n_silicone: int = 2, n_film: int = 1) -> Mesh:
    """Cell-centred 1-D mesh: n_silicone cells per silicone layer, odd n_film cells, then H."""
    n_s = _count(n_silicone, "n_silicone")
    n_f = _count(n_film, "n_film", odd=True)
    dx_outer = stack.t_silicone_outer / n_s
    dx_film = stack.t_film / n_f
    dx_inner = stack.t_silicone_inner / n_s
    layers: List[str] = []
    thick: List[float] = []
    for _ in range(n_s):
        layers.append("outer_silicone")
        thick.append(dx_outer)
    for _ in range(n_f):
        layers.append("film")
        thick.append(dx_film)
    for _ in range(n_s):
        layers.append("inner_silicone")
        thick.append(dx_inner)
    layers.append("H")
    thick.append(0.0)
    centers: List[float] = []
    faces: List[float] = []
    depth = 0.0
    for i, dx in enumerate(thick):
        centers.append(depth + 0.5 * dx)
        depth += dx
        if i < len(thick) - 1:
            faces.append(depth)
    return Mesh(n_s, n_f, tuple(layers), tuple(thick), tuple(centers), tuple(faces),
                n_s - 1, n_s + n_f - 1, n_s + (n_f - 1) // 2, len(layers) - 1)


# ---------------------------------------------------------------------------
# passive operator and linear algebra
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Operator:
    """Capacities and conductances of a chain with a front boundary at node 0 and a rear boundary at H."""
    capacities: Tuple[float, ...]
    face_conductances: Tuple[float, ...]
    front_conductance: float
    rear_conductance: float
    t_ambient: float
    t_reservoir: float
    outer_half_resistance: float
    front_convection_resistance: float
    sensor_node: int
    h_node: int

    def __post_init__(self) -> None:
        caps = tuple(_number(c, "capacity", strict_positive=True) for c in self.capacities)
        faces = tuple(_number(g, "face conductance", minimum=0.0) for g in self.face_conductances)
        object.__setattr__(self, "capacities", caps)
        object.__setattr__(self, "face_conductances", faces)
        n = len(caps)
        if n < 1:
            raise ValueError("at least one dynamic node is required")
        if len(faces) != n - 1:
            raise ValueError("face_conductances must have node_count - 1 entries")
        object.__setattr__(self, "front_conductance", _number(self.front_conductance, "front_conductance", minimum=0.0))
        object.__setattr__(self, "rear_conductance", _number(self.rear_conductance, "rear_conductance", minimum=0.0))
        object.__setattr__(self, "t_ambient", _number(self.t_ambient, "t_ambient"))
        object.__setattr__(self, "t_reservoir", _number(self.t_reservoir, "t_reservoir"))
        object.__setattr__(self, "outer_half_resistance",
                           _number(self.outer_half_resistance, "outer_half_resistance", minimum=0.0))
        object.__setattr__(self, "front_convection_resistance",
                           _number(self.front_convection_resistance, "front_convection_resistance",
                                   minimum=0.0, allow_inf=True))
        if isinstance(self.sensor_node, bool) or not isinstance(self.sensor_node, int) or not 0 <= self.sensor_node < n:
            raise ValueError("sensor_node out of range")
        if isinstance(self.h_node, bool) or not isinstance(self.h_node, int) or self.h_node != n - 1:
            raise ValueError("h_node must index the last dynamic node")

    @property
    def node_count(self) -> int:
        return len(self.capacities)


def front_flux(op: Operator, temps: Sequence[float]) -> float:
    """Heat exported through the front exit (W, positive toward ambient)."""
    return op.front_conductance * (temps[0] - op.t_ambient)


def rear_flux(op: Operator, temps: Sequence[float]) -> float:
    """Heat exported through the rear path (W, positive toward the reservoir; negative if it warms H)."""
    return op.rear_conductance * (temps[op.h_node] - op.t_reservoir)


def face_fluxes(op: Operator, temps: Sequence[float]) -> List[float]:
    """Internal face fluxes, positive from node i toward node i+1 (toward H)."""
    return [g * (temps[i] - temps[i + 1]) for i, g in enumerate(op.face_conductances)]


def surface_temperature(op: Operator, temps: Sequence[float]) -> float:
    """Outer face temperature from the boundary flux and the outer half-cell (quasi-steady reconstruction).
    Equals t_ambient + q*R_conv when h>0 and equals the first cell temperature when the front is adiabatic."""
    return temps[0] - front_flux(op, temps) * op.outer_half_resistance


def stored_energy(op: Operator, temps: Sequence[float], reference_C: float = 0.0) -> float:
    return math.fsum(c * (t - reference_C) for c, t in zip(op.capacities, temps))


def passive_exchange_sum(op: Operator, temps: Sequence[float]) -> float:
    """Sum over all nodes of the signed passive exchange.  Internal faces cancel pairwise, leaving
    exactly -(front_flux + rear_flux); used to demonstrate the network energy sum."""
    ff = face_fluxes(op, temps)
    n = op.node_count
    total = 0.0
    for i in range(n):
        inflow = (ff[i - 1] if i > 0 else 0.0) - (ff[i] if i < n - 1 else 0.0)
        if i == 0:
            inflow -= front_flux(op, temps)
        if i == op.h_node:
            inflow -= rear_flux(op, temps)
        total += inflow
    return total


def _implicit_solve(op: Operator, sources: Sequence[float], temps: Optional[Sequence[float]] = None,
                    dt: Optional[float] = None) -> List[float]:
    """Thomas-algorithm solve of (C/dt + K) T_new = C T_old/dt + s + boundary terms (backward Euler) or,
    with dt=None, of K T = s + boundary terms (steady).  K: diagonal = attached conductances,
    off-diagonal = -g_face."""
    n = op.node_count
    if len(sources) != n:
        raise ValueError("sources must have one entry per dynamic node")
    if dt is not None and (temps is None or len(temps) != n):
        raise ValueError("temps must have one entry per dynamic node")
    g = op.face_conductances
    diag = [0.0] * n
    rhs = [0.0] * n
    for i in range(n):
        d = 0.0
        r = float(sources[i])
        if dt is not None:
            d += op.capacities[i] / dt
            r += op.capacities[i] * temps[i] / dt
        if i > 0:
            d += g[i - 1]
        if i < n - 1:
            d += g[i]
        if i == 0:
            d += op.front_conductance
            r += op.front_conductance * op.t_ambient
        if i == op.h_node:
            d += op.rear_conductance
            r += op.rear_conductance * op.t_reservoir
        diag[i] = d
        rhs[i] = r
    upper = [0.0] * n
    work = [0.0] * n
    denom = diag[0]
    if denom == 0.0:
        raise ValueError("singular network: no conductance attached to node 0")
    upper[0] = (-g[0] / denom) if n > 1 else 0.0
    work[0] = rhs[0] / denom
    for i in range(1, n):
        lower = -g[i - 1]
        denom = diag[i] - lower * upper[i - 1]
        if denom == 0.0:
            raise ValueError("singular network")
        upper[i] = (-g[i] / denom) if i < n - 1 else 0.0
        work[i] = (rhs[i] - lower * work[i - 1]) / denom
    out = [0.0] * n
    out[n - 1] = work[n - 1]
    for i in range(n - 2, -1, -1):
        out[i] = work[i] - upper[i] * out[i + 1]
    return out


def steady_network(op: Operator, sources: Sequence[float]) -> Dict:
    """Independent steady network solution (nodal, tridiagonal elimination)."""
    src = [_number(s, "source") for s in sources]
    if len(src) != op.node_count:
        raise ValueError("sources must have one entry per dynamic node")
    total = math.fsum(src)
    if op.front_conductance == 0.0 and op.rear_conductance == 0.0:
        status = "nonunique_isolated_zero_net_source" if total == 0.0 else "no_finite_steady_state"
        return {"status": status, "net_source_W": total}
    temps = _implicit_solve(op, src)
    qf = front_flux(op, temps)
    qr = rear_flux(op, temps)
    return {"status": "unique", "temperatures_C": temps, "surface_C": surface_temperature(op, temps),
            "sensor_C": temps[op.sensor_node], "H_C": temps[op.h_node], "front_W": qf, "rear_W": qr,
            "balance_W": total - qf - qr}


def _initial_vector(value, n: int) -> List[float]:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return [_number(value, "initial temperature")] * n
    if isinstance(value, (list, tuple)):
        if len(value) != n:
            raise ValueError(f"initial temperature vector length {len(value)} != node count {n}")
        return [_number(v, "initial temperature") for v in value]
    raise ValueError("initial_temperatures must be a number or a sequence")


def integrate_constant(op: Operator, temps: Sequence[float], dt: float, n_steps: int,
                       sources: Sequence[float]) -> Dict:
    """Backward Euler with constant operator and sources; returns the trajectory and the energy audit."""
    dt = _number(dt, "dt", strict_positive=True)
    n_steps = _count(n_steps, "n_steps")
    if n_steps > MAX_STEPS:
        raise ValueError("step budget exceeded")
    state = _initial_vector(list(temps), op.node_count)
    src = [_number(s, "source") for s in sources]
    if len(src) != op.node_count:
        raise ValueError("sources must have one entry per dynamic node")
    initial = tuple(state)
    trajectory = [initial]
    injected = 0.0
    exported_front = 0.0
    exported_rear = 0.0
    max_power_residual = 0.0
    power_in = math.fsum(src)
    for _ in range(n_steps):
        new = _implicit_solve(op, src, state, dt)
        qf = front_flux(op, new)
        qr = rear_flux(op, new)
        d_energy = math.fsum(c * (a - b) for c, a, b in zip(op.capacities, new, state))
        residual_power = d_energy / dt - (power_in - qf - qr)
        if abs(residual_power) > max_power_residual:
            max_power_residual = abs(residual_power)
        injected += dt * power_in
        exported_front += dt * qf
        exported_rear += dt * qr
        state = new
        trajectory.append(tuple(state))
    stored = math.fsum(c * (a - b) for c, a, b in zip(op.capacities, state, initial))
    return {"temperatures_C": list(state), "trajectory": trajectory, "injected_J": injected,
            "exported_front_J": exported_front, "exported_rear_J": exported_rear, "stored_change_J": stored,
            "energy_residual_J": stored - injected + exported_front + exported_rear,
            "max_power_residual_W": max_power_residual}


# ---------------------------------------------------------------------------
# assembly: geometry + properties -> operator
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Assembly:
    stack: StackSpec
    materials: Materials
    boundary: Boundary
    mesh: Mesh

    def half_resistance(self, node: int) -> float:
        layer = self.mesh.layer_of_node[node]
        if layer == "H":
            return 0.0
        k = self.materials.k_film if layer == "film" else self.materials.k_silicone
        return 0.5 * self.mesh.thickness_of_node_m[node] / (k * self.stack.area)

    def capacities(self) -> List[float]:
        out: List[float] = []
        for layer, dx in zip(self.mesh.layer_of_node, self.mesh.thickness_of_node_m):
            if layer == "H":
                out.append(self.boundary.c_h)
            elif layer == "film":
                out.append(self.materials.rho_film * self.stack.area * dx * self.materials.cp_film)
            else:
                out.append(self.materials.rho_silicone * self.stack.area * dx * self.materials.cp_silicone)
        return out

    def face_components(self) -> List[Tuple[float, float, float]]:
        """(left half-cell, interface contact, right half-cell) resistances in K/W for every face."""
        out: List[Tuple[float, float, float]] = []
        for i in range(self.mesh.node_count - 1):
            contact = 0.0
            if i == self.mesh.outer_film_face:
                contact = self.boundary.r_c_outer / self.stack.area
            elif i == self.mesh.film_inner_face:
                contact = self.boundary.r_c_inner / self.stack.area
            out.append((self.half_resistance(i), contact, self.half_resistance(i + 1)))
        return out

    def operator(self) -> Operator:
        faces = tuple(1.0 / (a + b + c) for a, b, c in self.face_components())
        r_half0 = self.half_resistance(0)
        if self.boundary.h > 0.0:
            r_conv = 1.0 / (self.boundary.h * self.stack.area)
            g_front = 1.0 / (r_conv + r_half0)
        else:
            r_conv = math.inf
            g_front = 0.0
        g_rear = 0.0 if math.isinf(self.boundary.r_rej) else 1.0 / self.boundary.r_rej
        return Operator(tuple(self.capacities()), faces, g_front, g_rear, self.boundary.t_ambient,
                        self.boundary.t_reservoir, r_half0, r_conv, self.mesh.sensor_node, self.mesh.h_node)


def build_assembly(stack, materials: Optional[Materials] = None, boundary: Optional[Boundary] = None,
                   n_silicone: int = 2, n_film: int = 1) -> Assembly:
    spec = STACKS[stack] if isinstance(stack, str) else stack
    if not isinstance(spec, StackSpec):
        raise ValueError("stack must be a StackSpec or one of H1/H2/H3")
    return Assembly(spec, materials or Materials(), boundary or Boundary(), build_mesh(spec, n_silicone, n_film))


_MATERIAL_KEYS = ("cp_silicone", "k_silicone", "k_film", "cp_film", "rho_silicone", "rho_film")
_BOUNDARY_KEYS = ("c_h", "h", "r_rej", "t_ambient", "t_reservoir")


def apply_perturbation(materials: Materials, boundary: Boundary, perturbation: Optional[Dict[str, float]]):
    """Shared perturbations: 'r_c' sets BOTH interfaces (common origin); material keys are common to all
    cells of that material.  Unknown keys are rejected."""
    m, b = materials, boundary
    for key, value in (perturbation or {}).items():
        if key in _MATERIAL_KEYS:
            m = replace(m, **{key: value})
        elif key in _BOUNDARY_KEYS:
            b = replace(b, **{key: value})
        elif key == "r_c":
            b = replace(b, r_c_outer=value, r_c_inner=value)
        else:
            raise ValueError(f"unknown perturbation key {key!r}")
    return m, b


# ---------------------------------------------------------------------------
# independent analytic/reference helpers (credit: Coda's thermal_reference.py formulations)
# ---------------------------------------------------------------------------
def analytic_one_node(initial: float, bath: float, power: float, resistance: float, capacity: float,
                      time: float) -> float:
    """One node, one resistor, constant source: T(t) = T_eq + (T0 - T_eq) exp(-t/RC)."""
    equilibrium = bath + power * resistance
    return initial + (equilibrium - initial) * (-math.expm1(-time / (resistance * capacity)))


def analytic_two_insulated(t1: float, t2: float, c1: float, c2: float, conductance: float, time: float):
    """Two insulated capacities exchanging through one conductance (mean preserved, difference decays)."""
    mean = (c1 * t1 + c2 * t2) / (c1 + c2)
    diff = (t1 - t2) * math.exp(-conductance * (1.0 / c1 + 1.0 / c2) * time)
    return mean + c2 * diff / (c1 + c2), mean - c1 * diff / (c1 + c2)


def reference_two_node_steady(stack: StackSpec, materials: Materials, boundary: Boundary,
                              body_power: float, sensor_power: float) -> Dict:
    """Exact-rational series elimination in heat-flow variables (Fraction arithmetic), mirroring Coda's
    validation/thermal/thermal_reference.steady; independent of the nodal Thomas solve above."""
    def frac(x) -> Fraction:
        return Fraction(str(x))
    A = frac(stack.area)
    a = (frac(stack.t_silicone_inner) / (frac(materials.k_silicone) * A)
         + frac(stack.t_film) / (2 * frac(materials.k_film) * A) + frac(boundary.r_c_inner) / A)
    b_core = (frac(stack.t_silicone_outer) / (frac(materials.k_silicone) * A)
              + frac(stack.t_film) / (2 * frac(materials.k_film) * A) + frac(boundary.r_c_outer) / A)
    front_open = boundary.h > 0.0
    rear_open = not math.isinf(boundary.r_rej)
    P, J = frac(body_power), frac(sensor_power)
    t_amb, t_res = frac(boundary.t_ambient), frac(boundary.t_reservoir)
    if not front_open and not rear_open:
        return {"status": "no_finite_steady_state" if P + J > 0 else "nonunique"}
    r_conv = (1 / (frac(boundary.h) * A)) if front_open else None
    b = (b_core + r_conv) if front_open else None
    r = frac(boundary.r_rej) if rear_open else None
    if not rear_open:
        front = P + J
        rear = Fraction(0)
        S = t_amb + b * front
        H = S + a * P
    elif not front_open:
        front = Fraction(0)
        rear = P + J
        H = t_res + r * rear
        S = H + a * J
    else:
        front = ((t_res - t_amb) + r * (P + J) + a * J) / (a + b + r)
        rear = P + J - front
        S = t_amb + b * front
        H = S + a * (front - J)
    surface = (t_amb + r_conv * front) if front_open else S
    return {"status": "unique", "H_C": float(H), "sensor_C": float(S), "surface_C": float(surface),
            "front_W": float(front), "rear_W": float(rear), "a_K_per_W": float(a),
            "b_K_per_W": float(b) if b is not None else None}


# ---------------------------------------------------------------------------
# scenarios, numerics, results
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Scenario:
    case: str
    fault: str = "none"
    fault_time_s: float = 600.0
    body_power_W: float = 5.0
    body_shutdown_s: float = 900.0
    sensor_power_W: float = 0.10
    inner_contact_fault_r_c_m2K_per_W: float = 2.0e-2
    sensor_freeze_time_s: Optional[float] = None
    controller_threshold_C: Optional[float] = None

    def __post_init__(self) -> None:
        if not isinstance(self.case, str) or not self.case:
            raise ValueError("case must be a non-empty string")
        if self.fault not in FAULT_KINDS:
            raise ValueError(f"fault must be one of {FAULT_KINDS}")
        object.__setattr__(self, "fault_time_s", _number(self.fault_time_s, "fault_time_s", strict_positive=True))
        object.__setattr__(self, "body_power_W", _number(self.body_power_W, "body_power_W", minimum=0.0))
        if self.body_power_W > P_BODY_MAX_W:
            raise ValueError(f"body_power_W outside the bounded study envelope [0, {P_BODY_MAX_W}]")
        object.__setattr__(self, "body_shutdown_s", _number(self.body_shutdown_s, "body_shutdown_s", strict_positive=True))
        object.__setattr__(self, "sensor_power_W", _number(self.sensor_power_W, "sensor_power_W", minimum=0.0))
        if self.sensor_power_W > P_SENSOR_MAX_W:
            raise ValueError(f"sensor_power_W outside the bounded study envelope [0, {P_SENSOR_MAX_W}]")
        object.__setattr__(self, "inner_contact_fault_r_c_m2K_per_W",
                           _number(self.inner_contact_fault_r_c_m2K_per_W, "inner_contact_fault_r_c", minimum=0.0))
        if self.sensor_freeze_time_s is not None:
            object.__setattr__(self, "sensor_freeze_time_s",
                               _number(self.sensor_freeze_time_s, "sensor_freeze_time_s", strict_positive=True))
        if self.controller_threshold_C is not None:
            object.__setattr__(self, "controller_threshold_C",
                               _number(self.controller_threshold_C, "controller_threshold_C"))


CASE_DEFINITIONS: Dict[str, Dict] = {
    "F0": dict(fault="none"),
    "F1": dict(fault="rear_blocked"),
    "F2": dict(fault="inner_contact"),
    "F3": dict(fault="rear_blocked", sensor_freeze_time_s=600.0),
    "F4T": dict(fault="rear_blocked", controller_threshold_C=45.0),
    "F4F": dict(fault="rear_blocked", sensor_freeze_time_s=600.0, controller_threshold_C=45.0),
    "F5": dict(fault="both_exits_blocked"),
}
CASE_DESCRIPTIONS = {
    "F0": "nominal rear path and interfaces; body 5 W on [0,900) s then 0; sensor 0.10 W throughout",
    "F1": "rear conductance -> 0 at 600 s permanently; front path open",
    "F2": "inner silicone-film areal contact 2e-4 -> 2e-2 m2K/W at 600 s; uniform full-interface impairment, not localized delamination",
    "F3": "physical trajectory identical to F1; reported sensor frozen at its 599 s sample from 600 s on; open loop",
    "F4T": "truthful ideal sensor; body power latches to 0 at the first integer-second reported midplane >= 45 C (arbitrary study comparator), else scheduled 900 s shutdown; rear blocked at 600 s",
    "F4F": "same controller with the reported sensor frozen at 600 s (599 s value); rear blocked at 600 s",
    "F5": "both exits blocked at 600 s (h -> 0 adiabatic front, rear conductance 0); open loop; energy accumulation; no finite powered steady state",
}
BASE_CASES = tuple(CASE_DEFINITIONS)


def scenario_for_case(case: str) -> Scenario:
    if case not in CASE_DEFINITIONS:
        raise ValueError(f"unknown case {case!r}")
    return Scenario(case=case, **CASE_DEFINITIONS[case])


@dataclass(frozen=True)
class Numerics:
    dt_s: float = 0.5
    horizon_s: float = 3600.0
    sample_period_s: float = 1.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "dt_s", _number(self.dt_s, "dt_s", strict_positive=True))
        object.__setattr__(self, "horizon_s", _number(self.horizon_s, "horizon_s", strict_positive=True))
        object.__setattr__(self, "sample_period_s", _number(self.sample_period_s, "sample_period_s", strict_positive=True))


class TraceRow(NamedTuple):
    time_s: float
    body_power_W: float        # applied during the step ending at time_s
    sensor_power_W: float
    front_flux_W: float        # end-of-step value (backward Euler quadrature point)
    rear_flux_W: float
    surface_C: float
    temperatures_C: Tuple[float, ...]


@dataclass
class RunResult:
    summary: Dict
    rows: List[TraceRow]
    samples: List[Dict]
    segments: List[Tuple[float, Operator]]
    assembly: Assembly
    scenario: Scenario
    numerics: Numerics

    def operator_at(self, step_start_time_s: float) -> Operator:
        """Operator active for the step that starts at the given time (faults apply after the step ending
        at the fault instant)."""
        chosen = self.segments[0][1]
        for start, op in self.segments:
            if start <= step_start_time_s + GRID_TOLERANCE:
                chosen = op
        return chosen


def _grid_steps(value: float, dt: float