# ===========================================================================
# PART 2 of thermal_fv_transient.py -- append verbatim after deleting the dangling
# line "def _grid_steps(value: float, dt: float" at the end of Part 1.
# ===========================================================================

# ---------------------------------------------------------------------------
# external executed references transcribed from the source bundle (credit: Coda)
# status: executed by Coda in her sandbox; here they are cross-check targets only
# ---------------------------------------------------------------------------
CODA_STEADY_REFERENCE_5W = {   # validation/thermal/reference_results.json, body 5 W, sensor 0.1 W, rear open
    "H1": {"H_C": 33.83119986113005, "sensor_C": 33.70398462379287, "surface_C": 33.55500086793716,
           "front_W": 0.6844000694349729, "rear_W": 4.415599930565027},
    "H2": {"H_C": 33.86190245732054, "sensor_C": 33.6326495680521, "surface_C": 33.36310964174662,
           "front_W": 0.6690487713397297, "rear_W": 4.430951228660271},
    "H3": {"H_C": 33.91905575238601, "sensor_C": 33.501140687023764, "surface_C": 33.00590154758745,
           "front_W": 0.6404721238069959, "rear_W": 4.459527876193004},
}
CODA_STEADY_REFERENCE_5W_REAR_BLOCKED = {
    "H1": {"H_C": 90.94862037037036, "sensor_C": 89.86019444444445, "surface_C": 88.75, "front_W": 5.1, "rear_W": 0.0},
    "H2": {"H_C": 92.81899074074074, "sensor_C": 90.80463888888889, "surface_C": 88.75, "front_W": 5.1, "rear_W": 0.0},
    "H3": {"H_C": 96.55973148148148, "sensor_C": 92.69352777777777, "surface_C": 88.75, "front_W": 5.1, "rear_W": 0.0},
}
CODA_ONE_NODE_REFERENCE = {   # C=10 J/K, R=2 K/W, P=3 W, T0=Tb=20 C, t=20 s (validation/thermal)
    "exact_C": 23.792723352971347,
    "backward_euler_abs_error_K": {1.0: 0.05406025020934635, 0.5: 0.027307095158171535, 0.25: 0.013724073533140313},
}
CODA_TWO_INSULATED_REFERENCE = (22.414553294057306, 15.056964470628461)   # two_insulated(30,10,2,3,1,1.2)
LUMP2_EXECUTED_REFERENCE = {   # validation/thermal_transient/REPORT.md, sensor-on rows (T0-LUMP2-1, two-node)
    "H1": {"F0": {"peak_H_C": 33.831193, "peak_H_time_s": 900.0, "peak_surface_C": 33.554994,
                  "peak_surface_time_s": 900.0, "H_3600_C": 25.170303},
           "F1": {"peak_H_C": 61.143480, "peak_H_time_s": 900.0, "peak_surface_C": 59.747155,
                  "peak_surface_time_s": 901.0, "H_3600_C": 26.374204}},
    "H2": {"F0": {"peak_H_C": 33.861287, "peak_H_time_s": 900.0, "peak_surface_C": 33.362444,
                  "peak_surface_time_s": 900.0, "H_3600_C": 25.168602},
           "F1": {"peak_H_C": 55.545063, "peak_H_time_s": 900.0, "peak_surface_C": 53.153638,
                  "peak_surface_time_s": 904.0, "H_3600_C": 26.798252}},
    "H3": {"F0": {"peak_H_C": 33.884652, "peak_H_time_s": 900.0, "peak_surface_C": 32.963939,
                  "peak_surface_time_s": 900.0, "H_3600_C": 25.165436},
           "F1": {"peak_H_C": 50.169875, "peak_H_time_s": 900.0, "peak_surface_C": 45.881263,
                  "peak_surface_time_s": 914.0, "H_3600_C": 28.187988}},
}
CHECKPOINT_TIMES_S = (599.0, 600.0, 601.0, 900.0, 3600.0)
COMPARATORS_C = {"surface_actual_40C": ("surface_actual", 40.0), "H_60C": ("H", 60.0),
                 "sensor_actual_45C": ("sensor_actual", 45.0)}


# ---------------------------------------------------------------------------
# grid, faults, sources
# ---------------------------------------------------------------------------
def _grid_steps(value: float, dt: float, name: str = "time") -> int:
    """Number of dt-steps spanning `value`.  `value` must be a non-negative integer multiple of dt (within
    GRID_TOLERANCE) so that every event, sample and horizon instant ends a step exactly; no step straddles
    a discontinuity."""
    value = _number(value, name, minimum=0.0)
    dt = _number(dt, "dt", strict_positive=True)
    ratio = value / dt
    steps = int(round(ratio))
    if abs(ratio - steps) > GRID_TOLERANCE * max(1.0, abs(ratio)):
        raise ValueError(f"{name}={value!r} is not an integer multiple of dt={dt!r}")
    return steps


def _time_at(step: int, dt: float) -> float:
    """Grid time as a product (not an accumulated sum), rounded to 1 ns for labelling."""
    return float(round(step * dt, 9))


def faulted_boundary(boundary: Boundary, scenario: Scenario) -> Boundary:
    """Boundary in force after the fault instant.  Blocked exits are exact zero conductances."""
    if scenario.fault == "none":
        return boundary
    if scenario.fault == "rear_blocked":
        return replace(boundary, r_rej=math.inf)
    if scenario.fault == "inner_contact":
        return replace(boundary, r_c_inner=scenario.inner_contact_fault_r_c_m2K_per_W)
    if scenario.fault == "both_exits_blocked":
        return replace(boundary, r_rej=math.inf, h=0.0)
    raise ValueError(f"unknown fault {scenario.fault!r}")


def source_vector(op: Operator, body_power_W: float, sensor_power_W: float) -> List[float]:
    """Sensor power at the film-midplane cell, body power at H, each counted exactly once."""
    src = [0.0] * op.node_count
    src[op.sensor_node] += _number(sensor_power_W, "sensor_power_W", minimum=0.0)
    src[op.h_node] += _number(body_power_W, "body_power_W", minimum=0.0)
    return src


def _fluxes_at(op: Operator, temps: Sequence[float]) -> Dict[str, float]:
    return {"front_W": front_flux(op, temps), "rear_W": rear_flux(op, temps),
            "surface_C": surface_temperature(op, temps)}


def _operator_change(before: Operator, after: Operator) -> Dict:
    changed = [i for i, (a, b) in enumerate(zip(before.face_conductances, after.face_conductances)) if a != b]
    return {"front_conductance_W_per_K": [before.front_conductance, after.front_conductance],
            "rear_conductance_W_per_K": [before.rear_conductance, after.rear_conductance],
            "changed_face_indices": changed,
            "changed_face_conductances_W_per_K": [[before.face_conductances[i], after.face_conductances[i]]
                                                  for i in changed],
            "capacities_changed": before.capacities != after.capacities}


