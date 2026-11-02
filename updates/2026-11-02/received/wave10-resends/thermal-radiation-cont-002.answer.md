# thermal-radiation-001 — continuation (Red, Claude/Anthropic, for Richard (Andrei) Pemberton)

Continuation of the earlier instance's partial answer. Nothing here was executed by me (no tools); all tolerances are design values awaiting Red's sandbox run. Credit: model reference and float fixtures are Coda's (Codex Lily) executed T0-HYP-1 / T0-LUMP2-1 artefacts quoted in the bundle; the fixture module below transcribes them verbatim (labelled), it does not recompute them.

## Blocking defect in the delivered material: truncated file

`validation/thermal_radiation/thermal_radiation.py` was cut mid-statement. Minimal repair instruction for Red (no other delivered line changes):

1. Delete the final partial line of the truncated file, which reads exactly `            if lo < candidate < hi and abs(`.
2. Append the block below (`FILE: … thermal_radiation.py — CONTINUATION`). Its first line is the complete form of that deleted line, at the same 12-space indent inside `solve_canonical`.

FILE: validation/thermal_radiation/thermal_radiation.py — CONTINUATION (append after deleting the truncated last line)
```python
            if lo < candidate < hi and abs(2.0*f) <= abs(dx_old*df):
                newton = candidate
        dx_old = dx
        if newton is None:
            T_new = lo + 0.5*(hi - lo)              # bisection: bracket halves
            bisections += 1
        else:
            T_new = newton                          # Newton: |step| <= |dx_old|/2 by the rule above
        dx = T_new - T
        f_new = gamma(T_new)
        if f_new == 0.0:
            return ScalarSolution(T_new, iterations, bisections, 0.0, lo0, hi0, lo, hi)
        if f_new < 0.0:
            lo = T_new
        else:
            hi = T_new
        scale = (abs(K*T_new) + abs(D)
                 + M*(abs(front.convective_flux(T_new)) + abs(front.radiative_flux(T_new))))
        if (abs(f_new) <= RESIDUAL_FLOOR_FACTOR*EPSILON_MACHINE*scale
                or abs(dx) <= rel_tol*abs(T_new)
                or hi - lo <= rel_tol*hi
                or T_new == T):
            return ScalarSolution(T_new, iterations, bisections, f_new, lo0, hi0, lo, hi)
        T, f, df = T_new, f_new, dgamma(T_new)
    raise RuntimeError("Safeguarded Newton reached the iteration cap without convergence")


from dataclasses import asdict


# ----------------------------------------------------------------------------------------------
# Exact rational eps = 0 network (for the exactness check against Coda's reference_results.json)
# ----------------------------------------------------------------------------------------------
def _frac(value):
    """Exact rational from int, Fraction or decimal/ratio string; floats go through str()
    (Coda's convention), so 0.1 means 1/10 rather than the binary double."""
    if isinstance(value, bool):
        raise ValueError("Boolean is not a number")
    if isinstance(value, Fraction):
        return value
    if isinstance(value, (int, str)):
        return Fraction(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("Nonfinite value")
        return Fraction(str(value))
    raise ValueError("Unsupported numeric type")


def steady_linear_exact(R_HS, R_SO, R_rej, hA, P, J, T_amb, T_res):
    """Exact rational eps = 0 steady network in H/S/O/q variables (any consistent temperature
    unit; the algebra is translation invariant).  R_rej = math.inf blocks the rear; hA = 0 closes
    the front.  Same connectivity and source placement as Coda's thermal_reference.steady."""
    blocked = isinstance(R_rej, float) and math.isinf(R_rej)
    R_HS, R_SO, hA, P, J, T_amb, T_res = (_frac(x) for x in (R_HS, R_SO, hA, P, J, T_amb, T_res))
    if min(R_HS, R_SO, hA, P, J) < 0:
        raise ValueError("Negative resistance/conductance/source outside the reference domain")
    if not blocked:
        R_rej = _frac(R_rej)
        if R_rej <= 0:
            raise ValueError("R_rej must be positive or math.inf")
    front_open = hA > 0
    if blocked and not front_open:
        return {"status": "no_finite_steady_state" if P + J > 0 else "nonunique"}
    if blocked:
        q = P + J
        O = T_amb + q/hA
    elif not front_open:
        q = Fraction(0)
        O = T_res + R_rej*(P + J) + R_HS*J          # isothermal front side, nothing leaves
    else:
        E = T_res + R_rej*(P + J) + R_HS*J
        q = (E - T_amb)/(R_HS + R_SO + R_rej + 1/hA)
        O = T_amb + q/hA
    S = O + R_SO*q
    H = S + R_HS*(q - J)
    q_rear = Fraction(0) if blocked else (H - T_res)/R_rej
    return {"status": "unique", "H": H, "S": S, "surface": O, "front": q, "rear": q_rear,
            "balance": P + J - q - q_rear}


def nominal_steady_exact(stack, body_power, h="8", blocked_rear=False, R_rej="2",
                         sensor_power="0.1", T_amb="25", T_res="25"):
    """Exact rational T0-HYP-1 row in Celsius (eps = 0), for Fraction/float equality checks."""
    res = exact_stack_resistances(stack)
    rear = math.inf if blocked_rear else _frac(R_rej)
    out = steady_linear_exact(res["R_HS"], res["R_SO"], rear, _frac(h)*res["area"],
                              body_power, sensor_power, T_amb, T_res)
    out.update(stack=stack, body_power=_frac(body_power), sensor_power=_frac(sensor_power),
               rear_blocked=blocked_rear, R_HS=res["R_HS"], R_SO=res["R_SO"])
    return out


# ----------------------------------------------------------------------------------------------
# Nonlinear steady network T0-RAD-1
# ----------------------------------------------------------------------------------------------
def _admit_steady_inputs(R_HS, R_SO, R_rej, front, P, J, T_res_K):
    R_HS = finite_number(R_HS, "R_HS")
    R_SO = finite_number(R_SO, "R_SO")
    R_rej = finite_number(R_rej, "R_rej", allow_inf=True)
    P = finite_number(P, "P")
    J = finite_number(J, "J")
    T_res_K = finite_number(T_res_K, "T_res_K")
    if not isinstance(front, FrontBoundary):
        raise ValueError("front must be a FrontBoundary")
    if R_HS < 0.0 or R_SO < 0.0:
        raise ValueError("Negative resistance")
    if R_rej <= 0.0:
        raise ValueError("R_rej must be positive or +inf (blocked)")
    if P < 0.0 or J < 0.0:
        raise ValueError("Negative source outside the proven domain")
    if T_res_K <= 0.0:
        raise ValueError("Reservoir temperature must be positive Kelvin")
    return R_HS, R_SO, R_rej, P, J, T_res_K


def _canonical_coefficients(R_HS, R_SO, R_rej, P, J, T_res_K):
    """(K, M, D, R_th, E, rear_open) of K*T + M*Phi(T) = D (ANALYSIS.md section 3)."""
    if math.isfinite(R_rej):
        R_th = R_HS + R_SO + R_rej
        E = T_res_K + R_rej*(P + J) + R_HS*J
        return 1.0/R_th, 1.0, E/R_th, R_th, E, True
    return 0.0, 1.0, P + J, math.inf, None, False


def steady_radiative(R_HS, R_SO, R_rej, front, P, J, T_res_K):
    """Unique steady state of the H-S-O network with convection + grey-body radiation at O.
    All temperatures Kelvin.  Fluxes positive outward; q_rear is the ideal reservoir's demand."""
    R_HS, R_SO, R_rej, P, J, T_res_K = _admit_steady_inputs(R_HS, R_SO, R_rej, front, P, J, T_res_K)
    rear_open = math.isfinite(R_rej)
    base = dict(R_HS_K_W=R_HS, R_SO_K_W=R_SO, R_rej_K_W=(R_rej if rear_open else None),
                rear_blocked=not rear_open, P_W=P, J_W=J, T_amb_K=front.T_amb_K,
                T_sur_K=front.T_sur_K, T_res_K=T_res_K, h_W_m2K=front.h, eps=front.eps,
                area_m2=front.area)
    if not rear_open and not front.exit_open():
        base["status"] = "no_finite_steady_state" if P + J > 0.0 else "nonunique"
        return base
    K, M, D, R_th, E, _ = _canonical_coefficients(R_HS, R_SO, R_rej, P, J, T_res_K)
    sol = solve_canonical(K, M, D, front)
    O = sol.T_K
    q_conv = front.convective_flux(O)
    q_rad = front.radiative_flux(O)
    q = q_conv + q_rad
    if rear_open:
        H = T_res_K + R_rej*(P + J - q)
        q_rear = (H - T_res_K)/R_rej
        S = H - R_HS*(q - J)
    else:
        q_rear = 0.0
        S = O + R_SO*q
        H = S + R_HS*(q - J)
    base.update(status="unique", T_H_K=H, T_S_K=S, T_O_K=O,
                T_H_C=celsius(H), T_S_C=celsius(S), T_O_C=celsius(O),
                q_front_W=q, q_conv_W=q_conv, q_rad_W=q_rad, q_rear_W=q_rear, q_HS_W=q - J,
                balance_W=P + J - q - q_rear,
                node_balance_H_W=P - (q - J) - q_rear,
                residual_front_K=(S - O) - R_SO*q,
                K_W_K=K, M=M, D_W=D, R_th_K_W=(R_th if rear_open else None), E_K=E,
                newton=asdict(sol),
                margin_surface_40C_K=40.0 - celsius(O),
                margin_internal_60C_K=60.0 - celsius(H),
                comparator_label="study_comparator_only")
    return base


def nominal_inputs(stack, h=8.0, eps=0.0, blocked_rear=False, R_rej=NOMINAL_R_REJ_K_W,
                   T_amb_C=25.0, T_sur_C=25.0, T_res_C=25.0):
    """Float nominal T0-HYP-1 inputs for a stack: (R_HS, R_SO, R_rej, FrontBoundary, T_res_K)."""
    res = exact_stack_resistances(stack)
    front = FrontBoundary(h=h, eps=eps, area=AREA_M2, T_amb_K=kelvin(T_amb_C), T_sur_K=kelvin(T_sur_C))
    return float(res["R_HS"]), float(res["R_SO"]), (math.inf if blocked_rear else R_rej), front, kelvin(T_res_C)


def nominal_steady(stack, body_power, h=8.0, eps=0.0, blocked_rear=False, R_rej=NOMINAL_R_REJ_K_W,
                   T_amb_C=25.0, T_sur_C=25.0, T_res_C=25.0, sensor_power=NOMINAL_SENSOR_POWER_W):
    R_HS, R_SO, rear, front, T_res_K = nominal_inputs(stack, h, eps, blocked_rear, R_rej,
                                                      T_amb_C, T_sur_C, T_res_C)
    out = steady_radiative(R_HS, R_SO, rear, front, body_power, sensor_power, T_res_K)
    out.update(stack=stack, body_power_W=float(body_power), sensor_power_W=float(sensor_power))
    return out


# ----------------------------------------------------------------------------------------------
# Linearized radiative coefficient h_r = 4 eps sigma T_m^3 (ANALYSIS.md section 7)
# ----------------------------------------------------------------------------------------------
def linearized_h_r(eps, T_m_K):
    """W/(m2 K)."""
    return 4.0*eps*SIGMA_W_M2K4*T_m_K**3


def flux_linearization(front, T_K, T_m_K):
    """Flux-level comparison of eps*sigma*A*(T^4 - Tw^4) with h_r*A*(T - Tw), h_r at T_m.
    Returns the exact error, the rigorous bound (B1) and the arithmetic-mean identity values."""
    Tw = front.T_sur_K
    dT = T_K - Tw
    Tbar = 0.5*(T_K + Tw)
    c = front.radiation_constant
    h_r = linearized_h_r(front.eps, T_m_K)
    exact = front.radiative_flux(T_K)
    linear = h_r*front.area*dT
    error = exact - linear
    bound_B1 = c*abs(dT)*(12.0*max(Tbar, T_m_K)**2*abs(Tbar - T_m_K) + Tbar*dT*dT)
    return dict(T_K=T_K, T_m_K=T_m_K, delta_T_K=dT, T_bar_K=Tbar, h_r_W_m2K=h_r,
                exact_W=exact, linear_W=linear, error_W=error, bound_B1_W=bound_B1,
                bound_B1_holds=abs(error) <= bound_B1*(1.0 + 1e-12) + 1e-300,
                mean_identity_W=c*dT*(4.0*Tbar**3 + Tbar*dT*dT),
                e_mean_relative=dT*dT/(4.0*Tbar*Tbar),
                relative_error=(error/linear if linear != 0.0 else None))


def steady_linearized(R_HS, R_SO, R_rej, front, h_r, P, J, T_res_K):
    """Linear network with Phi replaced by hA(T-Ta) + h_r*A*(T-Tw), h_r fixed a priori."""
    R_HS, R_SO, R_rej, P, J, T_res_K = _admit_steady_inputs(R_HS, R_SO, R_rej, front, P, J, T_res_K)
    h_r = finite_number(h_r, "h_r")
    if h_r < 0.0:
        raise ValueError("h_r must be nonnegative")
    rear_open = math.isfinite(R_rej)
    K, M, D, R_th, E, _ = _canonical_coefficients(R_HS, R_SO, R_rej, P, J, T_res_K)
    G = K + M*(front.hA + h_r*front.area)
    if G <= 0.0:
        raise ValueError("Linearized network has no exit path")
    O = (D + M*(front.hA*front.T_amb_K + h_r*front.area*front.T_sur_K))/G
    q = front.hA*(O - front.T_amb_K) + h_r*front.area*(O - front.T_sur_K)
    if rear_open:
        H = T_res_K + R_rej*(P + J - q)
        q_rear = (H - T_res_K)/R_rej
        S = H - R_HS*(q - J)
    else:
        q_rear = 0.0
        S = O + R_SO*q
        H = S + R_HS*(q - J)
    return dict(status="unique", h_r_W_m2K=h_r, T_H_K=H, T_S_K=S, T_O_K=O, q_front_W=q,
                q_rear_W=q_rear, G_lin_W_K=G, K_W_K=K, M=M, D_W=D)


def linearization_error_analysis(R_HS, R_SO, R_rej, front, P, J, T_res_K, T_m_K, exact_row=None):
    """Solution-level error of the linearized coefficient: identity (B2), a priori bound (B3),
    H-propagation identity and sign information, against the exact nonlinear solution."""
    if exact_row is None:
        exact_row = steady_radiative(R_HS, R_SO, R_rej, front, P, J, T_res_K)
    if exact_row["status"] != "unique":
        raise ValueError("Exact row is not a unique steady state")
    T_m_K = finite_number(T_m_K, "T_m_K")
    if T_m_K <= 0.0:
        raise ValueError("T_m must be positive Kelvin")
    h_r = linearized_h_r(front.eps, T_m_K)
    lin = steady_linearized(R_HS, R_SO, R_rej, front, h_r, P, J, T_res_K)
    K, M, D, G = exact_row["K_W_K"], exact_row["M"], exact_row["D_W"], lin["G_lin_W_K"]
    O_star = exact_row["T_O_K"]
    Tw = front.T_sur_K

    def dq(T):
        return front.radiative_flux(T) - h_r*front.area*(T - Tw)

    predicted = M*dq(O_star)/G
    observed = lin["T_O_K"] - O_star
    lo, hi = canonical_bracket(K, M, D, front)
    candidates = [abs(dq(lo)), abs(dq(hi))]
    if lo <= T_m_K <= hi:
        candidates.append(abs(dq(T_m_K)))
    bound_B3 = M*max(candidates)/G
    rear_open = exact_row["R_rej_K_W"] is not None
    factor_H = exact_row["R_rej_K_W"]/exact_row["R_th_K_W"] if rear_open else 1.0
    error_H = lin["T_H_K"] - exact_row["T_H_K"]
    Tbar = 0.5*(O_star + Tw)
    dT = O_star - Tw
    return dict(T_m_K=T_m_K, h_r_W_m2K=h_r, T_O_lin_K=lin["T_O_K"], T_S_lin_K=lin["T_S_K"],
                T_H_lin_K=lin["T_H_K"], error_O_K=observed, error_H_K=error_H,
                predicted_error_O_K=predicted, identity_B2_residual_K=observed - predicted,
                identity_H_residual_K=error_H - factor_H*observed,
                bound_B3_K=bound_B3, bound_B3_holds=abs(observed) <= bound_B3 + 1e-9,
                bracket_K=[lo, hi], delta_q_at_exact_W=dq(O_star), T_bar_exact_K=Tbar,
                mean_cubic_law_K=M*front.radiation_constant*Tbar*dT**3/G,
                T_m_at_or_below_true_mean=T_m_K <= Tbar + 1e-12)


# ----------------------------------------------------------------------------------------------
# Two-node transient T0-LUMP2-RAD-1 (explicit reimplementation of Coda's documented structure)
# ----------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class TransientParameters:
    """ch, cs J/K; g = 1/R_HS W/K; R_SO K/W; gr = 1/R_rej W/K (0 = blocked); reservoir Kelvin."""
    ch: float
    cs: float
    g: float
    R_SO: float
    gr: float
    reservoir_K: float
    front: FrontBoundary

    def __post_init__(self):
        for name in ("ch", "cs", "g", "R_SO", "gr", "reservoir_K"):
            object.__setattr__(self, name, finite_number(getattr(self, name), name))
        if not isinstance(self.front, FrontBoundary):
            raise ValueError("front must be a FrontBoundary")
        if self.ch <= 0.0 or self.cs <= 0.0:
            raise ValueError("Capacities must be positive")
        if min(self.g, self.R_SO, self.gr) < 0.0:
            raise ValueError("Negative passive parameter")
        if self.reservoir_K <= 0.0:
            raise ValueError("Reservoir temperature must be positive Kelvin")


def nominal_transient(stack, h=8.0, eps=0.0, R_rej=NOMINAL_R_REJ_K_W, T_amb_C=25.0, T_sur_C=25.0,
                      T_res_C=25.0, ch=NOMINAL_C_H_J_K):
    R_HS, R_SO, rear, front, T_res_K = nominal_inputs(stack, h, eps, False, R_rej, T_amb_C, T_sur_C, T_res_C)
    gr = 0.0 if math.isinf(rear) else 1.0/rear
    return TransientParameters(ch=ch, cs=nominal_panel_capacity(stack), g=1.0/R_HS, R_SO=R_SO,
                               gr=gr, reservoir_K=T_res_K, front=front)


def surface_from_sensor(params, S_K):
    """Massless-surface relation (S - O)/R_SO = Phi(O) for a given S (used for the t = 0 row)."""
    if params.R_SO == 0.0:
        return S_K, params.front.flux(S_K), None
    K = 1.0/params.R_SO
    sol = solve_canonical(K, 1.0, S_K*K, params.front)
    return sol.T_K, params.front.flux(sol.T_K), sol


def implicit_step(params, H_K, S_K, P, J, step):
    """One backward-Euler step; the nonlinear massless surface is solved implicitly
    (kappa*O + (1 + kappa*R_SO)*Phi(O) = D_n, ANALYSIS.md section 6)."""
    alpha = params.ch/step + params.g + params.gr
    beta = params.ch*H_K/step + P + params.gr*params.reservoir_K
    kappa = params.cs/step + params.g*(params.ch/step + params.gr)/alpha
    D = params.cs*S_K/step + J + params.g*beta/alpha
    M = 1.0 + kappa*params.R_SO
    sol = solve_canonical(kappa, M, D, params.front)
    O = sol.T_K
    q = params.front.flux(O)
    S_new = O + params.R_SO*q
    H_new = (beta + params.g*S_new)/alpha
    return H_new, S_new, O, q, sol


def simulate(params, initial_K, segments, dt):
    """Backward Euler over segments {duration, p, j, optional gr}; Kelvin states.
    Same admission structure, step budget and end-step energy audit as T0-LUMP2-1."""
    if not isinstance(params, TransientParameters):
        raise ValueError("TransientParameters required")
    dt = finite_number(dt, "dt")
    if dt <= 0.0:
        raise ValueError("dt must be positive")
    if not isinstance(initial_K, (tuple, list)) or len(initial_K) != 2:
        raise ValueError("Two initial Kelvin states required")
    H, S = (finite_number(v, "initial state") for v in initial_K)
    if H <= 0.0 or S <= 0.0:
        raise ValueError("Initial states must be positive Kelvin")
    if not isinstance(segments, (list, tuple)) or not segments:
        raise ValueError("Nonempty segment list required")
    admitted = []
    total_steps = 0
    active = params
    total_duration = 0.0
    for segment in segments:
        if not isinstance(segment, dict) or set(segment) - {"duration", "p", "j", "gr"}:
            raise ValueError("Unknown segment field")
        if not {"duration", "p", "j"} <= set(segment):
            raise ValueError("Missing segment field")
        duration = finite_number(segment["duration"], "duration")
        P = finite_number(segment["p"], "body power")
        J = finite_number(segment["j"], "sensor power")
        if duration <= 0.0:
            raise ValueError("duration must be positive")
        if not 0.0 <= P <= P_MAX_W or not 0.0 <= J <= J_MAX_W:
            raise ValueError("Source outside bounded study envelope")
        if "gr" in segment:
            active = replace(active, gr=segment["gr"])
        ratio = duration/dt
        if not math.isfinite(ratio) or ratio > MAX_STEPS:
            raise ValueError("Step budget exceeded")
        count = math.ceil(ratio)
        total_steps += count
        if total_steps > MAX_STEPS:
            raise ValueError("Step budget exceeded")
        total_duration += duration
        if not math.isfinite(total_duration):
            raise ValueError("Nonfinite total horizon")
        admitted.append((duration, P, J, active, count))

    initial_H, initial_S = H, S
    first = admitted[0][3]
    O0, q0, sol0 = surface_from_sensor(first, S)
    newton0 = sol0.iterations if sol0 is not None else 0
    time = 0.0
    injected = exported_front = exported_rear = throughput = max_residual = 0.0
    max_newton = total_newton = newton0
    trace = [dict(time=0.0, dt=0.0, H_K=H, S_K=S, O_K=O0, front_W=q0,
                  conv_W=first.front.convective_flux(O0), rad_W=first.front.radiative_flux(O0),
                  rear_W=first.gr*(H - first.reservoir_K), p_W=admitted[0][1], j_W=admitted[0][2],
                  energy_residual_J=0.0, newton_iterations=newton0)]
    events = []
    previous_gr = params.gr
    for duration, P, J, active, count in admitted:
        start = time
        end = start + duration
        events.append(dict(time=start, before_state_K=[H, S], after_state_K=[H, S],
                           old_gr=previous_gr, new_gr=active.gr, p_W=P, j_W=J))
        previous_gr = active.gr
        for index in range(count):
            step = dt if index < count - 1 else duration - (count - 1)*dt
            if step <= 0.0:
                raise ValueError("Nonpositive final step")
            H_new, S_new, O, q, sol = implicit_step(active, H, S, P, J, step)
            rear = active.gr*(H_new - active.reservoir_K)
            if not all(math.isfinite(x) for x in (H_new, S_new, O, q, rear)):
                raise ValueError("Nonfinite numerical state/flux")
            H, S = H_new, S_new
            time = end if index == count - 1 else start + (index + 1)*dt
            injected += step*(P + J)
            exported_front += step*q
            exported_rear += step*rear
            throughput += step*(abs(P) + abs(J) + abs(q) + abs(rear))
            delta_energy = params.ch*(H - initial_H) + params.cs*(S - initial_S)
            residual = delta_energy - injected + exported_front + exported_rear
            max_residual = max(max_residual, abs(residual))
            max_newton = max(max_newton, sol.iterations)
            total_newton += sol.iterations
            trace.append(dict(time=time, dt=step, H_K=H, S_K=S, O_K=O, front_W=q,
                              conv_W=active.front.convective_flux(O), rad_W=active.front.radiative_flux(O),
                              rear_W=rear, p_W=P, j_W=J, energy_residual_J=residual,
                              newton_iterations=sol.iterations))
    return dict(model="T0-LUMP2-RAD-1", trace=trace, events=events, steps=total_steps,
                injected_J=injected, exported_front_J=exported_front, exported_rear_J=exported_rear,
                final_stored_energy_change_J=params.ch*(H - initial_H) + params.cs*(S - initial_S),
                max_energy_residual_abs_J=max_residual,
                energy_tolerance_J=1e-8 + 1e-10*throughput,
                max_newton_iterations=max_newton, total_newton_iterations=total_newton,
                physical_validation=False)


def trace_peak(trace, key):
    """Row holding the maximum of `key`; the first maximum is retained on ties."""
    best = trace[0]
    for row in trace[1:]:
        if row[key] > best[key]:
            best = row
    return best


def trace_at(trace, time_s, tol=1e-9):
    for row in trace:
        if abs(row["time"] - time_s) <= tol:
            return row
    raise KeyError(f"No trace row at t = {time_s} s")
```

