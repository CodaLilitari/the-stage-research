# Deliverable: `thermal-hotspot-2d-001` — 2-D localized inner-interface impairment model

Contributor note: this packet was written by Claude (via Red) as a bounded extension of the T0-HYP-1 contract prepared by Coda (Codex Lily). The 1-D two-node steady reference transcribed below is Coda's (`validation/thermal/thermal_reference.py`, sha256 `7032a2cd…`); the fixture numbers in the tests are copied from Coda's executed `reference_results.json` (sha256 `e97cf35c…`). Earlier Claude Fable 5.1 contributions are not reproduced here. **Nothing below has been executed by me.** All numerical statements in the notes are static expectations and are labelled as such; Red's sandbox run is the only source of actual numbers.

## 0. What is delivered and what is not

Delivered (complete, runnable, stdlib only):

- `hotspot2d/model.py` — parameters, z-mesh (through-thickness), in-plane mesh (planar strip or axisymmetric disc), finite-volume network assembly with the raised contact resistance applied **only** on inner-interface faces of patch cells, Jacobi-preconditioned conjugate gradient (PCG), bordered banded Cholesky (direct cross-check, used for speed in the transient), backward-Euler integrator with exact event restarts, surface reconstruction, energy audit, transcription of Coda's two-node 1-D steady reference, fin-type and two-layer modal spreading-length analysis, numerical decay-length fit.
- `hotspot2d/study.py` — the predeclared study (d); writes one JSON file to a caller-supplied `--out` path.
- `tests/test_hotspot2d.py` — unittests for (b) and (c).
- `hotspot2d/NOTES.md` — derivation, node/face map, SPD/PCG convergence proof, predeclared hypotheses and criteria, limits.

Not implemented (explicit): F3/F4 controller cases, F5 double-block, property sweeps (cp, C_H, k), outer-interface patches, a patch at the panel edge, radiation, human contact, strain dependence, any real-geometry data. Mesh-refinement for the *transient* in space is not run in the study (only steady spatial refinement and transient time refinement).

Static reasoning that Red should check against the executed output (not claims): because the dominant source is at H and the front path is convection-dominated (1/h = 0.125 m²K/W ≫ r_fault = 0.02), a localized inner-interface impairment is expected to produce a **cool** spot in the film/surface over the patch (≈ 10–15 % of T_H−T_amb) and a small **uniform** rise of T_H, not a film hot spot; the lateral spreading length is expected to be sub-mm to a few mm (so patches with w ≥ 5 mm approach the uniform-F2 local values at their centre). These are expectations about the model, to be confirmed or refuted by the run.

---

FILE: hotspot2d/__init__.py
```python
"""2-D (through-thickness x in-plane) localized-impairment extension of the
T0-HYP-1 synthetic thermal reference. Standard library only. Model only."""
```

FILE: hotspot2d/model.py
```python
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
```

