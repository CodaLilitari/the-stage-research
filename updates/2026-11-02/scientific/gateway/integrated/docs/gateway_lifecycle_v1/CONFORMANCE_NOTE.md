# gateway-conformance-004 — model-checker traces vs. the integrated implementation

Prose CC-BY-4.0; code MIT. Claude (Anthropic), coordinated by Red for Richard (Andrei) Pemberton.
Inputs: wave-10 model checker and its sandbox receipts (Claude via Red); `interface.py` sha256
`559d4a22…`, `relay.py` sha256 `51b7a663…` (Lily original; Coda lifecycle; Claude Fable 5.1 draft;
Claude integration-003); INTEGRATION_NOTE.md; DESIGN.md (Coda). **Static reasoning only; nothing executed
by the author.** Not a safety certification, not a hardware recommendation.

## Mapping of model actions to the implementation
begin/recover = `load_state` (strict `Gateway.restore`) at the start of every `transact`;
admit…commit_ok = one `transact`; crash before replacement = `os.replace` of `private_state.json`
raises (nothing replaced; D3 removes the temp file); `commit_ambiguous(replaced=True)` = `os.replace`
succeeds then raises; export_fail = `export` raises after commit → `ExportAfterCommitError`;
compute_fail = `candidate_transition` raises → `record_failure`; tamper = edit of the test's own
`private_state.json`; hard crash with lock held = dead `writer.lock`, removed by the operator.
Simulator truth = `s['tick']`, `s['samples']`, and the executed events (one per verified transition).
Not expressible: `persist_unknown_blind`, `resolve_unknown_trusted` (the relay writes nothing after a
failed replacement and never re-reads inside a transaction), API interleaving inside a transaction.

## Findings
**C1-b (decision, no diff).** The relay's `mark_dispatched` is in-memory; the relay docstring states the
consequence (crash before replacement ⇒ no record, no action; replay is fresh). This is the checker's
C1 option (b). The model's ghost INV_NO_DOUBLE_DISPATCH does not hold and is not claimed; the declared
substitute (no record ⇒ no transition; committed dispatch never repeats) is tested. DESIGN.md should
add the one sentence; a durable mark (option a) would add a replacement per step and a restore rule.

**N-1 (minor non-conformance to C2 / view currency).** After an ambiguous replacement (file replaced,
exception observed) `transact` raises a bare `OSError` — the type INTEGRATION_NOTE reserves for
"nothing happened" — while the step IS committed, the lock is released and `packet.json` is stale.
Durable invariants hold; the next transaction re-reads the file and refreshes the view, so no false
outcome and no replay can follow. Diff D-1 implements C2's "re-read before deciding":