FILE: validation/thermal_radiation/reference_fixture.py
```python
"""Verbatim transcription of Coda's (Codex Lily) EXECUTED reference values used as independent
test targets.  Nothing here is computed; every number is copied from the quoted sources.
Sources: validation/thermal/reference_results.json
         (sha256 e97cf35c8accb051096fdca20ec89a0a157015b863e94cb01020a8fdb5af3a56),
         validation/thermal_transient/REPORT.md
         (sha256 86f9b6107dc2e62b9e497454924c3463230bc96ba9495ab0bdc2baa24d6b25a6).
Celsius values; eps = 0 (no radiation); h = 8 W/(m2 K); R_rej = 2 K/W unless blocked."""

STEADY_ROWS = [
    dict(stack="H1", body_power=1, rear_blocked=False, H=26.90248230028146, S=26.891868221020427,
         surface=26.85948562324088, front=0.14875884985927018, rear=0.9512411501407299,
         front_exact="239951/1613020"),
    dict(stack="H1", body_power=5, rear_blocked=False, H=33.83119986113005, S=33.70398462379287,
         surface=33.55500086793716, front=0.6844000694349729, rear=4.415599930565027,
         front_exact="1103951/1613020"),
    dict(stack="H1", body_power=10, rear_blocked=False, H=42.492096812190795, S=42.21913012725842,
         surface=41.92439492380752, front=1.3539515939046014, rear=8.7460484060954,
         front_exact="2183951/1613020"),
    dict(stack="H1", body_power=5, rear_blocked=True, H=90.94862037037036, S=89.86019444444445,
         surface=88.75, front=5.1, rear=0.0, front_exact="51/10"),
    dict(stack="H2", body_power=1, rear_blocked=False, H=26.907261860110584, S=26.88858113572823,
         surface=26.829613374308842, front=0.14636906994470728, rear=0.9536309300552928,
         front_exact="241951/1653020"),
    dict(stack="H2", body_power=5, rear_blocked=False, H=33.86190245732054, S=33.6326495680521,
         surface=33.36310964174662, front=0.6690487713397297, rear=4.430951228660271,
         front_exact="1105951/1653020"),
    dict(stack="H2", body_power=10, rear_blocked=False, H=42.55520320383298, S=42.062735108456934,
         surface=41.52997997604385, front=1.3223983980835077, rear=8.777601601916492,
         front_exact="2185951/1653020"),
    dict(stack="H2", body_power=5, rear_blocked=True, H=92.81899074074074, S=90.80463888888889,
         surface=88.75, front=5.1, rear=0.0, front_exact="51/10"),
    dict(stack="H3", body_power=1, rear_blocked=False, H=26.916159074909697, S=26.883744465399086,
         surface=26.774005781814406, front=0.1419204625451524, rear=0.9580795374548476,
         front_exact="245951/1733020"),
    dict(stack="H3", body_power=5, rear_blocked=False, H=33.91905575238601, S=33.501140687023764,
         surface=33.00590154758745, front=0.6404721238069959, rear=4.459527876193004,
         front_exact="1109951/1733020"),
    dict(stack="H3", body_power=10, rear_blocked=False, H=42.6726765992314, S=41.772885964054616,
         surface=40.79577125480375, front=1.2636617003843003, rear=8.836338299615699,
         front_exact="2189951/1733020"),
    dict(stack="H3", body_power=5, rear_blocked=True, H=96.55973148148148, S=92.69352777777777,
         surface=88.75, front=5.1, rear=0.0, front_exact="51/10"),
]

# One-node analytic fixture and backward-Euler errors (reference_results.json).
ONE_NODE = dict(initial_C=20, bath_C=20, power_W=3, resistance_K_W=2, capacity_J_K=10, time_s=20,
                exact_C=23.792723352971347,
                backward_euler_abs_error_K={1.0: 0.05406025020934635, 0.5: 0.027307095158171535,
                                            0.25: 0.013724073533140313})

# Coupled equal-capacity two-node eigenmode check (REPORT.md): max errors at t = 1 s for dt .1/.05/.025.
TWO_NODE_MODE_ERRORS_K = (0.020207465088315557, 0.01016162613712357, 0.005091732219151546)

# REPORT.md fault-suite table, sensor-on cases (Celsius, 6 decimals as printed).
# ASSUMPTION (Red): the REPORT does not state the scenario timestep; dt = 1 s is assumed because
# peak times are reported at 1-second resolution.  A mismatch would show as a ~1e-2 K discrepancy.
TRANSIENT_REPORT = {
    ("H1", "intact"):    dict(peak_H_C=33.831193, peak_H_time_s=900.0, peak_surface_C=33.554994, H_3600_C=25.170303),
    ("H1", "rear_loss"): dict(peak_H_C=61.143480, peak_H_time_s=900.0, peak_surface_C=59.747155, H_3600_C=26.374204),
    ("H2", "intact"):    dict(peak_H_C=33.861287, peak_H_time_s=900.0, peak_surface_C=33.362444, H_3600_C=25.168602),
    ("H2", "rear_loss"): dict(peak_H_C=55.545063, peak_H_time_s=900.0, peak_surface_C=53.153638, H_3600_C=26.798252),
    ("H3", "intact"):    dict(peak_H_C=33.884652, peak_H_time_s=900.0, peak_surface_C=32.963939, H_3600_C=25.165436),
    ("H3", "rear_loss"): dict(peak_H_C=50.169875, peak_H_time_s=900.0, peak_surface_C=45.881263, H_3600_C=28.187988),
}
TRANSIENT_REPORT_DT_ASSUMED_S = 1.0


def fault_segments(loss, sensor_W=0.1):
    """Coda's fault schedule: 5 W body to 900 s then 0; sensor throughout; rear loss at 600 s.
    Three segments are used for both cases so that intact/loss traces share one time grid."""
    second = dict(duration=300, p=5, j=sensor_W)
    if loss:
        second["gr"] = 0.0
    return [dict(duration=600, p=5, j=sensor_W), second, dict(duration=2700, p=0, j=sensor_W)]
```

