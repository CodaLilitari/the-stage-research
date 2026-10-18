# AB-LFR1: completed finite-release benchmark

**Lilitari (Lily), 17 October 2026.** This is an independent, deliberately linear numerical verification instrument. It does not execute AB-CT0's 54-case matrix, reproduce Red's PF0/AL1 runs, rank actual carriers, demonstrate tissue viability or supply a clinical protocol.

## Observed environment and freeze

Before evaluation, the sandbox recorded CPython 3.13.5, Linux 6.18.55, x86_64, 64-bit. NumPy 2.3.5, SciPy 1.17.0, mpmath 1.3.0 and SymPy 1.14.0 imported successfully. Only the standard library and mpmath were used for the benchmark. No installation, download, external-account action or GPU was required.

The 22 explicit cases and tolerances were frozen at **2026-10-17T22:48:03.053746Z**, before model evaluation. They contain no randomness. The case SHA-256 is:

`026f087fe1c95bc82f941ec122e050e32c742a436628b06eda4ef837173aadea`

The freeze is a local-clock receipt, not independently notarized preregistration. Cases include zero rates/capacity/inlet, inaccessible k=0 inventory, weak and strong finite rates, k=1e12, exact repeated eigenvalues, gamma=1e-24 near degeneracy, large capacity, short/long transit and one dimensional one-wall fixture. No frozen input or tolerance changed.

## Derived model

With effective wall/tissue flux `J=G*c`, exchanging perimeter `p`, area `A`, flow `Q>0`, and transit coordinate `t=A*x/Q`, define `alpha=p*G/A` [s^-1]. Then

```
c' = -(alpha+k*gamma)*c + k*b
b' = k*gamma*c - k*b
c(0)=c0; b(0)=gamma*c0
```

The solution is `exp(M*t)*(c0,gamma*c0)`. `benchmark.py` evaluates stable real eigenmodes with an exact Jordan limit. The independent evaluator uses mpmath's high-precision 4x4 matrix exponential with extra rows integrating sink and net release directly. See `DERIVATION.md` for the complete formulas, dimensionless conversion, singular equilibrium limit and positive conservative discretization.

## Actual final results

The final run is `runs/attempt_003`. It completed **22 cases, 198 time-point comparisons and 176 backward-Euler mesh runs**. Meshes have 32 through 4096 segments, doubling each time. These counts are deterministic numerical checks, not independent biological observations.

- Final runner: **1612 passed / 1613 checks; one retained failed negative-control expectation**. All correct-model analytic/reference, positivity, inventory, limiting, semigroup and selected convergence assertions passed.
- Maximum absolute free-state discrepancy from the high-precision reference: **2.220446049250313e-16 mol/m3**.
- Maximum absolute bound-state discrepancy: **1.1641532182693481e-10 mol/m3**, at the very large hypothetical inventory scale; the mixed component tolerance ratio stayed below **8.5164e-5** (pass requires <=1).
- Maximum propagator-entry tolerance ratio: **8.6992e-5**.
- Maximum total analytic conservation residual normalized by initial total content: **1.6653345369377348e-16**. Free and bound inventories are also checked separately.
- Maximum backward-Euler separate/global/segment normalized inventory residual: **1.8042303762122459e-13**, below its frozen **5e-10** tolerance.
- All six preselected convergence cases passed. Last observed orders range **0.999851 to 1.000641**; largest selected finest-mesh normalized state error is **4.4902591e-5**, below **5e-4**.
- All sampled states and propagator entries were nonnegative without clipping.
- Terminal reference evaluations at 90 and 120 decimal digits differed by at most **9.1109e-92** under `abs(delta)/(1+abs(reference))`. This is a numerical precision check, not a rigorous interval enclosure.
- Supplementary stable-flux audit: **198/198 passed** on unchanged frozen cases.
- Standard-library-only portable replay, actually executed with `python -S`: **10/10 tests passed**, including 198 time-point subcases.

Final runner loop wall time was **1.156 s**; whole command wall time was **1.79 s**, with maximum resident memory **101,512 KiB, about 99.1 MiB**. These are sandbox measurements, not Richard Pemberton's machine performance. Authorship, source reading and review took substantially longer than the numerical loop; START/END receipts record the bounded work interval.

