# Reproducing — research update 2026-11-02

Requirements: Python 3.10 or later, standard library only, no network. Recorded on Python 3.13.18 on Linux.

Work in a disposable copy of this folder, because several scripts write outputs next to themselves. Then run:

    python -B verify_release.py               # read-only integrity check of this folder
    python -B tools/reproduce_check.py        # 20 checks, about 30 s
    python -B tools/reproduce_check.py --long # adds the 8-seed First Leaf harness

`tools/reproduce_check.py` is the authoritative list of commands. For each check it records the working
directory, module search path and environment variables used. It prints, next to every result, the outcome
recorded on 2 November 2026. [REPRODUCTION_RECEIPT.txt](REPRODUCTION_RECEIPT.txt) is the run of that script
against this published layout before release.

| Area | Where to start | Expected outcome |
|---|---|---|
| Finite-volume fault model | `scientific/thermal/fv1d`: `python -B -m unittest test_thermal_fv_transient` | 28 OK |
| N-version cross-check | `scientific/thermal/nversion/crosscheck/nversion_crosscheck.py`. Inputs are the published result files; see the script for the five paths | `OVERALL (judged tiers): PASS` with the F2-fixed oracle results |
| Layered oracle | `scientific/thermal/layered_oracle`: `python -B oracle/layered_oracle.py --out <file>` | 9 cases; tests 21 OK |
| Integrated gateway | `scientific/gateway/integrated` with `PYTHONPATH=src`: the seven `tests.*` modules | 128 OK, 4 expected failures |
| First Leaf harness | `scientific/gateway/oracle_baseline`: `python -B oracle/fl_harness.py --mode local --seed-first 20001 --seed-count 8 --out <file>` | public oracle 0.139 vs random 1.038 |
| SITE0 audit | `scientific/numerics/site0_audit/validation/site0/revised_v1`, with `SITE0_ORIGINAL_PATH` and `SITE0_FROZEN_TESTS_DIR` set | 2 failures and 1 error at extreme scales (open issue); frozen suites blind to the mutant |

Expected failures are listed in KNOWN_ISSUES.md. A check that differs from its recorded outcome, in either
direction, is worth reporting. Re-running the full studies (for example `rad_study.py`, the supervisor
`run_matrix.py`, or the 2-D `study.py`) regenerates the published result JSON files. Floating-point output can differ
in the last digits across platforms. The cross-check's tolerances are far wider than that.