FILE: validation/thermal_radiation/test_thermal_radiation.py
```python
"""unittest suite for T0-RAD-1 / T0-LUMP2-RAD-1 (thermal-radiation-001).  Standard library only.
Expected values come from independent closed forms, exact rational arithmetic, or Coda's
transcribed executed fixtures -- never from the functions under test."""
import math
import os
import sys
import unittest
from fractions import Fraction

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import thermal_radiation as tr  # noqa: E402
import reference_fixture as fx  # noqa: E402

STACKS = ("H1", "H2", "H3")
POWERS = (1, 5, 10)
H_VALUES = (3.0, 8.0, 15.0)
EPS_VALUES = (0.0, 0.1, 0.5, 0.9)
T25 = tr.kelvin(25.0)


def coda_linear_step(params, H, S, P, J, step):
    """Coda's documented T0-LUMP2-1 backward-Euler 2x2 formula (rc_transient.simulate), with
    ga = 1/(R_SO + 1/(hA)) as the eps = 0 elimination of the massless surface."""
    ga = 1.0/(params.R_SO + 1.0/params.front.hA)
    A = params.ch/step + params.gr
    B = params.cs/step + ga
    det = A*B + params.g*(A + B)
    bh = params.ch*H/step + P + params.gr*params.reservoir_K
    bs = params.cs*S/step + J + ga*params.front.T_amb_K
    return (bh*(B + params.g) + params.g*bs)/det, (bs*(A + params.g) + params.g*bh)/det


class TestExactReference(unittest.TestCase):
    def test_eps_zero_fraction_equality_with_coda_rows(self):
        for row in fx.STEADY_ROWS:
            with self.subTest(stack=row["stack"], P=row["body_power"], blocked=row["rear_blocked"]):
                exact = tr.nominal_steady_exact(row["stack"], row["body_power"], blocked_rear=row["rear_blocked"])
                self.assertEqual(exact["status"], "unique")
                self.assertEqual(str(exact["front"]), row["front_exact"])
                self.assertEqual(exact["balance"], Fraction(0))
                for key in ("H", "S", "surface", "front", "rear"):
                    self.assertEqual(float(exact[key]), row[key])

    def test_eps_zero_newton_path_matches_reference_floats(self):
        for row in fx.STEADY_ROWS:
            with self.subTest(stack=row["stack"], P=row["body_power"], blocked=row["rear_blocked"]):
                out = tr.nominal_steady(row["stack"], row["body_power"], h=8.0, eps=0.0,
                                        blocked_rear=row["rear_blocked"])
                self.assertEqual(out["status"], "unique")
                self.assertLessEqual(abs(out["T_H_C"] - row["H"]), 1e-9)
                self.assertLessEqual(abs(out["T_S_C"] - row["S"]), 1e-9)
                self.assertLessEqual(abs(out["T_O_C"] - row["surface"]), 1e-9)
                self.assertLessEqual(abs(out["q_front_W"] - row["front"]), 1e-9)
                self.assertLessEqual(abs(out["q_rear_W"] - row["rear"]), 1e-9)
                self.assertEqual(out["q_rad_W"], 0.0)


class TestSteadyProperties(unittest.TestCase):
    def test_grid_unique_balanced_bracketed(self):
        for blocked, powers in ((False, POWERS), (True, (5,))):
            for stack in STACKS:
                for P in powers:
                    for h in H_VALUES:
                        for eps in EPS_VALUES:
                            with self.subTest(stack=stack, P=P, h=h, eps=eps, blocked=blocked):
                                out = tr.nominal_steady(stack, P, h=h, eps=eps, blocked_rear=blocked)
                                self.assertEqual(out["status"], "unique")
                                self.assertLessEqual(abs(out["balance_W"]), 1e-9)
                                self.assertLessEqual(abs(out["node_balance_H_W"]), 1e-9)
                                self.assertLessEqual(abs(out["residual_front_K"]), 1e-9)
                                n = out["newton"]
                                self.assertLessEqual(n["iterations"], 60)
                                self.assertGreaterEqual(out["T_O_K"], n["bracket_lo_K"] - 1e-6)
                                self.assertLessEqual(out["T_O_K"], n["bracket_hi_K"] + 1e-6)
                                self.assertGreaterEqual(out["T_O_K"], T25 - 1e-9)
                                self.assertGreaterEqual(out["q_rad_W"], 0.0)
                                self.assertEqual(out["comparator_label"], "study_comparator_only")

    def test_strict_monotonicity_in_eps_and_h(self):
        for stack in STACKS:
            for P in POWERS:
                for h in H_VALUES:
                    rows = [tr.nominal_steady(stack, P, h=h, eps=e) for e in EPS_VALUES]
                    for a, b in zip(rows, rows[1:]):
                        self.assertLess(b["T_O_K"], a["T_O_K"])
                        self.assertLess(b["T_S_K"], a["T_S_K"])
                        self.assertLess(b["T_H_K"], a["T_H_K"])
                        self.assertGreater(b["q_front_W"], a["q_front_W"])
                        self.assertLess(b["q_rear_W"], a["q_rear_W"])
                for eps in EPS_VALUES:
                    rows = [tr.nominal_steady(stack, P, h=h, eps=eps) for h in H_VALUES]
                    for a, b in zip(rows, rows[1:]):
                        self.assertLess(b["T_O_K"], a["T_O_K"])
                        self.assertLess(b["T_H_K"], a["T_H_K"])
                        self.assertGreater(b["q_front_W"], a["q_front_W"])

    def test_blocked_rear_front_carries_all_power_and_is_hotter(self):
        for stack in STACKS:
            for eps in (0.1, 0.5, 0.9):
                blocked = tr.nominal_steady(stack, 5, h=8.0, eps=eps, blocked_rear=True)
                opened = tr.nominal_steady(stack, 5, h=8.0, eps=eps, blocked_rear=False)
                self.assertLessEqual(abs(blocked["q_front_W"] - 5.1), 1e-9)
                self.assertEqual(blocked["q_rear_W"], 0.0)
                self.assertLess(blocked["T_O_C"], 88.75)        # radiation adds an exit vs the eps = 0 row
                self.assertGreater(blocked["T_O_K"], opened["T_O_K"])
                self.assertGreater(blocked["T_H_K"], opened["T_H_K"])

    def test_degenerate_statuses(self):
        self.assertEqual(tr.nominal_steady("H1", 5, h=0.0, eps=0.0, blocked_rear=True)["status"],
                         "no_finite_steady_state")
        self.assertEqual(tr.nominal_steady("H1", 0, h=0.0, eps=0.0, blocked_rear=True,
                                           sensor_power=0.0)["status"], "nonunique")

    def test_closed_front_finite_rear(self):
        R_HS, R_SO, R_rej, front, T_res = tr.nominal_inputs("H2", h=0.0, eps=0.0)
        out = tr.steady_radiative(R_HS, R_SO, R_rej, front, 5.0, 0.1, T_res)
        self.assertEqual(out["status"], "unique")
        self.assertLessEqual(abs(out["q_front_W"]), 1e-12)
        self.assertLessEqual(abs(out["T_H_K"] - (T_res + 2.0*5.1)), 1e-9)
        self.assertLessEqual(abs(out["T_S_K"] - (T_res + 2.0*5.1 + R_HS*0.1)), 1e-9)
        self.assertLessEqual(abs(out["T_O_K"] - out["T_S_K"]), 1e-9)

    def test_pure_radiation_front(self):
        out = tr.nominal_steady("H1", 5, h=0.0, eps=0.5)
        self.assertEqual(out["status"], "unique")
        self.assertEqual(out["q_conv_W"], 0.0)
        self.assertGreater(out["T_O_K"], T25)
        self.assertLessEqual(abs(out["balance_W"]), 1e-9)
        self.assertLessEqual(abs(out["q_front_W"] - out["q_rad_W"]), 1e-12)

    def test_warm_reservoir_signed_flux(self):
        out = tr.nominal_steady("H1", 0, h=8.0, eps=0.5, T_res_C=60.0, sensor_power=0.0)
        self.assertEqual(out["status"], "unique")
        self.assertLess(out["q_rear_W"], 0.0)                 # reservoir supplies heat
        self.assertGreater(out["q_front_W"], 0.0)
        self.assertTrue(T25 < out["T_O_K"] < out["T_S_K"] < out["T_H_K"] < tr.kelvin(60.0))
        self.assertLessEqual(abs(out["balance_W"]), 1e-9)

    def test_solve_canonical_against_closed_forms(self):
        rad = tr.FrontBoundary(h=0.0, eps=0.9, area=0.01, T_amb_K=T25, T_sur_K=T25)
        sol = tr.solve_canonical(0.0, 1.0, 50.0, rad)
        T_closed = (50.0/rad.radiation_constant + T25**4)**0.25
        self.assertLessEqual(abs(sol.T_K - T_closed), 1e-10*T_closed)
        self.assertLessEqual(sol.iterations, 60)
        conv = tr.FrontBoundary(h=5.0, eps=0.0, area=0.01, T_amb_K=T25, T_sur_K=T25)
        K, M, D = 0.1, 2.0, 40.0
        sol = tr.solve_canonical(K, M, D, conv)
        T_lin = (D + M*conv.hA*T25)/(K + M*conv.hA)
        self.assertLessEqual(abs(sol.T_K - T_lin), 1e-10*T_lin)
        self.assertLessEqual(sol.bracket_lo_K, sol.T_K + 1e-6)
        self.assertGreaterEqual(sol.bracket_hi_K, sol.T_K - 1e-6)
        with self.assertRaises(ValueError):
            tr.solve_canonical(0.0, 1.0, 1.0, tr.FrontBoundary(0.0, 0.0, 0.01, T25, T25))


class TestLinearization(unittest.TestCase):
    def setUp(self):
        self.front = tr.FrontBoundary(h=8.0, eps=0.7, area=0.01, T_amb_K=T25, T_sur_K=T25)

    def test_flux_identities_and_bound_B1(self):
        Tw = self.front.T_sur_K
        for T in (298.15, 300.0, 320.0, 350.0, 400.0):
            dT = T - Tw
            Tbar = 0.5*(T + Tw)
            mean = tr.flux_linearization(self.front, T, Tbar)
            self.assertLessEqual(abs(mean["exact_W"] - mean["mean_identity_W"]), 1e-12*max(1.0, abs(mean["exact_W"])))
            self.assertLessEqual(abs(mean["exact_W"] - mean["linear_W"]*(1.0 + mean["e_mean_relative"])),
                                 1e-12*max(1.0, abs(mean["exact_W"])))
            self.assertGreaterEqual(mean["error_W"], -1e-15)              # mean coefficient underestimates
            cold = tr.flux_linearization(self.front, T, Tw)
            x = dT/Tw
            series = 4.0*self.front.radiation_constant*Tw**3*dT*(1.0 + 1.5*x + x*x + 0.25*x**3)
            self.assertLessEqual(abs(cold["exact_W"] - series), 1e-12*max(1.0, abs(series)))
            for T_m in (280.0, 298.15, 310.0, 340.0, 420.0):
                lin = tr.flux_linearization(self.front, T, T_m)
                self.assertTrue(lin["bound_B1_holds"])
                self.assertLessEqual(abs(lin["error_W"]), lin["bound_B1_W"]*(1.0 + 1e-12) + 1e-300)

    def test_solution_identity_B2_bound_B3_and_signs(self):
        for blocked in (False, True):
            for stack in STACKS:
                for P in POWERS:
                    for h in H_VALUES:
                        for eps in (0.1, 0.5, 0.9):
                            R_HS, R_SO, R_rej, front, T_res = tr.nominal_inputs(stack, h=h, eps=eps, blocked_rear=blocked)
                            exact = tr.steady_radiative(R_HS, R_SO, R_rej, front, float(P), 0.1, T_res)
                            Tbar = 0.5*(exact["T_O_K"] + front.T_sur_K)
                            for T_m in (front.T_sur_K, Tbar, Tbar + 15.0):
                                with self.subTest(stack=stack, P=P, h=h, eps=eps, blocked=blocked, T_m=T_m):
                                    an = tr.linearization_error_analysis(R_HS, R_SO, R_rej, front, float(P), 0.1,
                                                                         T_res, T_m, exact_row=exact)
                                    self.assertLessEqual(abs(an["identity_B2_residual_K"]), 1e-8)
                                    self.assertLessEqual(abs(an["identity_H_residual_K"]), 1e-8)
                                    self.assertTrue(an["bound_B3_holds"])
                                    if T_m <= Tbar:
                                        self.assertGreaterEqual(an["error_O_K"], -1e-9)   # hot-side (conservative) error
                                    if T_m == Tbar:
                                        self.assertLessEqual(abs(an["error_O_K"] - an["mean_cubic_law_K"]), 1e-8)


class TestTransient(unittest.TestCase):
    def test_eps_zero_step_matches_coda_2x2_algebra(self):
        params = tr.nominal_transient("H2", h=8.0, eps=0.0)
        H = Hc = 310.0
        S = Sc = 305.0
        for _ in range(50):
            H, S, O, q, sol = tr.implicit_step(params, H, S, 5.0, 0.1, 1.0)
            Hc, Sc = coda_linear_step(params, Hc, Sc, 5.0, 0.1, 1.0)
            self.assertLessEqual(abs(H - Hc), 1e-8)
            self.assertLessEqual(abs(S - Sc), 1e-8)
            self.assertLessEqual(abs((S - O)/params.R_SO - q), 1e-9)

    def test_one_node_limit_against_coda_fixture(self):
        one = fx.ONE_NODE
        closed = tr.FrontBoundary(h=0.0, eps=0.0, area=0.01, T_amb_K=T25, T_sur_K=T25)
        params = tr.TransientParameters(ch=float(one["capacity_J_K"]), cs=1.0, g=0.0, R_SO=0.1,
                                        gr=1.0/one["resistance_K_W"], reservoir_K=tr.kelvin(one["bath_C"]), front=closed)
        exact = one["bath_C"] + one["power_W"]*one["resistance_K_W"]*(-math.expm1(-one["time_s"]/(one["resistance_K_W"]*one["capacity_J_K"])))
        self.assertLessEqual(abs(exact - one["exact_C"]), 1e-12)
        errors = []
        for dt in (1.0, 0.5, 0.25):
            run = tr.simulate(params, (tr.kelvin(one["initial_C"]), tr.kelvin(one["initial_C"])),
                              [dict(duration=one["time_s"], p=one["power_W"], j=0.0)], dt)
            final = run["trace"][-1]
            self.assertLessEqual(abs(final["S_K"] - tr.kelvin(one["initial_C"])), 1e-9)   # decoupled S
            err = abs(tr.celsius(final["H_K"]) - exact)
            self.assertLessEqual(abs(err - one["backward_euler_abs_error_K"][dt]), 1e-9)
            errors.append(err)
        for a, b in zip(errors, errors[1:]):
            self.assertTrue(1.8 <= a/b <= 2.1)

    def test_coupled_eigenmodes_translated_to_kelvin(self):
        base = 300.0
        front = tr.FrontBoundary(h=200.0, eps=0.0, area=0.01, T_amb_K=base, T_sur_K=base)   # hA = 2
        params = tr.TransientParameters(ch=1.0, cs=1.0, g=1.0, R_SO=0.5, gr=1.0, reservoir_K=base, front=front)
        errors = []
        for dt in (0.1, 0.05, 0.025):
            run = tr.simulate(params, (base + 1.0, base), [dict(duration=1.0, p=0.0, j=0.0)], dt)
            final = run["trace"][-1]
            H_exact = 0.5*(math.exp(-1.0) + math.exp(-3.0))
            S_exact = 0.5*(math.exp(-1.0) - math.exp(-3.0))
            errors.append(max(abs(final["H_K"] - base - H_exact), abs(final["S_K"] - base - S_exact)))
        for err, ref in zip(errors, fx.TWO_NODE_MODE_ERRORS_K):
            self.assertLessEqual(abs(err - ref), 1e-9)
        for a, b in zip(errors, errors[1:]):
            self.assertTrue(1.7 <= a/b <= 2.2)

    def test_long_time_equilibrium_matches_nonlinear_steady(self):
        for stack in STACKS:
            for eps in (0.0, 0.5, 0.9):
                with self.subTest(stack=stack, eps=eps):
                    params = tr.nominal_transient(stack, h=8.0, eps=eps)
                    run = tr.simulate(params, (T25, T25), [dict(duration=10000.0, p=5.0, j=0.1)], 10.0)
                    final = run["trace"][-1]
                    steady = tr.nominal_steady(stack, 5, h=8.0, eps=eps)
                    self.assertLessEqual(abs(final["H_K"] - steady["T_H_K"]), 1e-8)
                    self.assertLessEqual(abs(final["S_K"] - steady["T_S_K"]), 1e-8)
                    self.assertLessEqual(abs(final["O_K"] - steady["T_O_K"]), 1e-8)
                    self.assertLessEqual(abs(final["front_W"] - steady["q_front_W"]), 1e-9)
                    self.assertLessEqual(abs(final["rear_W"] - steady["q_rear_W"]), 1e-9)

    def test_equilibrium_is_held(self):
        steady = tr.nominal_steady("H3", 5, h=8.0, eps=0.5)
        params = tr.nominal_transient("H3", h=8.0, eps=0.5)
        run = tr.simulate(params, (steady["T_H_K"], steady["T_S_K"]), [dict(duration=1000.0, p=5.0, j=0.1)], 10.0)
        for row in run["trace"]:
            self.assertLessEqual(abs(row["H_K"] - steady["T_H_K"]), 1e-8)
            self.assertLessEqual(abs(row["S_K"] - steady["T_S_K"]), 1e-8)

    def test_energy_accounting_and_trace_reconstruction(self):
        params = tr.nominal_transient("H3", h=8.0, eps=0.9)
        run = tr.simulate(params, (T25, T25), fx.fault_segments(loss=True), 1.0)
        self.assertLessEqual(run["max_energy_residual_abs_J"], run["energy_tolerance_J"])
        net = sum(r["dt"]*(r["p_W"] + r["j_W"] - r["front_W"] - r["rear_W"]) for r in run["trace"][1:])
        self.assertLessEqual(abs(net - run["final_stored_energy_change_J"]), run["energy_tolerance_J"])
        self.assertLessEqual(abs(run["injected_J"] - (900*5.0 + 3600*0.1)), 1e-8)
        for r in run["trace"]:
            self.assertLessEqual(abs(r["front_W"] - r["conv_W"] - r["rad_W"]), 1e-12)

    def test_rear_loss_event_continuity_and_zero_rear_flux(self):
        params = tr.nominal_transient("H1", h=8.0, eps=0.5)
        run = tr.simulate(params, (T25, T25), fx.fault_segments(loss=True), 1.0)
        event = run["events"][1]
        self.assertEqual(event["time"], 600.0)
        self.assertEqual(event["before_state_K"], event["after_state_K"])
        self.assertEqual(event["old_gr"], 0.5)
        self.assertEqual(event["new_gr"], 0.0)
        self.assertEqual(run["events"][2]["new_gr"], 0.0)                 # loss persists
        for r in run["trace"]:
            if r["time"] > 600.0:
                self.assertEqual(r["rear_W"], 0.0)

    def test_pointwise_eps_ordering(self):
        for stack in STACKS:
            for loss in (False, True):
                runs = [tr.simulate(tr.nominal_transient(stack, h=8.0, eps=e), (T25, T25),
                                    fx.fault_segments(loss=loss), 1.0) for e in (0.0, 0.5, 0.9)]
                for cooler, warmer in zip(runs[1:], runs[:-1]):
                    self.assertEqual(len(cooler["trace"]), len(warmer["trace"]))
                    for a, b in zip(cooler["trace"], warmer["trace"]):
                        self.assertEqual(a["time"], b["time"])
                        self.assertLessEqual(a["H_K"], b["H_K"] + 1e-9)
                        self.assertLessEqual(a["S_K"], b["S_K"] + 1e-9)
                        self.assertLessEqual(a["O_K"], b["O_K"] + 1e-9)

    def test_rear_loss_at_least_as_warm_as_intact(self):
        for eps in (0.0, 0.5):
            params = tr.nominal_transient("H2", h=8.0, eps=eps)
            intact = tr.simulate(params, (T25, T25), fx.fault_segments(loss=False), 1.0)
            loss = tr.simulate(params, (T25, T25), fx.fault_segments(loss=True), 1.0)
            for a, b in zip(loss["trace"], intact["trace"]):
                self.assertGreaterEqual(a["H_K"], b["H_K"] - 1e-9)
                self.assertGreaterEqual(a["S_K"], b["S_K"] - 1e-9)
            self.assertGreater(tr.trace_peak(loss["trace"], "H_K")["H_K"], tr.trace_peak(intact["trace"], "H_K")["H_K"])

    def test_eps_zero_cross_check_against_coda_report(self):
        """ASSUMPTION: Coda's REPORT scenarios used dt = 1 s (not stated); tolerance 1e-5 K on
        6-decimal printed values."""
        for (stack, case), ref in fx.TRANSIENT_REPORT.items():
            with self.subTest(stack=stack, case=case):
                run = tr.simulate(tr.nominal_transient(stack, h=8.0, eps=0.0), (T25, T25),
                                  fx.fault_segments(loss=(case == "rear_loss")), fx.TRANSIENT_REPORT_DT_ASSUMED_S)
                peak_H = tr.trace_peak(run["trace"], "H_K")
                self.assertEqual(peak_H["time"], ref["peak_H_time_s"])
                self.assertLessEqual(abs(tr.celsius(peak_H["H_K"]) - ref["peak_H_C"]), 1e-5)
                peak_O = tr.trace_peak(run["trace"], "O_K")
                self.assertLessEqual(abs(tr.celsius(peak_O["O_K"]) - ref["peak_surface_C"]), 1e-5)
                self.assertLessEqual(abs(tr.celsius(run["trace"][-1]["H_K"]) - ref["H_3600_C"]), 1e-5)

    def test_initial_row_surface_satisfies_massless_relation(self):
        params = tr.nominal_transient("H1", h=8.0, eps=0.9)
        run = tr.simulate(params, (T25 + 20.0, T25 + 10.0), [dict(duration=5.0, p=1.0, j=0.1)], 1.0)
        row = run["trace"][0]
        self.assertLessEqual(abs((row["S_K"] - row["O_K"])/params.R_SO - row["front_W"]), 1e-9)
        self.assertEqual(row["time"], 0.0)


class TestInputRejection(unittest.TestCase):
    def test_front_boundary_guards(self):
        for kwargs in (dict(h=-1.0), dict(eps=1.5), dict(eps=float("nan")), dict(h=float("inf")),
                       dict(area=0.0), dict(T_amb_K=0.0), dict(T_sur_K=-5.0), dict(eps=True)):
            base = dict(h=8.0, eps=0.5, area=0.01, T_amb_K=T25, T_sur_K=T25)
            base.update(kwargs)
            with self.assertRaises(ValueError):
                tr.FrontBoundary(**base)

    def test_steady_guards(self):
        R_HS, R_SO, R_rej, front, T_res = tr.nominal_inputs("H1", eps=0.5)
        for args in ((-1.0, R_SO, R_rej, front, 5.0, 0.1, T_res), (R_HS, R_SO, 0.0, front, 5.0, 0.1, T_res),
                     (R_HS, R_SO, R_rej, front, -5.0, 0.1, T_res), (R_HS, R_SO, R_rej, front, 5.0, -0.1, T_res),
                     (R_HS, R_SO, R_rej, front, 5.0, 0.1, 0.0), (R_HS, R_SO, R_rej, "front", 5.0, 0.1, T_res),
                     (R_HS, R_SO, float("nan"), front, 5.0, 0.1, T_res)):
            with self.assertRaises(ValueError):
                tr.steady_radiative(*args)
        with self.assertRaises(ValueError):
            tr.nominal_steady("H4", 5)

    def test_transient_guards(self):
        params = tr.nominal_transient("H1", h=8.0, eps=0.5)
        good = [dict(duration=10, p=1, j=0.1)]
        with self.assertRaises(ValueError):
            tr.TransientParameters(ch=0.0, cs=1.0, g=1.0, R_SO=0.1, gr=0.5, reservoir_K=T25, front=params.front)
        with self.assertRaises(ValueError):
            tr.TransientParameters(ch=1.0, cs=1.0, g=1.0, R_SO=0.1, gr=-0.5, reservoir_K=T25, front=params.front)
        for segments, dt in (([dict(duration=10, p=11, j=0.1)], 1.0), ([dict(duration=10, p=1, j=0.3)], 1.0),
                             ([dict(duration=10, p=1, j=0.1, bogus=1)], 1.0), ([dict(duration=10, p=1)], 1.0),
                             ([dict(duration=1e9, p=1, j=0.1)], 1.0), ([], 1.0), (good, 0.0),
                             (good, float("nan")), ([dict(duration=-1, p=1, j=0.1)], 1.0),
                             ([dict(duration=10, p=1, j=0.1, gr=-1.0)], 1.0)):
            with self.assertRaises(ValueError):
                tr.simulate(params, (T25, T25), segments, dt)
        with self.assertRaises(ValueError):
            tr.simulate(params, (0.0, T25), good, 1.0)
        with self.assertRaises(ValueError):
            tr.simulate(params, (T25,), good, 1.0)
        with self.assertRaises(ValueError):
            tr.simulate("params", (T25, T25), good, 1.0)


if __name__ == "__main__":
    unittest.main()
```