FILE: hotspot2d/study.py
```python
"""Predeclared study for thermal-hotspot-2d-001 (section (d) of the task).

Everything is a model result at the modeled scale. The 0.1 K / 0.5 K
detection comparators and the 40/60 C contract comparators are arbitrary
study comparators (study_comparator_only), not instrument specifications or
safety limits. Writes one JSON file to --out; no other file writes.

Expected runtime is not measured by the author; CPython estimate: minutes.
Use --quick for a reduced grid.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from typing import Dict, List

from hotspot2d import model as M

PREDECLARED = {
    "extension": M.EXTENSION,
    "contract": M.CONTRACT,
    "patch_half_widths_m": [1e-3, 2e-3, 5e-3, 10e-3, 20e-3],
    "stacks": ["H1", "H2", "H3"],
    "rear_states": ["open_R2", "blocked"],
    "geometries": {"planar": "all stacks", "axisymmetric": "H2 open rear only"},
    "body_power_W": 5.0, "sensor_power_W": 0.1,
    "detection_thresholds_K": [0.1, 0.5],
    "steady_mesh": {"n_outer": 3, "n_film": 1, "n_inner": 3, "dy_fine_m": 0.5e-3,
                    "dy_coarse_m": 5e-3, "margin_m": 8e-3},
    "transient_mesh": {"n_outer": 2, "n_film": 1, "n_inner": 2, "dy_fine_m": 0.5e-3,
                       "dy_coarse_m": 5e-3, "margin_m": 6e-3},
    "transient_dt_s": 2.0, "transient_refinement_dt_s": 1.0,
    "transient_cases": "F0 (no fault) and patch fault at 600 s for w in {2 mm, 20 mm}, "
                       "planar, open rear, body 5 W on [0,900) s, sensor 0.1 W throughout, "
                       "horizon 3600 s; plus 1-D uniform F2 (n_y=1) for comparison",
    "criteria": {
        "time_refinement_max_dT_K": 0.05,
        "mesh_refinement_max_dT_K": 0.10,
        "energy_residual_J_tolerance": 1e-6,
        "spreading_length_modal_rel_tol": 0.25,
        "spreading_length_fin_vs_modal_factor": 2.0,
    },
    "hypotheses": {
        "HYP1": "T_H(ref) <= T_H(w) <= T_H(uniform F2), non-decreasing in w (same rear state).",
        "HYP2": "Film midplane over the patch centre is <= unfaulted value (a cool spot, not a hot spot) "
                "and >= T_mid(uniform F2) - [T_H(uniform F2) - T_H(w)].",
        "HYP3": "Open rear: |T_mid_edge(w) - T_mid_edge(ref)| < 0.1 K for all w <= 20 mm.",
        "HYP4": "Open rear: |T_mid_centre(w) - T_mid_centre(ref)| >= 0.5 K for w >= 5 mm and < 0.5 K for w = 1 mm.",
        "HYP5": "Fitted lateral decay length within 25 % of the two-layer modal value; fin estimate within factor 2.",
        "HYP6": "Blocked rear: max film and max surface temperature with a patch do not exceed the uniform-F2 "
                "blocked values by more than 0.5 K (convection-dominated front path).",
    },
}


def _summ(p, zm, ym, faulted, rear_open):
    net = M.Network(p, zm, ym, faulted, rear_open, p.P_body)
    T, info = M.solve_steady(net, "direct")
    s = M.steady_summary(net, T)
    s["solver"] = info
    return net, T, s


def steady_study(quick: bool) -> Dict[str, object]:
    pm = PREDECLARED["steady_mesh"]
    ws = PREDECLARED["patch_half_widths_m"] if not quick else [2e-3, 20e-3]
    rows = []
    hyp = {k: [] for k in ("HYP1", "HYP2", "HYP3", "HYP4", "HYP6")}
    for stack in PREDECLARED["stacks"]:
        p = M.Params(stack=stack)
        zm = M.build_zmesh(p, pm["n_outer"], pm["n_film"], pm["n_inner"])
        geoms = ["planar", "axisymmetric"] if stack == "H2" else ["planar"]
        for geom in geoms:
            for rear in PREDECLARED["rear_states"]:
                if geom == "axisymmetric" and rear != "open_R2":
                    continue
                rear_open = rear == "open_R2"
                ref = M.reference_1d_steady(p, rear_open=rear_open)
                f2 = M.reference_1d_steady(p, r_inner=p.r_fault, rear_open=rear_open)
                prev_TH = ref["H"]
                for w in ws:
                    ym = M.default_ymesh(geom, w, pm["dy_fine_m"], pm["dy_coarse_m"], pm["margin_m"])
                    net, T, s = _summ(p, zm, ym, True, rear_open)
                    dTc = s["T_mid_centre"] - ref["S"]
                    dTe = s["T_mid_edge"] - ref["S"]
                    dF2 = f2["S"] - ref["S"]
                    row = {"stack": stack, "geometry": geom, "rear": rear, "w_m": w,
                           "n_unknowns": net.n, **s,
                           "ref_1d_unfaulted": {"H": ref["H"], "S": ref["S"], "surface": ref["surface"],
                                                "front": ref["front"], "rear": ref["rear"]},
                           "ref_1d_uniform_F2": {"H": f2["H"], "S": f2["S"], "surface": f2["surface"],
                                                 "front": f2["front"], "rear": f2["rear"]},
                           "delta_T_mid_centre_vs_ref_K": dTc,
                           "delta_T_mid_edge_vs_ref_K": dTe,
                           "delta_T_H_vs_ref_K": s["T_H"] - ref["H"],
                           "centre_deficit_fraction_of_uniform": (dTc / dF2) if abs(dF2) > 1e-12 else None,
                           "detect_centre": {str(th): abs(dTc) >= th for th in PREDECLARED["detection_thresholds_K"]},
                           "detect_edge": {str(th): abs(dTe) >= th for th in PREDECLARED["detection_thresholds_K"]},
                           "comparators_study_comparator_only": {
                               "surface_max_minus_40C": s["T_surf_max"] - 40.0,
                               "H_minus_60C": s["T_H"] - 60.0}}
                    tol = 1e-9
                    hyp["HYP1"].append({"case": (stack, geom, rear, w),
                                        "pass": ref["H"] - tol <= s["T_H"] <= f2["H"] + tol and s["T_H"] >= prev_TH - tol})
                    prev_TH = s["T_H"]
                    hyp["HYP2"].append({"case": (stack, geom, rear, w),
                                        "pass": s["T_mid_centre"] <= ref["S"] + tol and
                                        s["T_mid_centre"] >= f2["S"] - (f2["H"] - s["T_H"]) - tol})
                    if rear_open:
                        hyp["HYP3"].append({"case": (stack, geom, rear, w), "pass": abs(dTe) < 0.1})
                        if w >= 5e-3 - 1e-12:
                            hyp["HYP4"].append({"case": (stack, geom, rear, w), "pass": abs(dTc) >= 0.5})
                        if abs(w - 1e-3) < 1e-12:
                            hyp["HYP4"].append({"case": (stack, geom, rear, w), "pass": abs(dTc) < 0.5})
                    else:
                        hyp["HYP6"].append({"case": (stack, geom, rear, w),
                                            "pass": s["T_mid_max"] <= f2["S"] + 0.5 and
                                            s["T_surf_max"] <= f2["surface"] + 0.5})
                    rows.append(row)
    return {"rows": rows, "hypotheses": {k: {"all_pass": all(r["pass"] for r in v), "cases": v}
                                        for k, v in hyp.items()}}


def spreading_study(quick: bool) -> Dict[str, object]:
    out = []
    for stack in PREDECLARED["stacks"]:
        p = M.Params(stack=stack)
        ell_modal = M.modal_spreading_length(p, p.r_c)
        ell_modal_noconv = M.modal_spreading_length(p, p.r_c, include_convection=False)
        ell_fin = M.fin_spreading_length(p, p.r_c)
        ell_modal_f = M.modal_spreading_length(p, p.r_fault)
        ell_fin_f = M.fin_spreading_length(p, p.r_fault)
        rec = {"stack": stack, "ell_modal_unfaulted_m": ell_modal,
               "ell_modal_unfaulted_no_convection_m": ell_modal_noconv,
               "ell_fin_unfaulted_m": ell_fin, "ell_modal_faulted_m": ell_modal_f,
               "ell_fin_faulted_m": ell_fin_f,
               "fin_within_factor2_of_modal": 0.5 <= ell_fin / ell_modal <= 2.0}
        if not (quick and stack != "H3"):
            # fine mesh so that dy <= ell/4 near the patch edge
            dy = min(0.25e-3, ell_modal / 5)
            nz = 4
            zm = M.build_zmesh(p, nz, 1, nz)
            ym = M.default_ymesh("planar", 10e-3, dy, 2.5e-3, max(8 * ell_modal, 8e-3))
            net = M.Network(p, zm, ym, True, True, p.P_body)
            T, _ = M.solve_steady(net, "direct")
            fit = M.fit_decay_length(ym, net.film_midplane(T), ell_modal)
            rec["numerical_fit"] = fit
            rec["n_unknowns"] = net.n
            if fit is not None:
                rec["fit_over_modal"] = fit["ell_fit_m"] / ell_modal
                rec["HYP5_pass"] = abs(rec["fit_over_modal"] - 1.0) <= 0.25 and rec["fin_within_factor2_of_modal"]
        out.append(rec)
    return {"rows": out}


def refinement_study() -> Dict[str, object]:
    p = M.Params(stack="H1")
    levels = []
    for r in (1, 2, 4):
        zm = M.build_zmesh(p, 2 * r, 1, 2 * r)
        ym = M.ymesh_from_faces("planar", M.faces_from_segments([0.0, 0.045, 0.055, 0.1], [9 * r, 2 * r, 9 * r]), 5e-3)
        net = M.Network(p, zm, ym, True, True, p.P_body)
        T, _ = M.solve_steady(net, "direct")
        s = M.steady_summary(net, T)
        levels.append({"refine": r, "n_unknowns": net.n, "T_H": s["T_H"], "T_mid_centre": s["T_mid_centre"],
                       "T_mid_min": s["T_mid_min"], "T_surf_min": s["T_surf_min"]})
    orders = {}
    maxchange = {}
    for key in ("T_H", "T_mid_centre", "T_mid_min", "T_surf_min"):
        q = [lv[key] for lv in levels]
        orders[key] = M.observed_order(q[0], q[1], q[2])
        maxchange[key] = abs(q[1] - q[2])
    return {"levels": levels, "observed_order": orders, "last_change_K": maxchange,
            "criterion_0p10K_met_on_finest_pair": all(v <= 0.10 for v in maxchange.values())}


def _hist(res: M.TransientResult, every: float = 10.0) -> Dict[str, List[float]]:
    keep = [k for k, t in enumerate(res.t) if abs(t / every - round(t / every)) < 1e-9]
    return {f: [getattr(res, f)[k] for k in keep]
            for f in ("t", "T_H", "T_mid_centre", "T_mid_edge", "T_mid_min", "T_mid_max", "T_surf_min", "T_surf_max")}


def _peaks(res: M.TransientResult) -> Dict[str, object]:
    out = {}
    for f in ("T_H", "T_mid_centre", "T_mid_max", "T_surf_max"):
        v = getattr(res, f)
        k = max(range(len(v)), key=lambda i: v[i])
        out[f] = {"peak_C": v[k], "t_peak_s": res.t[k]}
    for name, series, thr in (("surface_40C", res.T_surf_max, 40.0), ("H_60C", res.T_H, 60.0)):
        cross = next((res.t[i] for i, x in enumerate(series) if x >= thr), None)
        out[name + "_study_comparator_only"] = cross if cross is not None else "not_crossed_in_horizon"
    return out


def _detect(res_fault: M.TransientResult, res_base: M.TransientResult, field: str, thr: float):
    for t, a, b in zip(res_fault.t, getattr(res_fault, field), getattr(res_base, field)):
        if t >= 600.0 - 1e-9 and abs(a - b) >= thr:
            return {"t_first_sample_s": t, "deviation_K": a - b}
    return "not_crossed_in_horizon"


def transient_study(quick: bool) -> Dict[str, object]:
    pm = PREDECLARED["transient_mesh"]
    dt = PREDECLARED["transient_dt_s"]
    stacks = PREDECLARED["stacks"] if not quick else ["H1"]
    ws = [2e-3, 20e-3]
    out = []
    for stack in stacks:
        p = M.Params(stack=stack)
        zm = M.build_zmesh(p, pm["n_outer"], pm["n_film"], pm["n_inner"])
        sched_f0 = M.event_schedule(fault_time=None)
        sched_f2 = M.event_schedule(fault_time=600.0)
        # 1-D uniform F2 with the same code (single in-plane cell)
        ym1 = M.ymesh_from_faces("planar", [0.0, M.PANEL_SIDE], M.PANEL_SIDE / 2)
        res_1d_f0 = M.simulate(p, zm, ym1, sched_f0, dt)
        res_1d_f2 = M.simulate(p, zm, ym1, sched_f2, dt)
        for w in ws:
            ym = M.default_ymesh("planar", w, pm["dy_fine_m"], pm["dy_coarse_m"], pm["margin_m"])
            base = M.simulate(p, zm, ym, sched_f0, dt)
            fault = M.simulate(p, zm, ym, sched_f2, dt)
            rec = {"stack": stack, "w_m": w, "dt_s": dt, "n_unknowns": len(base.final_state),
                   "F0_audit": base.audit, "patch_audit": fault.audit,
                   "F0_peaks": _peaks(base), "patch_peaks": _peaks(fault),
                   "uniform_F2_1d_peaks": _peaks(res_1d_f2),
                   "detect_centre": {str(th): _detect(fault, base, "T_mid_centre", th) for th in PREDECLARED["detection_thresholds_K"]},
                   "detect_edge": {str(th): _detect(fault, base, "T_mid_edge", th) for th in PREDECLARED["detection_thresholds_K"]},
                   "detect_centre_uniform_F2_1d": {str(th): _detect(res_1d_f2, res_1d_f0, "T_mid_centre", th) for th in PREDECLARED["detection_thresholds_K"]},
                   "state_continuity_at_600s": [b for b in fault.segment_boundaries if abs(b["t"] - 600.0) < 1e-9],
                   "history_every_10s": {"F0": _hist(base), "patch": _hist(fault), "uniform_F2_1d": _hist(res_1d_f2)}}
            if stack == "H1" and abs(w - 20e-3) < 1e-12:
                fine = M.simulate(p, zm, ym, sched_f2, PREDECLARED["transient_refinement_dt_s"])
                diffs = []
                for k, t in enumerate(fault.t):
                    diffs.append(abs(fault.T_mid_centre[k] - fine.value_at("T_mid_centre", t)))
                diffs_H = [abs(fault.T_H[k] - fine.value_at("T_H", fault.t[k])) for k in range(len(fault.t))]
                rec["time_refinement"] = {"dt_coarse_s": dt, "dt_fine_s": PREDECLARED["transient_refinement_dt_s"],
                                          "max_dT_mid_centre_K": max(diffs), "max_dT_H_K": max(diffs_H),
                                          "criterion_0p05K_met": max(diffs) <= 0.05 and max(diffs_H) <= 0.05}
            out.append(rec)
    return {"rows": out}


def run(out_path: str, quick: bool = False) -> Dict[str, object]:
    report = {"contract": M.CONTRACT, "extension": M.EXTENSION,
              "status": "model_only_not_validated_not_a_safety_or_design_claim",
              "predeclared": PREDECLARED,
              "spreading": spreading_study(quick),
              "steady": steady_study(quick),
              "refinement": refinement_study(),
              "transient": transient_study(quick),
              "omitted": ["F3/F4 controller cases", "F5 double block", "cp/C_H/k sweeps",
                          "outer-interface patch", "patch at panel edge", "radiation", "human contact",
                          "strain dependence", "transient spatial refinement", "real geometry"]}
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=1, default=str)
    return report


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", required=True, help="output JSON path (only file written)")
    ap.add_argument("--quick", action="store_true", help="reduced grid")
    args = ap.parse_args(argv)
    rep = run(args.out, args.quick)
    brief = {"steady_rows": len(rep["steady"]["rows"]),
             "hypotheses": {k: v["all_pass"] for k, v in rep["steady"]["hypotheses"].items()},
             "spreading": [{k: r.get(k) for k in ("stack", "ell_modal_unfaulted_m", "fit_over_modal", "HYP5_pass")}
                           for r in rep["spreading"]["rows"]],
             "refinement_orders": rep["refinement"]["observed_order"],
             "transient_rows": len(rep["transient"]["rows"]), "out": args.out}
    print(json.dumps(brief, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

FILE: tests/test_hotspot2d.py
```python
"""Unit tests for the 2D-PATCH-EXT-1 model. Expected values for the 1-D
limits are (i) Coda's executed reference_results.json numbers (fixtures below,
sha256 e97cf35c...) and (ii) the transcribed two-node reference; both are
independent of the finite-volume code under test."""
import math
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from hotspot2d import model as M  # noqa: E402

