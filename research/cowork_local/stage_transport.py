"""stage_transport.py - oxygen transport utilities for The Stage (research/cowork_local).

Author: Red (Claude, Anthropic) via Claude Cowork, 2026-10-15.
Status: computational investigation only. No tissue, clinical or viability claim.
Dependencies: numpy only (runs under the project's .venv-stage as well as plain Python 3.10+).

Model class (the same constitutive assumptions as research/artificial_blood/pf0.py):
  tissue slab 0 < x < H :  D C'' = q C / (Km + C)           C = FREE O2  [mol m^-3]
  channel wall x = 0    :  J = -D C'(0) = P (Cb - C(0))       J [mol m^-2 s^-1], P [m s^-1]
  back face x = H       :  C'(H) = 0
  lumen (plug flow)     :  Q beta dCb/dz = -W J(Cb)           Q [m^3 s^-1], W, z [m]
beta is PF0's hypothetical linear lumen capacity (C_total = beta * C_free). Only free O2
diffuses, so Q and beta enter only through the product Q*beta.

Continuum solution used here (independent of PF0's 24-cell x 32-segment grid):
  * Slab: RK4 shooting from the back face (C = s, C' = 0) to the wall, carrying the
    sensitivity dC/ds. For every slab-minimum s this gives the wall flux J(s), the lumen
    concentration Cb(s) = C(0) + J/P and dCb/ds to RK4 accuracy.
  * Lumen: dCb/dz = -W J(Cb)/(Q beta) is autonomous and separable, so the outlet obeys
        T(s_out) = W L / (Q beta),   T(s) = integral_s^{s_in} (dCb/ds') / J(s') ds',
    where s_in is the slab minimum at Cb = C_in (the infinite-flow "ceiling"). The minimum
    of a module sits at its outlet back face and is s_out itself.
  * Tables are built on a uniform grid in y = ln s and evaluated/inverted with cubic
    Hermite interpolation using the exact y-derivatives (4th-order accurate). Below the
    grid (s < 1e-14 C_in) the exact first-order (linear-kinetics) asymptote is used.

A vectorised re-implementation of PF0's own discrete equations (pf0_discrete_channel) is
included only to reproduce PF0's saved outputs; it is not used for the new results.
"""
import itertools
import numpy as np

UL_MIN = 1e-9 / 60.0  # m^3 s^-1 per microlitre per minute


# ----------------------------------------------------------------------------- slab
def shoot(s, H, q, Km, D, P, n_steps=1000):
    """RK4 shooting from the slab back face for an array of back-face values s [mol/m3].

    Returns a dict of arrays: C0 (tissue conc. at the wall), J (flux into tissue),
    Cb (lumen bulk concentration that produces this profile), dCb_ds, dJ_ds.
    """
    s = np.atleast_1d(np.asarray(s, dtype=float))
    h = H / n_steps
    w = s.copy()
    p = np.zeros_like(s)
    v = np.ones_like(s)
    u = np.zeros_like(s)
    inv_d = 1.0 / D

    def rhs(w_, p_, v_, u_):
        den = Km + w_
        return p_, q * w_ / den * inv_d, u_, q * Km / (den * den) * v_ * inv_d

    for _ in range(n_steps):
        k1 = rhs(w, p, v, u)
        k2 = rhs(w + 0.5 * h * k1[0], p + 0.5 * h * k1[1], v + 0.5 * h * k1[2], u + 0.5 * h * k1[3])
        k3 = rhs(w + 0.5 * h * k2[0], p + 0.5 * h * k2[1], v + 0.5 * h * k2[2], u + 0.5 * h * k2[3])
        k4 = rhs(w + h * k3[0], p + h * k3[1], v + h * k3[2], u + h * k3[3])
        w = w + h / 6.0 * (k1[0] + 2 * k2[0] + 2 * k3[0] + k4[0])
        p = p + h / 6.0 * (k1[1] + 2 * k2[1] + 2 * k3[1] + k4[1])
        v = v + h / 6.0 * (k1[2] + 2 * k2[2] + 2 * k3[2] + k4[2])
        u = u + h / 6.0 * (k1[3] + 2 * k2[3] + 2 * k3[3] + k4[3])
    J = D * p
    return {"C0": w, "J": J, "Cb": w + J / P, "dCb_ds": v + D * u / P, "dJ_ds": D * u}