FILE: validation/thermal_radiation/rad_study.py
```python
"""RAD-STUDY-1: predeclared small study of the outer-face radiation extension (T0-RAD-1 steady,
T0-LUMP2-RAD-1 transient).  Standard library only; deterministic; writes only to the caller-
supplied output path.  Usage: python rad_study.py OUTPUT_JSON [--overwrite]
Criteria C1-C6 and the output schema are fixed in ANALYSIS.md section 8 before execution.
Computational modelling only; no physical validation or safety claim."""
import argparse
import hashlib
import json
import math
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import thermal_radiation as tr  # noqa: E402
import reference_fixture as fx  # noqa: E402

STACKS = ("H1", "H2", "H3")
POWERS = (1, 5, 10)
H_VALUES = (3.0, 8.0, 15.0)
EPS_VALUES = (0.0, 0.1, 0.5, 0.9)
TRANSIENT_EPS = (0.0, 0.5, 0.9)
TRANSIENT_H = 8.0
DT_S = 1.0
EQUILIBRIUM_HORIZON_S, EQUILIBRIUM_DT_S = 10000.0, 10.0

# Predeclared numerical thresholds (ANALYSIS.md section 8); never relaxed after execution.
TOL = dict(balance_W=1e-9, reference_K=1e-9, reference_W=1e-9, newton_iterations=60,
           bracket_slack_K=1e-6, linearization_identity_K=1e-8, bound_B3_slack_K=1e-9,
           blocked_flux_W=1e-9, equilibrium_K=1e-8, ordering_K=1e-9, report_K=1e-5)

T_AMB_C = T_SUR_C = T_RES_C = 25.0
T25 = tr.kelvin(25.0)


def steady_row(stack, P, h, eps, blocked, eps0_surface_K):
    out = tr.nominal_steady(stack, P, h=h, eps=eps, blocked_rear=blocked)
    row = {k: out[k] for k in ("stack", "body_power_W", "sensor_power_W", "h_W_m2K", "eps", "rear_blocked",
                               "R_rej_K_W", "status", "T_H_K", "T_S_K", "T_O_K", "T_H_C", "T_S_C", "T_O_C",
                               "q_front_W", "q_conv_W", "q_rad_W", "q_rear_W", "balance_W", "node_balance_H_W",
                               "residual_front_K", "margin_surface_40C_K", "margin_internal_60C_K",
                               "comparator_label", "K_W_K", "M", "D_W")}
    row["newton"] = {k: out["newton"][k] for k in ("iterations", "bisections", "residual_W", "bracket_lo_K", "bracket_hi_K")}
    row["reservoir_heat_demand_W"] = out["q_rear_W"]
    row["linearization"] = None
    if eps > 0.0:
        R_HS, R_SO, R_rej, front, T_res = tr.nominal_inputs(stack, h=h, eps=eps, blocked_rear=blocked)
        Tw = front.T_sur_K
        variants = {"a_priori_eps0_mean": 0.5*(eps0_surface_K + Tw),
                    "exact_mean": 0.5*(out["T_O_K"] + Tw),
                    "cold_side": Tw}
        row["linearization"] = {}
        for name, T_m in variants.items():
            an = tr.linearization_error_analysis(R_HS, R_SO, R_rej, front, float(P), out["sensor_power_W"], T_res, T_m, exact_row=out)
            row["linearization"][name] = {k: an[k] for k in ("T_m_K", "h_r_W_m2K", "T_O_lin_K", "T_H_lin_K", "error_O_K",
                                                             "error_H_K", "predicted_error_O_K", "identity_B2_residual_K",
                                                             "identity_H_residual_K", "bound_B3_K", "bound_B3_holds",
                                                             "T_m_at_or_below_true_mean", "mean_cubic_law_K")}
    return row


def steady_grid():
    rows, blocked_rows = [], []
    for stack in STACKS:
        for h in H_VALUES:
            for P in POWERS:
                base = tr.nominal_steady(stack, P, h=h, eps=0.0)
                for eps in EPS_VALUES:
                    rows.append(steady_row(stack, P, h, eps, False, base["T_O_K"]))
            base_b = tr.nominal_steady(stack, 5, h=h, eps=0.0, blocked_rear=True)
            for eps in EPS_VALUES:
                blocked_rows.append(steady_row(stack, 5, h, eps, True, base_b["T_O_K"]))
    return rows, blocked_rows


def summarize_run(stack, eps, case, run):
    trace = run["trace"]

    def state(row):
        return dict(time_s=row["time"], H_C=tr.celsius(row["H_K"]), S_C=tr.celsius(row["S_K"]), O_C=tr.celsius(row["O_K"]),
                    front_W=row["front_W"], conv_W=row["conv_W"], rad_W=row["rad_W"], rear_W=row["rear_W"])

    peaks = {}
    for key, label in (("H_K", "peak_H"), ("S_K", "peak_S"), ("O_K", "peak_surface")):
        best = tr.trace_peak(trace, key)
        peaks[label] = dict(C=tr.celsius(best[key]), time_s=best["time"])
    samples = [state(r) for r in trace if abs(r["time"] - round(r["time"]/60.0)*60.0) < 1e-9]
    return dict(stack=stack, eps=eps, h_W_m2K=TRANSIENT_H, case=case, dt_s=DT_S, horizon_s=trace[-1]["time"],
                segments=fx.fault_segments(loss=(case == "rear_loss")), peaks=peaks,
                checkpoints={"600": state(tr.trace_at(trace, 600.0)), "900": state(tr.trace_at(trace, 900.0))},
                final=state(trace[-1]), samples_60s=samples,
                margin_surface_40C_K=40.0 - peaks["peak_surface"]["C"], margin_internal_60C_K=60.0 - peaks["peak_H"]["C"],
                comparator_label="study_comparator_only",
                energy=dict(injected_J=run["injected_J"], exported_front_J=run["exported_front_J"],
                            exported_rear_J=run["exported_rear_J"], stored_change_J=run["final_stored_energy_change_J"],
                            max_residual_abs_J=run["max_energy_residual_abs_J"], tolerance_J=run["energy_tolerance_J"],
                            within_tolerance=run["max_energy_residual_abs_J"] <= run["energy_tolerance_J"]),
                newton=dict(max_iterations=run["max_newton_iterations"], total_iterations=run["total_newton_iterations"]),
                events=run["events"], steps=run["steps"])


def transient_study():
    runs, summaries = {}, []
    for stack in STACKS:
        for eps in TRANSIENT_EPS:
            params = tr.nominal_transient(stack, h=TRANSIENT_H, eps=eps)
            for case in ("intact", "rear_loss"):
                run = tr.simulate(params, (T25, T25), fx.fault_segments(loss=(case == "rear_loss")), DT_S)
                runs[(stack, eps, case)] = run
                summaries.append(summarize_run(stack, eps, case, run))
    equilibria = []
    for stack in STACKS:
        for eps in TRANSIENT_EPS:
            run = tr.simulate(tr.nominal_transient(stack, h=TRANSIENT_H, eps=eps), (T25, T25),
                              [dict(duration=EQUILIBRIUM_HORIZON_S, p=5.0, j=0.1)], EQUILIBRIUM_DT_S)
            steady = tr.nominal_steady(stack, 5, h=TRANSIENT_H, eps=eps)
            final = run["trace"][-1]
            equilibria.append(dict(stack=stack, eps=eps, dH_K=final["H_K"] - steady["T_H_K"], dS_K=final["S_K"] - steady["T_S_K"],
                                   dO_K=final["O_K"] - steady["T_O_K"], max_energy_residual_abs_J=run["max_energy_residual_abs_J"],
                                   energy_tolerance_J=run["energy_tolerance_J"]))
    return runs, summaries, equilibria


def evaluate_criteria(rows, blocked_rows, runs, summaries, equilibria):
    allrows = rows + blocked_rows
    c = {}
    c1 = dict(status_unique=all(r["status"] == "unique" for r in allrows),
              max_abs_balance_W=max(abs(r["balance_W"]) for r in allrows),
              max_abs_node_balance_H_W=max(abs(r["node_balance_H_W"]) for r in allrows),
              max_abs_residual_front_K=max(abs(r["residual_front_K"]) for r in allrows),
              max_newton_iterations=max(r["newton"]["iterations"] for r in allrows),
              all_in_bracket=all(r["newton"]["bracket_lo_K"] - TOL["bracket_slack_K"] <= r["T_O_K"] <= r["newton"]["bracket_hi_K"] + TOL["bracket_slack_K"] for r in allrows))
    c1["pass"] = (c1["status_unique"] and c1["max_abs_balance_W"] <= TOL["balance_W"] and c1["max_abs_node_balance_H_W"] <= TOL["balance_W"]
                  and c1["max_abs_residual_front_K"] <= TOL["balance_W"] and c1["max_newton_iterations"] <= TOL["newton_iterations"] and c1["all_in_bracket"])
    c["C1_balance_convergence"] = c1

    by_key = {(r["stack"], r["body_power_W"], r["h_W_m2K"], r["eps"], r["rear_blocked"]): r for r in allrows}
    worst_K = worst_W = 0.0
    for ref in fx.STEADY_ROWS:
        r = by_key[(ref["stack"], float(ref["body_power"]), 8.0, 0.0, ref["rear_blocked"])]
        worst_K = max(worst_K, abs(r["T_H_C"] - ref["H"]), abs(r["T_S_C"] - ref["S"]), abs(r["T_O_C"] - ref["surface"]))
        worst_W = max(worst_W, abs(r["q_front_W"] - ref["front"]), abs(r["q_rear_W"] - ref["rear"]))
    c["C2_reference_reproduction"] = dict(max_abs_temperature_difference_K=worst_K, max_abs_flux_difference_W=worst_W,
                                          pass_=None, **{"pass": worst_K <= TOL["reference_K"] and worst_W <= TOL["reference_W"]})
    del c["C2_reference_reproduction"]["pass_"]

    mono_eps = mono_h = True
    for stack in STACKS:
        for P in POWERS:
            for h in H_VALUES:
                seq = [by_key[(stack, float(P), h, e, False)] for e in EPS_VALUES]
                for a, b in zip(seq, seq[1:]):
                    mono_eps &= b["T_O_K"] < a["T_O_K"] and b["T_S_K"] < a["T_S_K"] and b["T_H_K"] < a["T_H_K"] and b["q_front_W"] > a["q_front_W"] and b["q_rear_W"] < a["q_rear_W"]
            for e in EPS_VALUES:
                seq = [by_key[(stack, float(P), h, e, False)] for h in H_VALUES]
                for a, b in zip(seq, seq[1:]):
                    mono_h &= b["T_O_K"] < a["T_O_K"] and b["T_H_K"] < a["T_H_K"] and b["q_front_W"] > a["q_front_W"]
    c["C3_monotonicity"] = dict(strict_in_eps=mono_eps, strict_in_h=mono_h, **{"pass": mono_eps and mono_h})

    lin_rows = [r for r in allrows if r["linearization"]]
    ident = max(abs(v["identity_B2_residual_K"]) for r in lin_rows for v in r["linearization"].values())
    ident_H = max(abs(v["identity_H_residual_K"]) for r in lin_rows for v in r["linearization"].values())
    b3 = all(v["bound_B3_holds"] for r in lin_rows for v in r["linearization"].values())
    hot_side = all(r["linearization"][k]["error_O_K"] >= -TOL["bound_B3_slack_K"] for r in lin_rows for k in ("exact_mean", "cold_side"))
    cubic = max(abs(r["linearization"]["exact_mean"]["error_O_K"] - r["linearization"]["exact_mean"]["mean_cubic_law_K"]) for r in lin_rows)
    max_err = {k: max(abs(r["linearization"][k]["error_O_K"]) for r in lin_rows) for k in ("a_priori_eps0_mean", "exact_mean", "cold_side")}
    c["C4_linearization"] = dict(max_identity_B2_residual_K=ident, max_identity_H_residual_K=ident_H, bound_B3_holds_everywhere=b3,
                                 mean_and_cold_coefficients_overpredict=hot_side, max_cubic_law_residual_K=cubic,
                                 max_abs_surface_error_K_by_variant=max_err,
                                 **{"pass": ident <= TOL["linearization_identity_K"] and ident_H <= TOL["linearization_identity_K"] and b3 and hot_side and cubic <= TOL["linearization_identity_K"]})

    blocked_flux = max(abs(r["q_front_W"] - (r["body_power_W"] + r["sensor_power_W"])) for r in blocked_rows)
    blocked_rear_zero = all(r["q_rear_W"] == 0.0 for r in blocked_rows)
    hotter = all(r["T_O_K"] > by_key[(r["stack"], 5.0, r["h_W_m2K"], r["eps"], False)]["T_O_K"] for r in blocked_rows)
    c["C5_blocked_rear"] = dict(max_abs_front_minus_total_source_W=blocked_flux, rear_flux_exactly_zero=blocked_rear_zero,
                                blocked_surface_hotter_than_open=hotter,
                                **{"pass": blocked_flux <= TOL["blocked_flux_W"] and blocked_rear_zero and hotter})

    energy_ok = all(s["energy"]["within_tolerance"] for s in summaries)
    order_eps = loss_warm = True
    for stack in STACKS:
        for case in ("intact", "rear_loss"):
            seq = [runs[(stack, e, case)]["trace"] for e in TRANSIENT_EPS]
            for cooler, warmer in zip(seq[1:], seq[:-1]):
                order_eps &= len(cooler) == len(warmer) and all(a["H_K"] <= b["H_K"] + TOL["ordering_K"] and a["S_K"] <= b["S_K"] + TOL["ordering_K"] and a["O_K"] <= b["O_K"] + TOL["ordering_K"] for a, b in zip(cooler, warmer))
        for e in TRANSIENT_EPS:
            loss, intact = runs[(stack, e, "rear_loss")]["trace"], runs[(stack, e, "intact")]["trace"]
            loss_warm &= all(a["H_K"] >= b["H_K"] - TOL["ordering_K"] and a["S_K"] >= b["S_K"] - TOL["ordering_K"] for a, b in zip(loss, intact))
    eq_worst = max(max(abs(e["dH_K"]), abs(e["dS_K"]), abs(e["dO_K"])) for e in equilibria)
    report_worst = 0.0
    for (stack, case), ref in fx.TRANSIENT_REPORT.items():
        trace = runs[(stack, 0.0, case)]["trace"]
        pk = tr.trace_peak(trace, "H_K")
        report_worst = max(report_worst, abs(tr.celsius(pk["H_K"]) - ref["peak_H_C"]), abs(tr.celsius(tr.trace_peak(trace, "O_K")["O_K"]) - ref["peak_surface_C"]),
                           abs(tr.celsius(trace[-1]["H_K"]) - ref["H_3600_C"]), 0.0 if pk["time"] == ref["peak_H_time_s"] else math.inf)
    c["C6_transient"] = dict(energy_within_tolerance_all_runs=energy_ok, pointwise_eps_ordering=order_eps, rear_loss_at_least_as_warm=loss_warm,
                             max_abs_equilibrium_gap_K=eq_worst, max_abs_difference_vs_coda_report_K=report_worst,
                             coda_report_dt_assumed_s=fx.TRANSIENT_REPORT_DT_ASSUMED_S,
                             max_newton_iterations=max(s["newton"]["max_iterations"] for s in summaries),
                             **{"pass": energy_ok and order_eps and loss_warm and eq_worst <= TOL["equilibrium_K"] and report_worst <= TOL["report_K"]})
    c["all_pass"] = all(c[k]["pass"] for k in c if k != "all_pass")
    return c


SCHEMA = {
    "steady_rows[]": ["stack", "body_power_W", "sensor_power_W", "h_W_m2K", "eps", "rear_blocked", "R_rej_K_W", "status",
                      "T_H_K/T_S_K/T_O_K and _C", "q_front_W (=q_conv_W+q_rad_W, outward)", "q_rear_W = reservoir_heat_demand_W (signed, H->reservoir)",
                      "balance_W", "node_balance_H_W", "residual_front_K", "newton{iterations,bisections,residual_W,bracket_lo_K,bracket_hi_K}",
                      "margin_surface_40C_K, margin_internal_60C_K (comparator_label=study_comparator_only)",
                      "linearization{a_priori_eps0_mean|exact_mean|cold_side}{T_m_K,h_r_W_m2K,T_O_lin_K,T_H_lin_K,error_O_K,error_H_K,predicted_error_O_K,identity_B2_residual_K,identity_H_residual_K,bound_B3_K,bound_B3_holds,T_m_at_or_below_true_mean,mean_cubic_law_K} or null at eps=0"],
    "transient_runs[]": ["stack", "eps", "h_W_m2K", "case intact|rear_loss", "dt_s", "horizon_s", "segments", "peaks{peak_H,peak_S,peak_surface}{C,time_s}",
                         "checkpoints{600,900}", "final", "samples_60s[]", "margins (study_comparator_only)", "energy{...,within_tolerance}", "newton", "events", "steps"],
    "equilibrium_checks[]": ["stack", "eps", "dH_K", "dS_K", "dO_K", "max_energy_residual_abs_J", "energy_tolerance_J"],
    "criteria_results": "C1..C6 with pass flags and the measured quantities; all_pass",
}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", help="output JSON path (only file written)")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)
    output = Path(args.output)
    if output.exists() and not args.overwrite:
        raise SystemExit("Refusing to overwrite existing results; pass --overwrite")
    rows, blocked_rows = steady_grid()
    runs, summaries, equilibria = transient_study()
    criteria = evaluate_criteria(rows, blocked_rows, runs, summaries, equilibria)
    here = Path(__file__).resolve().parent
    record = dict(
        study_id="RAD-STUDY-1", contract="T0-HYP-1 (unchanged) + labelled extension T0-RAD-1 / T0-LUMP2-RAD-1",
        status="executed_synthetic_study", physical_validation=False, safety_certification=False,
        provenance="Red (Claude, Anthropic) for The Stage with Richard (Andrei) Pemberton; references by Coda (Codex Lily)",
        assumptions=["emissivity eps is an assumed study parameter, not a material property",
                     "convection h is an assumed coefficient, not measured or derived from airflow",
                     "radiative surroundings at T_amb = 25 C; unit view factor; grey diffuse surface; no sky/enclosure model",
                     "outer surface massless and isothermal (quasi-steady), as in T0-LUMP2-1",
                     "C_H = 20 J/K and C_S from T0-LUMP2-1 are hypothetical storage values",
                     "Coda REPORT cross-check assumes its scenario dt = 1 s (not stated in the source)",
                     "rear reservoir is an ideal boundary; its heat demand is reported, its realization is unmodeled",
                     "40 C / 60 C are arbitrary study comparators (study_comparator_only), not limits"],
        constants=dict(sigma_W_m2K4=tr.SIGMA_W_M2K4, area_m2=tr.AREA_M2, T_amb_C=T_AMB_C, T_sur_C=T_SUR_C, T_res_C=T_RES_C,
                       R_rej_K_W=tr.NOMINAL_R_REJ_K_W, P_sensor_W=tr.NOMINAL_SENSOR_POWER_W, C_H_J_K=tr.NOMINAL_C_H_J_K,
                       C_S_J_K={s: tr.nominal_panel_capacity(s) for s in STACKS},
                       R_HS_K_W={s: float(tr.exact_stack_resistances(s)["R_HS"]) for s in STACKS}),
        design=dict(stacks=STACKS, body_power_W=POWERS, h_W_m2K=H_VALUES, eps=EPS_VALUES, blocked_rear_power_W=5,
                    transient_eps=TRANSIENT_EPS, transient_h_W_m2K=TRANSIENT_H, dt_s=DT_S, schedule="5 W to 900 s then 0; 0.1 W sensor throughout; rear loss at 600 s in loss cases",
                    equilibrium_check=dict(horizon_s=EQUILIBRIUM_HORIZON_S, dt_s=EQUILIBRIUM_DT_S), tolerances=TOL),
        steady_rows=rows, blocked_rear_rows=blocked_rows, transient_runs=summaries, equilibrium_checks=equilibria,
        criteria_results=criteria, schema=SCHEMA,
        source_sha256={"thermal_radiation.py": hashlib.sha256((here/"thermal_radiation.py").read_bytes()).hexdigest(),
                       "rad_study.py": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                       "reference_fixture.py": hashlib.sha256((here/"reference_fixture.py").read_bytes()).hexdigest()})
    output.write_text(json.dumps(record, indent=1, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps(dict(output=str(output), steady_rows=len(rows), blocked_rows=len(blocked_rows), transient_runs=len(summaries),
                          criteria={k: (v["pass"] if isinstance(v, dict) else v) for k, v in criteria.items()}), indent=1))
    print("stack eps   T_O_C        T_H_C        q_front_W    q_rear_W   (P=5 W, h=8)")
    for r in rows:
        if r["body_power_W"] == 5.0 and r["h_W_m2K"] == 8.0 and r["eps"] in (0.0, 0.5, 0.9):
            print(f'{r["stack"]}   {r["eps"]:.1f} {r["T_O_C"]:12.6f} {r["T_H_C"]:12.6f} {r["q_front_W"]:12.6f} {r["q_rear_W"]:10.6f}')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

FILE: validation/thermal_radiation/ANALYSIS.md
```markdown
# T0-RAD-1 / T0-LUMP2-RAD-1: outer-face radiation extension of T0-HYP-1 — analysis and predeclaration