# Coda, validation/thermal/reference_results.json, 5 W body + 0.1 W sensor, rear R=2 K/W
CODA_5W = {"H1": (33.83119986113005, 33.70398462379287, 33.55500086793716, 0.6844000694349729, 4.415599930565027),
           "H2": (33.86190245732054, 33.6326495680521, 33.36310964174662, 0.6690487713397297, 4.430951228660271),
           "H3": (33.91905575238601, 33.501140687023764, 33.00590154758745, 0.6404721238069959, 4.459527876193004)}
CODA_5W_BLOCKED_H = {"H1": 90.94862037037036, "H2": 92.81899074074074, "H3": 96.55973148148148}


def small_mesh(p, geom="planar", w=0.0, refine=1, nz=2):
    zm = M.build_zmesh(p, nz, 1, nz)
    ym = M.default_ymesh(geom, w, dy_fine=2e-3, dy_coarse=10e-3, margin=4e-3, refine=refine)
    return zm, ym


class TestMeshAndAssembly(unittest.TestCase):
    def test_areas_sum_to_panel_area(self):
        for geom in ("planar", "axisymmetric"):
            ym = M.default_ymesh(geom, 5e-3)
            self.assertAlmostEqual(ym.total_area, M.PANEL_AREA, places=12)

    def test_patch_membership_and_faulted_faces(self):
        p = M.Params()
        zm, ym = small_mesh(p, w=5e-3)
        c = M.PANEL_SIDE / 2
        for j in range(ym.n):
            self.assertEqual(ym.in_patch[j], abs(ym.centres[j] - c) < 5e-3)
        self.assertTrue(any(abs(f - (c - 5e-3)) < 1e-12 for f in ym.faces))
        self.assertTrue(any(abs(f - (c + 5e-3)) < 1e-12 for f in ym.faces))
        net = M.Network(p, zm, ym, True, True, 5.0)
        self.assertEqual(sorted(net.faulted_cells), [j for j in range(ym.n) if ym.in_patch[j]])
        self.assertAlmostEqual(ym.patch_area, 2 * 5e-3 * M.PANEL_SIDE, places=12)
        self.assertEqual(M.Network(p, zm, ym, False, True, 5.0).faulted_cells, [])

    def test_matrix_symmetric_and_positive_definite(self):
        p = M.Params(R_rej=math.inf)
        zm, ym = small_mesh(p, w=3e-3)
        net = M.Network(p, zm, ym, True, False, 5.0)
        self.assertTrue(net.is_symmetric())
        for seed in range(3):
            x = [math.sin(0.37 * k + seed) for k in range(net.n)]
            self.assertGreater(net.quadratic_form(x), 0.0)
        self.assertGreater(net.quadratic_form([1.0] * net.n), 0.0)  # boundary term makes constants non-null


