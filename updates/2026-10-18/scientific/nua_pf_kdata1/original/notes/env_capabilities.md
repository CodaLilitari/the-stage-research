# PF-KDATA1 — Environment capabilities (recorded 2026-10-17, before any fitting)

- python 3.12.3; numpy 1.26.4; scipy 1.11.4; pandas 2.1.4; matplotlib 3.6.3
- 2 vCPUs; ~7 GB RAM total (shared VM)
- Fitting tools available: scipy.optimize.curve_fit (Levenberg-Marquardt /
  trust-region reflective), scipy.optimize.least_squares; no lmfit, no emcee
  (not installed; budget does not assume them).
- No internet-scraped data beyond public HTTP downloads; no browser automation
  needed for this task.
- Budgets (per packet): <=20 min computation/review; <=30 fit/validation
  calls total including failed fits/retries. A call = one optimizer run
  (curve_fit / least_squares invocation) or one validation recomputation.
  Ledger: notes/fit_ledger.json (frozen before fitting; appended per call).
- Missing-dependency policy: if a needed package cannot be installed from the
  public index, stop and report exact version/platform requirements (none
  anticipated: numpy/scipy/pandas/matplotlib suffice).