Red (Claude, Anthropic) for The Stage with Richard (Andrei) Pemberton, task thermal-radiation-001.
Builds on Coda's (Codex Lily) executed references `validation/thermal/thermal_reference.py`
(T0-HYP-1, `reference_results.json`) and `validation/thermal_transient/rc_transient.py` (T0-LUMP2-1).
The T0-HYP-1 baseline is unchanged; radiation is a labelled separate case in absolute Kelvin, as the
contract requires. Synthetic computational modelling only: not empirical validation, not a safety
certification, not a hardware design recommendation. This file states no executed numbers; the study
JSON produced by `rad_study.py` is the only numerical record, and it is filled by execution.

## 1 Scope and files
`thermal_radiation.py` (model, solvers), `reference_fixture.py` (verbatim Coda fixtures, labelled),
`test_thermal_radiation.py` (unittest), `rad_study.py` (RAD-STUDY-1, writes one JSON), this file.

## 2 Model
Nodes H (internal), S (sensor midplane), O (massless outer surface). R_HS = inner silicone + half film
+ inner contact; R_SO = outer silicone + half film + outer contact; R_rej ∈ (0, ∞] rear path to the
reservoir at T_r (∞ = blocked, zero conductance). Outer boundary, positive outward:
Φ(T) = hA(T − T_a) + εσA(T⁴ − T_w⁴), T_a = T_w = 298.15 K, ε ∈ [0, 1] assumed, h ∈ [3, 15] assumed.
Steady: P = (H−S)/R_HS + (H−T_r)/R_rej; J + (H−S)/R_HS = (S−O)/R_SO; (S−O)/R_SO = Φ(O).