def series_resistance_midplane_to_H(assembly: Assembly) -> float:
    """Sum of face resistances from the sensor-cell centre to H (must equal the contract's a)."""
    comps = assembly.face_components()
    m = assembly.mesh
    return math.fsum(a + b + c for a, b, c in comps[m.sensor_node:m.h_node])


def series_resistance_ambient_to_midplane(assembly: Assembly) -> float:
    """Convection + outer half-cell + faces up to the sensor-cell centre (must equal the contract's b)."""
    op = assembly.operator()
    comps = assembly.face_components()
    return (op.front_convection_resistance + op.outer_half_resistance
            + math.fsum(a + b + c for a, b, c in comps[:assembly.mesh.sensor_node]))


def _mesh_summary(assembly: Assembly) -> Dict:
    m = assembly.mesh
    op = assembly.operator()
    return {"n_silicone": m.n_silicone, "n_film": m.n_film, "node_count": m.node_count,
            "layer_of_node": list(m.layer_of_node), "thickness_of_node_m": list(m.thickness_of_node_m),
            "center_depth_m": list(m.center_depth_m), "face_depth_m": list(m.face_depth_m),
            "capacities_J_per_K": assembly.capacities(),
            "face_resistance_components_K_per_W": [{"left_half": a, "contact": b, "right_half": c, "total": a + b + c}
                                                   for a, b, c in assembly.face_components()],
            "interface_depths_m": list(m.interface_depths_m), "sensor_node": m.sensor_node, "h_node": m.h_node,
            "front_convection_resistance_K_per_W": op.front_convection_resistance,
            "outer_half_cell_resistance_K_per_W": op.outer_half_resistance,
            "series_R_midplane_to_H_K_per_W": series_resistance_midplane_to_H(assembly),
            "series_R_ambient_to_midplane_K_per_W": series_resistance_ambient_to_midplane(assembly)}


def _peak_entry(pairs: Sequence[Tuple[float, float]], body_end_s: Optional[float]) -> Dict:
    best_t, best_v = pairs[0]
    for t, v in pairs[1:]:
        if v > best_v:
            best_t, best_v = t, v
    after = body_end_s is not None and best_t > body_end_s + GRID_TOLERANCE
    return {"value_C": best_v, "time_s": best_t, "after_body_power_end": after,
            "delay_after_body_power_end_s": (best_t - body_end_s) if after else None,
            "resolution_note": "first maximum on the step grid; finite temporal resolution"}


def _comparator_report(step_pairs: Sequence[Tuple[float, float]], sample_pairs: Sequence[Tuple[float, float]],
                       threshold: float) -> Dict:
    first_step_t = None
    interp = None
    prev_t, prev_v = step_pairs[0]
    if prev_v >= threshold:
        first_step_t = interp = prev_t
    else:
        for t, v in step_pairs[1:]:
            if v >= threshold:
                first_step_t = t
                interp = (prev_t + (threshold - prev_v) / (v - prev_v) * (t - prev_t)) if v != prev_v else t
                break
            prev_t, prev_v = t, v
    first_sample_t = next((t for t, v in sample_pairs if v >= threshold), None)
    if first_sample_t is not None:
        status = "crossed_detected_at_sample"
    elif first_step_t is not None:
        status = "crossed_on_step_grid_only"
    else:
        status = "not_crossed_in_horizon"
    return {"comparator_C": threshold, "label": "study_comparator_only", "status": status,
            "first_sample_at_or_above_s": first_sample_t, "first_step_grid_time_at_or_above_s": first_step_t,
            "interpolated_crossing_estimate_s": interp,
            "interpolation_note": "linear interpolation between step-grid values; estimate, not a continuous root",
            "peak_minus_comparator_K": max(v for _, v in step_pairs) - threshold}


def _row_dict(row: TraceRow, op: Operator) -> Dict:
    return {"time_s": row.time_s, "temperatures_C": list(row.temperatures_C), "surface_actual_C": row.surface_C,
            "sensor_actual_C": row.temperatures_C[op.sensor_node], "H_C": row.temperatures_C[op.h_node],
            "front_flux_W": row.front_flux_W, "rear_flux_W": row.rear_flux_W,
            "body_power_W_step_ending_here": row.body_power_W, "sensor_power_W": row.sensor_power_W}


