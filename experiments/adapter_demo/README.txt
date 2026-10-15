CONTINUOUS MUJOCO JSON-LINES ADAPTER DEMONSTRATION

Engineering adapter, not an AI or embodiment experiment. No language model,
network, private archive, physical actuator, renderer, or biological material.

Run using the already installed project environment:
  .venv-stage\Scripts\python.exe experiments\adapter_demo\adapter.py demo
  .venv-stage\Scripts\python.exe experiments\adapter_demo\adapter.py serve

Run the commands from <PROJECT_ROOT>.
The demonstration writes only inside experiments\adapter_demo. It uses the
existing MuJoCo and NumPy installation, and changes no settings or other runs.

serve prints one initial observation JSON object, then reads one command JSON
object per stdin line and emits one receipt per stdout line. It creates no
files. The visible observation is position, velocity, logical_timestamp, and
observation_id. Model mass, motor gear, timestep and integrator are evaluator
configuration; --mass and --gear are evaluator launch options, not controller
commands. The controller has no checkpoint, filesystem, model, network, or
evaluator tools. This is a narrow API, not an adversarial operating-system sandbox.

Example first request:
{"command_id":"one","observation_id":"obs-0","motor":0.6,"deadline":1.0}

Use the newly returned observation ID for the next request. Each accepted motor
command advances the SAME body by 50 MuJoCo steps of 0.002 seconds. Position and
velocity persist; the body is not reset between pulses. Motor inputs must be
finite numbers in [-1,1]. deadline is a dispatch deadline in simulation seconds,
not a wall-clock deadline or a promise that the command finishes by that time.

Stop request replaces motor with stop:true:
{"command_id":"stop-one","observation_id":"obs-1","stop":true,"deadline":1.0}

Stop zeroes motor control and latches against future dispatch without advancing
simulation time. It does not instantly zero velocity or model a physical brake.
No async commands are queued, and no automatic re-arm is exposed.

Receipts separate requested, admitted, executed, before, and observed. Malformed,
duplicate, stale and expired requests leave state unchanged. Invalid JSON is
rejected without execution. No observation provides hidden evaluator config.

The demo executes 20 continuous commands; saves a LOCAL trusted checkpoint after
command 7; restores it to a new adapter; and compares all 13 resumed receipts and
the full final checkpoint with an uninterrupted rollout. Checkpoints include
MuJoCo integration state, model configuration/version, command IDs, observation
sequence, and stop latch. Checkpoint/restore is evaluator code, not a controller
command. Portability across MuJoCo versions is explicitly rejected.

A separate mass=2 rollout under identical inputs demonstrates evaluator-side
dynamics perturbation. It is a separate comparison body, not a claim of adaptive
control. The faults include an attempted filesystem-shaped command, nonfinite
and out-of-bound motor values, malformed ID, deadline, stale observation,
duplicate restored ID, and restoring an already-stopped adapter.

Actual artifacts: results.json, trace.jsonl, checkpoint.json, manifest-sha256.txt.
All equality and fault outcomes are in results.json. The test validates this
finite synchronous scalar adapter; it certifies neither physical safety nor
general malicious-input robustness, operating-system isolation, or AI agency.