## 3 Canonical scalar equation
With q = (S−O)/R_SO, E = T_r + R_rej(P+J) + R_HS J, R_th = R_HS + R_SO + R_rej:
O = E − R_th q, so the steady problem is Γ(T) := K T + M Φ(T) − D = 0 with
(K, M, D) = (1/R_th, 1, E/R_th) (finite rear) or (0, 1, P+J) (blocked rear).
Backward-Euler step Δ (section 6): (K, M, D) = (κ, 1 + κR_SO, D_n).

## 4 Existence, uniqueness, monotonicity (statements; proofs delivered in answer part (a))
Lemma 1: Γ convex and strictly increasing on T > 0 if K > 0 or h > 0 or ε > 0.
Lemma 2: explicit bracket L = min(T_lo, D/K) (K>0) or T_lo (K=0, D ≥ 0), U = T_hi + max(0, D−KT_hi)/(K+MΦ′(T_hi)),
with Γ(L) ≤ 0 ≤ Γ(U) and L > 0 for positive-Kelvin baths and nonnegative sources.
Theorem 1: exactly one root in [L, U], unique on (0, ∞); closed-exit cases give the reference statuses
`no_finite_steady_state` (P+J > 0) / `nonunique` (P+J = 0).
Corollary: with common baths, T_a ≤ O ≤ E, 0 ≤ q ≤ P+J, and O, S, H strictly decrease in ε and in h
while q increases and the reservoir demand decreases.