# ---------------------------------------------------------------------------
# one scenario: event schedule + backward Euler + sampling + controller + audit
# ---------------------------------------------------------------------------
def run_scenario(assembly: Assembly, scenario: Scenario, numerics: Numerics, initial_temperature_C: float = 25.0,
                 run_id: Optional[str] = None, perturbation: Optional[Dict[str, float]] = None) -> RunResult:
    """Integrate one scenario.  Steps end exactly on every event; the operator/source in force during a
    step is the one valid at the step start.  Fluxes in a row are end-of-step values (the backward-Euler
    quadrature point).  Physical state is never altered by observation or controller code; the
    controller only changes the body-power schedule for subsequent steps."""
    if not isinstance(assembly, Assembly) or not isinstance(scenario, Scenario) or not isinstance(numerics, Numerics):
        raise ValueError("run_scenario needs Assembly, Scenario and Numerics instances")
    dt = numerics.dt_s
    n_total = _grid_steps(numerics.horizon_s, dt, "horizon_s")
    if n_total < 1 or n_total > MAX_STEPS:
        raise ValueError(f"step count {n_total} outside 1..{MAX_STEPS}")
    steps_per_sample = _grid_steps(numerics.sample_period_s, dt, "sample_period_s")
    if steps_per_sample < 1:
        raise ValueError("sample_period_s must be at least dt_s")
    fault_step = _grid_steps(scenario.fault_time_s, dt, "fault_time_s") if scenario.fault != "none" else None
    shutdown_step = _grid_steps(scenario.body_shutdown_s, dt, "body_shutdown_s")
    freeze_step = None
    if scenario.sensor_freeze_time_s is not None:
        freeze_step = _grid_steps(scenario.sensor_freeze_time_s, dt, "sensor_freeze_time_s")
        if freeze_step % steps_per_sample != 0:
            raise ValueError("sensor_freeze_time_s must lie on the sample grid")
    op_nominal = assembly.operator()
    boundary_final = faulted_boundary(assembly.boundary, scenario)
    op_fault = replace(assembly, boundary=boundary_final).operator()
    fault_in_horizon = fault_step is not None and fault_step < n_total
    n = op_nominal.node_count
    caps = op_nominal.capacities
    temps = _initial_vector(initial_temperature_C, n)
    initial = tuple(temps)
    segments: List[Tuple[float, Operator]] = [(0.0, op_nominal)]
    if fault_in_horizon:
        segments.append((_time_at(fault_step, dt), op_fault))

    def operator_for_step(k: int) -> Operator:
        return op_fault if (fault_step is not None and k >= fault_step) else op_nominal

    ctrl = {"tripped": False, "trip_step": None, "frozen_value": None, "previous_reported": None}
    rows: List[TraceRow] = []
    samples: List[Dict] = []
    events: List[Dict] = []

    def body_power_for_step(k: int) -> float:
        return 0.0 if (ctrl["tripped"] or k >= shutdown_step) else scenario.body_power_W

    def take_sample(k: int, op_used: Operator, current: Sequence[float]) -> None:
        t = _time_at(k, dt)
        actual = current[op_used.sensor_node]
        if freeze_step is not None and k >= freeze_step:
            if ctrl["frozen_value"] is None:
                frozen = ctrl["previous_reported"] if ctrl["previous_reported"] is not None else actual
                ctrl["frozen_value"] = frozen
                events.append({"time_s": t, "kind": "observation_freeze",
                               "detail": "reported sensor value frozen at the previous sample; no physical effect",
                               "frozen_reported_C": frozen, "actual_sensor_C": actual, "state_continuous": True,
                               "announces_failure": False})
            reported = ctrl["frozen_value"]
        else:
            reported = actual
        ctrl["previous_reported"] = reported
        body_before = body_power_for_step(k)
        if (scenario.controller_threshold_C is not None and not ctrl["tripped"]
                and reported >= scenario.controller_threshold_C):
            ctrl["tripped"] = True
            ctrl["trip_step"] = k
            events.append({"time_s": t, "kind": "controller_latch",
                           "detail": "reported midplane >= threshold at an integer-second sample; body power latched to 0",
                           "reported_sensor_C": reported, "actual_sensor_C": actual,
                           "body_power_before_W": body_before, "body_power_after_W": 0.0,
                           "effective": body_before > 0.0, "state_continuous": True})
        fl = _fluxes_at(op_used, current)
        samples.append({"time_s": t, "surface_actual_C": fl["surface_C"], "sensor_actual_C": actual,
                        "sensor_reported_C": reported, "H_C": current[op_used.h_node],
                        "front_flux_W": fl["front_W"], "rear_flux_W": fl["rear_W"],
                        "body_power_next_step_W": body_power_for_step(k), "controller_tripped": ctrl["tripped"]})

    op0 = operator_for_step(0)
    take_sample(0, op0, temps)
    fl0 = _fluxes_at(op0, temps)
    rows.append(TraceRow(0.0, body_power_for_step(0), scenario.sensor_power_W, fl0["front_W"], fl0["rear_W"],
                         fl0["surface_C"], tuple(temps)))
    injected_body = injected_sensor = exported_front = exported_rear = throughput = 0.0
    max_power_residual = 0.0
    peak_front, peak_rear, min_rear = -math.inf, -math.inf, math.inf
    for k in range(n_total):
        op = operator_for_step(k)
        body = body_power_for_step(k)
        sensor = scenario.sensor_power_W
        new = _implicit_solve(op, source_vector(op, body, sensor), temps, dt)
        if not all(math.isfinite(x) for x in new):
            raise ValueError("non-finite temperature state")
        qf = front_flux(op, new)
        qr = rear_flux(op, new)
        d_energy = math.fsum(c * (a - b) for c, a, b in zip(caps, new, temps))
        residual_power = d_energy / dt - (body + sensor - qf - qr)
        max_power_residual = max(max_power_residual, abs(residual_power))
        injected_body += dt * body
        injected_sensor += dt * sensor
        exported_front += dt * qf
        exported_rear += dt * qr
        throughput += dt * (abs(body) + abs(sensor) + abs(qf) + abs(qr))
        peak_front, peak_rear, min_rear = max(peak_front, qf), max(peak_rear, qr), min(min_rear, qr)
        temps = new
        k1 = k + 1
        t1 = _time_at(k1, dt)
        rows.append(TraceRow(t1, body, sensor, qf, qr, surface_temperature(op, new), tuple(new)))
        if fault_in_horizon and k1 == fault_step:
            events.append({"time_s": t1, "kind": "fault", "detail": scenario.fault,
                           "state_before_C": list(temps), "state_after_C": list(temps), "state_continuous": True,
                           "fluxes_before": _fluxes_at(op_nominal, temps), "fluxes_after": _fluxes_at(op_fault, temps),
                           "body_power_before_W": body, "body_power_after_W": body_power_for_step(k1),
                           "operator_change": _operator_change(op_nominal, op_fault),
                           "impulsive_source": False})
        if k1 == shutdown_step and k1 < n_total:
            events.append({"time_s": t1, "kind": "scheduled_body_shutdown",
                           "detail": "body power -> 0; sensor power continues; NOT all-power-off",
                           "body_power_before_W": body, "body_power_after_W": 0.0,
                           "already_zero_due_to_controller_latch": ctrl["tripped"], "state_continuous": True})
        if k1 % steps_per_sample == 0:
            take_sample(k1, op, temps)

    final_op = operator_for_step(n_total)
    final_body = body_power_for_step(n_total)
    stored = math.fsum(c * (a - b) for c, a, b in zip(caps, temps, initial))
    injected = injected_body + injected_sensor
    residual = stored - injected + exported_front + exported_rear
    tolerance = CRITERIA["energy_residual_abs_floor_J"] + CRITERIA["energy_residual_relative"] * throughput
    if ctrl["trip_step"] is not None and ctrl["trip_step"] < shutdown_step:
        body_end, body_end_kind = _time_at(ctrl["trip_step"], dt), "controller_latch"
    elif shutdown_step <= n_total:
        body_end, body_end_kind = _time_at(shutdown_step, dt), "scheduled_shutdown"
    else:
        body_end, body_end_kind = None, "not_within_horizon"
    s_node, h_node = op_nominal.sensor_node, op_nominal.h_node
    series = {"surface_actual": [(r.time_s, r.surface_C) for r in rows],
              "sensor_actual": [(r.time_s, r.temperatures_C[s_node]) for r in rows],
              "H": [(r.time_s, r.temperatures_C[h_node]) for r in rows]}
    sample_series = {"surface_actual": [(s["time_s"], s["surface_actual_C"]) for s in samples],
                     "sensor_actual": [(s["time_s"], s["sensor_actual_C"]) for s in samples],
                     "H": [(s["time_s"], s["H_C"]) for s in samples]}
    peaks = {key: _peak_entry(val, body_end) for key, val in series.items()}
    peaks["sensor_reported_at_samples"] = _peak_entry([(s["time_s"], s["sensor_reported_C"]) for s in samples], body_end)
    comparators = {name: _comparator_report(series[field], sample_series[field], thr)
                   for name, (field, thr) in COMPARATORS_C.items()}
    checkpoints: Dict[str, object] = {}
    for t in CHECKPOINT_TIMES_S:
        if t > numerics.horizon_s + GRID_TOLERANCE:
            checkpoints[f"{t:g}"] = "beyond_horizon"
            continue
        try:
            step = _grid_steps(t, dt, "checkpoint")
        except ValueError:
            checkpoints[f"{t:g}"] = "not_on_step_grid"
            continue
        checkpoints[f"{t:g}"] = _row_dict(rows[step], final_op)
    discrepancies = [(abs(s["sensor_reported_C"] - s["sensor_actual_C"]), s["time_s"]) for s in samples]
    worst_disc = max(discrepancies) if discrepancies else (0.0, None)
    recon = reconstruct_energy_from_rows(rows, caps, dt)
    summary = {
        "run_id": run_id or f"{assembly.stack.name}-{scenario.case}",
        "model_id": MODEL_ID, "module_version": MODULE_VERSION, "contract_version": CONTRACT_VERSION,
        "stack": assembly.stack.name, "case": scenario.case,
        "case_description": CASE_DESCRIPTIONS.get(scenario.case, "custom scenario"),
        "perturbation": dict(perturbation or {}),
        "parameters": {"stack": asdict(assembly.stack), "materials": asdict(assembly.materials),
                       "boundary_initial": asdict(assembly.boundary),
                       "boundary_final": asdict(boundary_final if fault_in_horizon else assembly.boundary),
                       "mesh": _mesh_summary(assembly), "numerics": asdict(numerics), "scenario": asdict(scenario),
                       "initial_temperatures_C": list(initial)},
        "events": events,
        "body_power_end_s": body_end, "body_power_end_kind": body_end_kind,
        "fault_within_horizon": fault_in_horizon,
        "peaks": peaks,
        "comparators_study_comparator_only": comparators,
        "checkpoints": checkpoints,
        "samples_60s": [s for s in samples if abs(s["time_s"] / 60.0 - round(s["time_s"] / 60.0)) < GRID_TOLERANCE],
        "energy": {"injected_J": injected, "injected_body_J": injected_body, "injected_sensor_J": injected_sensor,
                   "exported_front_to_ambient_J": exported_front, "exported_rear_to_reservoir_J": exported_rear,
                   "stored_change_J": stored, "residual_J": residual, "tolerance_J": tolerance,
                   "within_predeclared_tolerance": abs(residual) <= tolerance,
                   "max_instantaneous_power_residual_W": max_power_residual,
                   "reconstructed_from_trace_J": recon["reconstructed_net_input_J"],
                   "reconstructed_residual_J": recon["reconstructed_residual_J"],
                   "absolute_throughput_J": throughput,
                   "peak_front_flux_W": peak_front, "peak_rear_flux_W": peak_rear, "min_rear_flux_W": min_rear,
                   "quadrature": "end-of-step (right endpoint), consistent with backward Euler"},
        "reservoir_heat_demand": {"integrated_J": exported_rear, "peak_W": peak_rear, "min_W": min_rear,
                                  "sign_convention": "positive = delivered to reservoir; negative = reservoir warms H",
                                  "realization": "ideal isothermal boundary; energy/mass/environment coupling unmodeled"},
        "controller": {"present": scenario.controller_threshold_C is not None,
                       "threshold_C": scenario.controller_threshold_C, "tripped": ctrl["tripped"],
                       "trip_time_s": _time_at(ctrl["trip_step"], dt) if ctrl["trip_step"] is not None else None,
                       "trip_effective": body_end_kind == "controller_latch",
                       "sample_period_s": numerics.sample_period_s,
                       "note": "arbitrary study-comparator trip; sample-grid detection only; not a safety architecture"},
        "sensor_observability": {"mode": "frozen_from_sample" if freeze_step is not None else "truthful_ideal",
                                 "freeze_time_s": scenario.sensor_freeze_time_s,
                                 "frozen_reported_C": ctrl["frozen_value"],
                                 "max_abs_reported_minus_actual_K": worst_disc[0],
                                 "time_of_max_discrepancy_s": worst_disc[1],
                                 "note": "ideal sensor assumes zero lag/bias; a frozen sensor does not announce failure"},
        "long_time_target_if_final_conditions_held":
            steady_network(final_op, source_vector(final_op, final_body, scenario.sensor_power_W)),
        "final_state": {"time_s": rows[-1].time_s, "temperatures_C": list(temps),
                        "surface_actual_C": rows[-1].surface_C, "sensor_actual_C": temps[s_node],
                        "H_C": temps[h_node], "front_flux_W": rows[-1].front_flux_W,
                        "rear_flux_W": rows[-1].rear_flux_W, "body_power_W": final_body,
                        "sensor_power_W": scenario.sensor_power_W},
        "labels": {"comparators": "study_comparator_only", "physical_validation": False,
                   "scale": "1-D uniform-interface synthetic panel model (T0-HYP-1)",
                   "not_represented": ASSUMPTION_LEDGER["omitted"]["value"],
                   "authorship": "code written as text by Red's Claude contributor; results exist only when executed"},
    }
    return RunResult(summary, rows, samples, segments, assembly, scenario, numerics)