class TestSteadyLimits(unittest.TestCase):
    def test_w_zero_recovers_1d_reference_all_stacks(self):
        for stack, (H, S, surf, front, rear) in CODA_5W.items():
            p = M.Params(stack=stack)
            zm, ym = small_mesh(p, w=0.0)
            net = M.Network(p, zm, ym, True, True, 5.0)  # fault flag on, but no patch cells
            for method, tol in (("direct", 1e-9), ("pcg", 1e-7)):
                T, info = M.solve_steady(net, method)
                self.assertTrue(info["converged"])
                s = M.steady_summary(net, T)
                self.assertAlmostEqual(s["T_H"], H, delta=tol)
                self.assertAlmostEqual(s["T_mid_centre"], S, delta=tol)
                self.assertAlmostEqual(s["T_mid_edge"], S, delta=tol)
                self.assertAlmostEqual(s["T_surf_centre"], surf, delta=tol)
                self.assertAlmostEqual(s["front_W"], front, delta=tol)
                self.assertAlmostEqual(s["rear_W"], rear, delta=tol)
                self.assertLess(abs(s["balance_W"]), 1e-9)

    def test_blocked_rear_w_zero_recovers_coda_blocked_values(self):
        for stack, H in CODA_5W_BLOCKED_H.items():
            p = M.Params(stack=stack, R_rej=math.inf)
            zm, ym = small_mesh(p, w=0.0)
            net = M.Network(p, zm, ym, True, False, 5.0)
            T, _ = M.solve_steady(net, "direct")
            s = M.steady_summary(net, T)
            self.assertAlmostEqual(s["T_H"], H, delta=1e-9)
            self.assertAlmostEqual(s["T_surf_centre"], 88.75, delta=1e-9)
            self.assertAlmostEqual(s["front_W"], 5.1, delta=1e-9)

    def test_full_patch_recovers_uniform_F2_both_geometries(self):
        for geom in ("planar", "axisymmetric"):
            for stack in ("H1", "H3"):
                p = M.Params(stack=stack)
                zm, ym = small_mesh(p, geom=geom, w=M.full_patch_width(geom))
                self.assertTrue(all(ym.in_patch))
                net = M.Network(p, zm, ym, True, True, 5.0)
                T, _ = M.solve_steady(net, "direct")
                s = M.steady_summary(net, T)
                ref = M.reference_1d_steady(p, r_inner=p.r_fault)
                self.assertAlmostEqual(s["T_H"], ref["H"], delta=1e-9)
                self.assertAlmostEqual(s["T_mid_centre"], ref["S"], delta=1e-9)
                self.assertAlmostEqual(s["T_surf_centre"], ref["surface"], delta=1e-9)
                self.assertAlmostEqual(s["front_W"], ref["front"], delta=1e-9)
                self.assertLess(s["T_mid_max"] - s["T_mid_min"], 1e-9)  # laterally uniform

    def test_transcribed_reference_matches_coda_fixture(self):
        for stack, (H, S, surf, front, rear) in CODA_5W.items():
            ref = M.reference_1d_steady(M.Params(stack=stack))
            self.assertAlmostEqual(ref["H"], H, places=10)
            self.assertAlmostEqual(ref["S"], S, places=10)
            self.assertAlmostEqual(ref["surface"], surf, places=10)
            self.assertAlmostEqual(ref["front"], front, places=10)

    def test_pcg_agrees_with_direct_on_patch_case(self):
        p = M.Params(stack="H2")
        zm, ym = small_mesh(p, w=6e-3)
        net = M.Network(p, zm, ym, True, True, 5.0)
        Td, _ = M.solve_steady(net, "direct")
        Tp, info = M.solve_steady(net, "pcg", tol=1e-14)
        self.assertTrue(info["converged"])
        self.assertLess(max(abs(a - b) for a, b in zip(Td, Tp)), 1e-8)
        self.assertLess(net.residual_norm(Td), 1e-10)

    def test_steady_energy_balance_with_patch(self):
        for rear_open in (True, False):
            p = M.Params(stack="H1", R_rej=2.0 if rear_open else math.inf)
            zm, ym = small_mesh(p, w=8e-3)
            net = M.Network(p, zm, ym, True, rear_open, 5.0)
            T, _ = M.solve_steady(net, "direct")
            s = M.steady_summary(net, T)
            self.assertAlmostEqual(s["source_W"], 5.1, places=12)
            self.assertLess(abs(s["balance_W"]), 1e-9)

    def test_mesh_refinement_observed_order(self):
        """Factor-2 refinement in z and y; predeclared: order >= 1.0 for the
        smooth functionals T_H and T_mid_centre, differences decreasing."""
        p = M.Params(stack="H1")
        q = {"T_H": [], "T_mid_centre": [], "T_mid_min": []}
        for r in (1, 2, 4):
            zm = M.build_zmesh(p, 2 * r, 1, 2 * r)
            ym = M.ymesh_from_faces("planar", M.faces_from_segments([0.0, 0.045, 0.055, 0.1], [9 * r, 2 * r, 9 * r]), 5e-3)
            net = M.Network(p, zm, ym, True, True, 5.0)
            T, _ = M.solve_steady(net, "direct")
            s = M.steady_summary(net, T)
            for k in q:
                q[k].append(s[k])
        for k in ("T_H", "T_mid_centre"):
            e1, e2 = abs(q[k][0] - q[k][1]), abs(q[k][1] - q[k][2])
            self.assertLess(e2, e1, msg=k)
            order = M.observed_order(*q[k])
            if order is not None:
                self.assertGreaterEqual(order, 1.0, msg=f"{k}: observed order {order}")
        # the patch is a cold spot over its centre in the open-rear case (model expectation)
        ref = M.reference_1d_steady(p)
        self.assertLess(q["T_mid_centre"][-1], ref["S"])