## Selected one-second results

The following synthetic family has alpha=1 s^-1, gamma=4, c0=1 and b0=4 mol/m3. Uptake is the independent reference's integral of alpha*c over the transit, in mol/m3.

| k [s^-1] | free c(T) | bound b(T) | integrated uptake |
|---:|---:|---:|---:|
| 0 | 0.3678794412 | 4.0000000000 | 0.6321205588 |
| 0.01 | 0.3782812040 | 3.9855009727 | 0.6362178233 |
| 1 | 0.7194121559 | 3.4711913532 | 0.8093964909 |
| 100 | 0.8176831360 | 3.2772766223 | 0.9050402417 |
| 1000 | 0.8186259591 | 3.2751587634 | 0.9062152775 |
| 1e12, still finite | 0.8187307531 | 3.2749230123 | 0.9063462346 |
| algebraic equilibrium | 0.8187307531 | 3.2749230123 | 0.9063462346 |

The equal-looking rounded final rows are **not identical models**. Their normalized endpoint state difference is **1.04694e-13**. At k=100 and 1000, the corresponding differences from the separate algebraic limit are **1.047617e-3** and **1.047940e-4**. Weak finite k=1e-8 differs from the inaccessible-storage limit by **1.056964e-8**.

## Failure retained, not fixed by changing the target

The frozen one-step explicit-Euler negative-control expectation fails. The equilibrated inlet has exactly zero initial exchange, so the first step remains positive at `(0.9375,4)`. A post-hoc second step becomes strongly negative in the bound component. The final runner retains the original failure and labels the extension separately.

Attempts 001 and 002 originally reported 1612/1612 because their generic Euler-control check already examined two steps. Review caught that mismatch with the frozen one-step wording. Both earlier source/result sets remain, and attempt 003 restores the precise frozen check. No all-pass preregistration claim is made. `FAILURES_AND_DEVIATIONS.md` explains the accounting and the mathematical reason.

The total-content-driven-sink and k=0-replaced-by-equilibrium negative controls are both detected. These are deliberate incorrect-model implementations, not failed physics results.

## A useful stiff-flux warning

At k=1e12 and t=0.001, directly calculating `k*(b-gamma*c)` from otherwise accurate binary64 states gives **0.7989164885**, versus reference **0.7998400160 mol/m3/s**. The stable identity `alpha*gamma*c0*E12(t)` gives **0.7998400160**, agreeing within floating-point accuracy. The largest observed direct-subtraction absolute error was **9.23527e-4**.

This distinguishes state accuracy, reaction-rate evaluation and conservative inventory accuracy. It also explains why a large coefficient multiplying a small subtraction needs its own numerical audit. The supplementary correction adds a cancellation-resistant evaluator; it does not replace finite k with equilibrium.

## Dimensional fixture and intended use

For C19, A=1e-7 m2, one exchanging width p=1e-3 m, L=1e-3 m, Q=2 microlitres/min = 2e-9/60 m3/s, and **synthetic effective G=5e-5 m/s**, the conversion yields alpha=0.5 s^-1 and T=3 s. With k=2 s^-1 and gamma=4, `Da=1.5` and `kT=6`. For c0=0.2, the computed outlet is c=**0.1440258595**, b=**0.6051881665** mol/m3, with uptake **0.2507859740** mol/m3. This is a dimensional check, **not** a reproduction of AB-CT0's tissue basepoint: effective G is not silently identified with its raw wall permeability.

Use the benchmark to test a separately labeled linear verification mode of the nonlinear implementation. Compare identical segment endpoints and distinguish finite-binding approximation, axial discretization and nonlinear residual errors. The backward-Euler comparison is first-order endpoint convergence, not a global certified error bound. Do not change AB-CT0's frozen matrix to make it resemble this benchmark.

## Unknowns and exclusions

No actual carrier relaxation constant, hemoglobin affinity, protein-fold-derived off-rate, tissue demand, viable geometry or clinical performance is estimated. No radial tissue PDE, viscosity law, matched-pump matrix, recirculation reservoir or oxygenator was executed. Red's supplied report remains Red-reported; its original numerical files were not independently reproduced here. The model/surface observation is Coda-reported separately from Lilitari's credit. No new public release was made.
