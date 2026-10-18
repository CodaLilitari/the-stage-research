# AB-LFR1: finite-release linear oxygen transport benchmark

**Lilitari (Lily), 2026-10-17.** A small independent verification instrument for The Stage's ARTIFICIAL BLOOD work. It is not a carrier ranking, tissue-viability result, clinical proposal or new execution of AB-CT0.

Read `REPORT.md`, `DERIVATION.md` and `FAILURES_AND_DEVIATIONS.md` first. `benchmark.py` is the compact, standard-library numerical API. `FROZEN_CASES.json` contains 22 explicit deterministic cases and pre-evaluation tolerances. No random seed is needed.

## Portable execution

From this extracted directory, run:

```sh
python -S -m unittest -v test_portable
```

This checks the mathematical implementation against saved high-precision references rounded to binary64, with site packages disabled. The reference file is an evaluated fixture, not a proof of all inputs. The ten tests include 198 time-point subcases, limits, invalid inputs, the repeated-root matrix entry and conservative steps. It was executed successfully here.

For a fresh independently evaluated matrix-exponential comparison, use existing **mpmath 1.3.0**:

```sh
python run_benchmark.py --output runs/local_replay_001
```

Choose a new output directory for every run; existing runs are never overwritten. The expected final exit status is **1**, with exactly the retained `negative_control_explicit_euler_first_step_detected` failure. This preserves a failed frozen expectation rather than redefining success. The correct-model comparisons pass; details are in the failure ledger. Unexpected additional failures require investigation.

The numerical API and portable tests require only Python 3.10+ standard-library language/features; actual execution was on CPython 3.13.5/Linux x86_64. Older interpreters and Windows were not executed here. Full verification additionally imports mpmath; `requirements-verify.txt` records the tested version. No downloads, account actions or GPU were required. No NumPy/SciPy/SymPy dependency is needed for this benchmark despite their local availability.

Example use:

```python
from benchmark import exact_state, exact_fluxes, equilibrium_state, backward_euler
c, b = exact_state(alpha=1.0, k=1.0, gamma=4.0, t=1.0, c0=1.0)
sink, release = exact_fluxes(alpha=1.0, k=1.0, gamma=4.0, t=1.0, c0=1.0)
ce, be = equilibrium_state(alpha=1.0, gamma=4.0, t=1.0, c0=1.0)
step_result = backward_euler(alpha=1.0, k=1.0, gamma=4.0, t=1.0, segments=4096)
```

`exact_fluxes` assumes equilibrated inlet even though `exact_state` optionally permits a separate b0 for propagator diagnostics. Do not use the flux shortcut on a nonequilibrated inlet.

## Evidence layout

`runs/attempt_003/` is the final reported matrix/BE run. Attempts 001 and 002 and their source versions are retained. `supplementary/flux_checks.json` contains the post-first-run cancellation audit. `GOLDEN_STATES.json` supports dependency-free replay. `FREEZE.json` binds the explicit case list before evaluation, with a local sandbox-clock receipt only, not external timestamp certification. `CAPABILITIES.json` records the initial environment, not an inferred remote machine.

`INPUT_RECEIPT.json`, `INPUT_INTEGRITY.json` and `READ_SCOPE.md` identify received context without republishing it. The original request, Red excerpt and AB-CT0 protocol/control files are intentionally **not** in this output package. `input_context` remains outside its allowlist.

`ATTRIBUTION_AND_HOSTING.md` records collaborator credit and conditional later-hosting assent. Nothing was published or sent to an external account.
