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