# ------------------------------------------------------------- Hermite helpers
def _hermite_eval(y, y0, dy, F, dF):
    t_full = (y - y0) / dy
    k = np.clip(np.floor(t_full).astype(np.int64), 0, len(F) - 2)
    t = t_full - k
    t2 = t * t
    t3 = t2 * t
    return ((2 * t3 - 3 * t2 + 1) * F[k] + (t3 - 2 * t2 + t) * dy * dF[k]
            + (-2 * t3 + 3 * t2) * F[k + 1] + (t3 - t2) * dy * dF[k + 1])


def _hermite_invert(target, y0, dy, F, dF, increasing):
    if increasing:
        k = np.searchsorted(F, target) - 1
    else:
        k = np.searchsorted(-F, -target) - 1
    k = np.clip(k, 0, len(F) - 2)
    fa, fb = F[k], F[k + 1]
    da, db = dy * dF[k], dy * dF[k + 1]
    t = np.clip((target - fa) / (fb - fa), 0.0, 1.0)
    for _ in range(10):
        t2 = t * t
        t3 = t2 * t
        val = (2 * t3 - 3 * t2 + 1) * fa + (t3 - 2 * t2 + t) * da + (-2 * t3 + 3 * t2) * fb + (t3 - t2) * db
        der = (6 * t2 - 6 * t) * fa + (3 * t2 - 4 * t + 1) * da + (-6 * t2 + 6 * t) * fb + (3 * t2 - 2 * t) * db
        t = np.clip(t - (val - target) / der, 0.0, 1.0)
    return y0 + (k + t) * dy


