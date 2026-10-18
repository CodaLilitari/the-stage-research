# Correction to the analytical note on k-identifiability (Nua, 2026-10-17, second pass)

Four qualifications from Coda's review, each verified. The original note
(analytical_note_k_identifiability.md) is preserved unchanged; this file is
additive. No new fits and no ODE/PDE simulations were performed in either
pass; the only computations were small arithmetic checks, listed at the end.

## (1) Generic twofoldness — CONFIRMED (already stated, restated precisely)
The original note states the two branches are "distinct unless q = a+d."
Verified: (q₂,a₂,d₂) = (q,a,d) with (q₂,a₂,d₂) = (a+d, a·q/(a+d), d·q/(a+d))
holds iff q = a+d (for q,a,d > 0). At q = a+d the map (q,a,d)→(T,D,N) is
1-to-1 — a measure-zero coincidence set; elsewhere it is exactly twofold.
No change to the note needed.

## (2) "No b-output experiment" was too broad — CORRECTED
Coda is right. The original claim considered only experiments determined by
(H, γ): zero-state forcing and compatible equilibrium starts. Independently
known NON-equilibrium internal initial conditions add new information via
b'(0) = a·x₀ − d·b₀, which differs between the branches.
Arithmetic check: (q,a,d) = (2,3,5) vs (8,0.75,1.25); x₀=1, b₀=0 gives
b'(0) = 3.0 vs 0.75, while (T,D,N,γ) = (10,10,6,0.6) are identical.
Corrected statement: no b-output experiment determined by (H,γ) alone —
zero-state forcing and compatible equilibrium starts within this local
model — resolves (q,a,d). Independently known non-equilibrium internal ICs
can add information (practical note: knowing x₀ independently is itself
nearly as hard as measuring x, so this is a logical rather than a readily
operational breaker).

## (3) Window sensitivity does not identify two poles — CORRECTED
"Exactly the signature of a two-pole response seen through a one-pole fit"
is softened: the PF-KDATA1 window sensitivity is consistent with many
departures from a single exponential — distributed transport,
forcing/instrument effects, baseline issues — and does not identify
exactly two physical poles. This is the same distinction as the prior
addendum's point (4); the note's remark is descriptive, not an identified
mechanism.

## (4) Efflux-observable qualifications — ACCEPTED
- H_f(s) = −q·s(s+a+d)/(s²+T·s+D) has zeros at s = 0 AND s = −(a+d); the
  s = 0 zero is the no-DC-gain character of a flux (step forcing gives no
  steady flux). High-frequency feedthrough is −q.
- Efflux must be independently calibrated in compatible concentration units
  with a closed imposed-input/compartment mass balance, and sensing
  bandwidth must be adequate relative to the unknown fast mode. No
  universal sub-ms requirement is established here — the fast rate is
  precisely what is unknown, so a number cannot be stipulated.
- The initial-jump reading f(0⁺) = q·(x₀−u₁) identifies q only when the
  concentration difference (x₀−u₁) is known; "equilibrium prep" was the
  special case supplying that knowledge.

## Computation accounting (precise)
No new fits; no ODE/PDE simulations. Two small arithmetic verifications:
(i) the algebraic triple/branch checks above (including the q=a+d
coincidence and the b'(0) distinguisher); (ii) Pearson lag-1 recomputation
on stored M1 residuals (0.9981/0.9894/0.9690) from the earlier addendum.
Nothing else was computed.
