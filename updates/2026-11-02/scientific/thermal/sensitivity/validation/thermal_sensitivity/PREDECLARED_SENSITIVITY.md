# PREDECLARED: thermal-sensitivity-001 (which T0-HYP-1 assumptions control the conclusions)

Written by Claude (Anthropic) for Red before any execution. The author has no execution tools; Red
executes the code and returns observed results. Observed results are compared to the checks and
predictions below without posthoc relaxation. Nothing here is physical validation, a safety
certification, a hardware design recommendation or a public release.

## Question
Coda's executed steady reference (validation/thermal/REPORT.md) found that the thicker hypothetical
cover lowers the modeled outer temperature while raising the internal node temperature
(H1/H2/H3 surfaces 33.555/33.363/33.006 C vs internal 33.831/33.862/33.919 C at 5 W). Determine,
over the contract's declared sensitivity domains, where this surface/internal ranking reversal
holds (reference direction), flips (opposite direction) or ties, and which assumptions control the
steady temperatures and the two-node transient peaks.

## Read-only inputs (by hash, from the source bundle)
- validation/thermal/thermal_reference.py  sha256 7032a2cd...e56d (Coda, exact rational steady network)
- validation/thermal/reference_results.json  sha256 e97cf35c...af56 (12 steady rows, exact front strings)
- validation/thermal_transient/rc_transient.py  sha256 94ff435d...25b0 (Coda, T0-LUMP2-1; called, not reimplemented)
- Coda's reports and predeclarations; T0-HYP-1 contract excerpt (Coda's packet).
Hash matches are recorded in the output JSON as information; a mismatch is reported as a deviation.

## Model (closed form, exact rational arithmetic)
a = R_HS = t_i/(k_s A) + t_f/(2 k_f A) + r_c/A;  b = R_SA = t_o/(k_s A) + t_f/(2 k_f A) + r_c/A + c;
c = 1/(h A);  D = a + b + r;  N = (T_res - T_amb) + r (P + J) + a J;  F = N/D;  B = P + J - F;
T_surface = T_amb + c F;  T_S = T_amb + b F;  T_H = T_S + a (F - J) = T_res + r B.
Rear blocked (zero rear conductance): F = P + J, B = 0. Partials: dF/da = (J b - r P - (T_res-T_amb))/D^2,
dF/db = -F/D, dF/dr = B/D, dF/dP = r/D, dF/dJ = (a+r)/D, dF/dT_res = 1/D = -dF/dT_amb, chained
through da/dk_s = -t_i/(k_s^2 A), db/dk_s = -t_o/(k_s^2 A), da/dk_f = db/dk_f = -t_f/(2 k_f^2 A),
da/dr_c = db/dr_c = 1/A, db/dh = dc/dh = -1/(h^2 A), da/dt_i = db/dt_o = 1/(k_s A),
da/dt_f = db/dt_f = 1/(2 k_f A). See steady_closed_form.py docstring.

## Analytic claim to be checked (AC3, AC4, predictions P1-P4)
For stacks X (thinner) and Y (thicker) under identical exogenous conditions:
T_surface(X)-T_surface(Y) = c (F_X - F_Y) and T_H(X)-T_H(Y) = -r (F_X - F_Y). With finite r the two
rankings are always opposite unless F_X = F_Y. sign(F_X - F_Y) = sign(N_X D_Y - N_Y D_X). For symmetric
stacks (t_o = t_i within each stack, shared relative deviations) this equals
(a_Y - a_X) [ r (2P + J) - J/(h A) + 2 (T_res - T_amb) ]: the direction depends only on R_rej, h, P
(and J, A, reservoir offset). With T_res = T_amb the flipped direction requires
R_rej (2P + J) < J/(h A), i.e. R_rej < kappa/h with kappa = J/(A (2P + J)) = 100/21 K/W at P = 1 W,
100/101 at 5 W, 100/201 at 10 W. Blocked rear: surface tie, interior ordered by cover resistance.