def reconstruct_energy_from_rows(rows: Sequence[TraceRow], capacities: Sequence[float], dt: float) -> Dict:
    """Independent re-summation of the trace: sum dt*(P+J-q_front-q_rear) over steps vs C*(T_end-T_0)."""
    net = math.fsum(dt * (r.body_power_W + r.sensor_power_W - r.front_flux_W - r.rear_flux_W) for r in rows[1:])
    stored = math.fsum(c * (a - b) for c, a, b in zip(capacities, rows[-1].temperatures_C, rows[0].temperatures_C))
    return {"reconstructed_net_input_J": net, "stored_change_J": stored, "reconstructed_residual_J": stored - net}


# ---------------------------------------------------------------------------
# deterministic run list (51 <= 60)
# ---------------------------------------------------------------------------
SENSITIVITY_RUNS: Tuple[Tuple[str, Dict[str, float]], ...] = (
    ("F1", {"cp_silicone": 1000.0}), ("F1", {"cp_silicone": 2000.0}),
    ("F1", {"c_h": 5.0}), ("F1", {"c_h": 100.0}),
    ("F1", {"r_c": 0.0}), ("F1", {"r_c": 2.0e-3}),
    ("F4T", {"c_h": 5.0}), ("F4T", {"c_h": 100.0}),
    ("F0", {"cp_silicone": 1000.0}), ("F0", {"cp_silicone": 2000.0}),
)


def deterministic_run_list() -> List[Dict]:
    runs: List[Dict] = []
    for stack in STACK_NAMES:
        for case in BASE_CASES:
            runs.append({"run_id": f"{stack}-{case}-nominal", "stack": stack, "case": case, "perturbation": {}})
        for case, pert in SENSITIVITY_RUNS:
            key = "_".join(f"{k}{v:g}" for k, v in pert.items())
            runs.append({"run_id": f"{stack}-{case}-{key}", "stack": stack, "case": case, "perturbation": dict(pert)})
    if len(runs) != 51 or len({r["run_id"] for r in runs}) != 51:
        raise RuntimeError("run list must contain 51 unique runs")
    return runs


