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