## Factors and declared domains (assumed study domains, from the contract; not measured distributions)
| factor | domain | note |
|---|---|---|
| k_s shared silicone conductivity | [0.18, 0.35] W/(m K) | one value for all silicone layers of all stacks |
| k_f shared film conductivity | [0.12, 0.25] W/(m K) | |
| r_c areal contact resistance | [0, 2.0e-3] m2 K/W | same at both interfaces |
| h outer convection | [3, 15] W/(m2 K) | never called measured |
| R_rej rear resistance | [1, 10] K/W | blocked (infinite) handled as a separate discrete case |
| P_body | {1, 5, 10} W | discrete; analyses are run conditional on each level |
| thickness, mode common_bias | delta_all in [-0.10, 0.10] | all layers (outer, film, inner) scaled by 1+delta_all |
| thickness, mode independent_layers | delta_outer, delta_film, delta_inner each in [-0.10, 0.10] | independent |
Assumptions: J = 0.10 W, T_amb = T_res = 25 C, A = 0.01 m2, film 0.050 mm, C_H = 20 J/K and Coda's
cover-capacity formula (silicone rho 1030, cp 1500; film rho 1420, cp 1090) are held fixed and are not
in any declared domain. Relative thickness deviations are shared across the three stacks (identical
exogenous conditions); stack-specific deviations are not studied. Internal node attachment stays ideal.

## Sampling conventions
Unit-cube points are mapped linearly onto the intervals (uniform measure). This is a convention for
describing variance over the declared study domain; it is not a belief distribution, and no confidence
interval is derived. Morris elementary effects are reported per unit of normalized factor range.

## Sample sizes, seeds, scenarios (defaults; CLI may change them and any change is a recorded deviation)
- Seed 20261101; every analysis derives its own deterministic string seed "<seed>|<analysis>|<mode>|P<level>".
- Steady: Morris r = 20 trajectories, p = 4 levels (Delta = 2/3); Sobol base N = 2048 (evaluations (k+2) N).
  Outputs: T_surface and T_H of H1, H2, H3; gaps T_surface(H1)-T_surface(H3), T_H(H1)-T_H(H3). Per mode and P level.
