"""T0-RAD-1 / T0-LUMP2-RAD-1: outer-face grey-body radiation extension of the T0-HYP-1
synthetic thermal reference.  Python 3.10+ standard library only; deterministic; no I/O.

Provenance.  Red (Claude, Anthropic) for The Stage with Richard (Andrei) Pemberton, task
thermal-radiation-001.  Builds on Coda's (Codex Lily) executed references:
validation/thermal/thermal_reference.py (T0-HYP-1 exact rational steady network) and
validation/thermal_transient/rc_transient.py (T0-LUMP2-1 two-node backward Euler).  The
two-node equations are REIMPLEMENTED explicitly here (not imported) so that the eps = 0
limit can be compared with the documented T0-LUMP2-1 step algebra in the tests.

Model (Kelvin inside this module; the contract says radiation uses absolute Kelvin).
Nodes: internal H, sensor midplane S, massless outer surface O.
  R_HS  inner silicone + half film + inner contact            (K/W)
  R_SO  outer silicone + half film + outer contact            (K/W)
  R_rej rear path H -> isothermal reservoir, +inf = blocked   (K/W)
Outer boundary, convection and grey-body radiation in parallel, positive outward:
  Phi(T) = h*A*(T - T_amb) + eps*sigma*A*(T^4 - T_sur^4)       (W)
The steady problem and every backward-Euler step reduce to one scalar equation
  K*T + M*Phi(T) = D,   K >= 0, M > 0,
solved by a bracketed, safeguarded Newton iteration (proofs in ANALYSIS.md).

Scope.  Synthetic computational modelling only.  Emissivity and convection coefficient
are assumed study parameters, not material or measured properties.  No physical
validation, safety certification or hardware recommendation is implied.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from fractions import Fraction
import math
import sys

SIGMA_W_M2K4 = 5.670374419e-8          # Stefan-Boltzmann constant, CODATA 2018
KELVIN_OFFSET = 273.15
AREA_M2 = 0.01
EPSILON_MACHINE = sys.float_info.epsilon
P_MAX_W = 10.0                         # computational input envelope (as T0-LUMP2-1), not a hardware limit
J_MAX_W = 0.2
MAX_STEPS = 100_000
MAX_NEWTON_ITERATIONS = 200
NEWTON_RELATIVE_TOLERANCE = 1e-13
RESIDUAL_FLOOR_FACTOR = 8.0

STACK_SILICONE_THICKNESS_M = {"H1": "0.0005", "H2": "0.001", "H3": "0.002"}
FILM_THICKNESS_M = "0.00005"
NOMINAL_K_SILICONE_W_MK = "0.27"
NOMINAL_K_FILM_W_MK = "0.20"
NOMINAL_CONTACT_M2K_W = "0.0002"
NOMINAL_SENSOR_POWER_W = 0.1
NOMINAL_R_REJ_K_W = 2.0
NOMINAL_C_H_J_K = 20.0                 # hypothetical internal storage, T0-LUMP2-1 assumption


def kelvin(celsius_value):
    """Celsius -> Kelvin with the exact 273.15 offset."""
    return celsius_value + KELVIN_OFFSET


def celsius(kelvin_value):
    return kelvin_value - KELVIN_OFFSET


def finite_number(value, name, allow_inf=False):
    """Admit non-Boolean int/float; reject NaN and (unless allowed) infinity."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a non-Boolean int or float")
    value = float(value)
    if math.isnan(value) or (math.isinf(value) and not allow_inf):
        raise ValueError(f"{name} must be finite")
    return value


def exact_stack_resistances(stack, k_silicone=NOMINAL_K_SILICONE_W_MK, k_film=NOMINAL_K_FILM_W_MK,
                            contact_r=NOMINAL_CONTACT_M2K_W, area="0.01", thickness_factor="1"):
    """Exact rational T0-HYP-1 half-stack resistances (K/W); decimal strings keep rationals exact.
    The contract stacks are symmetric (outer thickness = inner thickness), so R_HS = R_SO."""
    if stack not in STACK_SILICONE_THICKNESS_M:
        raise ValueError("Unknown reference stack")
    A = Fraction(area)
    t = Fraction(STACK_SILICONE_THICKNESS_M[stack])*Fraction(thickness_factor)
    half = (t/(Fraction(k_silicone)*A) + Fraction(FILM_THICKNESS_M)/(2*Fraction(k_film)*A)
            + Fraction(contact_r)/A)
    return {"R_HS": half, "R_SO": half, "area": A}


def nominal_panel_capacity(stack):
    """T0-LUMP2-1 effective panel storage C_S (J/K): silicone rho 1030 kg/m3, cp 1500 J/(kg K);
    film rho 1420, cp 1090 -- assumed by Coda; transcribed with the same float expression order."""
    if stack not in STACK_SILICONE_THICKNESS_M:
        raise ValueError("Unknown reference stack")
    thick = {"H1": .0005, "H2": .001, "H3": .002}[stack]
    area = .01
    return 1030*area*(2*thick)*1500 + 1420*area*.00005*1090


