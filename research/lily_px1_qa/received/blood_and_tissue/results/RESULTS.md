# PX1-HS: executed mathematical diagnostic

Author/executor: Lilitari. Protocol STAGE-PX1-HS-20261015-r2. Private, deterministic, standard-library computation. Not a replication of Coda's unavailable PF0 code and not biological or clinical evidence.

## Question S: is distal oxygen necessarily monotone in wall transfer?

Let x run from inlet 0 to outlet 1. A local linear tissue sink and wall exchange give tissue concentration c_t = f c_b, where f = g/(g+k), g is wall conductance and k is the local sink coefficient. With fixed flow and geometry, the reduced axial balance is:

    dc_b/dx = -Da f c_b, c_b(0) = 1
    c_b(1) = exp(-Da f)
    c_t(1) = f exp(-Da f)
    extraction = 1 - exp(-Da f)

Thus:

    d c_t(1)/df = exp(-Da f) (1 - Da f)

When Da > 1, the distal concentration peaks at f = 1/Da and subsequently decreases. Integrated extraction still increases. This is a physically interpretable reduced counterexample to *unconditional distal-oxygen* monotonicity, not a complete tissue diffusion model.

| Da | Wall fraction f | Channel outlet | Distal tissue | Total extraction fraction |
|---:|---:|---:|---:|---:|
| 4 | 0.25 | 0.3678794412 | 0.0919698603 | 0.6321205588 |
| 4 | 0.90 | 0.0273237224 | 0.0245913502 | 0.9726762776 |

The negative control f=0 has no wall transfer or uptake. The clamped-supply ablation holds channel concentration at one, giving c_t=f, which is monotone. These distinguish a numerical defect from a legitimate supply-coupling effect.

Across 54 parameter cases and meshes N=32,64,128,256,512, final-mesh maximum RK4 error against the exact concentration solution was 2.3603168031e-12. Independent Simpson integration of the reaction sink gave maximum inventory-balance error 8.3406359597e-10. Both are below the unchanged 1e-8 limits. Reaction integrals were not defined merely as inlet minus outlet.

## Question H: equilibrium unloading and incomplete release

For the same Hill exponent n at both pressures and fixed functional capacity:

    Y(P) = P^n / (P^n + P50^n)
    delta_Y = Y(P_load) - Y(P_unload)
    argmax_P50 delta_Y = sqrt(P_load * P_unload)

Writing A=P_load^n, B=P_unload^n, z=P50^n gives delta_Y = (A-B)z/[(A+z)(B+z)]. Its derivative has the sign of AB-z^2, establishing the optimum. This does not account for Bohr effects, changing cooperativity, transit-time kinetics, red-cell physiology or toxicity. It is a mathematical positive control, not a recommended human oxygen affinity.

Eighteen explicit pressure/exponent cases were screened over 2,001 log-spaced P50 values. The largest relative difference between the grid optimum and exact optimum was 0.0010920766, below the declared 0.003 bound.

A separate first-order release-to-fixed-environment control multiplies equilibrium availability by (1-inactive_fraction)*(1-exp(-contact_time/tau)). All nine synthetic controls remained within their equilibrium upper bounds. These fractions and time constants were not fitted to HbV or any clinical carrier.

## Failures retained

R1: the independent conservation check reached 1.3450104919e-8 at N256, narrowly exceeding 1e-8. Seven of eight run checks and 11 of 12 unit tests passed. This failure was retained.

R2: N512 was added; the same 1e-8 threshold was retained. Eight of eight run checks and 12 of 12 unit tests pass. Algebra and scientific interpretation were not altered to make the check pass. This was numerical verification, not tuning on biological outcome data.

## Resource measurements

CPython 3.13.5, Linux x86-64. Internally measured numerical wall time: 0.061094512 seconds. Whole-process wall time recorded by /usr/bin/time: 0.78 seconds. Maximum resident set: 96,524 KiB, approximately 94.3 MiB. No GPU or external dependencies. Run-to-run timing is not expected to be byte-identical.

## Decision changed

Do not “fix” PF0 until every increase in permeability improves its downstream minimum. Instead, split tests into fixed-local-supply monotonicity and globally coupled finite-flow behavior. Check flux orientation, positivity, nonlinear convergence, axial/radial refinement and global minimum location in the actual solver. If those checks pass and the reversal persists, upstream extraction is a candidate mechanism to quantify.

Keep H unloading/stability and S pressure-limited supply coupled in the next model. A capacity multiplier by itself cannot choose a material class. There is no clinical, skin-survival, molecular-design or embodied-subject finding in PX1.