- Transient (Coda's T0-LUMP2-1 via rc_transient.simulate, backward Euler dt = 1 s): Morris r = 10,
  Sobol base N = 64 (screening grade), P_body = 5 W only, scenario "rear_loss_sensor_on" exactly as
  Coda's fault suite: start H = S = 25 C, body power on until 900 s then 0, sensor 0.1 W throughout, rear
  conductance set to zero at 600 s; horizon 1800 s (peaks lie near 900 s; a peak within 300 s of the
  horizon is flagged). Outputs: peak H and peak reconstructed surface for H1, H2, H3 and their H1-H3 gaps.
  Rear blocked from the start is evaluated deterministically at nominal factors for all stacks and P levels.
- Exact grid classification (Fractions): common_bias grid k_s{0.18,0.265,0.35} x k_f{0.12,0.185,0.25} x
  r_c{0,1e-3,2e-3} x h{3,3.5,4,4.5,5,6,8,10,12,15} x R_rej{1,1.1,1.2,1.3,1.5,2,3,5,7,10} x delta{-0.1,0,0.1};
  independent_layers grid uses the end points of k_s, k_f, r_c, h{3,3.5,4,4.5,5,8,15}, R_rej{1,1.2,1.5,2,5,10}
  and three levels per delta. Grid counts over-resolve the low-h/low-R_rej corner by design and are NOT domain
  fractions; the uniform-measure flip fraction is computed analytically.

## Estimators
Morris: EE_i = [f(x + d e_i) - f(x)]/d with d = +/-2/3 on the 4-level grid; mu, mu* (mean |EE|), sigma (sample s.d.).
Sobol: independent Latin-hypercube matrices A, B; AB_i replaces column i of A by B's; outputs centred by the
pooled mean; S_i = (1/N) sum f_B (f_ABi - f_A)/V (Saltelli 2010); S_Ti = (1/2N) sum (f_A - f_ABi)^2 / V (Jansen 1999);
V = pooled population variance of A and B evaluations.

## Acceptance checks (all declared before execution)
AC1 Closed form reproduces Coda's 12 reference rows: exact Fraction equality of the front flux strings, and
    |T_H|, |T_S|, |T_surface| differences <= 1e-9 K.
AC2 Hand-coded partials equal exact dual-number partials exactly (Fraction equality) for 18 nominal cases
    (3 stacks x 3 P x rear present/blocked). Tests also require exact central differences (relative step 1e-6)
    to agree within 1e-9 (1 + |partial|).
AC3 Brute-force exact temperature comparison on every 7th grid point never yields a same-direction ranking.
AC4 Analytic pattern from the discriminant equals the brute-force pattern on every checked grid point; the
    pattern is identical for pairs (H1,H2), (H2,H3) and (H1,H3) at those points (AC4b).
AC5 Method self-checks: Morris on a linear function returns mu = coefficients to 1e-9 with sigma <= 1e-9;
    Sobol on f = x1 + 2 x2 x3 (exact S = 0.3,0.3,0.3; S_T = 0.3,0.4,0.4) within 0.05 at N = 4096.
AC6 Reproducibility: regenerating the steady common_bias P = 5 designs with the same seed gives identical
    design digests and identical indices; the unit tests also require identical JSON from two small runs.
AC7 Transient wrapper at nominal factors reproduces rc_transient.nominal fields within 1e-12 relative and
    Coda's tabulated peaks (REPORT.md, 6 decimals) within 1e-5 K and 1 s for all six nominal cases.
AC8 Every transient run satisfies rc_transient's own energy audit (max residual <= its tolerance).
AC9 Every transient peak time is at least 300 s before the horizon.
AC10 Sobol sanity: steady (N = 2048) min S_i >= -0.05, sum S_i <= 1.10, S_Ti >= S_i - 0.05; transient
    (N = 64) min S_i >= -0.15, sum S_i <= 1.30, S_Ti >= S_i - 0.25. Sanity bounds, not proofs.

## Predeclared predictions (falsifiable statements from the analytic claim; evaluated at full grid resolution)
P1 common_bias: flipped points occur only at P = 1 W, exactly in the (h, R_rej) cells
   {(3,1),(3,1.1),(3,1.2),(3,1.3),(3,1.5),(3.5,1),(3.5,1.1),(3.5,1.2),(3.5,1.3),(4,1),(4,1.1),(4.5,1)},
   and every point in a flipped cell is flipped (class is cell-constant because k_s, k_f, r_c, delta cancel).
P2 No tie occurs at any finite-R_rej grid point (ties are measure zero away from the blocked case).
P3 independent_layers: flipped points occur only at P = 1 W and only in cells with h <= 5 and R_rej <= 1.5.
P4 Rear blocked: every grid point is classified tie_surface (surface equal, interior ordered).
Uniform-measure flip fraction of the [3,15]x[1,10] rectangle: (kappa ln(kappa/3) - (kappa - 3))/108 ~ 0.0041
at P = 1 W with kappa = 100/21; 0 at P = 5 and 10 W.

## Deviation policy
Any CLI change of seed or sample sizes, any skipped section and any hash mismatch is listed under
"deviations" in the output. Failed checks or predictions are kept and reported; no threshold is relaxed.

## Claim boundary
Synthetic two-node steady and lumped transient models with fixed nominal properties and assumed convection.
No spatial mesh, delamination, radiation, controller, contact safety, biological viability or deployment claim.
The 40/60 C comparators are study_comparator_only. Coda's PF0 6/7 history is unchanged.

## Credits
Coda (Codex Lily) collaborating with Andrei (Richard Pemberton): exact steady reference, two-node transient
model, predeclarations and executed reports used here as read-only inputs. Earlier Claude Fable 5.1 work on
the thermal contract is referenced in the sources but not contained in them; nothing here checks or
attributes Fable's formulation. Red: coordination and execution. Claude (Anthropic): this package.