## 5 Solver (Theorem 2)
Bracketed safeguarded Newton started at U; Newton step accepted only inside the bracket and when
|2Γ| ≤ |Γ′|·|step two iterations ago|, else bisection. Exact arithmetic: monotone quadratic convergence
from above. Any arithmetic: bracket width below τ in ≤ 2⌈log₂((U−L)/τ)⌉ iterations. Termination: residual
floor 8·ε_mach·(|KT| + |D| + M(|conv| + |rad|)), relative step/bracket 1e-13, or no representable
progress; the 200-iteration cap raises instead of returning silently.

## 6 Transient implicit step (T0-LUMP2-RAD-1)
C_H Ḣ = P − g(H−S) − g_r(H−T_r); C_S Ṡ = J + g(H−S) − q; q = (S−O)/R_SO = Φ(O).
Backward Euler: α = C_H/Δ + g + g_r, β = C_H H_n/Δ + P + g_r T_r, κ = C_S/Δ + g(C_H/Δ + g_r)/α,
D_n = C_S S_n/Δ + J + gβ/α; solve κO + (1+κR_SO)Φ(O) = D_n; S_{n+1} = O + R_SO Φ(O); H_{n+1} = (β + gS_{n+1})/α.
Unique step for every Δ > 0; ℓ¹-nonexpansive (unconditionally stable); discrete comparison principle;
per-step identity C_HΔH + C_SΔS = Δ(P + J − q − q_r) + Δ·Γ(O), so the audited energy residual is Δ·(Newton
residual) plus roundoff. At ε = 0 the step equals Coda's 2×2 formula with g_a = 1/(R_SO + 1/(hA)).
The two-node equations are REIMPLEMENTED explicitly (not imported from `rc_transient.py`), preserving
its segment structure, source envelope (0..10 W, 0..0.2 W), step budget and end-step energy audit.