# ------------------------------------------------------------- module table
class ModuleTable:
    """Continuum response of one perfused module (one channel + one-sided slab).

    Parameters (SI): H depth [m], q maximal volumetric demand [mol m^-3 s^-1], Km [mol m^-3],
    D tissue diffusivity [m^2 s^-1], P effective wall transfer coefficient [m s^-1],
    W wall width [m], L channel length [m], Cin free inlet concentration [mol m^-3].
    """

    def __init__(self, H, q, Km, D, P, W, L, Cin, n_s=2001, n_x=1000, s_lo_rel=1e-14, label=""):
        self.H, self.q, self.Km, self.D, self.P = float(H), float(q), float(Km), float(D), float(P)
        self.W, self.L, self.Cin, self.label = float(W), float(L), float(Cin), label
        self.n_s, self.n_x, self.s_lo_rel = n_s, n_x, s_lo_rel

        def sh(sv):
            return shoot(sv, self.H, self.q, self.Km, self.D, self.P, n_x)

        # ceiling s_in: Cb(s_in) = Cin (bracket on a log grid, then safeguarded Newton)
        trial = np.geomspace(Cin * s_lo_rel, Cin * (1.0 - 1e-13), 241)
        cb_trial = sh(trial)["Cb"]
        i = int(np.searchsorted(cb_trial, Cin))
        lo = trial[max(i - 1, 0)]
        hi = trial[min(i, len(trial) - 1)]
        s = lo
        for _ in range(80):
            r = sh(np.array([s]))
            f = r["Cb"][0] - Cin
            if f > 0:
                hi = min(hi, s)
            else:
                lo = max(lo, s)
            s_new = s - f / r["dCb_ds"][0]
            if not (lo <= s_new <= hi):
                s_new = 0.5 * (lo + hi)
            if abs(s_new - s) <= 1e-15 * s:
                s = s_new
                break
            s = s_new
        self.s_in = s  # infinite-flow (fixed-lumen) worst-region concentration

        self.y0 = np.log(Cin * s_lo_rel)
        self.y = np.linspace(self.y0, np.log(self.s_in), n_s)
        self.dy = self.y[1] - self.y[0]
        sg = np.exp(self.y)
        r = sh(sg)
        self.s = sg
        self.C0 = r["C0"]
        self.J = r["J"]
        self.Cb = r["Cb"]
        dcb_dy = r["dCb_ds"] * sg
        self.g = dcb_dy / self.J                      # -dT/dy  [s m^-1]
        gp = np.gradient(self.g, self.dy, edge_order=2)
        seg = self.dy * (self.g[:-1] + self.g[1:]) / 2.0 + self.dy ** 2 * (gp[:-1] - gp[1:]) / 12.0
        self.T = np.zeros(n_s)
        self.T[:-1] = np.cumsum(seg[::-1])[::-1]       # T(y_top) = 0
        self.lnCb = np.log(self.Cb)
        self.dlnCb_dy = dcb_dy / self.Cb
        self.cb_top_error = abs(self.Cb[-1] - Cin) / Cin

    # --- evaluations on y = ln s
    def T_of_y(self, y):
        y = np.asarray(y, dtype=float)
        out = np.empty_like(y)
        below = y < self.y0
        above = y >= self.y[-1]
        mid = ~(below | above)
        out[mid] = _hermite_eval(y[mid], self.y0, self.dy, self.T, -self.g)
        out[below] = self.T[0] + self.g[0] * (self.y0 - y[below])
        out[above] = 0.0
        return out

    def y_of_T(self, tv):
        tv = np.asarray(tv, dtype=float)
        out = np.empty_like(tv)
        beyond = tv > self.T[0]
        top = tv <= 0.0
        mid = ~(beyond | top)
        out[mid] = _hermite_invert(tv[mid], self.y0, self.dy, self.T, -self.g, increasing=False)
        out[beyond] = self.y0 - (tv[beyond] - self.T[0]) / self.g[0]
        out[top] = self.y[-1]
        return out

    def lncb_of_y(self, y):
        y = np.asarray(y, dtype=float)
        out = np.empty_like(y)
        below = y < self.y0
        above = y >= self.y[-1]
        mid = ~(below | above)
        out[mid] = _hermite_eval(y[mid], self.y0, self.dy, self.lnCb, self.dlnCb_dy)
        out[below] = self.lnCb[0] + (y[below] - self.y0)
        out[above] = self.lnCb[-1]
        return out

    def y_of_lncb(self, v):
        v = np.asarray(v, dtype=float)
        out = np.empty_like(v)
        below = v < self.lnCb[0]
        above = v >= self.lnCb[-1]
        mid = ~(below | above)
        out[mid] = _hermite_invert(v[mid], self.y0, self.dy, self.lnCb, self.dlnCb_dy, increasing=True)
        out[below] = self.y0 + (v[below] - self.lnCb[0])
        out[above] = self.y[-1]
        return out

    # --- channel-level quantities
    def outlet(self, qbeta, cb_in=None):
        """Outlet back-face minimum s_out and outlet bulk Cb_out for capacity-flow Q*beta [m3/s].

        cb_in: inlet bulk concentration (array or None for the fresh inlet Cin).
        """
        qbeta = np.atleast_1d(np.asarray(qbeta, dtype=float))
        t_add = self.W * self.L / qbeta
        if cb_in is None:
            t_start = np.zeros_like(qbeta)
        else:
            cb_in = np.broadcast_to(np.asarray(cb_in, dtype=float), qbeta.shape)
            t_start = self.T_of_y(self.y_of_lncb(np.log(cb_in)))
        y_out = self.y_of_T(t_start + t_add)
        return np.exp(y_out), np.exp(self.lncb_of_y(y_out))

    def qbeta_for_y(self, y):
        """Smallest Q*beta [m3/s] whose fresh-inlet outlet minimum is >= exp(y); inf at/above ceiling."""
        y = np.asarray(y, dtype=float)
        t = self.T_of_y(y)
        out = np.full_like(y, np.inf)
        ok = (y < self.y[-1]) & (t > 0)
        out[ok] = self.W * self.L / t[ok]
        return out

    @property
    def nominal_uptake(self):
        """Zero-order nominal uptake q*W*H*L [mol/s] (an upper bound on actual uptake)."""
        return self.q * self.W * self.H * self.L

    @property
    def fixed_lumen_drop(self):
        return self.Cin - self.s_in


