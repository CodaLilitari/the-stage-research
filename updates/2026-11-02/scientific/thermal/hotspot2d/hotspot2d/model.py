"""Finite-volume 2-D conduction model of the T0-HYP-1 stacks with a localized
inner silicone/film contact impairment.

Extension label: 2D-PATCH-EXT-1 (labelled amendment to T0-HYP-1: adds in-plane
conduction in one direction and a spatially bounded inner-interface fault;
all other parameters, boundaries and sources follow T0-HYP-1 verbatim).

Coordinates
-----------
z : through-thickness, cell index i = 0 at the outer (ambient) silicone,
    increasing toward the internal node H.
y : in-plane. "planar": a strip patch of half-width w centred at y = L/2
    on a panel of width L = 0.1 m and depth D = 0.1 m (adiabatic edges).
    "axisymmetric": a disc patch of radius w centred at r = 0 on an
    equal-area disc of radius R = sqrt(A/pi) (adiabatic rim).

Unknown ordering: cell (i, j) -> j*n_z + i; the lumped node H is the last
unknown. H is a single isothermal lump (C_H, P_body, rear path) connected to
every inner-silicone bottom cell through that cell's half thickness (ideal
attachment, as in the contract).

Everything here is a mathematical model; it is not evidence about hardware.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

CONTRACT = "T0-HYP-1"
EXTENSION = "2D-PATCH-EXT-1"

STACK_SILICONE_THICKNESS = {"H1": 0.5e-3, "H2": 1.0e-3, "H3": 2.0e-3}
FILM_THICKNESS = 50e-6
PANEL_SIDE = 0.100
PANEL_AREA = PANEL_SIDE * PANEL_SIDE
DISC_RADIUS = math.sqrt(PANEL_AREA / math.pi)


# --------------------------------------------------------------------------
# parameters
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class Params:
    """T0-HYP-1 nominal values. All assumed; none measured."""
    stack: str = "H1"
    k_s: float = 0.27          # W/(m K) silicone
    k_f: float = 0.20          # W/(m K) film
    rho_s: float = 1030.0      # kg/m3 (approx. conversion of specific gravity)
    cp_s: float = 1500.0       # J/(kg K) ASSUMED for the synthetic reference
    rho_f: float = 1420.0
    cp_f: float = 1090.0
    r_c: float = 2.0e-4        # m2 K/W nominal contact, both interfaces
    r_fault: float = 2.0e-2    # m2 K/W faulted inner contact (F2 value)
    h: float = 8.0             # W/(m2 K) assumed, not measured
    T_amb: float = 25.0
    T_res: float = 25.0
    R_rej: float = 2.0         # K/W; math.inf = blocked rear
    C_H: float = 20.0          # J/K assumed lump
    P_body: float = 5.0        # W
    P_sensor: float = 0.10     # W, film midplane, counted once

    @property
    def t_s(self) -> float:
        return STACK_SILICONE_THICKNESS[self.stack]


# --------------------------------------------------------------------------
# through-thickness mesh
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class ZMesh:
    dz: Tuple[float, ...]
    k: Tuple[float, ...]
    rhoc: Tuple[float, ...]
    face_r: Tuple[float, ...]   # nominal contact resistance on face (i,i+1)
    i_mid: int                  # film midplane cell (sensor sheet)
    i_inner_face: int           # face index of the inner silicone/film interface
    n_outer: int
    n_film: int
    n_inner: int

    @property
    def n(self) -> int:
        return len(self.dz)


def build_zmesh(p: Params, n_outer: int = 2, n_film: int = 1, n_inner: int = 2) -> ZMesh:
    """Cells: outer silicone (n_outer), film (odd n_film so the midplane is a
    cell centre), inner silicone (n_inner). Contact resistance only on the two
    real material interfaces, never on refined internal faces."""
    if n_film < 1 or n_film % 2 == 0:
        raise ValueError("n_film must be odd so that the midplane is a cell centre")
    if n_outer < 1 or n_inner < 1:
        raise ValueError("at least one cell per silicone layer")
    t = p.t_s
    dz = [t / n_outer] * n_outer + [FILM_THICKNESS / n_film] * n_film + [t / n_inner] * n_inner
    k = [p.k_s] * n_outer + [p.k_f] * n_film + [p.k_s] * n_inner
    rc_s, rc_f = p.rho_s * p.cp_s, p.rho_f * p.cp_f
    rhoc = [rc_s] * n_outer + [rc_f] * n_film + [rc_s] * n_inner
    face_r = [0.0] * (len(dz) - 1)
    face_r[n_outer - 1] = p.r_c                 # outer silicone | film
    face_r[n_outer + n_film - 1] = p.r_c        # film | inner silicone
    return ZMesh(tuple(dz), tuple(k), tuple(rhoc), tuple(face_r),
                 n_outer + n_film // 2, n_outer + n_film - 1, n_outer, n_film, n_inner)


# --------------------------------------------------------------------------
# in-plane mesh
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class YMesh:
    geometry: str
    faces: Tuple[float, ...]
    centres: Tuple[float, ...]
    widths: Tuple[float, ...]
    areas: Tuple[float, ...]         # z-face (through-thickness) area of each cell
    face_factor: Tuple[float, ...]   # length factor of internal in-plane face j|j+1
    centre_dist: Tuple[float, ...]   # distance between centres j and j+1
    in_patch: Tuple[bool, ...]
    w: float

    @property
    def n(self) -> int:
        return len(self.centres)

    @property
    def total_area(self) -> float:
        return sum(self.areas)

    @property
    def patch_area(self) -> float:
        return sum(a for a, f in zip(self.areas, self.in_patch) if f)

    @property
    def centre_position(self) -> float:
        return PANEL_SIDE / 2 if self.geometry == "planar" else 0.0


def faces_from_segments(breaks: Sequence[float], counts: Sequence[int]) -> List[float]:
    if len(counts) != len(breaks) - 1:
        raise ValueError("need one count per segment")
    faces = [float(breaks[0])]
    for (a, b), n in zip(zip(breaks[:-1], breaks[1:]), counts):
        if n < 1 or b <= a:
            raise ValueError("segments must be positive with >=1 cell")
        for m in range(1, n + 1):
            faces.append(float(b) if m == n else a + (b - a) * m / n)
    return faces


def ymesh_from_faces(geometry: str, faces: Sequence[float], w: float) -> YMesh:
    if geometry not in ("planar", "axisymmetric"):
        raise ValueError("geometry must be 'planar' or 'axisymmetric'")
    f = [float(x) for x in faces]
    if any(b <= a for a, b in zip(f[:-1], f[1:])):
        raise ValueError("faces must be strictly increasing")
    centres = [0.5 * (a + b) for a, b in zip(f[:-1], f[1:])]
    widths = [b - a for a, b in zip(f[:-1], f[1:])]
    if geometry == "planar":
        if abs(f[0]) > 1e-12 or abs(f[-1] - PANEL_SIDE) > 1e-12:
            raise ValueError("planar faces must span [0, L]")
        areas = [PANEL_SIDE * wd for wd in widths]           # depth D = 0.1 m
        face_factor = [PANEL_SIDE] * (len(centres) - 1)
        c = PANEL_SIDE / 2
        in_patch = [abs(yc - c) < w for yc in centres]
    else:
        if abs(f[0]) > 1e-12 or abs(f[-1] - DISC_RADIUS) > 1e-12:
            raise ValueError("axisymmetric faces must span [0, R]")
        areas = [math.pi * (b * b - a * a) for a, b in zip(f[:-1], f[1:])]
        face_factor = [2.0 * math.pi * f[j] for j in range(1, len(f) - 1)]
        in_patch = [yc < w for yc in centres]
    centre_dist = [centres[j + 1] - centres[j] for j in range(len(centres) - 1)]
    return YMesh(geometry, tuple(f), tuple(centres), tuple(widths), tuple(areas),
                 tuple(face_factor), tuple(centre_dist), tuple(in_patch), float(w))


def default_ymesh(geometry: str, w: float, dy_fine: float = 0.5e-3, dy_coarse: float = 5e-3,
                  margin: float = 6e-3, refine: int = 1) -> YMesh:
    """Patch boundaries are always mesh faces. Cells within `margin` of the
    patch (and inside it) use dy_fine; the rest use dy_coarse."""
    if w < 0:
        raise ValueError("w must be >= 0")
    if geometry == "planar":
        c, Lmax = PANEL_SIDE / 2, PANEL_SIDE
        pts = [0.0, c - w - margin, c - w, c + w, c + w + margin, Lmax]
        fine_lo, fine_hi = c - w - margin, c + w + margin
    else:
        Lmax = DISC_RADIUS
        pts = [0.0, w, w + margin, Lmax]
        fine_lo, fine_hi = 0.0, w + margin
    pts = sorted(min(max(x, 0.0), Lmax) for x in pts)
    breaks: List[float] = []
    for x in pts:
        if not breaks or x - breaks[-1] > 1e-12:
            breaks.append(x)
    counts = []
    for a, b in zip(breaks[:-1], breaks[1:]):
        mid = 0.5 * (a + b)
        target = dy_fine if (fine_lo - 1e-12 <= mid <= fine_hi + 1e-12) else dy_coarse
        counts.append(max(1, math.ceil((b - a) / target - 1e-9)) * refine)
    return ymesh_from_faces(geometry, faces_from_segments(breaks, counts), w)


def full_patch_width(geometry: str) -> float:
    return PANEL_SIDE / 2 if geometry == "planar" else DISC_RADIUS


# --------------------------------------------------------------------------
# network assembly
# --------------------------------------------------------------------------
def _dot(a: Sequence[float], b: Sequence[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


class Network:
    """Conductance network K (W/K), capacities C (J/K), sources q (W) and
    boundary couplings g_bnd/T_bnd for one fault state and one body power.

    K = sum_edges G (e_p - e_q)(e_p - e_q)^T + sum_boundary g_b e_p e_p^T.
    """

    def __init__(self, p: Params, zm: ZMesh, ym: YMesh, faulted: bool,
                 rear_open: bool, body_power: float):
        self.p, self.zm, self.ym = p, zm, ym
        self.faulted, self.rear_open, self.body_power = faulted, rear_open, body_power
        n_z, n_y = zm.n, ym.n
        self.n_z, self.n_y = n_z, n_y
        n = n_z * n_y + 1
        self.n, self.iH = n, n - 1
        diag = [0.0] * n
        rows: List[List[Tuple[int, float]]] = [[] for _ in range(n)]

        def add_edge(a: int, b: int, G: float) -> None:
            diag[a] += G
            diag[b] += G
            rows[a].append((b, -G))
            rows[b].append((a, -G))

        self.faulted_cells: List[int] = []
        for j in range(n_y):
            A = ym.areas[j]
            for i in range(n_z - 1):
                r = zm.face_r[i]
                if faulted and ym.in_patch[j] and i == zm.i_inner_face:
                    r = p.r_fault
                    self.faulted_cells.append(j)
                R = zm.dz[i] / (2 * zm.k[i]) + zm.dz[i + 1] / (2 * zm.k[i + 1]) + r
                add_edge(self.idx(i, j), self.idx(i + 1, j), A / R)
            add_edge(self.idx(n_z - 1, j), self.iH, A / (zm.dz[-1] / (2 * zm.k[-1])))
        for j in range(n_y - 1):
            for i in range(n_z):
                G = zm.k[i] * zm.dz[i] * ym.face_factor[j] / ym.centre_dist[j]
                add_edge(self.idx(i, j), self.idx(i, j + 1), G)

        g_bnd = [0.0] * n
        T_bnd = [0.0] * n
        self.top_cells = []
        for j in range(n_y):
            a = self.idx(0, j)
            g_bnd[a] = ym.areas[j] / (zm.dz[0] / (2 * zm.k[0]) + 1.0 / p.h)
            T_bnd[a] = p.T_amb
            self.top_cells.append(a)
        g_rear = 1.0 / p.R_rej if (rear_open and math.isfinite(p.R_rej) and p.R_rej > 0) else 0.0
        g_bnd[self.iH] = g_rear
        T_bnd[self.iH] = p.T_res
        for a in range(n):
            diag[a] += g_bnd[a]

        C = [0.0] * n
        q = [0.0] * n
        A_tot = ym.total_area
        for j in range(n_y):
            for i in range(n_z):
                C[self.idx(i, j)] = zm.rhoc[i] * zm.dz[i] * ym.areas[j]
            q[self.idx(zm.i_mid, j)] = p.P_sensor * ym.areas[j] / A_tot
        C[self.iH] = p.C_H
        q[self.iH] = body_power

        self.rows, self.diag = rows, diag
        self.g_bnd, self.T_bnd, self.C, self.q = g_bnd, T_bnd, C, q
        self.g_rear = g_rear

    # ---- indexing / post-processing -------------------------------------
    def idx(self, i: int, j: int) -> int:
        return j * self.n_z + i

    def rhs_steady(self) -> List[float]:
        return [qi + g * Tb for qi, g, Tb in zip(self.q, self.g_bnd, self.T_bnd)]

    def film_midplane(self, T: Sequence[float]) -> List[float]:
        return [T[self.idx(self.zm.i_mid, j)] for j in range(self.n_y)]

    def surface(self, T: Sequence[float]) -> List[float]:
        """Outer face temperature from the boundary flux (not the first cell)."""
        p, zm = self.p, self.zm
        rconv = 1.0 / p.h
        rhalf = zm.dz[0] / (2 * zm.k[0])
        return [p.T_amb + (T[a] - p.T_amb) * rconv / (rhalf + rconv) for a in self.top_cells]

    def front_power(self, T: Sequence[float]) -> float:
        return sum(self.g_bnd[a] * (T[a] - self.T_bnd[a]) for a in self.top_cells)

    def rear_power(self, T: Sequence[float]) -> float:
        return self.g_rear * (T[self.iH] - self.T_bnd[self.iH])

    def energy(self, T: Sequence[float]) -> float:
        return _dot(self.C, T)

    def total_source(self) -> float:
        return sum(self.q)

    def residual_norm(self, T: Sequence[float], diag_shift: Optional[Sequence[float]] = None,
                      b: Optional[Sequence[float]] = None) -> float:
        if b is None:
            b = self.rhs_steady()
        d = self.diag if diag_shift is None else [x + y for x, y in zip(self.diag, diag_shift)]
        r = [bi - v for bi, v in zip(b, matvec(self.rows, d, T))]
        return math.sqrt(_dot(r, r))

    def quadratic_form(self, x: Sequence[float]) -> float:
        return _dot(x, matvec(self.rows, self.diag, x))

    def is_symmetric(self, tol: float = 1e-12) -> bool:
        entries: Dict[Tuple[int, int], float] = {}
        for a, row in enumerate(self.rows):
            for c, v in row:
                entries[(a, c)] = entries.get((a, c), 0.0) + v
        return all(abs(v - entries.get((c, a), 0.0)) <= tol * (1 + abs(v)) for (a, c), v in entries.items())


def matvec(rows: Sequence[Sequence[Tuple[int, float]]], diag: Sequence[float],
           x: Sequence[float]) -> List[float]:
    return [d * xi + sum(v * x[c] for c, v in row) for d, xi, row in zip(diag, x, rows)]


# --------------------------------------------------------------------------
# solvers
# --------------------------------------------------------------------------
def pcg(rows, diag, b, x0=None, tol: float = 1e-13, maxiter: int = 200000):
    """Jacobi-preconditioned conjugate gradient for an SPD matrix given as
    (off-diagonal rows, diagonal). Stops when ||r|| <= tol*||b||.

    Convergence (standard result, see NOTES.md section 3): for M SPD and
    P = diag(M) SPD, PCG is CG on P^-1/2 M P^-1/2, which is SPD; the M-norm
    error after k steps is bounded by 2((sqrt(kappa)-1)/(sqrt(kappa)+1))^k
    times the initial error, and the exact-arithmetic iteration terminates
    in at most n steps. M here is SPD by the quadratic-form argument in
    NOTES.md, so convergence is guaranteed (up to roundoff).
    """
    n = len(b)
    x = list(x0) if x0 is not None else [0.0] * n
    if len(x) != n:
        raise ValueError("x0 length mismatch")
    if any(d <= 0 for d in diag):
        raise ValueError("Jacobi preconditioner needs positive diagonal")
    bnorm = math.sqrt(_dot(b, b)) or 1.0
    r = [bi - v for bi, v in zip(b, matvec(rows, diag, x))]
    z = [ri / di for ri, di in zip(r, diag)]
    pvec = z[:]
    rz = _dot(r, z)
    for it in range(maxiter + 1):
        rnorm = math.sqrt(_dot(r, r))
        if rnorm <= tol * bnorm:
            return x, it, True
        if it == maxiter:
            break
        Ap = matvec(rows, diag, pvec)
        pAp = _dot(pvec, Ap)
        if pAp <= 0:
            raise ArithmeticError("matrix not positive definite in PCG")
        alpha = rz / pAp
        x = [xi + alpha * pi for xi, pi in zip(x, pvec)]
        r = [ri - alpha * api for ri, api in zip(r, Ap)]
        z = [ri / di for ri, di in zip(r, diag)]
        rz_new = _dot(r, z)
        beta = rz_new / rz if rz != 0 else 0.0
        pvec = [zi + beta * pi for zi, pi in zip(z, pvec)]
        rz = rz_new
    return x, maxiter, False


def banded_cholesky(band: List[List[float]], bw: int) -> List[List[float]]:
    """Cholesky factor of a banded SPD matrix stored as band[i][k] = A[i, i-k]."""
    n = len(band)
    L = [row[:] for row in band]
    for i in range(n):
        Li = L[i]
        kmax = min(i, bw)
        for k in range(kmax, 0, -1):
            j = i - k
            Lj = L[j]
            s = Li[k]
            mmax = min(bw - k, j)
            for m in range(1, mmax + 1):
                s -= Li[k + m] * Lj[m]
            Li[k] = s / Lj[0]
        s = Li[0]
        for m in range(1, kmax + 1):
            s -= Li[m] * Li[m]
        if s <= 0.0:
            raise ArithmeticError("banded matrix is not positive definite")
        Li[0] = math.sqrt(s)
    return L


def banded_solve(L: List[List[float]], bw: int, b: Sequence[float]) -> List[float]:
    n = len(L)
    y = [0.0] * n
    for i in range(n):
        Li = L[i]
        s = b[i]
        for m in range(1, min(i, bw) + 1):
            s -= Li[m] * y[i - m]
        y[i] = s / Li[0]
    x = [0.0] * n
    for i in range(n - 1, -1, -1):
        s = y[i]
        for m in range(1, min(bw, n - 1 - i) + 1):
            s -= L[i + m][m] * x[i + m]
        x[i] = s / L[i][0]
    return x


class BorderedBandedSolver:
    """Direct solver for [[B, c],[c^T, d]] with B banded SPD (the cells) and
    one bordering unknown (H). Solves via Cholesky of B and a 1x1 Schur
    complement d - c^T B^-1 c, which is > 0 because the full matrix is SPD."""

    def __init__(self, rows, diag, iH: int, bw: int):
        self.iH, self.bw = iH, bw
        band = [[0.0] * (bw + 1) for _ in range(iH)]
        c = [0.0] * iH
        for i in range(iH):
            band[i][0] = diag[i]
            for col, v in rows[i]:
                if col == iH:
                    c[i] += v
                elif col < i:
                    k = i - col
                    if k > bw:
                        raise ValueError("entry outside the declared band")
                    band[i][k] += v
        self.L = banded_cholesky(band, bw)
        self.c = c
        self.v = banded_solve(self.L, bw, c)
        self.schur = diag[iH] - _dot(c, self.v)
        if self.schur <= 0:
            raise ArithmeticError("Schur complement not positive")

    def solve(self, b: Sequence[float]) -> List[float]:
        u = banded_solve(self.L, self.bw, b[:self.iH])
        xH = (b[self.iH] - _dot(self.c, u)) / self.schur
        x = [ui - xH * vi for ui, vi in zip(u, self.v)]
        x.append(xH)
        return x


def solve_steady(net: Network, method: str = "direct", tol: float = 1e-13,
                 x0: Optional[Sequence[float]] = None) -> Tuple[List[float], Dict[str, object]]:
    b = net.rhs_steady()
    if method == "pcg":
        x, it, ok = pcg(net.rows, net.diag, b, x0=x0, tol=tol)
        info = {"method": "pcg", "iterations": it, "converged": ok}
    elif method == "direct":
        x = BorderedBandedSolver(net.rows, net.diag, net.iH, net.n_z).solve(b)
        info = {"method": "direct", "iterations": 0, "converged": True}
    else:
        raise ValueError("method must be 'pcg' or 'direct'")
    info["residual_norm"] = net.residual_norm(x)
    return x, info


# --------------------------------------------------------------------------
# steady summary
# --------------------------------------------------------------------------
def centre_value(ym: YMesh, profile: Sequence[float]) -> float:
    """Value at the patch centre: y = L/2 (planar; exact cell centre, or mean
    of the two cells sharing the centre face, else linear interpolation) or
    the axis cell (axisymmetric)."""
    if ym.geometry == "axisymmetric":
        return profile[0]
    c = PANEL_SIDE / 2
    for j in range(ym.n):
        if abs(ym.centres[j] - c) < 1e-12:
            return profile[j]
    for j in range(1, ym.n):
        if abs(ym.faces[j] - c) < 1e-12:
            return 0.5 * (profile[j - 1] + profile[j])
    for j in range(ym.n - 1):
        if ym.centres[j] <= c <= ym.centres[j + 1]:
            f = (c - ym.centres[j]) / (ym.centres[j + 1] - ym.centres[j])
            return (1 - f) * profile[j] + f * profile[j + 1]
    return profile[-1]


def edge_value(ym: YMesh, profile: Sequence[float]) -> float:
    return profile[0] if ym.geometry == "planar" else profile[-1]


def steady_summary(net: Network, T: Sequence[float]) -> Dict[str, object]:
    mid = net.film_midplane(T)
    surf = net.surface(T)
    ym = net.ym
    jmin = min(range(ym.n), key=lambda j: mid[j])
    jmax = max(range(ym.n), key=lambda j: mid[j])
    front, rear = net.front_power(T), net.rear_power(T)
    return {
        "T_H": T[net.iH],
        "T_mid_centre": centre_value(ym, mid),
        "T_mid_edge": edge_value(ym, mid),
        "T_mid_min": mid[jmin], "y_mid_min": ym.centres[jmin],
        "T_mid_max": mid[jmax], "y_mid_max": ym.centres[jmax],
        "T_surf_centre": centre_value(ym, surf),
        "T_surf_min": min(surf), "T_surf_max": max(surf),
        "front_W": front, "rear_W": rear,
        "source_W": net.total_source(),
        "balance_W": net.total_source() - front - rear,
        "patch_area_m2": ym.patch_area, "total_area_m2": ym.total_area,
        "faulted_cells": len(net.faulted_cells),
    }


# --------------------------------------------------------------------------
# 1-D reference (transcribed from Coda's thermal_reference.py, sha256
# 7032a2cd...; heat-flow elimination, here in floats)
# --------------------------------------------------------------------------
def reference_two_node(a, b, r, P, J, ambient, reservoir, c) -> Dict[str, object]:
    """Coda's steady() in float arithmetic. a: H->sensor resistance (inner
    silicone + half film + inner contact); b: sensor->ambient (half film +
    outer contact + outer silicone + convection c); r: rear resistance."""
    front_open = math.isfinite(b)
    rear_open = math.isfinite(r)
    if not front_open and not rear_open:
        return {"status": "no_finite_steady_state" if P + J > 0 else "nonunique"}
    if not rear_open:
        front = P + J
        rear = 0.0
        S = ambient + b * front
        H = S + a * P
    elif not front_open:
        front = 0.0
        rear = P + J
        H = reservoir + r * rear
        S = H + a * J
    else:
        front = ((reservoir - ambient) + r * (P + J) + a * J) / (a + b + r)
        rear = P + J - front
        S = ambient + b * front
        H = S + a * (front - J)
    surface = ambient + c * front if front_open else None
    return {"status": "unique", "H": H, "S": S, "surface": surface,
            "front": front, "rear": rear, "balance": P + J - front - rear}


def reference_1d_steady(p: Params, r_inner: Optional[float] = None,
                        r_outer: Optional[float] = None, rear_open: bool = True,
                        body_power: Optional[float] = None) -> Dict[str, object]:
    A = PANEL_AREA
    t = p.t_s
    r_inner = p.r_c if r_inner is None else r_inner
    r_outer = p.r_c if r_outer is None else r_outer
    P = p.P_body if body_power is None else body_power
    a = t / (p.k_s * A) + FILM_THICKNESS / (2 * p.k_f * A) + r_inner / A
    a_out = t / (p.k_s * A) + FILM_THICKNESS / (2 * p.k_f * A) + r_outer / A
    c = 1.0 / (p.h * A)
    r = p.R_rej if (rear_open and math.isfinite(p.R_rej)) else math.inf
    out = reference_two_node(a, a_out + c, r, P, p.P_sensor, p.T_amb, p.T_res, c)
    out.update({"a": a, "b": a_out + c, "r": r})
    return out


# --------------------------------------------------------------------------
# transient: backward Euler with exact event restarts
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class Segment:
    t0: float
    t1: float
    body_power: float
    faulted: bool
    rear_open: bool


def event_schedule(fault_time: Optional[float] = 600.0, body_off_time: float = 900.0,
                   horizon: float = 3600.0, rear_block_time: Optional[float] = None,
                   body_power: float = 5.0) -> List[Segment]:
    """Piecewise-constant schedule with restarts at every event time."""
    times = {0.0, horizon, body_off_time}
    if fault_time is not None:
        times.add(fault_time)
    if rear_block_time is not None:
        times.add(rear_block_time)
    ts = sorted(t for t in times if 0.0 <= t <= horizon)
    segs = []
    for t0, t1 in zip(ts[:-1], ts[1:]):
        segs.append(Segment(t0, t1,
                            body_power if t0 < body_off_time else 0.0,
                            fault_time is not None and t0 >= fault_time,
                            not (rear_block_time is not None and t0 >= rear_block_time)))
    return segs


class TransientResult:
    def __init__(self):
        self.t: List[float] = []
        self.T_H: List[float] = []
        self.T_mid_centre: List[float] = []
        self.T_mid_edge: List[float] = []
        self.T_mid_min: List[float] = []
        self.T_mid_max: List[float] = []
        self.T_surf_min: List[float] = []
        self.T_surf_max: List[float] = []
        self.E: List[float] = []
        self.injected: List[float] = []
        self.exported: List[float] = []
        self.segment_boundaries: List[Dict[str, object]] = []
        self.final_state: List[float] = []
        self.audit: Dict[str, float] = {}

    def record(self, net: Network, t: float, T: Sequence[float], injected: float, exported: float):
        mid = net.film_midplane(T)
        surf = net.surface(T)
        self.t.append(t)
        self.T_H.append(T[net.iH])
        self.T_mid_centre.append(centre_value(net.ym, mid))
        self.T_mid_edge.append(edge_value(net.ym, mid))
        self.T_mid_min.append(min(mid))
        self.T_mid_max.append(max(mid))
        self.T_surf_min.append(min(surf))
        self.T_surf_max.append(max(surf))
        self.E.append(net.energy(T))
        self.injected.append(injected)
        self.exported.append(exported)

    def value_at(self, field: str, time: float) -> float:
        vals = getattr(self, field)
        j = min(range(len(self.t)), key=lambda k: abs(self.t[k] - time))
        return vals[j]


def simulate(p: Params, zm: ZMesh, ym: YMesh, segments: Sequence[Segment], dt: float,
             T_initial: Optional[Sequence[float]] = None, method: str = "direct",
             record_every: int = 1, pcg_tol: float = 1e-12) -> TransientResult:
    """Backward Euler: (C/h + K) T^{n+1} = (C/h) T^n + q + g_b T_b.
    Energy identity per step (exact for BE, internal transfers cancel pairwise):
    sum_p C_p (T_p^{n+1}-T_p^n) = h [sum q - sum_b g_b (T_p^{n+1} - T_b)]."""
    if dt <= 0:
        raise ValueError("dt must be positive")
    res = TransientResult()
    net0 = Network(p, zm, ym, segments[0].faulted, segments[0].rear_open, segments[0].body_power)
    T = list(T_initial) if T_initial is not None else [p.T_amb] * net0.n
    if len(T) != net0.n:
        raise ValueError("initial state length mismatch")
    injected = 0.0
    exported = 0.0
    E0 = net0.energy(T)
    res.record(net0, segments[0].t0, T, injected, exported)
    t = segments[0].t0
    for seg in segments:
        if abs(seg.t0 - t) > 1e-9:
            raise ValueError("segments must be contiguous")
        net = Network(p, zm, ym, seg.faulted, seg.rear_open, seg.body_power)
        res.segment_boundaries.append({"t": seg.t0, "T_H": T[net.iH],
                                       "T_mid_centre": centre_value(ym, net.film_midplane(T)),
                                       "faulted": seg.faulted, "rear_open": seg.rear_open,
                                       "body_power": seg.body_power})
        n_steps = max(1, int(round((seg.t1 - seg.t0) / dt)))
        hstep = (seg.t1 - seg.t0) / n_steps
        shift = [c / hstep for c in net.C]
        diag = [d + s for d, s in zip(net.diag, shift)]
        const = net.rhs_steady()
        solver = BorderedBandedSolver(net.rows, diag, net.iH, net.n_z) if method == "direct" else None
        q_tot = net.total_source()
        for s in range(n_steps):
            b = [sh * Ti + ci for sh, Ti, ci in zip(shift, T, const)]
            if solver is not None:
                T_new = solver.solve(b)
            else:
                T_new, _, ok = pcg(net.rows, diag, b, x0=T, tol=pcg_tol)
                if not ok:
                    raise ArithmeticError("PCG did not converge in transient step")
            t = seg.t1 if s == n_steps - 1 else seg.t0 + hstep * (s + 1)
            injected += hstep * q_tot
            exported += hstep * (net.front_power(T_new) + net.rear_power(T_new))
            T = T_new
            if (s + 1) % record_every == 0 or s == n_steps - 1:
                res.record(net, t, T, injected, exported)
    net_last = Network(p, zm, ym, segments[-1].faulted, segments[-1].rear_open, segments[-1].body_power)
    res.final_state = T
    res.audit = {"E0_J": E0, "E_end_J": net_last.energy(T), "injected_J": injected,
                 "exported_J": exported,
                 "residual_J": (net_last.energy(T) - E0) - injected + exported}
    return res


# --------------------------------------------------------------------------
# lateral spreading length (c)
# --------------------------------------------------------------------------
def fin_spreading_length(p: Params, r_inner: float) -> float:
    """Crude fin estimate: film + outer silicone as one laterally conducting
    layer (kappa = k_f t_f + k_s t_o, W/K per unit width) leaking to H through
    r_leak = r_inner + t_i/k_s and to ambient through 1/h (+half outer layer).
    ell^2 = kappa / (1/r_leak + 1/r_front)."""
    kappa = p.k_f * FILM_THICKNESS + p.k_s * p.t_s
    r_leak = r_inner + p.t_s / p.k_s
    r_front = 1.0 / p.h + p.t_s / (2 * p.k_s)
    return math.sqrt(kappa / (1.0 / r_leak + 1.0 / r_front))


def modal_spreading_length(p: Params, r_inner: float, include_convection: bool = True) -> float:
    """Slowest lateral decay length of a perturbation theta ~ exp(-y/ell) phi(z)
    in the two silicone layers (equal thickness t) with the film plus both
    contacts lumped into an areal resistance R_f = t_f/k_f + r_c + r_inner,
    H isothermal (phi=0) at the bottom and a convective (Robin) top.
    With x = t/ell, psi = -atan(h t/(k_s x)):  cos(2x+psi) = (R_f k_s x/t) cos x sin(x+psi).
    Limits: R_f -> 0 and h -> 0 give x = pi/4 (ell = 4t/pi); R_f large gives
    ell ~ sqrt(R_f k_s t) (fin regime). Film lateral conduction is neglected.
    Derivation in NOTES.md section 5."""
    t = p.t_s
    Rf = FILM_THICKNESS / p.k_f + p.r_c + r_inner

    def psi(x: float) -> float:
        return -math.atan(p.h * t / (p.k_s * x)) if include_convection else 0.0

    def F(x: float) -> float:
        ps = psi(x)
        return math.cos(2 * x + ps) - (Rf * p.k_s * x / t) * math.cos(x) * math.sin(x + ps)

    # admissible interval: x + psi(x) > 0 (positive outer-layer mode), x < pi/2
    lo = 1e-9
    if include_convection:
        a, b = 1e-9, math.pi / 2
        for _ in range(200):
            m = 0.5 * (a + b)
            if m + psi(m) > 0:
                b = m
            else:
                a = m
        lo = b + 1e-9
    hi = math.pi / 2 - 1e-12
    xs = [lo + (hi - lo) * k / 4000 for k in range(4001)]
    root = None
    for xa, xb in zip(xs[:-1], xs[1:]):
        fa, fb = F(xa), F(xb)
        if fa == 0.0:
            root = xa
            break
        if fa * fb < 0:
            a, b = xa, xb
            for _ in range(200):
                m = 0.5 * (a + b)
                if F(a) * F(m) <= 0:
                    b = m
                else:
                    a = m
            root = 0.5 * (a + b)
            break
    if root is None:
        raise ArithmeticError("no modal root found")
    return t / root


def fit_decay_length(ym: YMesh, profile: Sequence[float], ell_guess: float,
                     d1_factor: float = 2.0, d2_factor: float = 4.0) -> Optional[Dict[str, float]]:
    """Exponential fit of the perturbation theta_j = T_j - T_far outside the
    patch between distances ~d1_factor*ell and ~d2_factor*ell from the patch
    edge (where the slowest mode should dominate). Returns None if ill-posed."""
    edge = ym.centre_position + ym.w
    far = profile[-1]
    pairs = [(ym.centres[j] - edge, profile[j] - far) for j in range(ym.n) if ym.centres[j] > edge]
    if len(pairs) < 3:
        return None
    (d1, th1) = min(pairs, key=lambda pr: abs(pr[0] - d1_factor * ell_guess))
    (d2, th2) = min(pairs, key=lambda pr: abs(pr[0] - d2_factor * ell_guess))
    if d2 <= d1 or th1 * th2 <= 0 or abs(th2) < 1e-12:
        return None
    return {"ell_fit_m": (d2 - d1) / math.log(abs(th1) / abs(th2)),
            "d1_m": d1, "d2_m": d2, "theta1_K": th1, "theta2_K": th2}


def observed_order(q1: float, q2: float, q3: float, ratio: float = 2.0,
                   floor: float = 1e-11) -> Optional[float]:
    """Richardson-type observed order from three successive refinements."""
    e1, e2 = abs(q1 - q2), abs(q2 - q3)
    if e2 < floor or e1 < floor:
        return None
    return math.log(e1 / e2) / math.log(ratio)