## 7 Linearized coefficient h_r = 4εσT_m³ (statements; derivations in answer part (b))
Identity: O⁴ − T_w⁴ = 4T̄³ΔT + T̄ΔT³, T̄ = (O+T_w)/2, ΔT = O − T_w; the mean coefficient underestimates the
flux by the exact factor 1 + ΔT²/(4T̄²).
(B1) |q_rad − h_rAΔT| ≤ εσA|ΔT|[12·max(T̄,T_m)²·|T̄−T_m| + T̄ΔT²].
(B2) T_lin − T* = M·Δq(T*)/G_lin, Δq(T) = εσA(T⁴−T_w⁴) − h_rA(T−T_w), G_lin = K + M(h+h_r)A;
H_lin − H* = (R_rej/R_th)(T_lin − T*) (finite rear) or T_lin − T* (blocked).
(B3) |T_lin − T*| ≤ M·max{|Δq(L)|, |Δq(U)|, |Δq(T_m)| if T_m ∈ [L,U]}/G_lin, a priori from Lemma 2.
Sign: T_m ≤ T̄* ⇒ all node temperatures overpredicted; T_m = T̄* ⇒ T_lin − T* = MεσAT̄*ΔT*³/G_lin.

## 8 Predeclared study RAD-STUDY-1 (fixed before execution)
Steady grid: H1/H2/H3 × P_body 1/5/10 W × h 3/8/15 × ε 0/0.1/0.5/0.9, R_rej = 2 K/W (108 rows); blocked
rear at 5 W over h × ε (36 rows). Each ε > 0 row carries three linearization variants: a priori
T_m = (O(ε=0) + T_w)/2, exact mean T_m = (O* + T_w)/2, cold T_m = T_w.
Transient: stacks × ε 0/0.5/0.9 × {intact, rear loss at 600 s}, schedule 5 W to 900 s then 0, sensor 0.1 W
throughout, h = 8, dt = 1 s, 3600 s (18 runs); plus 9 equilibrium checks (constant 5 W/0.1 W, 10000 s, dt 10).

Criteria (thresholds are those in `rad_study.TOL`; failures are retained, never relaxed):
- C1 balance/convergence: all rows `unique`; |P+J−q−q_r| ≤ 1e-9 W; |node balance at H| ≤ 1e-9 W;
  |(S−O) − R_SO q| ≤ 1e-9 K; Newton iterations ≤ 60; O within the Lemma-2 bracket (1e-6 K slack).
- C2 reference reproduction: the 12 ε = 0 rows (h = 8) match Coda's `reference_results.json` floats within
  1e-9 K and 1e-9 W (exact Fraction equality is asserted in the unit tests).
- C3 monotonicity: for fixed (stack, P, h) O, S, H strictly decrease, q strictly increases, q_r strictly
  decreases in ε; for fixed (stack, P, ε) O, H strictly decrease and q increases in h.
- C4 linearization: identity (B2) and the H-propagation identity hold within 1e-8 K for every variant;
  bound (B3) holds (1e-9 K roundoff slack); mean and cold variants overpredict O; the cubic law holds for
  the exact-mean variant within 1e-8 K.
- C5 blocked rear: |q − (P+J)| ≤ 1e-9 W; q_r exactly 0; blocked surface hotter than the open row.
- C6 transient: energy residual within 1e-8 J + 1e-10·throughput for all runs; pointwise ε-ordering
  (larger ε never warmer, 1e-9 K); rear loss never cooler than intact (1e-9 K); equilibrium gap ≤ 1e-8 K;
  ε = 0 peaks/horizon agree with Coda's REPORT table within 1e-5 K under the labelled dt = 1 s assumption.

Output schema: `rad_study.SCHEMA`, mirrored in the JSON `schema` key. Rear flux is reported as the ideal
reservoir's heat demand; margins to 40 °C / 60 °C carry `comparator_label = study_comparator_only`.

Assumption register: ε and h are assumed study parameters; surroundings at 25 °C with unit view factor,
grey diffuse surface, no sky/enclosure; massless isothermal surface; C_H = 20 J/K and C_S as in
T0-LUMP2-1; σ = 5.670374419e-8 (CODATA 2018); exact 273.15 offset; Coda REPORT dt = 1 s assumed.
Omitted: in-plane spreading, view factors < 1, temperature-dependent properties, k/r_c/thickness
sensitivity sweeps, reservoir capacity cap, controller/events beyond rear loss, any Fable comparison.
A stack meeting the comparators is a conditional model result; failing is an equally legitimate outcome.
```

## Notes for Red (execution)

- Run from `validation/thermal_radiation/`: `python -m unittest -v test_thermal_radiation` then `python rad_study.py <output.json>`. Both import `thermal_radiation` and `reference_fixture` from their own directory.
- If any test fails, please return the failure text; the most likely assumption-sensitive one is `test_eps_zero_cross_check_against_coda_report` (dt = 1 s assumed for Coda's scenarios). The study's C6 carries the same labelled assumption and does not relax it.
- The `TestLinearization.test_solution_identity_B2_bound_B3_and_signs` loop evaluates 3×3×3×3×2×3 = 486 analyses; expected runtime is seconds. Transient tests run ~30 simulations of 3600 steps.

## Left unimplemented (explicit)
- No sensitivity sweep in k, r_c, thickness or R_rej beyond nominal/blocked; no capacity-cap piecewise law; no distributed (spatial) model; no view-factor/sky-temperature radiation; no Fable-output comparison (none in the bundle).
- `rc_transient.py` is not imported (reimplemented explicitly); the ε = 0 agreement with its documented 2×2 step is checked by `coda_linear_step` in the tests, not by executing Coda's file.
- All numbers remain to be produced by Red's sandbox run; none are reported here.