def run_from_spec(spec: Dict, numerics: Numerics, n_silicone: int = 2, n_film: int = 1) -> RunResult:
    materials, boundary = apply_perturbation(Materials(), Boundary(), spec.get("perturbation"))
    assembly = build_assembly(spec["stack"], materials, boundary, n_silicone, n_film)
    return run_scenario(assembly, scenario_for_case(spec["case"]), numerics, run_id=spec["run_id"],
                        perturbation=spec.get("perturbation"))


# ---------------------------------------------------------------------------
# verification checks (predeclared criteria from CRITERIA; failures are preserved, never loosened)
# ---------------------------------------------------------------------------
def check_uniform_hold(dt: float = 1.0, steps: int = 600) -> Dict:
    op = build_assembly("H1").operator()
    out = integrate_constant(op, [25.0] * op.node_count, dt, steps, [0.0] * op.node_count)
    dev = max(abs(t - 25.0) for row in out["trajectory"] for t in row)
    return {"criterion_K": CRITERIA["uniform_hold_K"], "observed_max_deviation_K": dev,
            "passed": dev <= CRITERIA["uniform_hold_K"]}


def check_insulated_inventory(stack: str = "H2", dt: float = 0.25, duration_s: float = 120.0,
                              body_W: float = 1.0, sensor_W: float = 0.1) -> Dict:
    op = build_assembly(stack, boundary=Boundary(h=0.0, r_rej=math.inf)).operator()
    out = integrate_constant(op, [25.0] * op.node_count, dt, _grid_steps(duration_s, dt), source_vector(op, body_W, sensor_W))
    expected = duration_s * (body_W + sensor_W)
    err = abs(out["stored_change_J"] - expected)
    return {"criterion_J": 1e-9, "expected_J": expected, "stored_change_J": out["stored_change_J"], "error_J": err,
            "exports_J": [out["exported_front_J"], out["exported_rear_J"]],
            "passed": err <= 1e-9 and out["exported_front_J"] == 0.0 and out["exported_rear_J"] == 0.0}


def check_one_node_exponential() -> Dict:
    op = Operator((10.0,), (), 0.0, 0.5, 20.0, 20.0, 0.0, math.inf, 0, 0)
    exact = analytic_one_node(20.0, 20.0, 3.0, 2.0, 10.0, 20.0)
    errors = {}
    for dt in (1.0, 0.5, 0.25):
        out = integrate_constant(op, [20.0], dt, int(round(20.0 / dt)), [3.0])
        errors[dt] = abs(out["temperatures_C"][0] - exact)
    ratios = [errors[1.0] / errors[0.5], errors[0.5] / errors[0.25]]
    coda = CODA_ONE_NODE_REFERENCE["backward_euler_abs_error_K"]
    match = max(abs(errors[d] - coda[d]) for d in errors)
    exact_match = abs(exact - CODA_ONE_NODE_REFERENCE["exact_C"])
    return {"exact_C": exact, "errors_K": {str(k): v for k, v in errors.items()}, "ratios": ratios,
            "max_abs_difference_to_coda_errors_K": match, "exact_difference_to_coda_K": exact_match,
            "passed": match <= 1e-9 and exact_match <= 1e-12 and all(1.8 < r < 2.1 for r in ratios)}


def check_two_node_insulated_modes() -> Dict:
    op = Operator((2.0, 3.0), (1.0,), 0.0, 0.0, 0.0, 0.0, 0.0, math.inf, 0, 1)
    exact = analytic_two_insulated(30.0, 10.0, 2.0, 3.0, 1.0, 1.2)
    errors, energy_dev = {}, 0.0
    for dt in (0.01, 0.005, 0.0025):
        out = integrate_constant(op, [30.0, 10.0], dt, int(round(1.2 / dt)), [0.0, 0.0])
        errors[dt] = max(abs(a - b) for a, b in zip(out["temperatures_C"], exact))
        energy_dev = max(energy_dev, abs(out["stored_change_J"]))
    ratios = [errors[0.01] / errors[0.005], errors[0.005] / errors[0.0025]]
    coda_match = max(abs(a - b) for a, b in zip(exact, CODA_TWO_INSULATED_REFERENCE))
    return {"exact_C": list(exact), "errors_K": {str(k): v for k, v in errors.items()}, "ratios": ratios,
            "weighted_energy_deviation_J": energy_dev, "exact_difference_to_coda_K": coda_match,
            "fixture_note": "dt 0.01/0.005/0.0025 chosen so the predeclared 0.01 K finest-error target is testable",
            "passed": all(1.8 < r < 2.2 for r in ratios) and errors[0.0025] < 0.01 and energy_dev <= 1e-10
            and coda_match <= 1e-12}


def check_passive_exchange_cancellation() -> Dict:
    op = build_assembly("H3", n_silicone=3, n_film=3).operator()
    temps = [25.0 + 1.7 * i - 0.3 * i * i for i in range(op.node_count)]
    total = passive_exchange_sum(op, temps)
    expected = -(front_flux(op, temps) + rear_flux(op, temps))
    err = abs(total - expected)
    return {"sum_of_passive_exchanges_W": total, "minus_boundary_exports_W": expected, "error_W": err,
            "passed": err <= 1e-12 * max(1.0, abs(expected))}


def check_steady_match(stacks: Sequence[str] = STACK_NAMES, meshes=((1, 1), (2, 1), (4, 3))) -> Dict:
    worst, details = 0.0, []
    keys = ("H_C", "sensor_C", "surface_C", "front_W", "rear_W")
    for stack in stacks:
        for ns, nf in meshes:
            for blocked in (False, True):
                asm = build_assembly(stack, boundary=Boundary(r_rej=math.inf) if blocked else Boundary(), n_silicone=ns, n_film=nf)
                op = asm.operator()
                fv = steady_network(op, source_vector(op, 5.0, 0.1))
                frac = reference_two_node_steady(asm.stack, asm.materials, asm.boundary, 5.0, 0.1)
                coda = (CODA_STEADY_REFERENCE_5W_REAR_BLOCKED if blocked else CODA_STEADY_REFERENCE_5W)[stack]
                d_frac = max(abs(fv[k] - frac[k]) for k in keys)
                d_coda = max(abs(fv[k] - coda[k]) for k in keys)
                worst = max(worst, d_frac, d_coda)
                details.append({"stack": stack, "mesh": [ns, nf], "rear_blocked": blocked,
                                "fv": {k: fv[k] for k in keys}, "max_diff_vs_fraction": d_frac, "max_diff_vs_coda": d_coda})
            # final-condition targets of F1/F2 (body 0, sensor 0.1) vs the exact-rational reference
            for case in ("F1", "F2"):
                sc = scenario_for_case(case)
                asm = build_assembly(stack, boundary=faulted_boundary(Boundary(), sc), n_silicone=ns, n_film=nf)
                op = asm.operator()
                fv = steady_network(op, source_vector(op, 0.0, 0.1))
                frac = reference_two_node_steady(asm.stack, asm.materials, asm.boundary, 0.0, 0.1)
                d_frac = max(abs(fv[k] - frac[k]) for k in keys)
                worst = max(worst, d_frac)
                details.append({"stack": stack, "mesh": [ns, nf], "final_conditions_of": case,
                                "fv": {k: fv[k] for k in keys}, "max_diff_vs_fraction": d_frac})
    return {"criterion_K_or_W": CRITERIA["steady_match_K"], "observed_max_abs_difference": worst,
            "passed": worst <= CRITERIA["steady_match_K"], "details": details}