@dataclass(frozen=True)
class FrontBoundary:
    """Massless outer surface: convection to T_amb_K and grey-body radiation to T_sur_K."""
    h: float
    eps: float
    area: float
    T_amb_K: float
    T_sur_K: float

    def __post_init__(self):
        for name in ("h", "eps", "area", "T_amb_K", "T_sur_K"):
            object.__setattr__(self, name, finite_number(getattr(self, name), name))
        if self.h < 0.0:
            raise ValueError("h must be nonnegative")
        if not 0.0 <= self.eps <= 1.0:
            raise ValueError("eps must lie in [0, 1]")
        if self.area <= 0.0:
            raise ValueError("area must be positive")
        if self.T_amb_K <= 0.0 or self.T_sur_K <= 0.0:
            raise ValueError("bath temperatures must be positive Kelvin")

    @property
    def hA(self):
        return self.h*self.area

    @property
    def radiation_constant(self):
        """eps*sigma*A in W/K^4."""
        return self.eps*SIGMA_W_M2K4*self.area

    def convective_flux(self, T):
        return self.hA*(T - self.T_amb_K)

    def radiative_flux(self, T):
        """eps*sigma*A*(T^4 - T_sur^4), factored to avoid cancellation near T_sur."""
        Tw = self.T_sur_K
        return self.radiation_constant*(T - Tw)*(T + Tw)*(T*T + Tw*Tw)

    def flux(self, T):
        return self.convective_flux(T) + self.radiative_flux(T)

    def derivative(self, T):
        return self.hA + 4.0*self.radiation_constant*T*T*T

    def exit_open(self):
        return self.h > 0.0 or self.eps > 0.0


@dataclass(frozen=True)
class ScalarSolution:
    T_K: float
    iterations: int
    bisections: int
    residual_W: float
    bracket_lo_K: float
    bracket_hi_K: float
    final_lo_K: float
    final_hi_K: float


def canonical_bracket(K, M, D, front):
    """ANALYSIS.md Lemma 2: [lo, hi] with Gamma(lo) <= 0 <= Gamma(hi) in exact arithmetic."""
    T_lo = min(front.T_amb_K, front.T_sur_K)
    T_hi = max(front.T_amb_K, front.T_sur_K)
    slope = K + M*front.derivative(T_hi)
    if slope <= 0.0:
        raise ValueError("No exit path (K = 0 and closed front): no finite solution")
    hi = T_hi + max(0.0, D - K*T_hi)/slope
    if K > 0.0:
        lo = min(T_lo, D/K)
    else:
        if D < 0.0:
            raise ValueError("Negative net source with blocked rear is outside the admitted domain")
        lo = T_lo
    if not lo > 0.0:
        raise ValueError("Bracket lower end is not a positive Kelvin temperature")
    return lo, hi


def solve_canonical(K, M, D, front, rel_tol=NEWTON_RELATIVE_TOLERANCE):
    """Solve K*T + M*Phi(T) = D for T > 0 K by bracketed, safeguarded Newton (Theorem 2)."""
    for name, value in (("K", K), ("M", M), ("D", D)):
        if not isinstance(value, float) or not math.isfinite(value):
            raise ValueError(f"{name} must be a finite float")
    if K < 0.0 or M <= 0.0:
        raise ValueError("Canonical coefficients need K >= 0 and M > 0")
    if not isinstance(front, FrontBoundary):
        raise ValueError("front must be a FrontBoundary")

    def gamma(T):
        return K*T + M*front.flux(T) - D

    def dgamma(T):
        return K + M*front.derivative(T)

    lo0, hi0 = canonical_bracket(K, M, D, front)
    lo, hi = lo0, hi0
    g_lo, g_hi = gamma(lo), gamma(hi)
    widen = max(1e-9, 1e-12*hi)
    tries = 0
    while g_lo > 0.0 and tries < 64:          # rounding guard; unreachable in exact arithmetic
        lo -= widen
        widen *= 2.0
        tries += 1
        if lo <= 0.0:
            raise RuntimeError("Could not establish a positive lower bracket")
        g_lo = gamma(lo)
    tries = 0
    while g_hi < 0.0 and tries < 64:
        hi += widen
        widen *= 2.0
        tries += 1
        g_hi = gamma(hi)
    if g_lo > 0.0 or g_hi < 0.0:
        raise RuntimeError("Bracket failure")
    if g_lo == 0.0:
        return ScalarSolution(lo, 0, 0, 0.0, lo0, hi0, lo, hi)
    if g_hi == 0.0:
        return ScalarSolution(hi, 0, 0, 0.0, lo0, hi0, lo, hi)

    T, f, df = hi, g_hi, dgamma(hi)          # start at the upper end: monotone Newton descent
    dx_old = dx = hi - lo
    bisections = 0
    iterations = 0
    while iterations < MAX_NEWTON_ITERATIONS:
        iterations += 1
        newton = None
        if df > 0.0:
            candidate = T - f/df
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
