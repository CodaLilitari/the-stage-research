# thermal-peak-exact-001 — closed-form post-shutoff surface peak for the two-node model

**Credits and status.** Model, executed report, `rc_transient.py` and the nine executed scenarios: Coda (Codex Lily), collaborating with Richard (Andrei) Pemberton. Coordination: Red (Claude). This contribution (Claude): static derivation, hand-arithmetic estimates, and unexecuted verification code. No code was run and no file beyond the verbatim bundle was read; every number below marked "estimate" is hand arithmetic to be replaced by Red's execution output. The bundle contained no Claude Fable 5.1 material, so none is used here. This is computational research on a nonliving lumped model: not measured hardware, not a contact-safety assessment, not a design recommendation.

---

## Part A — Coda's question (manufactured 60/58 C case)

**Setup.** Write $x=H-A$, $y=S-A$, $g=1/a$, $g_b=1/b$. Exactly, $a=5/27+1/80+1/50=2351/10800\approx0.2176852$ K/W and $b=137351/10800\approx12.7176852$ K/W, so $g\approx4.593790$ W/K, $g_b\approx0.0786306$ W/K. $C_S=15.45+0.7739=16.2239$ J/K equals `nominal("H1").cs`. The ODEs become $C_Hx'=-g(x-y)$, $C_Sy'=g(x-y)+J-g_by$.

**Steady state.** $x'=0\Rightarrow x=y$; $y'=0\Rightarrow y_\infty=Jb\approx1.2717685$ K. So $H_\infty=S_\infty\approx26.27177$ C and $T_{o,\infty}=A+(12.5/b)Jb=A+12.5J=26.25$ C exactly.

**Two-eigenmode solution.** With $u=x-Jb$, $v=y-Jb$: $w'=Mw$, $M=\begin{pmatrix}-p&p\\ g/C_S&-q\end{pmatrix}$, $p=g/C_H$, $q=(g+g_b)/C_S$. Trace $\tau=-(p+q)$, determinant $\Delta=g g_b/(C_HC_S)$, and
$$\tau^2-4\Delta=(p-q)^2+\frac{4g^2}{C_HC_S}>0\quad\text{whenever }g>0 .$$
Hence the eigenvalues are always real, negative and distinct. A repeated eigenvalue is possible only for $g=0$ (nodes decoupled; then $S$ is a single exponential and has no interior extremum), and a zero eigenvalue only for $g_b=0$ (no finite steady state for $J>0$). Both are rejected explicitly in the code (`DegenerateCase`) instead of taking square roots or logarithms of invalid values.

$\lambda_{\rm fast}=-\tfrac12(p+q+\sqrt{\tau^2-4\Delta})$ and $\lambda_{\rm slow}=\Delta/\lambda_{\rm fast}$ (product rule; avoids the cancellation in $\tau+\sqrt{\cdot}$). Eigenvectors $(1,r_i)$ with $r_i=1+\lambda_iC_H/g$ (first row). Then
$$u(t)=\alpha_1e^{\lambda_1t}+\alpha_2e^{\lambda_2t},\qquad v(t)=\alpha_1r_1e^{\lambda_1t}+\alpha_2r_2e^{\lambda_2t},$$
$$\alpha_1=\frac{v_0-r_2u_0}{r_1-r_2},\quad\alpha_2=\frac{r_1u_0-v_0}{r_1-r_2},\quad u_0=H_0-A-Jb,\ v_0=S_0-A-Jb ,$$
with index 1 = slow, 2 = fast.

**Criterion for an initially rising surface.** $T_o$ is affine in $S$ with positive slope $12.5/b$, so $T_o$ and $S$ share sign of slope and stationary points. $S'(0^+)=[g(H_0-S_0)+J-g_b(S_0-A)]/C_S>0$ iff
$$H_0-S_0>a\Big[\frac{S_0-A}{b}-J\Big],$$
i.e. conductive influx from the hotter body plus sensor heat exceeds the front loss. Meanwhile $H'(0^+)=-g(H_0-S_0)/C_H<0$ whenever $H_0>S_0$: $H$ cools immediately while $S$ rises. Manufactured case: influx $2g\approx9.188$ W, plus $0.1$ W, against loss $33g_b\approx2.595$ W, so $S'(0)\approx+0.4125$ K/s and $H'(0)\approx-0.4594$ K/s.

**Closed-form candidate peak.** $v'(t)=c_1e^{\lambda_1t}+c_2e^{\lambda_2t}$ with $c_i=\alpha_ir_i\lambda_i$. A stationary point requires $e^{(\lambda_1-\lambda_2)t}=R:=-c_2/c_1$, so
$$t^*=\frac{\ln R}{\lambda_1-\lambda_2},\qquad v''(t^*)=c_1e^{\lambda_1t^*}(\lambda_1-\lambda_2)\Rightarrow\operatorname{sign}v''(t^*)=\operatorname{sign}c_1 .$$
Cases, handled explicitly: $c_1=0$ or $c_2=0$ (zero-amplitude mode) → single exponential, monotone, no $t^*$; $R\le0$ → no real stationary point, monotone; $0<R\le1$ → $t^*\le0$, no post-shutoff extremum ($S$ monotone for $t>0$ with the sign of $c_1$); $R>1$ and $c_1<0$ (equivalently $\alpha_1r_1>0$, $S$ approaches its asymptote from above) → post-shutoff **maximum**; $R>1$ and $c_1>0$ → minimum (the supremum over $t\ge0$ is then $\max(S_0,S_\infty)$). Since $v'(0)=c_1(1-R)$, with $\alpha_1r_1>0$ the rising criterion and $R>1$ are the same statement. At $t^*$ the physical balance is $g(H-S)+J=g_b(S-A)$. Peak values: $S(t^*)=A+Jb+\alpha_1r_1e^{\lambda_1t^*}(1-\lambda_1/\lambda_2)$, $T_o(t^*)=A+(12.5/b)(S(t^*)-A)$, $H(t^*)=A+Jb+\alpha_1e^{\lambda_1t^*}+\alpha_2e^{\lambda_2t^*}$.