def check_long_time_approach(stacks: Sequence[str] = STACK_NAMES) -> Dict:
    worst_approach, worst_hold, details = 0.0, 0.0, []
    for stack in stacks:
        op = build_assembly(stack).operator()
        src = source_vector(op, 5.0, 0.1)
        target = steady_network(op, src)["temperatures_C"]
        approach = integrate_constant(op, [25.0] * op.node_count, 10.0, 1000, src)
        d_app = max(abs(a - b) for a, b in zip(approach["temperatures_C"], target))
        hold = integrate_constant(op, target, 2.0, 50, src)
        d_hold = max(abs(t - b) for row in hold["trajectory"] for t, b in zip(row, target))
        worst_approach, worst_hold = max(worst_approach, d_app), max(worst_hold, d_hold)
        details.append({"stack": stack, "approach_10000s_dt10_max_dev_K": d_app, "fixed_point_hold_max_dev_K": d_hold})
    return {"criterion_approach_K": CRITERIA["steady_match_K"], "criterion_hold_K": CRITERIA["fixed_point_hold_K"],
            "observed_approach_K": worst_approach, "observed_hold_K": worst_hold, "details": details,
            "passed": worst_approach <= CRITERIA["steady_match_K"] and worst_hold <= CRITERIA["fixed_point_hold_K"]}


def check_maximum_principle(stack: str = "H2", dt: float = 0.5, steps: int = 1200) -> Dict:
    """All inputs removed, both boundaries at 25 C, non-uniform hot start: no new extrema, no energy creation."""
    op = build_assembly(stack).operator()
    initial = [25.0 + 3.0 * (i + 1) for i in range(op.node_count)]
    out = integrate_constant(op, initial, dt, steps, [0.0] * op.node_count)
    bound_hi, bound_lo = max(max(initial), 25.0), min(min(initial), 25.0)
    running_max = max(initial)
    violation = 0.0
    for row in out["trajectory"][1:]:
        m = max(row)
        violation = max(violation, m - running_max, bound_lo - min(row), m - bound_hi)
        running_max = m
    tol = CRITERIA["energy_residual_abs_floor_J"] + CRITERIA["energy_residual_relative"] * abs(out["exported_front_J"] + out["exported_rear_J"])
    return {"max_extremum_violation_K": violation, "energy_residual_J": out["energy_residual_J"],
            "stored_change_J": out["stored_change_J"], "exports_J": [out["exported_front_J"], out["exported_rear_J"]],
            "passed": violation <= 1e-10 and abs(out["energy_residual_J"]) <= tol and out["stored_change_J"] < 0.0}


def _rows_max_difference(a: Sequence[TraceRow], b: Sequence[TraceRow]) -> float:
    if len(a) != len(b):
        raise ValueError("trace lengths differ")
    worst = 0.0
    for ra, rb in zip(a, b):
        worst = max(worst, abs(ra.time_s - rb.time_s), abs(ra.body_power_W - rb.body_power_W),
                    abs(ra.sensor_power_W - rb.sensor_power_W), abs(ra.front_flux_W - rb.front_flux_W),
                    abs(ra.rear_flux_W - rb.rear_flux_W), abs(ra.surface_C - rb.surface_C),
                    max(abs(x - y) for x, y in zip(ra.temperatures_C, rb.temperatures_C)))
    return worst


def check_f1_f3_identity(numerics: Numerics, stack: str = "H1", n_silicone: int = 2, n_film: int = 1) -> Dict:
    f1 = run_from_spec({"run_id": "chk-F1", "stack": stack, "case": "F1", "perturbation": {}}, numerics, n_silicone, n_film)
    f3 = run_from_spec({"run_id": "chk-F3", "stack": stack, "case": "F3", "perturbation": {}}, numerics, n_silicone, n_film)
    physical = _rows_max_difference(f1.rows, f3.rows)
    before = max((abs(a["sensor_reported_C"] - b["sensor_reported_C"]) for a, b in zip(f1.samples, f3.samples)
                  if a["time_s"] < 600.0 - GRID_TOLERANCE), default=0.0)
    after = max((abs(a["sensor_reported_C"] - b["sensor_reported_C"]) for a, b in zip(f1.samples, f3.samples)
                 if a["time_s"] >= 600.0 - GRID_TOLERANCE), default=0.0)
    return {"criterion_K": CRITERIA["f1_f3_physical_identity_K"], "max_physical_trace_difference": physical,
            "reported_difference_before_600s_K": before, "max_reported_difference_from_600s_K": after,
            "passed": physical <= CRITERIA["f1_f3_physical_identity_K"] and before == 0.0 and after > 0.0}


def check_event_continuity(numerics: Numerics, stacks: Sequence[str] = STACK_NAMES, n_silicone: int = 2,
                           n_film: int = 1, cases=("F1", "F2", "F5")) -> Dict:
    worst_pre, worst_jump, details = 0.0, 0.0, []
    bound = CRITERIA["post_event_single_step_change_bound_K"]
    for stack in stacks:
        f0 = run_from_spec({"run_id": "chk-F0", "stack": stack, "case": "F0", "perturbation": {}}, numerics, n_silicone, n_film)
        for case in cases:
            res = run_from_spec({"run_id": f"chk-{case}", "stack": stack, "case": case, "perturbation": {}}, numerics, n_silicone, n_film)
            fs = _grid_steps(600.0, numerics.dt_s)
            pre = _rows_max_difference(f0.rows[:fs + 1], res.rows[:fs + 1])
            jump = max(abs(a - b) for a, b in zip(res.rows[fs + 1].temperatures_C, res.rows[fs].temperatures_C))
            ev = [e for e in res.summary["events"] if e["kind"] == "fault"]
            continuous = bool(ev) and ev[0]["state_before_C"] == ev[0]["state_after_C"]
            worst_pre, worst_jump = max(worst_pre, pre), max(worst_jump, jump)
            details.append({"stack": stack, "case": case, "pre_fault_difference_to_F0": pre,
                            "first_post_fault_step_change_K": jump, "state_continuous": continuous,
                            "fluxes_before": ev[0]["fluxes_before"] if ev else None,
                            "fluxes_after": ev[0]["fluxes_after"] if ev else None})
    return {"criterion_jump_K": bound, "observed_pre_fault_difference": worst_pre, "observed_max_jump_K": worst_jump,
            "passed": worst_pre == 0.0 and worst_jump <= bound and all(d["state_continuous"] for d in details),
            "details": details}


