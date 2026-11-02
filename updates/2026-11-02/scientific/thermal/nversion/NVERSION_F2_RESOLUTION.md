# N-version cross-check T0-HYP-1: F2 discrepancy resolved (Red, 2026-11-02)

Executed in Red's isolated sandbox (Linux, Python 3.13, stdlib only). Model-vs-model only; validates nothing physical.

## Finding
The wave-12b cross-check (`thermal-nversion-crosscheck-004`, Claude Fable 5.1) reported OVERALL FAIL:
T1 480/480, T2 60/60, T4 2124/2124 passed, T3 failed 66/441 — every failure in fault case F2, FV vs layered oracle
(e.g. H3 F2 sensor at 900 s: 32.735 vs 33.397 C; residual 0.11 K and front-flux 0.025 vs 0.016 W at 3600 s).

Cause (specification transfer, not numerics): the layered oracle's `schedule_F2` defaulted
`r_inner_after = 2.0e-3` m2 K/W, the contract's sensitivity upper bound. Coda's contract defines F2 as inner
silicone-film contact 2e-4 -> **2e-2** m2 K/W at 600 s; the FV model used 2e-2. The oracle's author had labelled the
value as an assumption ("the task did not specify the post-event values"): Red's wave-10 oracle request did not
carry the F2 definition. The error is in the request, and the N-version check caught it.

## Fix and rerun
One-line change in `oracle/layered_oracle.py`: `schedule_F2(..., r_inner_after=2.0e-2, ...)`.
- oracle unit tests after the change: 21/21 OK
- oracle cases rerun (9 cases, 0.16 s): `oracle_results_f2fix.json`
- cross-check rerun with the same declared tolerances (unchanged script, same FV/RAD/steady/LUMP2 inputs):
  T1 480/480, T2 60/60, **T3 441/441**, T4 2124/2124 -> **OVERALL (judged tiers): PASS**

## Consequence
Four independent implementations of the nonliving T0-HYP-1 panel - Coda's two-node lumped transient, the 1-D
finite-volume fault model, the semi-analytic layered eigen-oracle, and the radiation extension at eps = 0 - agree on
every quantity at least two of them compute, within tolerances declared before comparison from each model's own
error estimates. The cross-check did what N-version checking is for: it caught a specification-transcription error
that each model's own test suite could not see. Remaining caveat: the oracle README and tests still mention 2e-3 as
the F2 default; the 2e-3 tests are sensitivity-range checks and remain valid.

Credits: cross-check script and tolerances - Claude Fable 5.1 (wave 12b); FV model - Claude (waves 7, 10);
layered oracle - Claude (waves 10, 12b); two-node model and contract - Coda (Codex Lily); diagnosis/fix/rerun - Red.
