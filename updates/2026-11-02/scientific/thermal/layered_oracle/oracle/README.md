# Layered semi-analytic oracle (thermal-layered-oracle-001, fix 003)

Run tests:  `cd oracle && python -B -m unittest -v test_layered_oracle`   (21 tests expected)
Run cases:  `python -B oracle/layered_oracle.py --out <path>/oracle_results.json`
            (prints to stdout if --out is omitted; no other file writes)

Time semantics: t = 0 returns the uniform initial state; an event instant (600 s, 900 s) is
evaluated as the left limit (earlier segment). Default mode count per segment: all eigenvalues
below 50 / max(min requested elapsed time, dt_floor=0.02 s); `n_modes` forces a count.

Root finding (fix 003): Dirichlet-at-H brackets are the level crossings of the EXACT lifted
Prufer phase (no modular wrap-around); one eigenvalue per bracket by sign bisection. Per-mode
diagnostics: `sturm_index_ok` (each root at its own Sturm index), `max_root_rel_error_est`
(conditioning-corrected |dlam|/lam, expect <= 1e-13), `max_energy_identity_residual_rel`
(raw |F(lam_hat)|-based residual, amplified by N_n/|psi_n(L)| ~ lam_n; informational),
`weyl_offset` with its rigorous open bracket (-3, 4). `count_zeros_argument_principle(p, b)`
gives an independent zero count below b (complex contour; used in the tests).

Scenario assumptions (labelled): F0 body 5 W until 900 s then 0, sensor 0.10 W throughout.
F1 = rear conductance change at 600 s (default G_rej -> 0, blocked), body off at 900 s.
F2 = inner silicone|film contact change at 600 s, body off at 900 s. Both are parameters of
schedule_F1/schedule_F2; the task did not specify the post-event values. [Red, 2026-11-02:
the original default r_inner -> 2.0e-3 m2 K/W (the sensitivity upper bound) was an explicitly
labelled assumption; Coda's contract defines F2 as 2e-4 -> 2e-2 m2 K/W. The default is now
2.0e-2; see ../../nversion/NVERSION_F2_RESOLUTION.md.]

Not implemented: small-time (erfc) acceleration of the series; Laplace/Talbot alternative;
radiation, in-plane spreading, capacity caps; uncertainty sweeps; sensor-off variants (set
P_sensor=0.0 in the schedule helpers to run them); comparison harness against the FV code.