def _max_sample_difference(a: Sequence[Dict], b: Sequence[Dict],
                           keys=("surface_actual_C", "sensor_actual_C", "H_C")) -> Dict[str, float]:
    if len(a) != len(b):
        raise ValueError("sample grids differ in length")
    out = {}
    for key in keys:
        worst = 0.0
        for ra, rb in zip(a, b):
            if abs(ra["time_s"] - rb["time_s"]) > GRID_TOLERANCE:
                raise ValueError("sample times differ")
            worst = max(worst, abs(ra[key] - rb[key]))
        out[key] = worst
    return out


def check_time_refinement(stacks: Sequence[str] = STACK_NAMES, horizon_s: float = 3600.0, n_silicone: int = 2,
                          n_film: int = 1, cases=("F1", "F2")) -> Dict:
    dts = tuple(CRITERIA["time_refinement_dts_s"])
    crit = CRITERIA["time_refinement_K"]
    all_pass, details = True, []
    for stack in stacks:
        for case in cases:
            samples = {}
            for dt in dts:
                samples[dt] = run_from_spec({"run_id": f"tr-{case}-{dt}", "stack": stack, "case": case, "perturbation": {}},
                                            Numerics(dt_s=dt, horizon_s=horizon_s), n_silicone, n_film).samples
            pairs = {}
            for coarse, fine in zip(dts, dts[1:]):
                pairs[f"{coarse:g}_vs_{fine:g}"] = _max_sample_difference(samples[coarse], samples[fine])
            coarse_pair = pairs[f"{dts[0]:g}_vs_{dts[1]:g}"]
            fine_pair = pairs[f"{dts[1]:g}_vs_{dts[2]:g}"]
            ok = all(fine_pair[k] < crit and (fine_pair[k] < coarse_pair[k] or fine_pair[k] <= 1e-12) for k in fine_pair)
            all_pass = all_pass and ok
            details.append({"stack": stack, "case": case, "pairs_K": pairs, "passed": ok})
    return {"criterion_K": crit, "dts_s": list(dts), "passed": all_pass, "details": details}


def check_mesh_refinement(stacks: Sequence[str] = STACK_NAMES, numerics: Optional[Numerics] = None,
                          n_silicone: int = 2, n_film: int = 1, cases=("F1", "F2")) -> Dict:
    numerics = numerics or Numerics()
    crit = CRITERIA["mesh_refinement_K"]
    finer = ((2 * n_silicone, n_film), (n_silicone, n_film + 2))
    all_pass, details = True, []
    for stack in stacks:
        for case in cases:
            spec = {"run_id": f"mr-{case}", "stack": stack, "case": case, "perturbation": {}}
            base = run_from_spec(spec, numerics, n_silicone, n_film)
            for ns, nf in finer:
                fine = run_from_spec(spec, numerics, ns, nf)
                diff = _max_sample_difference(base.samples, fine.samples)
                same_input = base.summary["energy"]["injected_J"] == fine.summary["energy"]["injected_J"]
                same_depths = base.summary["parameters"]["mesh"]["interface_depths_m"] == fine.summary["parameters"]["mesh"]["interface_depths_m"]
                tb, tf = base.summary["long_time_target_if_final_conditions_held"], fine.summary["long_time_target_if_final_conditions_held"]
                target_dev = max(abs(tb[k] - tf[k]) for k in ("H_C", "sensor_C", "surface_C")) if tb.get("status") == "unique" else 0.0
                ok = all(v < crit for v in diff.values()) and same_input and same_depths and target_dev <= CRITERIA["steady_match_K"]
                all_pass = all_pass and ok
                details.append({"stack": stack, "case": case, "base_mesh": [n_silicone, n_film], "fine_mesh": [ns, nf],
                                "max_difference_K": diff, "injected_identical": same_input,
                                "interface_depths_identical": same_depths, "steady_target_deviation_K": target_dev, "passed": ok})
    return {"criterion_K": crit, "passed": all_pass, "details": details}


def check_controller_sample_grid(stack: str = "H1", horizon_s: float = 3600.0, n_silicone: int = 2, n_film: int = 1) -> Dict:
    trips, details = [], []
    for dt in CRITERIA["time_refinement_dts_s"]:
        t = run_from_spec({"run_id": f"cg-F4T-{dt}", "stack": stack, "case": "F4T", "perturbation": {}},
                          Numerics(dt_s=dt, horizon_s=horizon_s), n_silicone, n_film).summary
        f = run_from_spec({"run_id": f"cg-F4F-{dt}", "stack": stack, "case": "F4F", "perturbation": {}},
                          Numerics(dt_s=dt, horizon_s=horizon_s), n_silicone, n_film).summary
        trips.append(t["controller"]["trip_time_s"])
        details.append({"dt_s": dt, "truthful_trip_time_s": t["controller"]["trip_time_s"],
                        "frozen_trip_time_s": f["controller"]["trip_time_s"],
                        "truthful_peak_H_C": t["peaks"]["H"]["value_C"], "frozen_peak_H_C": f["peaks"]["H"]["value_C"]})
    found = [x for x in trips if x is not None]
    spread = (max(found) - min(found)) if found else None
    consistent = len(found) in (0, len(trips))
    return {"criterion_spread_s": CRITERIA["controller_trip_grid_s"], "trip_times_s": trips, "spread_s": spread,
            "passed": consistent and (spread is None or spread <= CRITERIA["controller_trip_grid_s"]),
            "details": details, "note": "trip detected on the 1 s sample grid; not continuous-time protection"}


def run_verification(numerics: Optional[Numerics] = None, stacks: Sequence[str] = STACK_NAMES,
                     n_silicone: int = 2, n_film: int = 1) -> Dict:
    numerics = numerics or Numerics()
    return {
        "uniform_hold": check_uniform_hold(),
        "insulated_inventory": check_insulated_inventory(),
        "one_node_exponential": check_one_node_exponential(),
        "two_node_insulated_modes": check_two_node_insulated_modes(),
        "passive_exchange_cancellation": check_passive_exchange_cancellation(),
        "steady_match": check_steady_match(stacks),
        "long_time_approach_and_fixed_point": check_long_time_approach(stacks),
        "maximum_principle_no_inputs": check_maximum_principle(),
        "f1_f3_physical_identity": check_f1_f3_identity(numerics, stacks[0], n_silicone, n_film),
        "event_continuity": check_event_continuity(numerics, stacks, n_silicone, n_film),
        "time_refinement": check_time_refinement(stacks, numerics.horizon_s, n_silicone, n_film),
        "mesh_refinement": check_mesh_refinement(stacks, numerics, n_silicone, n_film),
        "controller_sample_grid": check_controller_sample_grid(stacks[0], numerics.horizon_s, n_silicone, n_film),
    }


