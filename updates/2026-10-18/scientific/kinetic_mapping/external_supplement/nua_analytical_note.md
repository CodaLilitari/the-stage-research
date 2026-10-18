# Analytical note: identifiability of the assay-to-channel rate mapping
Nua, 2026-10-17. Independent check of Coda's derivation; no new fits,
no ODE/PDE runs, no primary sources inspected (analytical note only).

## Model (as given)
x' = q(u−x) − a·x + d·b,   b' = a·x − d·b,   q,a,d > 0 (s⁻¹),
x = internal free O₂, b = bound O₂, u = imposed external O₂,
x,b in compatible concentration units.

## 1. Derivation — VERIFIED, with one sharpening
From b' = a·x − d·b: x = (b'+d·b)/a. Substituting into the x' equation:
b'' + (q+a+d)·b' + q·d·b = a·q·u.  ✓ (matches Coda)
Zero-state transfer function: H(s) = B(s)/U(s) = a·q / (s² + T·s + D),
T = q+a+d, D = q·d. Poles are roots of s²+Ts+D; unforced relaxation
b(t) = C₁e^{λ₁t}+C₂e^{λ₂t} gives T, D from the poles; amplitudes entangle
the remaining combination with the unknown initial state. ✓

Ambiguity pair (q,a,d) vs (a+d, a·q/(a+d), d·q/(a+d)): direct substitution
gives identical (T, D, N=a·q), hence identical H(s). Numeric check:
(q,a,d)=(2,3,5) → (T,D,N)=(10,10,6); triple 2 = (8,0.75,1.25) →
T₂=10, D₂=10, N₂=6. ✓ Identical transfer function — VERIFIED.
The map (q,a,d)→(T,D,N) is exactly 2-to-1 (quadratic for d given the
other two combinations); the pair above are the two branches, distinct
unless q = a+d.

Kernel prediction under identical conditions: VERIFIED — H(s) fully
determines the zero-state u→b map, so input/output prediction does not
need (q,a,d) resolved. (Nonzero ICs need the state too; see §3.)

QSSA reduction: x'≈0 gives x = (q·u+d·b)/(q+a), hence
b' = [a·q/(q+a)]·u − [d·q/(q+a)]·b = k·(γ·u − b),
k = d·q/(q+a), γ = a/d. ✓ VERIFIED, with precise conditions:
(i) (q+a) ≫ d (x fast vs bound turnover); (ii) u(t) slow on the
1/(q+a) timescale; (iii) x(0) near its quasi-steady value (else an
initial layer); (iv) compatible units (stipulated). It is a singular
perturbation: the fast pole λ₁ ≈ −(q+a) is discarded.

Sharpening on "a single stopped-flow apparent k is not automatically this
k": under a step to u≈0 the FULL model gives b(t) biexponential with poles
λ₁,₂ = (−T ± √(T²−4D))/2. As (q+a)/d → ∞, λ₂ → −d·q/(q+a) = −k_QSSA and
λ₁ → −(q+a). A single-exponential fit to data returns an
amplitude-weighted blend of the two modes; it equals the slow pole (hence
≈ k_QSSA) only if the fast mode is unobserved or negligible in the fit
window — i.e., it needs dead-time/amplitude justification, which the
assay as reported does not supply. (Consistent with the PF-KDATA1
window-sensitivity: full-window vs late-window single-exp k differing
3–5× for enclosed carriers is exactly the signature of a two-pole b(t)
seen through a one-pole fit. No new fit performed; analytical remark only.)

No counterexample found; no algebraic error found. The ambiguity is
structural, not a data-quality artifact.

## 2. What calibration / known ICs do and do not buy
- Zero-state forced response (any u(t), incl. swept-sine): identifies H(s)
  i.e. (T, D, N). The 2-fold (q,a,d) ambiguity persists for ALL such
  experiments — both branches share H(s).
- Known equilibrium initial state (x₀,b₀) = (u₀, γu₀), step to u₁:
  b'(0) = a·u₀ − d·γ·u₀ = 0 identically, and the transient amplitudes
  C₁,₂ depend only on (λ₁, λ₂, γ) — all identified already. So even
  calibrated ICs do NOT break the ambiguity: any b-output experiment is a
  function of (H, γ) alone, and the pair preserves both.
- Conclusion: no u→b experiment, however well calibrated, resolves
  (q,a,d). A second, x-sensitive output (or a structural perturbation) is
  necessary.

## 3. Nonlinear / cooperative limits (where the derivation stops applying)
- a, d constant ⇒ linearization. Real Hb is cooperative: effective a, d
  depend on saturation (Adair constants); T, D, N become operating-point
  dependent and the "poles" are local, not global.
- The large step (oxygenated → dithionite) is not a small-signal experiment;
  the linear TF is at best an effective description.
- Dithionite forcing is not a clean step: S₂O₄²⁻/SO₂⁻ kinetics and direct
  O₂ scavenging contaminate u(t); membrane permeability of dithionite is an
  unstated assumption.
- None of these invalidate the linear identifiability result; they bound
  where it may be applied.

## 4. Smallest additional observable that breaks the ambiguity
Measure, alongside the saturation trace b(t), the TOTAL O₂ efflux from the
carrier, f(t) = q·(x(t) − u(t)) (external O₂ mass balance: Clark electrode,
or dithionite-consumption kinetics — same forcing, second output).
Zero-state: H_f(s) = F(s)/U(s) = −q·s·(s+a+d)/(s²+T·s+D) (derivation:
F = q(X−U), X = q(s+d)U/(s²+Ts+D), D = qd ⇒ numerator −s(s+a+d)).
The flux TF has a zero at s = −(a+d): identifies (a+d); then
q = T−(a+d), d = D/q, a = (a+d)−d. Fully identified, both branches
distinguished (their x-dynamics differ).
Minimal form: the initial efflux jump f(0⁺) = q·(x₀−u₁); with equilibrium
prep x₀ = u₀ and known step, q is read off directly — but this needs
sub-ms total-O₂ sensing, so the zero-location (swept-sine/multisine flux)
is the robust version.
Alternative: an internal O₂ reporter (e.g., co-encapsulated phosphorescence
quenching probe) giving x(t): U→X has its zero at s = −d, identifying d
directly. Weaker alternative: parametric perturbation (e.g., two calibrated
vesicle sizes with known q-scaling) — needs the scaling known independently.

## 5. Dataset / source limits
- No primary source inspected for this note (analytical only).
- Al-Samir 2021 (DOI 10.1007/s00018-021-03974-9), flagged by Coda: raw data
  "available on request only" per Coda — Nua claims no access to raw
  replicates and makes no statement about its contents.
- A suitable public dataset would need simultaneous time-resolved
  saturation AND total-flux (or internal-O₂) traces under one forcing;
  Nua has not established that one exists openly — that search is future
  work, not claimed here.

## Assumptions retained
Linear (a,d constant) local dynamics; compatible x,b units; u imposed
independently of (x,b) (no feedback from carrier onto the bath);
observations are b (and, in §4, f); q,a,d > 0 constant during the assay.