class TestTransient(unittest.TestCase):
    def test_uniform_no_source_stays_uniform(self):
        p = M.Params(P_body=0.0, P_sensor=0.0)
        zm, ym = small_mesh(p, w=4e-3)
        segs = [M.Segment(0.0, 50.0, 0.0, True, True)]
        res = M.simulate(p, zm, ym, segs, 5.0, T_initial=[25.0] * (zm.n * ym.n + 1))
        self.assertLess(max(abs(x - 25.0) for x in res.final_state), 1e-12)
        self.assertLess(abs(res.audit["residual_J"]), 1e-9)

    def test_energy_audit_closes_with_fault_event(self):
        p = M.Params(stack="H2")
        zm, ym = small_mesh(p, w=5e-3)
        segs = M.event_schedule(fault_time=60.0, body_off_time=120.0, horizon=200.0)
        res = M.simulate(p, zm, ym, segs, 4.0)
        a = res.audit
        self.assertGreater(a["injected_J"], 0.0)
        self.assertLess(abs(a["residual_J"]), 1e-7 * (1.0 + a["injected_J"]))
        # bookkeeping path (recorded injected/exported) agrees with reconstruction from states
        self.assertAlmostEqual(res.E[-1] - res.E[0], res.injected[-1] - res.exported[-1], delta=1e-7)

    def test_state_continuity_at_fault_instant(self):
        p = M.Params(stack="H1")
        zm, ym = small_mesh(p, w=5e-3)
        segs = M.event_schedule(fault_time=40.0, body_off_time=80.0, horizon=100.0)
        res = M.simulate(p, zm, ym, segs, 2.0)
        b40 = [b for b in res.segment_boundaries if abs(b["t"] - 40.0) < 1e-9][0]
        k40 = [k for k, t in enumerate(res.t) if abs(t - 40.0) < 1e-9]
        self.assertEqual(len(k40), 1)
        self.assertAlmostEqual(res.T_H[k40[0]], b40["T_H"], places=12)
        self.assertAlmostEqual(res.T_mid_centre[k40[0]], b40["T_mid_centre"], places=12)

    def test_full_patch_transient_is_y_independent_and_matches_1d(self):
        p = M.Params(stack="H1")
        zm = M.build_zmesh(p, 2, 1, 2)
        segs = M.event_schedule(fault_time=30.0, body_off_time=60.0, horizon=90.0)
        ym1 = M.ymesh_from_faces("planar", [0.0, M.PANEL_SIDE], M.PANEL_SIDE / 2)
        ym8 = M.ymesh_from_faces("planar", M.faces_from_segments([0.0, M.PANEL_SIDE], [8]), M.PANEL_SIDE / 2)
        r1 = M.simulate(p, zm, ym1, segs, 3.0)
        r8 = M.simulate(p, zm, ym8, segs, 3.0)
        self.assertLess(max(abs(a - b) for a, b in zip(r1.T_H, r8.T_H)), 1e-9)
        self.assertLess(max(abs(a - b) for a, b in zip(r1.T_mid_centre, r8.T_mid_centre)), 1e-9)
        self.assertLess(max(a - b for a, b in zip(r8.T_mid_max, r8.T_mid_min)), 1e-9)

    def test_long_time_transient_tends_to_steady(self):
        p = M.Params(stack="H1")
        zm, ym = small_mesh(p, w=5e-3)
        segs = [M.Segment(0.0, 2000.0, 5.0, True, True)]
        res = M.simulate(p, zm, ym, segs, 10.0)
        net = M.Network(p, zm, ym, True, True, 5.0)
        T, _ = M.solve_steady(net, "direct")
        self.assertLess(max(abs(a - b) for a, b in zip(res.final_state, T)), 1e-3)

    def test_time_refinement_first_order(self):
        """Backward Euler: observed temporal order predeclared in [0.6, 1.5]."""
        p = M.Params(stack="H1")
        zm, ym = small_mesh(p, w=5e-3)
        segs = M.event_schedule(fault_time=100.0, body_off_time=200.0, horizon=240.0)
        vals = []
        for dt in (20.0, 10.0, 5.0):
            res = M.simulate(p, zm, ym, segs, dt)
            vals.append(res.value_at("T_H", 240.0))
        order = M.observed_order(*vals)
        self.assertIsNotNone(order)
        self.assertGreaterEqual(order, 0.6)
        self.assertLessEqual(order, 1.5)

    def test_pcg_transient_matches_direct(self):
        p = M.Params(stack="H2")
        zm, ym = small_mesh(p, w=4e-3)
        segs = [M.Segment(0.0, 20.0, 5.0, True, True)]
        rd = M.simulate(p, zm, ym, segs, 5.0, method="direct")
        rp = M.simulate(p, zm, ym, segs, 5.0, method="pcg", pcg_tol=1e-13)
        self.assertLess(max(abs(a - b) for a, b in zip(rd.final_state, rp.final_state)), 1e-7)


