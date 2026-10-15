# The Stage: living-covering and oxygen-transport research supplement

**Lilitari, 15 October 2026. Private computational work.** This supplements, and does not replace, the separately delivered First Leaf FL1-R package or the supplied v0.2/v0.3 founding documents.

Read `docs/H_S_EXPANSION.md` for the authored H/S program, `results/RESULTS.md` for the executed diagnostic, and `proposed_ct1/CT1_SPEC.md` for the next coupled experiment. `docs/SOURCES.md` records primary sources and read-depth limitations.

## What is actually executed

PX1-HS is a small deterministic mathematical diagnostic, not a blood substitute or tissue-survival result. Its S branch tests a serial-channel counterexample: stronger wall transfer can improve total oxygen uptake while worsening distal oxygen. Its H branch checks the exact Hill-equilibrium unloading optimum and finite-kinetic/inactive-carrier controls.

The final r2 run contains 54 transport parameter cases across five meshes (270 integrations), 18 equilibrium unloading cases, and nine kinetic controls. Eight acceptance checks and 12 unit tests pass. The original r1 conservation-tolerance failure, inputs and outputs remain in `history/r1`; r2 refines the mesh without relaxing the tolerance.

## Run locally

Python standard library only. Executed with CPython 3.13.5 on Linux. No GPU, network, patient data, private histories, API key, biological material or additional paid service is used.

From this package root:

```text
python src/check_package.py
python -m unittest discover -s tests -v
python src/diagnostics.py --output rerun_px1
```

Use a new output directory to keep results distinguishable. The original `results/execution/` is the returned result, not a destination for a rerun. All numerical inputs are explicit in `inputs/protocol.json`. There is no pseudorandom seed because the diagnostic contains no random sampling. The local freeze receipt is not an independently witnessed registration.

## Next-run planner, not a tissue solver

```text
python proposed_ct1/make_plan.py --output ct1_cases.jsonl
```

This creates the 486 predeclared hypothetical screening cases in CT1_SPEC. It does **not** solve them. The included `proposed_ct1/cases.jsonl` contains planned inputs, not simulated outcomes. Coda's validated PF0 solver and geometry/parameter manifest must be connected before CT1 results exist. Hypothetical capacity and viscosity combinations must not be described as actual HbV or PFC formulations.

## Interpretation, authorship and missing inputs

Coda's reported PA0, SW2, MuJoCo, PF0 and HC0 progress is attributed to Coda, not independently verified by Lilitari without the native source/output packets. PX1 is Lilitari's separate diagnostic, not a replication of PF0. No molecular structure prediction, coordinate alignment, manufactured carrier, living tissue or clinical intervention occurred here.

The referenced 57-second MP4 was not available in the mounted files or the Files video listing at inspection. Lily inspected none of its frames or audio. Coda's visual description is the only video-related report available here. The two original written documents were read in full in the accompanying First Leaf work.

The final process used about 94.3 MiB maximum resident memory and 0.78 seconds process wall time in this container; the internally timed numerical section was 0.061 seconds. Those measurements are not a benchmark of Richard Pemberton's computer. No RAM/storage upgrade is justified by this diagnostic.

The package has no public-release license declaration or publication action. Source works and optional dependencies retain their respective licenses. The manifest demonstrates byte fixity against this copy, not external authorship, timestamp, biological validity or clinical safety.
