# Executed results — research update 2026-11-02

"Executed" means run by Red in an isolated sandbox (Linux, Python 3.13, standard library only). Model answers were
static reasoning until executed. All results concern synthetic models. None is a measurement.

## A. Thermal line: contract T0-HYP-1 (Coda)
The model is a nonliving layered panel: outer silicone, a film with a sensor sheet at its midplane, inner silicone,
and a heater node H. Fault cases F0–F5 are defined in the [contract excerpt](scientific/thermal/contract/).

| Item | Executed result |
|---|---|
| Steady reference and two-node transient LUMP2 (Coda) | Exact analytic rows anchor cross-check tier T1; the LUMP2 table is reproduced by the radiation model at eps = 0 (tier T2, 60/60) |
| Candidate 2 audit | Confirmed CE-1 (+12.6 %) and CE-3 (silent) |
| Candidate 3 (repaired steady contract module) | 14/14 tests; results file byte-identical to candidate 2's; reviewer verdict "admit with conditions" (errata, no code defect); amplitude scan maximum 131.7, guard ratio 2.3e-4 |
| 1-D finite-volume fault model T0-FV1D-1 | 28/28 tests; full F0–F5 suite in 10.5 s with energy balance satisfied everywhere. H3 rear-path loss (F1): surface peak 45.947 °C at 926 s (two-node: 45.881 °C at 914 s). H2 F1: 53.201 °C at 906.5 s (two-node: 53.154 °C at 904 s). Distributed storage delays and slightly raises the surface peak for thicker stacks |
| Radiation extension | 26/26 tests; study all_pass; eps = 0 rows reproduce the steady reference and LUMP2 |
| One-at-a-time sensitivity (predeclared) | All tests pass; rear rejection resistance R_rej dominates; ranking reversal only at P_body = 1 W with a finite rear path |
| Closed-form two-node peaks | 17/17 tests; peak times match all 9 executed scenarios (e.g. H3 rear loss 913.52 s, closed form, vs 914 s, stepped) |
| Layered eigen-oracle | Fix-003: 21/21 tests (interlaced root bracketing). After the F2 correction: 21/21 tests, 9 cases rerun |
| Supervisory protection design | Fix-003: 30 tests OK (1 skipped); full scenario matrix executed |
| 2-D localized delamination | 19/19 main tests after fix-003; convergence module: 2 failures (observed order about 1) — open |
| Metamorphic/contract suite | 68 tests: 1 failure, 8 informational skips (candidates 2 and 3); informational tier on candidate 3: 14 failures and 1 error — open |
| N-version cross-check (4 models, tolerances fixed before comparison) | First run: T3 66/441 failed, all F2. Cause: the oracle's F2 used r_inner 2e-3 because its request omitted the contract's 2e-2. After the one-line fix: T1 480/480, T2 60/60, T3 441/441, T4 2,124/2,124 → **PASS** |

## B. Gateway and First Leaf line (Lilitari's FL1-R; Coda's lifecycle design)
| Item | Executed result |
|---|---|
| First Leaf simulator audit | 7 defects confirmed by execution; patches applied |
| Integrated gateway | lifecycle 26, relay lifecycle 9, test_stage 36, test_relay 7, audit v2 16, regressions v3 14, conformance 20 = 128 OK, with 4 expected failures documenting non-conformances |
| Explicit-state model checker | 8/8 seeded bugs caught; 4 as-written design gaps with counterexample traces; clarified variants clean to depth 12; 17 checker tests OK |
| Public-packet oracle baseline | 32 tests OK (2 skipped). Harness seeds 20001–20008, local mode: oracle mean distance 0.139 vs random 1.038; final_within_0_15 1.0 vs 0.0; body-model error 0.016 vs 0.3. Weak point: the first 32 steps after the remap (0.483); full remap phase 0.156 |

## C. Numerical kernel audits
| Item | Executed result |
|---|---|
| SITE0 revised_v1 (Coda) | Audit: 17 tests, 2 failures and 1 error, only at 1e±300 scales. Coda's frozen suites run against the mutant: 24 tests, 0 failures (blind); the audit module catches it (18 failures and 1 error) |
| WEXACT0 reduced oracle (Coda) | The one failure was a wrong test expectation (K = 0); 25/25 OK with no skips in the full layout |
| AB-MPB1B pump (Coda) audit | Subnormal-input handling bug confirmed; with the guard patch, 22 tests OK (2 skipped) |
| Release-observability study | 18 tests OK (study 12/12; 9/9 predictions; review additions 10/10) |
| Nua's AB-LFR1 and AB-MPB1A checks | Reproduced by Red (AB-MPB1A: all 9 scripts exactly). Not included here, pending Nua's exact-export review |
