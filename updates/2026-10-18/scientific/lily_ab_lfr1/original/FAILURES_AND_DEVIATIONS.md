# Failures, negative controls and numerical warnings

## Retained failed frozen expectation: first explicit-Euler step

The original frozen check list says to use **one** explicit-Euler step on C13 as a negative control. The intended expectation was a negative state. It fails: with equilibrated inlet `(c,b)=(1,4)`, `alpha=1`, `k=1e12`, `gamma=4`, and step `1/16`, the first result is `(0.9375,4)`, both nonnegative.

The explanation is algebraic, not an uncertain numerical diagnosis: the initial exchange `k*(gamma*c-b)` is exactly zero. The first step changes free content but not bound content. Only then is the stiff disequilibrium available to destabilize the next explicit step.

A **post-hoc second-step extension** gives approximately `(1.56250000008789e10, -1.5624999996e10)` and correctly detects loss of positivity. This extension does not repair the failed one-step expectation or change the frozen list.

## Implementation audit and retained run history

Attempts 001 and 002 recorded the two-step detection under a generic negative-control label and reported 1612/1612 assertions passed. Review identified that this did not test the precise one-step wording in the freeze. Their files and source copies are retained; those all-pass totals are **not** presented as complete satisfaction of every frozen expectation.

Attempt 003 restores the one-step check, records its failure and labels the second-step extension post-hoc. It records **1612 passed / 1613 checks, one failure**. All correct-model reference, positivity, inventory, limit, semigroup and selected convergence checks pass. Its exit code is deliberately 1 because the failed expectation is not waived. No case, tolerance or original result file was overwritten.

## Post-first-run numerical flux audit

A stiff direct evaluation of `k*(b-gamma*c)` can amplify binary64 cancellation. At C13, t=0.001 s, the accurate reference release is `0.7998400159988375 mol/m3/s`; direct subtraction of the computed binary64 states gives `0.7989164885202626`. The absolute error is `9.23527478574826e-4`. The states themselves agree to near machine precision.

The new equilibrated-inlet identity `release=alpha*gamma*c0*E12(t)` returns `0.7998400159988376`. All 198 supplementary flux comparisons pass the same absolute/relative coefficient tolerances. This audit was added after the first run, is marked supplementary, and reuses exactly the frozen cases. Do not treat accurate states as a guarantee of accurate naively subtracted stiff reaction rates.

Backward Euler separately records its analogous direct-rate subtraction discrepancy. Its conservative eliminated transfer formula, segment inventories and convergence pass; the direct-subtraction diagnostic is retained rather than silently set to zero.

## Deliberately incorrect model controls

Driving the sink with total `c+b` in C04 produces free concentration `-2.1606027941427883` instead of `0.36787944117144233` at t=1. Substituting algebraic equilibrium for k=0 also produces a large discrepancy. Both errors are detected as intended. They are intentional wrong-model controls, not failures of the derived finite-release model.

## Representation and limits

For C05, the exact positive free solution at the final time is below the binary64 range and rounds to zero. No clipping is performed. C21 checks relative accuracy on a small but representable positive terminal value. The small suite does not establish universal correctness over arbitrary floating-point inputs, radial tissue geometry, nonlinear kinetics or physiological parameter regimes.