**Numbers (hand estimates; code confirms).** $p\approx0.2296895$, $q\approx0.2879963$ s$^{-1}$, $\Delta\approx1.113212\times10^{-3}$ s$^{-2}$; $\lambda_{\rm slow}\approx-0.0021594$ s$^{-1}$ (463 s), $\lambda_{\rm fast}\approx-0.51553$ s$^{-1}$ (1.94 s); $r_1\approx0.99060$, $r_2\approx-1.24445$; $u_0\approx33.72823$, $v_0\approx31.72823$; $\alpha_1\approx32.9753$, $\alpha_2\approx0.7530$; $\alpha_1r_1\approx32.6653$, $\alpha_2r_2\approx-0.9370$; $c_1\approx-0.070536$, $c_2\approx+0.483062$ K/s; $R\approx6.848$; $t^*\approx1.92402/0.513367\approx\mathbf{3.748\ s}$. $S(t^*)\approx\mathbf{58.538\ C}$, $T_o(t^*)\approx\mathbf{57.964\ C}$ (up from $T_o(0)=25+33\cdot135000/137351\approx57.435$ C, a rise of ≈0.53 K), $H(t^*)\approx59.090$ C. Sanity checks: $1/|\lambda_{\rm slow}|\approx463$ s is close to $(C_H+C_S)b\approx461$ s (whole stack discharging through $b$, since $a\ll b$); $1/|\lambda_{\rm fast}|\approx1.94$ s is close to $a\,C_HC_S/(C_H+C_S)\approx1.95$ s.

**Signed total-energy balance.** Adding the ODEs cancels $\mp(H-S)/a$ exactly: $\frac{d}{dt}(C_HH+C_SS)=J-(S-A)/b$. On the modal solution this is the per-mode identity $(C_H+C_Sr_i)\lambda_i=-g_br_i$, which follows from the two eigen-equations ($g(r_i-1)=C_H\lambda_i$ and $g-(g+g_b)r_i=C_S\lambda_ir_i$; add them). This identity holds for *every* solution of the ODE, regardless of initial state or amplitudes, so verifying it confirms the eigenpairs and the bookkeeping but says nothing about $\alpha_i$, the initial-condition fit, or $t^*$. The transient shape must be verified separately: the tests check both node equations and the initial conditions pointwise and compare against an independent RK4 integration. Immediate consequence: at $t=0$ the front loss (2.595 W) exceeds $J$ (0.1 W), so total stored energy *decreases from the first instant* even while $S$ and $T_o$ rise — the rise is redistribution from $C_H$ to $C_S$, not storage growth. Energy above ambient: $C_H\cdot35+C_S\cdot33\approx1235.4$ J initially; $\int_0^\infty[(S-A)/b-J]dt=C_Hu_0+C_Sv_0\approx674.6+514.8\approx1189.3$ J leaves through the front; the remaining $(C_H+C_S)Jb\approx46.1$ J is the $J$-sustained asymptote.

**What this does and does not imply.** It implies that, within this lumped model, the 20 J/K body node keeps feeding the surface node for minutes after shutoff (slow mode ≈463 s) with a small, brief surface overshoot set by $a\ll b$. It does not imply anything about a real panel: $T_o$ is an algebraic quasi-steady reconstruction (no storage between $S$ and ambient), spatial gradients, lateral conduction, radiation, contact and real sensor behaviour are absent, and the 60/58 C state is manufactured, not simulation output.

---

## Part B — Extension: the nine executed scenarios (post-shutoff from the 900 s state)

For $t\ge900$ s the system is $C_Hx'=-g(x-y)-g_rx$, $C_Sy'=g(x-y)+J-g_by$ (reservoir = ambient = 25 C, so rear flux is $g_rx$), with $g_r=0.5$ W/K (intact) or $0$ (rear loss), $J=0.1$ or $0$ W, and per stack $a=0.2176852,\,0.4028704,\,0.7732407$ K/W, $C_S=16.2239,\,31.6739,\,62.5739$ J/K, $g_b=1/(a+12.5)$. Same derivation with
$$p=\frac{g+g_r}{C_H},\ q=\frac{g+g_b}{C_S},\ \Delta=\frac{gg_b+gg_r+g_rg_b}{C_HC_S},\ D=(p-q)^2+\frac{4g^2}{C_HC_S}>0,\ r_i=1+\frac{g_r+\lambda_iC_H}{g},$$
asymptote $y_\infty=J(g+g_r)/(gg_b+gg_r+g_rg_b)$, $x_\infty=((g+g_b)y_\infty-J)/g$ (reduces to $Jb$ for $g_r=0$ and to $0$ for $J=0$), $u_0=H(900)-A-x_\infty$, $v_0=S(900)-A-y_\infty$, and
$$t_{\rm peak}=900+\frac{1}{\lambda_1-\lambda_2}\ln\frac{-r_2\lambda_2\,(r_1u_0-v_0)}{r_1\lambda_1\,(v_0-r_2u_0)},\quad S_{\rm peak}=A+y_\infty+\alpha_1r_1e^{\lambda_1t^*}\Big(1-\frac{\lambda_1}{\lambda_2}\Big),\quad T_{o,\rm peak}=A+12.5g_b(S_{\rm peak}-A),$$
valid only in the "$R>1$, $c_1<0$" branch; otherwise the post-shutoff surface maximum is at 900 s. The per-mode energy identity becomes $(C_H+C_Sr_i)\lambda_i+g_r+g_br_i=0$.

Mode constants (estimates): rear loss H1 $\lambda\approx(-0.0021594,-0.51553)$, $r\approx(0.99060,-1.24445)$; H2 $\lambda\approx(-0.0014928,-0.20343)$, $r\approx(0.98797,-0.63912)$; H3 $\lambda\approx(-0.00090925,-0.085625)$, $r\approx(0.98594,-0.32418)$; intact H1 $\lambda\approx(-0.015777,-0.52690)$, $r\approx(1.04015,-1.18514)$. Fast time constants 1.9/4.9/11.7 s are consistent with the reported discrete peaks at 901/904/913–914 s. Intact cases: the 900 s state is (nearly) the heating steady state where $S'=0$; removing $P$ gives $S''=gH'/C_S<0$, so no post-shutoff rise — peak at 900 s as reported. (H3 intact retains a ≈0.04 K heating transient at 900 s, so the formula may return $t^*\sim0.05$ s with a rise $<10^{-5}$ K; the code reports it, the verifier treats it as "at shutoff" within tolerance.)