# ------------------------------------------------------------- arrangements
def parallel_fixed(tables, fractions, qbeta_tot):
    """Fresh-inlet parallel modules receiving fixed fractions of Q*beta. Returns minima (n_mod, n)."""
    qbeta_tot = np.atleast_1d(np.asarray(qbeta_tot, dtype=float))
    return np.array([t.outlet(f * qbeta_tot)[0] for t, f in zip(tables, fractions)])


def parallel_maxmin(tables, qbeta_tot, iters=200):
    """Max-min (equalising) split of total Q*beta among fresh-inlet parallel modules.

    Each module's minimum increases monotonically with its own Q*beta, so the optimum
    equalises all minima at tau, where sum_i W L / (beta T_i(tau)) = Q*beta_total.
    Returns tau (n,), allocation Q*beta per module (n_mod, n) normalised to the total.
    """
    qbeta_tot = np.atleast_1d(np.asarray(qbeta_tot, dtype=float))
    y_ceiling = min(np.log(t.s_in) for t in tables)
    lo = np.full_like(qbeta_tot, y_ceiling - 2.0e3)
    hi = np.full_like(qbeta_tot, y_ceiling)
    for _ in range(iters):
        mid = 0.5 * (lo + hi)
        need = sum(t.qbeta_for_y(mid) for t in tables)
        over = need > qbeta_tot
        hi = np.where(over, mid, hi)
        lo = np.where(over, lo, mid)
    alloc = np.array([t.qbeta_for_y(lo) for t in tables])
    alloc *= qbeta_tot / alloc.sum(axis=0)
    return np.exp(lo), alloc


def series_chain(tables_in_order, qbeta_tot):
    """All Q*beta passes the modules in the given order. Returns minima (n_mod, n), final outlet bulk."""
    qbeta_tot = np.atleast_1d(np.asarray(qbeta_tot, dtype=float))
    cb = None
    mins = []
    for t in tables_in_order:
        s_out, cb = t.outlet(qbeta_tot, cb_in=cb)
        mins.append(s_out)
    return np.array(mins), cb


def distinct_orders(keys):
    """Distinct permutations of module indices, treating modules with equal keys as identical."""
    seen, orders = set(), []
    for perm in itertools.permutations(range(len(keys))):
        sig = tuple(keys[i] for i in perm)
        if sig not in seen:
            seen.add(sig)
            orders.append(perm)
    return orders


# ------------------------------------------------------------- closed forms
def linear_module_closed_form(H, k1, D, P, W, L, Cin, qbeta):
    """First-order kinetics (C << Km): exact outlet minimum of one module.

    s_out = Cin exp(-NTU) / [(1 + a/P) cosh(phi)],  NTU = K W L/(Q beta),
    phi = H sqrt(k1/D), a = sqrt(D k1) tanh(phi), K = 1/(1/P + 1/a).
    """
    phi = H * np.sqrt(k1 / D)
    a = np.sqrt(D * k1) * np.tanh(phi)
    K = 1.0 / (1.0 / P + 1.0 / a)
    ntu = K * W * L / np.asarray(qbeta, dtype=float)
    return Cin * np.exp(-ntu) / ((1.0 + a / P) * np.cosh(phi)), ntu, K, a, phi


def lumen_film_conductance(D_fluid, hydraulic_diameter, sherwood):
    """Fully developed laminar lumen-side mass-transfer coefficient k_L = Sh D / d_h [m/s]."""
    return sherwood * D_fluid / hydraulic_diameter


def slit_resistance(mu, L, W, h):
    """Hydraulic resistance of a rectangular slit channel, h < W [Pa s m^-3].

    R = 12 mu L / (W h^3 (1 - 0.630 h/W)) (standard first-order aspect-ratio correction).
    """
    return 12.0 * mu * L / (W * h ** 3 * (1.0 - 0.630 * h / W))


# ------------------------------------------------------------- PF0-discrete mimic
def _thomas(lower, diag, upper, rhs):
    n = diag.shape[1]
    d = diag.copy()
    b = rhs.copy()
    for i in range(1, n):
        f = lower[:, i] / d[:, i - 1]
        d[:, i] -= f * upper[:, i - 1]
        b[:, i] -= f * b[:, i - 1]
    x = np.empty_like(b)
    x[:, -1] = b[:, -1] / d[:, -1]
    for i in range(n - 2, -1, -1):
        x[:, i] = (b[:, i] - upper[:, i] * x[:, i + 1]) / d[:, i]
    return x