class TestSpreadingLength(unittest.TestCase):
    def test_modal_limits(self):
        p = M.Params(stack="H1", h=1e-9, r_c=0.0)
        # R_f -> film only (small): x -> pi/4 within the small-film correction
        ell = M.modal_spreading_length(p, 0.0, include_convection=False)
        self.assertAlmostEqual(ell / (4 * p.t_s / math.pi), 1.0, delta=0.08)
        # large R_f: ell ~ sqrt(R_f k_s t)
        big = 10.0
        ell_big = M.modal_spreading_length(p, big, include_convection=False)
        self.assertAlmostEqual(ell_big / math.sqrt(big * p.k_s * p.t_s), 1.0, delta=0.05)

    def test_fin_within_factor_two_of_modal(self):
        for stack in ("H1", "H2", "H3"):
            p = M.Params(stack=stack)
            for r in (p.r_c, p.r_fault):
                ratio = M.fin_spreading_length(p, r) / M.modal_spreading_length(p, r)
                self.assertTrue(0.5 <= ratio <= 2.0, msg=f"{stack} r={r} ratio={ratio}")

    def test_numerical_decay_length_matches_modal_H3(self):
        """Predeclared: fitted decay length within 25 % of the modal value."""
        p = M.Params(stack="H3")
        ell = M.modal_spreading_length(p, p.r_c)
        zm = M.build_zmesh(p, 4, 1, 4)
        ym = M.default_ymesh("planar", 10e-3, dy_fine=0.5e-3, dy_coarse=2.5e-3, margin=20e-3)
        net = M.Network(p, zm, ym, True, True, 5.0)
        T, _ = M.solve_steady(net, "direct")
        fit = M.fit_decay_length(ym, net.film_midplane(T), ell)
        self.assertIsNotNone(fit)
        self.assertAlmostEqual(fit["ell_fit_m"] / ell, 1.0, delta=0.25,
                               msg=f"fit {fit['ell_fit_m']} vs modal {ell}")


if __name__ == "__main__":
    unittest.main()
```

FILE: hotspot2d/NOTES.md
```markdown
# 2D-PATCH-EXT-1 — notes, derivation, acceptance plan, limits

Labelled amendment to T0-HYP-1 (not a change of the common baseline): adds
one in-plane coordinate and a spatially bounded inner silicone/film contact
impairment (r_c 2e-4 -> 2e-2 m2 K/W only on a patch of half-width w). All
materials, thicknesses, sources, boundaries, R_rej, C_H and comparators are
T0-HYP-1 values. Written by Claude (Red run) on Coda's packet; the 1-D two-node
reference is Coda's (thermal_reference.py, transcribed). Nothing was executed
by the author; see Red's sandbox output for numbers.

## 1. Geometry and node/face map