**What Red must supply from execution** (the formula needs it; I cannot compute it): for each of the nine scenarios, $(H,S)$ at the trace row with `time == 900.0` (end of the 5 W segment; its `surface` must equal $A+12.5g_b(S-A)$), the `dt` used (report implies 1.0 s), and confirmation of the segment schedule assumed in `scenario_segments` (intact: 900 s at 5 W then 2700 s at 0 W; rear loss: 600 s, then 300 s with `gr=0.0`, then 2700 s at 0 W; sensor $J$ constant throughout). The code reads the state from the trace itself, so running `peak_exact.py` beside `rc_transient.py` is sufficient. As a labelled cross-check it also computes a fully analytic 900 s state by chaining the same closed form over the pre-shutoff phases; its difference from the executed state is backward-Euler pre-shutoff error (expected ≈0.02 K for H1 at dt = 1 s).

**Interpretation of comparisons.** The discrete peak is an argmax on a 1 s grid (≤~1 s offset) computed by first-order backward Euler, whose fast-mode error at dt = 1 s is ~0.02–0.05 K for H1 (report's own dt 1 vs 0.5 difference: 0.0198 K). Default advisory tolerances: 2 s and 0.1 K. Re-running at dt = 0.25 and 0.125 should shrink the differences roughly linearly; a residual that does not shrink indicates a schedule or model mismatch, not a formula tolerance issue.

---

## Code (unexecuted; standard library only)

FILE: validation/thermal_transient/peak_exact.py
```python
"""peak_exact.py -- closed-form two-eigenmode post-shutoff solution for Coda's nonliving two-node
RC model T0-LUMP2-1 (validation/thermal_transient/rc_transient.py).

Red/Claude contribution for thermal-peak-exact-001, written without execution.  Standard library
only, deterministic, no network; writes only to a caller-supplied output path.  Lumped computational
reference only: not measured hardware, not a contact-safety assessment, not a design recommendation.

Phase equations (t measured from the start of the phase, ambient = reservoir = A):
    C_H dH/dt = -g (H - S) - gr (H - A) + p
    C_S dS/dt =  g (H - S) + j  - gb (S - A)
g = 1/a (series conductance H->S), gb = 1/(a + rconv) (front branch), gr rear conductance
(0.5 W/K intact, 0 after rear loss), p body power, j sensor power.
Reconstructed surface: T_o = A + rconv * gb * (S - A), as in rc_transient.simulate().
"""
from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict, dataclass

AMBIENT_C = 25.0
RCONV_K_PER_W = 12.5
AREA_M2 = 0.01
BODY_CAPACITY_J_PER_K = 20.0
REAR_CONDUCTANCE_W_PER_K = 0.5
THICKNESS_M = {"H1": 0.0005, "H2": 0.001, "H3": 0.002}
SHUTOFF_S = 900.0
REAR_LOSS_S = 600.0
HORIZON_S = 3600.0
BODY_POWER_W = 5.0
SENSOR_POWER_W = 0.1

# Report order.  ASSUMPTION: this schedule reconstructs Coda's "Executed scenarios" paragraph.
SCENARIOS = [("H1", "intact", 0.1), ("H1", "rear_loss", 0.1), ("H1", "rear_loss", 0.0),
             ("H2", "intact", 0.1), ("H2", "rear_loss", 0.1), ("H2", "rear_loss", 0.0),
             ("H3", "intact", 0.1), ("H3", "rear_loss", 0.1), ("H3", "rear_loss", 0.0)]


class DegenerateCase(ValueError):
    """Raised instead of silently evaluating sqrt/log on invalid values."""


def front_resistance(thickness_m: float, area_m2: float = AREA_M2) -> float:
    """Series resistance a (K/W) between H and S; identical expression to rc_transient.nominal()."""
    return thickness_m / (0.27 * area_m2) + 0.00005 / (2 * 0.20 * area_m2) + 0.0002 / area_m2


def surface_node_capacity(thickness_m: float, area_m2: float = AREA_M2) -> float:
    """C_S (J/K) as in rc_transient.nominal(): silicone (cp 1500 assumed) plus film."""
    return 1030 * area_m2 * (2 * thickness_m) * 1500 + 1420 * area_m2 * 0.00005 * 1090


@dataclass(frozen=True)
class Phase:
    ch: float
    cs: float
    g: float
    gb: float
    gr: float
    p: float
    j: float
    ambient: float = AMBIENT_C
    rconv: float = RCONV_K_PER_W

    def surface(self, s: float) -> float:
        return self.ambient + self.rconv * self.gb * (s - self.ambient)


def stack_phase(stack: str, rear_intact: bool, body_w: float, sensor_w: float) -> Phase:
    a = front_resistance(THICKNESS_M[stack])
    return Phase(ch=BODY_CAPACITY_J_PER_K, cs=surface_node_capacity(THICKNESS_M[stack]),
                 g=1.0 / a, gb=1.0 / (a + RCONV_K_PER_W),
                 gr=REAR_CONDUCTANCE_W_PER_K if rear_intact else 0.0, p=body_w, j=sensor_w)


def manufactured_phase() -> Phase:
    """Coda's manufactured post-shutoff case: H1 resistances/capacity, no rear path, J = 0.1 W."""
    return stack_phase("H1", rear_intact=False, body_w=0.0, sensor_w=0.1)


@dataclass(frozen=True)
class Modes:
    lam_slow: float
    lam_fast: float
    r_slow: float
    r_fast: float
    x_inf: float  # H_inf - ambient
    y_inf: float  # S_inf - ambient


def modes(ph: Phase) -> Modes:
    """Eigenvalues (both negative, distinct), eigenvector second components, and steady state."""
    if min(ph.ch, ph.cs) <= 0.0:
        raise DegenerateCase("capacities must be positive")
    if min(ph.g, ph.gb, ph.gr) < 0.0:
        raise DegenerateCase("negative conductance")
    if ph.g == 0.0:
        raise DegenerateCase("g = 0: nodes decoupled; S(t) is a single exponential with no interior "
                             "extremum (the only configuration allowing a repeated eigenvalue)")
    det_num = ph.g * ph.gb + ph.g * ph.gr + ph.gr * ph.gb
    if det_num == 0.0:
        raise DegenerateCase("gb = gr = 0: zero eigenvalue; no finite steady state for a positive "
                             "source, peak formula not applicable")
    pcoef = (ph.g + ph.gr) / ph.ch
    qcoef = (ph.g + ph.gb) / ph.cs
    disc = (pcoef - qcoef) ** 2 + 4.0 * ph.g * ph.g / (ph.ch * ph.cs)  # = trace^2 - 4 det > 0
    root = math.sqrt(disc)
    lam_fast = -0.5 * (pcoef + qcoef + root)
    det = det_num / (ph.ch * ph.cs)
    lam_slow = det / lam_fast  # product of eigenvalues = det; avoids cancellation
    r_slow = 1.0 + (ph.gr + lam_slow * ph.ch) / ph.g
    r_fast = 1.0 + (ph.gr + lam_fast * ph.ch) / ph.g
    y_inf = (ph.g * (ph.p + ph.j) + ph.gr * ph.j) / det_num
    x_inf = ((ph.g + ph.gb) * y_inf - ph.j) / ph.g
    return Modes(lam_slow, lam_fast, r_slow, r_fast, x_inf, y_inf)


@dataclass(frozen=True)
class Amplitudes:
    a_slow: float
    a_fast: float


def amplitudes(ph: Phase, md: Modes, h0: float, s0: float) -> Amplitudes:
    u0 = h0 - ph.ambient - md.x_inf
    v0 = s0 - ph.ambient - md.y_inf
    denom = md.r_slow - md.r_fast  # > 0
    return Amplitudes((v0 - md.r_fast * u0) / denom, (md.r_slow * u0 - v0) / denom)


def state(ph: Phase, md: Modes, amp: Amplitudes, t: float) -> dict:
    """Exact H, S, surface and time derivatives at time t (from phase start)."""
    e_slow = math.exp(md.lam_slow * t)
    e_fast = math.exp(md.lam_fast * t)
    u = amp.a_slow * e_slow + amp.a_fast * e_fast
    v = amp.a_slow * md.r_slow * e_slow + amp.a_fast * md.r_fast * e_fast
    du = amp.a_slow * md.lam_slow * e_slow + amp.a_fast * md.lam_fast * e_fast
    dv = amp.a_slow * md.r_slow * md.lam_slow * e_slow + amp.a_fast * md.r_fast * md.lam_fast * e_fast
    h = ph.ambient + md.x_inf + u
    s = ph.ambient + md.y_inf + v
    return dict(t=t, H=h, S=s, surface=ph.surface(s), dH=du, dS=dv)


@dataclass(frozen=True)
class SurfaceExtremum:
    status: str
    t_star: float | None
    ratio: float | None
    initial_slope: float
    slow_velocity: float
    fast_velocity: float


def surface_extremum(md: Modes, amp: Amplitudes) -> SurfaceExtremum:
    """Stationary point of S (and of the affine surface); explicit limiting cases."""
    c_slow = amp.a_slow * md.r_slow * md.lam_slow
    c_fast = amp.a_fast * md.r_fast * md.lam_fast
    slope0 = c_slow + c_fast
    if c_slow == 0.0 and c_fast == 0.0:
        return SurfaceExtremum("constant", None, None, slope0, c_slow, c_fast)
    if c_slow == 0.0 or c_fast == 0.0:
        return SurfaceExtremum("single_mode_monotone", None, None, slope0, c_slow, c_fast)
    ratio = -c_fast / c_slow
    if ratio <= 0.0:
        return SurfaceExtremum("monotone_no_stationary_point", None, ratio, slope0, c_slow, c_fast)
    t_star = math.log(ratio) / (md.lam_slow - md.lam_fast)
    if t_star <= 0.0:
        return SurfaceExtremum("stationary_at_or_before_zero", t_star, ratio, slope0, c_slow, c_fast)
    status = "post_shutoff_maximum" if c_slow < 0.0 else "post_shutoff_minimum"
    return SurfaceExtremum(status, t_star, ratio, slope0, c_slow, c_fast)


def post_shutoff_peak(ph: Phase, h0: float, s0: float, shutoff_time: float = 0.0) -> dict:
    """Closed-form post-shutoff surface peak from the state (h0, s0) at shutoff."""
    md = modes(ph)
    amp = amplitudes(ph, md, h0, s0)
    ext = surface_extremum(md, amp)
    at0 = state(ph, md, amp, 0.0)
    result = dict(H0=h0, S0=s0, surface0=at0["surface"], dH0=at0["dH"], dS0=at0["dS"],
                  H_inf=ph.ambient + md.x_inf, S_inf=ph.ambient + md.y_inf,
                  surface_inf=ph.surface(ph.ambient + md.y_inf),
                  modes=asdict(md), amplitudes=asdict(amp), extremum=asdict(ext),
                  rising_criterion_met=at0["dS"] > 0.0, shutoff_time=shutoff_time)
    if ext.status == "post_shutoff_maximum":
        pk = state(ph, md, amp, ext.t_star)
        result.update(peak_kind="interior_maximum", peak_time=shutoff_time + ext.t_star,
                      peak_surface=pk["surface"], peak_S=pk["S"], H_at_peak=pk["H"])
        return result
    late_sign = ext.slow_velocity if ext.slow_velocity != 0.0 else ext.fast_velocity
    if late_sign <= 0.0 and ext.initial_slope <= 0.0:
        result.update(peak_kind="at_shutoff", peak_time=shutoff_time, peak_surface=at0["surface"],
                      peak_S=s0, H_at_peak=h0)
    else:
        s_sup = max(s0, ph.ambient + md.y_inf)
        result.update(peak_kind="supremum_not_attained_or_at_shutoff", peak_time=None,
                      peak_surface=ph.surface(s_sup), peak_S=s_sup, H_at_peak=None)
    return result


def mode_energy_identity_residuals(ph: Phase, md: Modes) -> list:
    """Per-mode form of d(C_H H + C_S S)/dt = j - gb (S-A) - gr (H-A): (C_H + C_S r) lam + gr + gb r = 0.
    Holds for every solution of the ODE; it does not test amplitudes or the peak algebra."""
    return [(ph.ch + ph.cs * r) * lam + ph.gr + ph.gb * r
            for lam, r in ((md.lam_slow, md.r_slow), (md.lam_fast, md.r_fast))]


def rk4_integrate(ph: Phase, h0: float, s0: float, t_end: float, dt: float) -> list:
    """Independent classical RK4 integration of the two ODEs (shape check, not used in the formula)."""
    def rhs(h, s):
        dh = (-ph.g * (h - s) - ph.gr * (h - ph.ambient) + ph.p) / ph.ch
        ds = (ph.g * (h - s) + ph.j - ph.gb * (s - ph.ambient)) / ph.cs
        return dh, ds
    n = int(round(t_end / dt))
    h, s = h0, s0
    samples = [(0.0, h, s)]
    for i in range(n):
        k1 = rhs(h, s)
        k2 = rhs(h + 0.5 * dt * k1[0], s + 0.5 * dt * k1[1])
        k3 = rhs(h + 0.5 * dt * k2[0], s + 0.5 * dt * k2[1])
        k4 = rhs(h + dt * k3[0], s + dt * k3[1])
        h += dt * (k1[0] + 2 * k2[0] + 2 * k3[0] + k4[0]) / 6.0
        s += dt * (k1[1] + 2 * k2[1] + 2 * k3[1] + k4[1]) / 6.0
        samples.append(((i + 1) * dt, h, s))
    return samples


def scenario_segments(case: str, sensor_w: float) -> list:
    """ASSUMED reconstruction of Coda's schedule (REPORT.md 'Executed scenarios')."""
    if case == "intact":
        return [dict(duration=SHUTOFF_S, p=BODY_POWER_W, j=sensor_w),
                dict(duration=HORIZON_S - SHUTOFF_S, p=0.0, j=sensor_w)]
    if case == "rear_loss":
        return [dict(duration=REAR_LOSS_S, p=BODY_POWER_W, j=sensor_w),
                dict(duration=SHUTOFF_S - REAR_LOSS_S, p=BODY_POWER_W, j=sensor_w, gr=0.0),
                dict(duration=HORIZON_S - SHUTOFF_S, p=0.0, j=sensor_w)]
    raise ValueError("case must be 'intact' or 'rear_loss'")


def analytic_shutoff_state(stack: str, case: str, sensor_w: float) -> tuple:
    """Exact (H, S) at 900 s by chaining the closed form over the pre-shutoff phases (cross-check)."""
    h = s = AMBIENT_C
    if case == "intact":
        phases = [(stack_phase(stack, True, BODY_POWER_W, sensor_w), SHUTOFF_S)]
    else:
        phases = [(stack_phase(stack, True, BODY_POWER_W, sensor_w), REAR_LOSS_S),
                  (stack_phase(stack, False, BODY_POWER_W, sensor_w), SHUTOFF_S - REAR_LOSS_S)]
    for ph, duration in phases:
        md = modes(ph)
        st = state(ph, md, amplitudes(ph, md, h, s), duration)
        h, s = st["H"], st["S"]
    return h, s


def verify_trace(trace: list, ph: Phase, shutoff_time: float = SHUTOFF_S,
                 time_tol_s: float = 2.0, temp_tol_k: float = 0.1) -> dict:
    """Compare an rc_transient.simulate() trace with the closed form started from its shutoff row.
    Shape check (pointwise H/S deviation, peak) is separate from the discrete energy identity check."""
    rows = [r for r in trace if r["time"] >= shutoff_time - 1e-9]
    if not rows or abs(rows[0]["time"] - shutoff_time) > 1e-9:
        raise ValueError("trace has no sample exactly at the shutoff time")
    for r in rows[1:]:
        if r["p"] != 0.0 or r["j"] != ph.j:
            raise ValueError("post-shutoff trace sources differ from the supplied phase")
    first = rows[0]
    h0, s0 = first["H"], first["S"]
    exact = post_shutoff_peak(ph, h0, s0, shutoff_time)
    md = modes(ph)
    amp = amplitudes(ph, md, h0, s0)
    best = max(rows, key=lambda r: r["surface"])  # first maximal sample
    dev_h = dev_s = dev_t = 0.0
    for r in rows:
        ex = state(ph, md, amp, r["time"] - shutoff_time)
        dev_h = max(dev_h, abs(r["H"] - ex["H"]))
        dev_s = max(dev_s, abs(r["S"] - ex["S"]))
        dev_t = max(dev_t, abs(r["surface"] - ex["surface"]))
    injected = sum(r["dt"] * r["j"] for r in rows[1:])
    exported = sum(r["dt"] * (r["front"] + r["rear"]) for r in rows[1:])
    stored = ph.ch * (rows[-1]["H"] - h0) + ph.cs * (rows[-1]["S"] - s0)
    exact_peak_time = exact["peak_time"] if exact["peak_time"] is not None else shutoff_time
    dt_peak = best["time"] - exact_peak_time
    d_surface = best["surface"] - exact["peak_surface"]
    within = (abs(dt_peak) <= time_tol_s and abs(d_surface) <= temp_tol_k and dev_s <= temp_tol_k
              and dev_h <= temp_tol_k)
    return dict(H900=h0, S900=s0, surface900=first["surface"],
                surface900_reconstruction_error=abs(first["surface"] - ph.surface(s0)),
                exact=exact, discrete_peak_time=best["time"], discrete_peak_surface=best["surface"],
                peak_time_difference_s=dt_peak, peak_surface_difference_K=d_surface,
                max_abs_dev_H=dev_h, max_abs_dev_S=dev_s, max_abs_dev_surface=dev_t,
                discrete_energy_residual_J=stored - injected + exported,
                mode_energy_identity_residuals=mode_energy_identity_residuals(ph, md),
                final_time=rows[-1]["time"], final_H_executed=rows[-1]["H"],
                final_H_exact=state(ph, md, amp, rows[-1]["time"] - shutoff_time)["H"],
                within_tolerance=within, time_tol_s=time_tol_s, temp_tol_k=temp_tol_k)


def manufactured_case_report() -> dict:
    ph = manufactured_phase()
    res = post_shutoff_peak(ph, 60.0, 58.0, 0.0)
    md = modes(ph)
    res.update(a_K_per_W=1.0 / ph.g, b_K_per_W=1.0 / ph.gb, C_S=ph.cs,
               energy_identity_residuals=mode_energy_identity_residuals(ph, md),
               initial_energy_above_ambient_J=ph.ch * 35.0 + ph.cs * 33.0,
               exported_after_shutoff_J=ph.ch * (35.0 - md.x_inf) + ph.cs * (33.0 - md.y_inf))
    return res


def run_executed_scenarios(rc, dt: float) -> list:
    out = []
    for stack, case, sensor_w in SCENARIOS:
        sim = rc.simulate(rc.nominal(stack), (AMBIENT_C, AMBIENT_C), scenario_segments(case, sensor_w), dt)
        ph = stack_phase(stack, case == "intact", 0.0, sensor_w)
        ver = verify_trace(sim["trace"], ph)
        h_an, s_an = analytic_shutoff_state(stack, case, sensor_w)
        an = post_shutoff_peak(ph, h_an, s_an, SHUTOFF_S)
        md = modes(ph)
        h_final_an = state(ph, md, amplitudes(ph, md, h_an, s_an), HORIZON_S - SHUTOFF_S)["H"]
        out.append(dict(stack=stack, case=case, sensor_w=sensor_w, dt=dt, executed=ver,
                        analytic_900s=dict(H=h_an, S=s_an, peak_time=an["peak_time"],
                                           peak_surface=an["peak_surface"], final_H=h_final_an),
                        max_energy_residual_program_J=sim["max_energy_residual_abs_J"]))
    return out


def _fmt(x) -> str:
    return "None" if x is None else f"{x:.6f}"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Closed-form post-shutoff surface peak (T0-LUMP2-1).")
    parser.add_argument("--dt", type=float, default=1.0, help="backward-Euler step for scenario runs")
    parser.add_argument("--out", default=None, help="optional JSON output path (only file written)")
    parser.add_argument("--no-rc", action="store_true", help="skip rc_transient scenario execution")
    parser.add_argument("--state", nargs=5, metavar=("STACK", "CASE", "SENSOR_W", "H900", "S900"),
                        help="compute the exact peak from a supplied 900 s state")
    args = parser.parse_args(argv)
    report = dict(manufactured=manufactured_case_report())
    m = report["manufactured"]
    print("Manufactured case (H0=60, S0=58, J=0.1 W, no rear path):")
    print(f"  a={m['a_K_per_W']:.7f} K/W b={m['b_K_per_W']:.7f} K/W lam_slow={m['modes']['lam_slow']:.7f}"
          f" lam_fast={m['modes']['lam_fast']:.7f} r_slow={m['modes']['r_slow']:.6f} r_fast={m['modes']['r_fast']:.6f}")
    print(f"  dS/dt(0+)={m['dS0']:.6f} K/s dH/dt(0+)={m['dH0']:.6f} K/s status={m['extremum']['status']}"
          f" ratio={_fmt(m['extremum']['ratio'])} t*={_fmt(m['extremum']['t_star'])} s")
    print(f"  surface(0)={m['surface0']:.6f} peak surface={_fmt(m['peak_surface'])} peak S={_fmt(m['peak_S'])}"
          f" H at peak={_fmt(m['H_at_peak'])} asymptotes H=S={m['S_inf']:.6f} surface={m['surface_inf']:.6f}")
    print(f"  per-mode energy identity residuals={m['energy_identity_residuals']}")
    if args.state:
        stack, case, sensor_w, h900, s900 = args.state
        ph = stack_phase(stack, case == "intact", 0.0, float(sensor_w))
        res = post_shutoff_peak(ph, float(h900), float(s900), SHUTOFF_S)
        report["supplied_state"] = dict(stack=stack, case=case, sensor_w=float(sensor_w), result=res)
        print(f"Supplied state {stack}/{case}/J={sensor_w}: peak time={_fmt(res['peak_time'])} s"
              f" peak surface={_fmt(res['peak_surface'])} C status={res['extremum']['status']}")
    if not args.no_rc:
        try:
            import rc_transient as rc
        except ImportError:
            rc = None
            print("rc_transient not importable: executed-scenario verification skipped")
        if rc is not None:
            rows = run_executed_scenarios(rc, args.dt)
            report["scenarios"] = rows
            print(f"Executed scenarios (dt={args.dt}); exact = closed form from executed 900 s state;"
                  " analytic = closed form chained from 25 C")
            print("stack case     J    H900       S900       exact_tpk  exact_pk   disc_tpk  disc_pk    "
                  "dev_S    an_tpk     an_pk      ok")
            for row in rows:
                v = row["executed"]
                e = v["exact"]
                a = row["analytic_900s"]
                print(f"{row['stack']}  {row['case']:9s}{row['sensor_w']:.1f}  {v['H900']:.6f} {v['S900']:.6f}"
                      f"  {_fmt(e['peak_time']):>10s} {_fmt(e['peak_surface'])} {v['discrete_peak_time']:8.1f}"
                      f"  {v['discrete_peak_surface']:.6f} {v['max_abs_dev_S']:.5f} {_fmt(a['peak_time']):>10s}"
                      f" {_fmt(a['peak_surface'])} {v['within_tolerance']}")
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=1, sort_keys=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

FILE: validation/thermal_transient/test_peak_exact.py
```python
"""Tests for peak_exact.py (unexecuted by the author; Red executes).  Standard library only."""
import math
import unittest
from dataclasses import replace

import peak_exact as pe

try:
    import rc_transient as rc
except ImportError:  # pragma: no cover
    rc = None

# Coda's executed backward-Euler values from REPORT.md (dt assumed 1 s); used only with loose
# tolerances that allow first-order discretization error.  Not physical validation.
REPORT = {
    ("H1", "intact", 0.1): dict(H900=33.831193, pk=33.554994, tpk=900.0, H3600=25.170303),
    ("H1", "rear_loss", 0.1): dict(H900=61.143480, pk=59.747155, tpk=901.0, H3600=26.374204),
    ("H1", "rear_loss", 0.0): dict(H900=60.446481, pk=59.055570, tpk=901.0, H3600=25.104135),
    ("H2", "intact", 0.1): dict(H900=33.861287, pk=33.362444, tpk=900.0, H3600=25.168602),
    ("H2", "rear_loss", 0.1): dict(H900=55.545063, pk=53.153638, tpk=904.0, H3600=26.798252),
    ("H2", "rear_loss", 0.0): dict(H900=54.963957, pk=52.578375, tpk=904.0, H3600=25.520601),
    ("H3", "intact", 0.1): dict(H900=33.884652, pk=32.963939, tpk=900.0, H3600=25.165436),
    ("H3", "rear_loss", 0.1): dict(H900=50.169875, pk=45.881263, tpk=914.0, H3600=28.187988),
    ("H3", "rear_loss", 0.0): dict(H900=49.704285, pk=45.421846, tpk=913.0, H3600=26.934740),
}


def all_phases():
    return [pe.manufactured_phase()] + [pe.stack_phase(s, intact, p, j) for s in ("H1", "H2", "H3")
                                        for intact in (True, False) for p in (0.0, 5.0) for j in (0.0, 0.1)]


class ParameterTests(unittest.TestCase):
    def test_resistance_and_capacities_match_coda_nominal(self):
        self.assertAlmostEqual(pe.front_resistance(0.0005), 2351 / 10800, places=12)
        self.assertAlmostEqual(pe.surface_node_capacity(0.0005), 16.2239, places=9)
        self.assertAlmostEqual(pe.surface_node_capacity(0.001), 31.6739, places=9)
        self.assertAlmostEqual(pe.surface_node_capacity(0.002), 62.5739, places=9)


class ModeTests(unittest.TestCase):
    def test_eigenpairs_satisfy_matrix_equation_and_ordering(self):
        for ph in all_phases():
            md = pe.modes(ph)
            self.assertLess(md.lam_fast, md.lam_slow)
            self.assertLess(md.lam_slow, 0.0)
            for lam, r in ((md.lam_slow, md.r_slow), (md.lam_fast, md.r_fast)):
                row1 = (-(ph.g + ph.gr) + ph.g * r) / ph.ch - lam
                row2 = (ph.g - (ph.g + ph.gb) * r) / ph.cs - lam * r
                self.assertLess(abs(row1), 1e-12)
                self.assertLess(abs(row2), 1e-12)

    def test_steady_state_satisfies_both_equations(self):
        for ph in all_phases():
            md = pe.modes(ph)
            h, s = ph.ambient + md.x_inf, ph.ambient + md.y_inf
            self.assertLess(abs(-ph.g * (h - s) - ph.gr * (h - ph.ambient) + ph.p), 1e-9)
            self.assertLess(abs(ph.g * (h - s) + ph.j - ph.gb * (s - ph.ambient)), 1e-9)

    def test_per_mode_energy_identity(self):
        for ph in all_phases():
            for res in pe.mode_energy_identity_residuals(ph, pe.modes(ph)):
                self.assertLess(abs(res), 1e-10)

    def test_degenerate_cases_raise_instead_of_invalid_sqrt_or_log(self):
        ph = pe.manufactured_phase()
        with self.assertRaises(pe.DegenerateCase):
            pe.modes(replace(ph, g=0.0))
        with self.assertRaises(pe.DegenerateCase):
            pe.modes(replace(ph, gb=0.0, gr=0.0))


class ManufacturedCaseTests(unittest.TestCase):
    def setUp(self):
        self.ph = pe.manufactured_phase()
        self.md = pe.modes(self.ph)
        self.amp = pe.amplitudes(self.ph, self.md, 60.0, 58.0)
        self.res = pe.post_shutoff_peak(self.ph, 60.0, 58.0, 0.0)

    def test_initial_conditions_and_both_odes_pointwise(self):
        st0 = pe.state(self.ph, self.md, self.amp, 0.0)
        self.assertAlmostEqual(st0["H"], 60.0, places=9)
        self.assertAlmostEqual(st0["S"], 58.0, places=9)
        for t in (0.0, 0.5, 3.75, 50.0, 1000.0):
            st = pe.state(self.ph, self.md, self.amp, t)
            r_h = self.ph.ch * st["dH"] + self.ph.g * (st["H"] - st["S"]) + self.ph.gr * (st["H"] - 25.0) - self.ph.p
            r_s = self.ph.cs * st["dS"] - self.ph.g * (st["H"] - st["S"]) - self.ph.j + self.ph.gb * (st["S"] - 25.0)
            self.assertLess(abs(r_h), 1e-9)
            self.assertLess(abs(r_s), 1e-9)

    def test_hand_estimates(self):
        res, ext, md = self.res, self.res["extremum"], self.md
        self.assertEqual(ext["status"], "post_shutoff_maximum")
        self.assertTrue(3.70 < ext["t_star"] < 3.80)
        self.assertAlmostEqual(res["peak_surface"], 57.964, delta=0.01)
        self.assertAlmostEqual(res["peak_S"], 58.538, delta=0.01)
        self.assertAlmostEqual(res["H_at_peak"], 59.090, delta=0.01)
        self.assertAlmostEqual(res["dS0"], 0.4125, delta=0.002)
        self.assertLess(res["dH0"], 0.0)
        self.assertAlmostEqual(res["surface0"], 57.435, delta=0.002)
        self.assertAlmostEqual(md.lam_slow, -0.0021594, delta=1e-5)
        self.assertAlmostEqual(md.lam_fast, -0.51553, delta=1e-3)
        self.assertAlmostEqual(res["surface_inf"], 26.25, places=9)
        self.assertTrue(res["rising_criterion_met"])

    def test_stationarity_balance_at_peak(self):
        pk = pe.state(self.ph, self.md, self.amp, self.res["extremum"]["t_star"])
        self.assertLess(abs(pk["dS"]), 1e-9)
        self.assertLess(abs(self.ph.g * (pk["H"] - pk["S"]) + self.ph.j - self.ph.gb * (pk["S"] - 25.0)), 1e-9)

    def test_rk4_independent_integration_matches_modal_solution(self):
        samples = pe.rk4_integrate(self.ph, 60.0, 58.0, 20.0, 0.01)
        worst = max(abs(s - pe.state(self.ph, self.md, self.amp, t)["S"]) for t, h, s in samples)
        self.assertLess(worst, 1e-7)
        t_max, _h, s_max = max(samples, key=lambda row: row[2])
        self.assertLess(abs(t_max - self.res["extremum"]["t_star"]), 0.011)
        self.assertLess(abs(s_max - self.res["peak_S"]), 1e-5)

    def test_energy_identity_vs_shape(self):
        # Identity holds for ANY amplitudes (here deliberately wrong ones): it cannot verify the shape.
        wrong = pe.Amplitudes(a_slow=1.0, a_fast=-3.0)
        for t in (0.0, 2.0, 100.0):
            st = pe.state(self.ph, self.md, wrong, t)
            lhs = self.ph.ch * st["dH"] + self.ph.cs * st["dS"]
            rhs = self.ph.j - self.ph.gb * (st["S"] - 25.0)
            self.assertLess(abs(lhs - rhs), 1e-9)
        self.assertGreater(abs(pe.state(self.ph, self.md, wrong, 0.0)["H"] - 60.0), 1.0)


class ClassificationTests(unittest.TestCase):
    def test_zero_fast_amplitude_is_single_mode_monotone(self):
        md = pe.modes(pe.manufactured_phase())
        ext = pe.surface_extremum(md, pe.Amplitudes(a_slow=1.0, a_fast=0.0))
        self.assertEqual(ext.status, "single_mode_monotone")
        self.assertIsNone(ext.t_star)

    def test_state_on_slow_mode_has_no_post_shutoff_extremum(self):
        ph = pe.manufactured_phase()
        md = pe.modes(ph)
        res = pe.post_shutoff_peak(ph, 25.0 + md.x_inf + 1.0, 25.0 + md.y_inf + md.r_slow, 0.0)
        self.assertNotIn(res["extremum"]["status"], ("post_shutoff_maximum", "post_shutoff_minimum"))

    def test_equal_initial_temperatures_do_not_rise(self):
        res = pe.post_shutoff_peak(pe.manufactured_phase(), 58.0, 58.0, 0.0)
        self.assertLess(res["dS0"], 0.0)
        self.assertEqual(res["peak_kind"], "at_shutoff")
        self.assertEqual(res["peak_time"], 0.0)


class VerifyTraceTests(unittest.TestCase):
    def test_exact_samples_pass_verification(self):
        ph = pe.manufactured_phase()
        md = pe.modes(ph)
        amp = pe.amplitudes(ph, md, 60.0, 58.0)
        trace = []
        for k in range(61):
            st = pe.state(ph, md, amp, float(k))
            trace.append(dict(time=900.0 + k, dt=0.0 if k == 0 else 1.0, H=st["H"], S=st["S"],
                              surface=st["surface"], front=ph.gb * (st["S"] - 25.0),
                              rear=ph.gr * (st["H"] - 25.0), p=0.0, j=ph.j))
        ver = pe.verify_trace(trace, ph)
        self.assertLess(ver["max_abs_dev_S"], 1e-9)
        self.assertLessEqual(abs(ver["discrete_peak_time"] - ver["exact"]["peak_time"]), 0.75)
        self.assertTrue(0.0 <= ver["exact"]["peak_surface"] - ver["discrete_peak_surface"] <= 0.01)
        self.assertTrue(ver["within_tolerance"])
        self.assertTrue(math.isfinite(ver["discrete_energy_residual_J"]))


class AnalyticVersusReportTests(unittest.TestCase):
    """Analytic chain vs Coda's executed table; loose tolerances absorb backward-Euler error.
    Depends on the ASSUMED schedule in peak_exact.scenario_segments."""

    def test_analytic_chain_against_report_values(self):
        for (stack, case, j), rep in REPORT.items():
            h900, s900 = pe.analytic_shutoff_state(stack, case, j)
            ph = pe.stack_phase(stack, case == "intact", 0.0, j)
            res = pe.post_shutoff_peak(ph, h900, s900, pe.SHUTOFF_S)
            self.assertAlmostEqual(h900, rep["H900"], delta=0.01 if case == "intact" else 0.1)
            self.assertAlmostEqual(res["peak_surface"], rep["pk"], delta=0.1)
            self.assertLessEqual(abs((res["peak_time"] or pe.SHUTOFF_S) - rep["tpk"]), 2.0)
            md = pe.modes(ph)
            h3600 = pe.state(ph, md, pe.amplitudes(ph, md, h900, s900), pe.HORIZON_S - pe.SHUTOFF_S)["H"]
            self.assertAlmostEqual(h3600, rep["H3600"], delta=0.05)
            if case == "intact":
                self.assertLess((res["peak_time"] or pe.SHUTOFF_S) - pe.SHUTOFF_S, 0.5)
                self.assertLess(res["peak_surface"] - res["surface0"], 1e-3)
            else:
                self.assertEqual(res["extremum"]["status"], "post_shutoff_maximum")


@unittest.skipUnless(rc is not None, "rc_transient.py not importable")
class ExecutedScenarioTests(unittest.TestCase):
    def test_h1_rear_loss_sensor_on_reproduces_report_and_verifies(self):
        sim = rc.simulate(rc.nominal("H1"), (25.0, 25.0), pe.scenario_segments("rear_loss", 0.1), 1.0)
        ver = pe.verify_trace(sim["trace"], pe.stack_phase("H1", False, 0.0, 0.1))
        self.assertAlmostEqual(ver["H900"], 61.143480, delta=1e-5)  # schedule assumption check
        self.assertEqual(ver["discrete_peak_time"], 901.0)
        self.assertAlmostEqual(ver["discrete_peak_surface"], 59.747155, delta=1e-5)
        self.assertAlmostEqual(sim["trace"][-1]["H"], 26.374204, delta=1e-5)
        self.assertLess(abs(ver["discrete_energy_residual_J"]), 1e-6)
        self.assertTrue(ver["within_tolerance"])

    def test_all_nine_scenarios_within_advisory_tolerance(self):
        for row in pe.run_executed_scenarios(rc, 1.0):
            self.assertTrue(row["executed"]["within_tolerance"], msg=f"{row['stack']}/{row['case']}/{row['sensor_w']}")


if __name__ == "__main__":
    unittest.main()
```

**How Red should run it** (in the sandbox, beside `rc_transient.py`): `python -B -I -m unittest -v test_peak_exact` then `python -B -I peak_exact.py --dt 1.0 --out <path>` and optionally `--dt 0.25` to watch the discrete/exact differences shrink. Red can also feed a checkpoint state directly: `python peak_exact.py --no-rc --state H1 rear_loss 0.1 <H900> <S900>`.

---

## Limitations, assumptions, and what is not done

- All numbers labelled "estimate" are hand arithmetic; tolerances in the tests are chosen from my error estimates (BE first-order error ≈0.02–0.05 K at dt = 1 s). If a test fails, report the printed values rather than loosening the tolerance.
- **Assumption:** `scenario_segments` reconstructs Coda's schedule (rear loss as `gr=0.0` from 600 s; sensor constant). `ExecutedScenarioTests` cross-checks this against the report's 61.143480 / 59.747155 / 26.374204 numbers to 1e-5; a failure there means the schedule or dt differs, not that the closed form is wrong.
- The exact peak from the executed 900 s state is exact for the continuous ODE started from a backward-Euler state; the analytic-chain state isolates pre-shutoff discretization error. Neither is physical validation.
- Not implemented: closed-form peak of $H$ (trivially $H$ falls immediately since $H(900)>S(900)$ and $H>A$); exact treatment of partial-step segment ends (not needed at dt = 1, 0.5, 0.25); any distributed, radiative, lateral or contact modelling.