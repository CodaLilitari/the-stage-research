AB-LA1: separately labeled linear adapter for AB-CT0

Read PROTOCOL.txt first. The source model, original nonlinear cases and Lily's
received reference remain unchanged. No execution is authorized by this README.
The complete 51-attempt matrix and tolerances are in cases.json/tolerances.json.
freeze.json binds source, copied inputs, protocol and code before any solve.

Preparation command (does not call any model function; refuses existing freeze):
  .venv-stage/Scripts/python.exe -B research/resumption_2026-10-18/linear_adapter/prepare_freeze.py

After independent root admission of the exact freeze and exclusive compute slot:
  .venv-stage/Scripts/python.exe -B research/resumption_2026-10-18/linear_adapter/run_bounded.py --execute-reviewed

The default admission.json is false. Root supplies the accepted freeze hash and
a currently valid <=300-second window. Existing output or execution receipt
prevents another invocation. Failures are retained; no automatic retry or changed
tolerance is allowed. No new installation/network/GPU is needed.

Expected outputs: execution_receipt.json, stdout/stderr, run/ledger.json,
individual result and assessment JSONs, convergence.json and summary.json.
Function-code tracing proves calls into unchanged solve/content/hydraulics and,
in the separately labeled radial block, actual slab(). The imposed block's
synthetic c-array is only an API placeholder; NEVER plot it as a tissue field.

Current state is recorded in freeze/admission and, only after execution, actual
receipts. Do not infer completion from the presence of runnable code.
