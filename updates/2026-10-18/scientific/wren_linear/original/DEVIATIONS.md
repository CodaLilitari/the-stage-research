# Deviations from FROZEN_PLAN.md (sha256 1267daf2...83f6)
Wren (AI collaborator, via Grok Bot)

1. Run 1 (~19:12 EDT): bench.py crashed at the first algebraic log line (`log()` was defined with an unused
   `call` parameter, so `log("D","algebraic","ok")` raised TypeError). The 12 ODE calls before it (6 exact+balance,
   6 RK4) had executed but nothing was persisted. Logged as ledger calls 1-12, FAIL-lost.
2. To stay inside the 24-call cap, run 2 was re-planned (after the freeze, recorded here, not in the plan):
   6 exact+balance, RK4 for F2 only, D, E, F6 diagnostic, 2 hydraulics = 12 calls; k* bisection dropped.
   The run-1 source was edited in place; its exact bytes were not preserved (only the bug above differed,
   plus these scope edits).
3. Run 2 (~19:13 EDT): all 12 calls executed, then json.dump crashed on a numpy.bool_ (the Gauss-Legendre
   integral returns numpy float64, so balance_ok was numpy bool). Only the first part of results.json was flushed
   (kept as results_PARTIAL_run2_truncated.json). ledger.csv and ENV.txt were not written by code; both were
   reconstructed by hand from the plan, the traceback and the truncated file.
4. Cap reached (24/24). No third run. bench.py now carries float()/bool() casts and is FIXED BUT UNEXECUTED;
   bench_run2_as_executed.py is the exact code of run 2.
5. Hydraulic binding caps, delivered pressure/power and F1 c(T) are hand arithmetic from captured values,
   labelled as such, not ledger calls.
A clean completion needs a new frozen plan and ledger authorized by Coda.
