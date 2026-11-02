# 2D-PATCH-EXT-1 — fix-003 addendum (to be read with NOTES.md §4 and §6)

Written by Claude (via Red) after Red's execution of the wave-10 packet
(receipts ab66db0b…, afe808b6…, f00ce120…). Model only; nothing here was
executed by the author.

## 8. Mesh-refinement test: what the 0.27 meant and the corrected criterion

- The wave-10 sequence (H1, w = 5 mm, dy = 5/2.5/1.25 mm) had dy/ell_U =
  7.3, 3.7, 1.8 (ell_U = 0.682 mm, modal). T_H depends on the lateral exchange
  across the patch edges, captured only to a fraction f(dy) = (ell_U+ell_F)/
  [dy(1 + sum lambda/(1-lambda))], lambda + 1/lambda = 2 + (dy/ell)^2:
  f = 0.41, 0.66, 0.86. Predicted apparent order 0.31; executed 0.27. Implied
  total lateral effect on T_H ≈ 2.8 mK; resolved T_H ≈ 33.8419 °C (finest
  wave-10 level ≈ 0.4 mK high). Not round-off (differences ~1e5 x the solver
  noise), not a coupling defect (1-D limits exact to 1e-9 on every mesh).
- T_mid_centre's apparent 2.56 is a mesh coincidence: at r = 1 the two centre
  cells are the patch-edge cells (dy = w); the edge imprint falls ~1 → 0.24 →
  0.10 (continuum 0.045), giving an apparent ≈ 2.4 and ≈ 1.7 mK residual error.
- Corrected criterion (hotspot2d/convergence.py, tests/test_convergence_fix003.py):
  precondition max dy <= ell_U/2 within 4 ell_U of the edges at the coarsest
  level (else the sequence is rejected, not scored); noise floor 1e-9 K; finest
  pair change <= 1 mK (hard) and <= 0.10 K (study criterion, kept); order >= 1.0
  (predeclared, unchanged); order >= 1.5 reported as a separate tightened test;
  a deliberately defective sequence (fault boundary one cell off the faces,
  first order) must fail the tightened floor.
- Effect on the executed study: none of its conclusions depend on the artefact;
  steady-mesh errors are ~0.1 mK (T_H) and ~1 mK (centre) by the same model.

## 9. HYP6 (blocked rear) — expectation corrected by the executed results

NOTES §6 expected the patch to barely change the front exit because 1/h >>
r_fault. That is true per unit area (the patch cuts the local front flux by
~13 %), but with the rear blocked the deficit over area fraction f must leave
through the unfaulted area: q_u/q_uniform = 1/[(1-f) + f R_u/R_f]. Predicted
surface excess (P/hA)(q_u/q_uniform - 1): H1 f = 0.1 → +0.86 K (criterion 0.5
K: fails, as executed), H3 f = 0.4 → +3.3 K (executed +2.98 K surface, +3.16 K
film; lateral spreading trims the peak). Uniform F2 bounds T_H (HYP1 passed
in all 35 cases) but not the local film/surface maxima, which occur beside
the patch over the unfaulted area. Section 6's "strongest justified claim"
must be narrowed accordingly (see the fix-003 answer, section 3).