- Planar variant: panel width L = 0.1 m (y), depth D = 0.1 m (uniform, not
  modeled), A = L*D = 0.01 m2. Patch = strip |y - L/2| < w across the full
  depth; patch area fraction 2w/L. Edges y = 0, L adiabatic.
- Axisymmetric variant: equal-area disc R = sqrt(A/pi) = 0.0564 m; patch =
  disc r < w; rim adiabatic. (The square panel is replaced by a disc of the
  same area: an approximation, labelled.)
- Through-thickness cells i = 0..n_z-1 (outer silicone n_o cells, film n_f odd
  cells, inner silicone n_i cells). Cell (i, j) -> unknown j*n_z + i; H is the
  last unknown. Film midplane cell i_mid = n_o + n_f//2 carries the sensor
  sheet source, split in proportion to cell area A_j (total exactly P_sensor,
  grid-independent).
- z-face (i,i+1) of column j: G = A_j / (dz_i/(2k_i) + dz_{i+1}/(2k_{i+1}) + r),
  r = r_c at the two material interfaces, r = r_fault at the inner interface
  if cell j is in the patch, r = 0 on refined internal faces.
- Top face: G = A_j / (dz_0/(2k_0) + 1/h) to T_amb. Bottom face: G = A_j /
  (dz_last/(2k_last)) to H (ideal attachment, as in the contract).
- In-plane face (j, j+1) in layer i: G = k_i dz_i P_f / (y_{c,j+1} - y_{c,j}),
  P_f = D (planar) or 2*pi*r_f (axisymmetric). No lateral contact resistance
  (interfaces are thin series layers).
- H: capacity C_H, source P_body, conductance 1/R_rej to T_res (0 if blocked).
- Surface temperature is reconstructed from the boundary flux:
  T_s,j = T_amb + (T_0j - T_amb)*(1/h)/(dz_0/(2k_0) + 1/h).

In the 1-D limit (no in-plane gradient) the cell-centre finite-volume steady
solution is exact for the series network (piecewise-linear profile, source at a
cell centre), so w = 0 and w = full width must reproduce Coda's two-node
numbers to roundoff regardless of mesh. The tests use this.

## 2. Equations

Steady: K T = q + G_b T_b. Transient (backward Euler, step h):
(C/h + K) T^{n+1} = (C/h) T^n + q + G_b T_b, with q piecewise constant and the
integration restarted exactly at every event time (600 s fault, 900 s body
off). States are continuous across events (no impulsive source declared).

Energy: summing all cell equations, every internal exchange G_e (T_q - T_p)
appears once with each sign and cancels, leaving
sum_p C_p (T_p^{n+1} - T_p^n) = h [ sum q - sum_top G_amb,j (T_0j^{n+1} - T_amb)
- G_rear (T_H^{n+1} - T_res) ], exact for backward Euler with the exported heat
evaluated at t^{n+1}. The audit reports E(t)-E(0) - injected + exported (should
be roundoff) and the independent reconstruction from recorded states.

## 3. SPD and solver convergence (proof sketch)

K = sum_edges G_e (e_p - e_q)(e_p - e_q)^T + sum_boundary g_b e_p e_p^T, so
x^T K x = sum_e G_e (x_p - x_q)^2 + sum_b g_b x_p^2 >= 0, with equality only if
x is constant on the (connected) network graph and x_p = 0 at every node with
g_b > 0. Since h > 0 always gives g_b > 0 at the top cells, x = 0: K is SPD
(also when the rear is blocked). M = C/h + K is SPD a fortiori.

PCG with Jacobi preconditioner P = diag(M) (SPD): equivalent to CG on
P^{-1/2} M P^{-1/2}, which is SPD. CG minimises the M-norm of the error over
the Krylov space, giving ||e_k||_M <= 2 ((sqrt(kappa)-1)/(sqrt(kappa)+1))^k
||e_0||_M (kappa = condition number of the preconditioned matrix) and finite
termination in <= n steps in exact arithmetic (Hestenes-Stiefel; any standard
text, e.g. Saad, Iterative Methods for Sparse Linear Systems, ch. 6). The code
stops at ||r|| <= tol ||b||; the tests use tol 1e-13..1e-14 and compare against
the direct solver.

Direct cross-check: with the H column removed the cell block is banded (half
bandwidth n_z); it is SPD (a principal submatrix of an SPD matrix) so banded
Cholesky exists without pivoting; the bordered unknown H is handled by the 1x1
Schur complement d - c^T B^{-1} c > 0. Used for the transient for speed.

## 4. Predeclared verification (b)

- w = 0 (planar) reproduces Coda's 5 W rows for H1/H2/H3 (T_H, S, surface,
  front, rear) to 1e-9 (direct) / 1e-7 (PCG); blocked rear reproduces
  90.9486/92.8190/96.5597 C and 88.75 C surface.
- w = L/2 (planar) and w = R (axisymmetric) reproduce the uniform F2 two-node
  result (r_inner = 2e-2) to 1e-9 and are laterally uniform to 1e-9.
- Factor-2 refinement in z and y (patch faces fixed): successive differences
  decrease; observed order >= 1.0 for T_H and T_mid_centre (expected ~2;
  singular gradient at the patch edge may reduce it). Study records the 0.10 K
  criterion on the finest pair.
- Steady balance |sources - front - rear| < 1e-9 W; transient residual
  < 1e-7 (1 + injected) J; uniform/no-source invariance; continuity at the
  fault instant; y-independence of the full-patch transient vs n_y = 1;
  long-time convergence to the steady solve (1e-3 K); temporal observed order
  in [0.6, 1.5] for backward Euler; PCG vs direct in the transient.
If a criterion fails, keep the failed run; do not loosen the criterion.

## 5. Lateral spreading length (c)

Fin estimate (crude): treat film + outer silicone as one laterally conducting
layer, kappa = k_f t_f + k_s t_o [W/K per unit width], leaking to H through
r_leak = r_inner + t_i/k_s and to ambient through 1/h: ell_fin^2 = kappa /
(1/r_leak + 1/r_front). Static expectation (unexecuted arithmetic): ~0.55 mm
(H1), ~2.0 mm (H3) unfaulted; ~1.6 mm (H1), ~3.5 mm (H3) inside the patch.

