MP0: a first physical-simulation instrument for The Stage

Coda with Richard Pemberton, 15 October 2026. This is an executed engineering baseline.
It is not a language-model experiment, robotic deployment, or identity test.

The isolated project Python environment contains MuJoCo 3.16.0, Gymnasium 1.4.0
and dependencies downloaded from PyPI through its official package index.
MuJoCo is a free open-source physics engine; its official Python documentation
recommends the PyPI mujoco package, which includes the native library.
Sources checked 15 October 2026:
https://mujoco.org/
https://mujoco.readthedocs.io/en/stable/python.html
https://gymnasium.farama.org/api/env/

Question: does fresh calibration predict velocity changes after a simulated mass
or motor-direction change better than a calibration retained from the old body?
The controller is a scalar least-squares estimator, not an LLM. A slider has one
frictionless degree of freedom. Four bounded motor pulses estimate its response.
We vary mass and motor sign across 64 fixed seeds and use 16 subsequent test
commands per seed. Calibration receives small Gaussian velocity noise; the test
target is the noiseless simulator velocity. A frozen analytic oracle checks the
simulator against delta-v = command * motor-sign * duration / mass. Zero prediction
and shuffled action/observation pairings are controls. Results are grouped by seed.

Execution from the workspace root:
  .venv-stage\Scripts\python.exe experiments\mujoco_probe\run_probe.py

The initial --freeze command saved config, code hash, versions and a local UTC
timestamp before execution. It is not independently witnessed preregistration.
Do not edit the frozen source in place to fit these results. Design a separate
version if the model, metrics or assumptions change. Reruns overwrite this simple
prototype's result files; preserve a copy before making a comparison run.

Observed result: fresh calibration had lower per-seed MSE than stale calibration
in 64/64 seeds and 1,024 probes. Read results.json for actual MSEs and limitations.
The four integrity checks passed: command bounds, deterministic reset, analytic
agreement and finite predictions. This confirms a usable local physics runtime
and a measured baseline for later experiments; it does not establish autonomous
adaptation, continuous embodiment, contact dynamics, or robustness to delay.

Independent audit recalculated all 64 per-seed scores and replayed all 1,024
targets in a fresh simulator. Saved targets matched exactly. Its report and
explicitly labeled post-run calibration reconstruction are under
experiments/independent_qa/mujoco_run_1792070771296866300/.
Two additional limits: initial receipts did not save calibration measurements
or the shuffle index; the audit reconstruction is not an original run record.
Also, random shuffling was the identity in 2/64 seeds, so that condition is a
permutation control, not guaranteed-corrupted correspondence in every seed.

Next justified implementation step: use an explicit observation/action adapter
to introduce changing body dynamics and delayed receipts without exposing truth
parameters to the tested controller. Preserve oracle access only for evaluation.