def pf0_discrete_slab(cb, H, P, q, Km, D, n=24, tol=1e-13, max_iter=300):
    """Batch Newton solve of PF0's finite-volume slab equations (same discretisation)."""
    cb = np.atleast_1d(np.asarray(cb, dtype=float))
    H = np.broadcast_to(np.asarray(H, dtype=float), cb.shape)
    P = np.broadcast_to(np.asarray(P, dtype=float), cb.shape)
    m = cb.size
    dx = H / n
    g = D / dx
    wall = 1.0 / (1.0 / P + dx / (2.0 * D))
    gl = np.empty((m, n))
    gl[:, 0] = wall
    gl[:, 1:] = g[:, None]
    gr = np.empty((m, n))
    gr[:, :-1] = g[:, None]
    gr[:, -1] = 0.0
    lower = gl.copy()
    lower[:, 0] = 0.0
    active = cb > 0
    c = np.where(active[:, None], np.repeat(cb[:, None], n, axis=1), 0.0)
    scale = np.maximum(q * H, 1e-15)
    norm = np.zeros(m)
    for _ in range(max_iter):
        left = np.empty_like(c)
        left[:, 0] = cb
        left[:, 1:] = c[:, :-1]
        right = np.empty_like(c)
        right[:, :-1] = c[:, 1:]
        right[:, -1] = c[:, -1]
        den = Km + c
        res = gl * (left - c) + gr * (right - c) - dx[:, None] * q * c / den
        norm = np.where(active, np.abs(res).max(axis=1), 0.0)
        if np.all(norm <= tol * scale):
            break
        diag = -gl - gr - dx[:, None] * q * Km / den ** 2
        delta = _thomas(lower, diag, gr, -res)
        trial = c + delta
        trial = np.where(trial < 0.0, 0.1 * c, trial)
        trial = np.minimum(trial, cb[:, None])
        c = np.where(active[:, None], trial, 0.0)
    flux = wall * (cb - c[:, 0])
    uptake = (q * c / (Km + c)).sum(axis=1) * dx
    return c, flux, uptake, norm / scale


def pf0_discrete_channel(H, flow_uL_min, P, beta, q, Km, D, W, L, Cin, nt=24, nz=32,
                         bisect_tol=1e-12, bisect_max=50):
    """Vectorised re-implementation of PF0's simulate(): backward-Euler axial stations with a
    bisection for the station concentration, finite-volume slab at each station."""
    H, flow, P, beta = [np.atleast_1d(np.asarray(a, dtype=float)) for a in (H, flow_uL_min, P, beta)]
    m = H.size
    Q = flow * UL_MIN
    dz = L / nz
    factor = W * dz / (Q * beta)
    ci = np.full(m, Cin)
    minimum = np.full(m, Cin)
    uptake = np.zeros(m)
    worst_res = np.zeros(m)
    for _ in range(nz):
        prev = ci.copy()
        lo = np.zeros(m)
        hi = prev.copy()
        done = np.zeros(m, dtype=bool)
        for _ in range(bisect_max):
            mid = 0.5 * (lo + hi)
            flux = pf0_discrete_slab(mid, H, P, q, Km, D, nt)[1]
            up = (mid + factor * flux - prev) > 0
            hi = np.where(~done & up, mid, hi)
            lo = np.where(~done & ~up, mid, lo)
            done = done | ((hi - lo) < bisect_tol)
            if done.all():
                break
        ci = 0.5 * (lo + hi)
        c, flux, upt, res = pf0_discrete_slab(ci, H, P, q, Km, D, nt)
        minimum = np.minimum(minimum, c.min(axis=1))
        uptake += W * dz * upt
        worst_res = np.maximum(worst_res, res)
    delivered = Q * beta * (Cin - ci)
    return {"minimum": minimum, "outlet": ci, "uptake": uptake, "delivered": delivered,
            "mass_balance": np.abs(delivered - uptake) / np.maximum(np.maximum(np.abs(delivered), np.abs(uptake)), 1e-20),
            "max_station_residual": worst_res}