Two-layer modal analysis (more defensible): a steady perturbation theta =
e^{-y/ell} phi(z) satisfies phi'' + phi/ell^2 = 0 in each silicone layer.
Inner layer (phi = 0 at H): phi = sin(z/ell). Outer layer with Robin top:
phi = C cos((t_o - zeta)/ell + psi), tan(psi) = -h ell/k_s. Film plus both
contacts lumped as areal resistance R_f = t_f/k_f + r_c + r_inner (film lateral
conduction k_f t_f = 1e-5 W/K neglected vs k_s t >= 1.35e-4). Flux continuity
C sin(x+psi) = cos x and temperature jump C cos(x+psi) - sin x = (R_f k_s x/t)
cos x, with x = t/ell, give cos(2x+psi) = (R_f k_s x/t) cos x sin(x+psi). The
smallest admissible root gives the slowest mode. Limits: R_f, h -> 0: x = pi/4,
ell = 4t/pi; R_f large: ell ~ sqrt(R_f k_s t) (fin regime). Static expectation:
ell ~ 0.7 mm (H1), ~1.3 mm (H2), ~2.6 mm (H3) unfaulted; ~1.8 mm (H1), ~4 mm
(H3) faulted. Hence w in [1, 20] mm spans w << ell to w >> ell, and for w >= ~5
mm the patch centre should approach the uniform-F2 local state. Numerical
check: exponential fit of the film-midplane perturbation outside the patch
between ~2 ell and ~4 ell (second mode ~ ell/3 is then suppressed); criterion
|ell_fit/ell_modal - 1| <= 0.25; fin within factor 2 of modal.

## 6. Predeclared study (d) — hypotheses recorded, not asserted

HYP1 T_H(ref) <= T_H(w) <= T_H(uniform F2), non-decreasing in w (Rayleigh
monotonicity heuristic for the P_body part; the small J part is not covered).
HYP2 Over the patch centre the film is a cool spot (<= unfaulted) and not
colder than the uniform-F2 value minus the H shift.
HYP3 Open rear: edge-sensor deviation < 0.1 K for all w <= 20 mm.
HYP4 Open rear: centre deviation >= 0.5 K for w >= 5 mm, < 0.5 K for w = 1 mm.
HYP5 Spreading length agreement (section 5).
HYP6 Blocked rear: max film/surface with a patch within 0.5 K of the uniform-F2
blocked values (front path dominated by 1/h = 0.125 >> r_fault = 0.02 m2 K/W,
so the patch barely changes the exit).
Transient: detection time = first 2 s sample after 600 s where the patch run
deviates from the F0 run by >= 0.1 / 0.5 K (centre and edge midplane);
peaks and times for H, film and surface; 40/60 C crossings reported as
not_crossed_in_horizon when absent; time-refinement 0.05 K criterion on H1
w = 20 mm.

Static physical expectation to be tested, not asserted: because the dominant
source is H and the front path is convection-limited, the localized inner
impairment produces a local DEFICIT of film/surface temperature over the patch
(~r_fault/(r_fault + 1/h) ~ 14 % of T_H - T_amb) and a small uniform rise of
T_H; no film hot spot is expected in this contract. The strongest justified
claim if the hypotheses hold: within this model the uniform F2 case is an
upper envelope for T_H and for the magnitude of the local film deficit, and a
centre midplane sensor sees the patch while an edge sensor does not. The most
important counterexample candidate: in regimes where the fault blocks the
dominant exit (not this contract: here the front exit is convection-limited),
a localized fault can exceed the uniform case by concentrating flux on the
unfaulted area; HYP6 is the explicit check that this does not occur here.

## 7. Limits (honest)

Model only: idealised H lump (cannot have a local hot spot by construction),
no traces/components/adhesive mass, uniform assumed h, no radiation, no human
contact, no strain dependence, equal-area disc approximation for the
axisymmetric case, step change of r_c on cell faces (patch boundary snapped to
the mesh; actual patch area reported), film lateral conduction neglected only
in the analytic length (not in the FV model), transient mesh coarser than the
steady mesh, no spatial refinement of the transient, no property sweeps.
Smallest next steps: (i) distributed H structure with its own lateral
conduction; (ii) a fault at the outer interface; (iii) a sensor-power
sensitivity (local sensor heating is where a true hot spot could arise);
(iv) patch at the panel edge; (v) cp/C_H/k sweeps shared with Coda's suite.
```

## Notes for Red (how to run, and what I expect you may need to correct)

Run order: `python -m unittest tests.test_hotspot2d` then `python -m hotspot2d.study --out <path>/hotspot2d_results.json` (add `--quick` first if runtime matters). Everything prints only a brief JSON summary; the single output file is the `--out` path.

Points I could not verify without execution and that most plausibly need a correction pass:

1. **Observed spatial order** (`test_mesh_refinement_observed_order`): the predeclared floor 1.0 for `T_mid_centre` may be missed if the patch-edge gradient singularity dominates at these coarse levels; if so, keep the failure, report the measured order, and do not loosen the floor silently.
2. **Spreading-length fit** (`test_numerical_decay_length_matches_modal_H3`): the 25 % band rests on my derivation in NOTES §5 (sign of the jump condition re-derived once; the h=0, R_f→0 limit x = π/4 and the large-R_f fin limit are consistency checks the test also exercises). A failure here points first at the modal derivation or the fit window, not at the FV code.
3. **PCG iteration counts / runtime**: Jacobi-PCG with tol 1e-13 on ~10³ unknowns may take several hundred iterations; the test meshes are small, but if `maxiter` is hit, the test asserts `converged` and will fail honestly.
4. **Runtime of the study**: unmeasured estimate of minutes in CPython (transient runs at dt = 2 s with ≈600 unknowns). `--quick` reduces the grid.
5. The expected physical outcome (cool spot over the patch, small uniform T_H rise, HYP6 holding) is a static expectation; if the executed results contradict it, the results stand and the notes' expectation is what needs revising.