def cross_check_lump2(by_id: Dict[str, Dict]) -> Dict:
    """Expectation (not acceptance) comparison against Coda's executed two-node T0-LUMP2-1."""
    exp = CRITERIA["cross_check_lump2_expectation_K"]
    rows, all_within = [], True
    for stack in STACK_NAMES:
        for case in ("F0", "F1"):
            s = by_id.get(f"{stack}-{case}-nominal")
            if s is None:
                continue
            ref = LUMP2_EXECUTED_REFERENCE[stack][case]
            cp = s["checkpoints"].get("3600")
            h3600 = cp["H_C"] if isinstance(cp, dict) else s["final_state"]["H_C"]
            d = {"peak_H": abs(s["peaks"]["H"]["value_C"] - ref["peak_H_C"]),
                 "peak_surface": abs(s["peaks"]["surface_actual"]["value_C"] - ref["peak_surface_C"]),
                 "H_at_3600": abs(h3600 - ref["H_3600_C"])}
            within = all(d[k] <= exp[k] for k in d)
            all_within = all_within and within
            rows.append({"stack": stack, "case": case, "fv_peak_H_C": s["peaks"]["H"]["value_C"],
                         "fv_peak_H_time_s": s["peaks"]["H"]["time_s"],
                         "fv_peak_surface_C": s["peaks"]["surface_actual"]["value_C"],
                         "fv_peak_surface_time_s": s["peaks"]["surface_actual"]["time_s"], "fv_H_3600_C": h3600,
                         "lump2": ref, "abs_difference_K": d, "within_expectation": within})
    return {"expectation_K": exp, "rows": rows, "all_within_expectation": all_within if rows else None,
            "meaning": "agreement between two models of the same contract; validates nothing physical"}


def evaluate_acceptance(verification: Optional[Dict], run_summaries: Sequence[Dict], cross_check: Optional[Dict]) -> Dict:
    checks = []
    for name, item in (verification or {}).items():
        checks.append({"check": name, "passed": bool(item.get("passed")), "action_if_unmet": "stop dependent comparisons; preserve run"})
    if run_summaries:
        energy_ok = all(s["energy"]["within_predeclared_tolerance"] for s in run_summaries)
        power_ok = all(s["energy"]["max_instantaneous_power_residual_W"] <= CRITERIA["instantaneous_power_residual_W"] for s in run_summaries)
        recon_ok = all(abs(s["energy"]["reconstructed_residual_J"]) <= 1e-8 for s in run_summaries)
        checks.append({"check": "energy_audit_all_runs", "passed": energy_ok and power_ok and recon_ok,
                       "runs_outside_tolerance": [s["run_id"] for s in run_summaries if not s["energy"]["within_predeclared_tolerance"]],
                       "action_if_unmet": "exclude listed runs from comparisons; preserve them"})
    failed = [c["check"] for c in checks if not c["passed"]]
    return {"all_predeclared_checks_passed": not failed, "failed_checks": failed, "checks": checks,
            "cross_check_lump2_within_expectation": (cross_check or {}).get("all_within_expectation"),
            "policy": "criteria fixed before results; failed runs preserved; no post-hoc loosening",
            "meaning": "verification of the model's numerics only; not physical accuracy"}


# ---------------------------------------------------------------------------
# suite, output, CLI
# ---------------------------------------------------------------------------
def run_suite(numerics: Optional[Numerics] = None, stacks: Sequence[str] = STACK_NAMES,
              run_ids: Optional[Sequence[str]] = None, include_verification: bool = True,
              n_silicone: int = 2, n_film: int = 1) -> Dict:
    numerics = numerics or Numerics()
    wanted_stacks = set(stacks)
    specs = [s for s in deterministic_run_list() if s["stack"] in wanted_stacks]
    if run_ids is not None:
        wanted = set(run_ids)
        specs = [s for s in specs if s["run_id"] in wanted]
    summaries = [run_from_spec(spec, numerics, n_silicone, n_film).summary for spec in specs]
    by_id = {s["run_id"]: s for s in summaries}
    payload = {"model_id": MODEL_ID, "module_version": MODULE_VERSION, "contract_version": CONTRACT_VERSION,
               "status": "executed_synthetic_model_runs_if_this_file_exists; physical_validation=false",
               "numerics": asdict(numerics), "production_mesh": {"n_silicone": n_silicone, "n_film": n_film},
               "scenario_table": CASE_DESCRIPTIONS, "run_list": specs, "run_count": len(summaries),
               "runs": summaries, "assumption_ledger": ASSUMPTION_LEDGER, "criteria": CRITERIA,
               "credits": {"packet_and_contract": "Coda (Codex Lily)", "steady_reference_and_LUMP2": "Coda",
                           "earlier_steady_contract_work": "Claude Fable 5.1 (not reproduced)",
                           "fv_module": "Red's Claude contributor (text only)", "coordination": "Red with Richard (Andrei) Pemberton"}}
    payload["verification"] = run_verification(numerics, tuple(stacks), n_silicone, n_film) if include_verification else None
    payload["cross_check_against_lump2"] = cross_check_lump2(by_id)
    payload["acceptance"] = evaluate_acceptance(payload["verification"], summaries, payload["cross_check_against_lump2"])
    return payload


def write_results(payload: Dict, output_path: str, overwrite: bool = False) -> str:
    import os
    if os.path.exists(output_path) and not overwrite:
        raise FileExistsError(f"refusing to overwrite {output_path}; pass overwrite=True")
    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(_jsonable(payload), handle, indent=1)
        handle.write("\n")
    return output_path


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="T0-FV1D-1 finite-volume transient fault suite (synthetic model only)")
    parser.add_argument("--output", required=True, help="caller-supplied JSON output path (only file written)")
    parser.add_argument("--dt", type=float, default=0.5)
    parser.add_argument("--n-silicone", type=int, default=2)
    parser.add_argument("--n-film", type=int, default=1)
    parser.add_argument("--quick", action="store_true", help="H1 only (runs and verification)")
    parser.add_argument("--skip-verification", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)
    stacks = ("H1",) if args.quick else STACK_NAMES
    payload = run_suite(Numerics(dt_s=args.dt), stacks, include_verification=not args.skip_verification,
                        n_silicone=args.n_silicone, n_film=args.n_film)
    write_results(payload, args.output, overwrite=args.overwrite)
    brief = {"output": args.output, "run_count": payload["run_count"],
             "acceptance": {k: payload["acceptance"][k] for k in ("all_predeclared_checks_passed", "failed_checks",
                                                                  "cross_check_lump2_within_expectation")},
             "nominal_peaks": {s["run_id"]: {"surface_C": s["peaks"]["surface_actual"]["value_C"],
                                             "surface_t_s": s["peaks"]["surface_actual"]["time_s"],
                                             "H_C": s["peaks"]["H"]["value_C"], "H_t_s": s["peaks"]["H"]["time_s"],
                                             "energy_ok": s["energy"]["within_predeclared_tolerance"]}
                               for s in payload["runs"] if s["perturbation"] == {}}}
    print(json.dumps(_jsonable(brief)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
