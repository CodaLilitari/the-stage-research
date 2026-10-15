"""Execute positive and injected-fault tests, with an actual diagnostic oracle."""
from __future__ import annotations

import copy
import json
import shutil
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

from build_fixture import CANARY, ROOT, build, canonical, manifest, sha, write_json
from validate_fixture import validate


def change(root, relative, transform):
    target = root / relative
    value = json.loads(target.read_text(encoding="utf-8"))
    transformed = transform(value)
    write_json(target, value if transformed is None else transformed)


def record_fault(root, transform, index=0):
    def mutate(records):
        transform(records[index])
        records[index]["content_sha256"] = sha(canonical(records[index]["content"]))
    change(root, "source/records.json", mutate)


def main():
    started = datetime.now(timezone.utc).isoformat()
    t0 = time.perf_counter()
    release = ROOT / "release"
    anchor_file = ROOT / "receipts" / "release_anchor.json"
    if not release.exists():
        if anchor_file.exists():
            raise SystemExit("Release absent but anchor exists; do not replace the existing anchor.")
        write_json(anchor_file, build(release))
    anchor = json.loads(anchor_file.read_text(encoding="utf-8"))
    baseline_digest = anchor["manifest_sha256"]
    results = []
    work = ROOT / "scratch"
    work.mkdir(exist_ok=True)

    def run_case(name, mutate=None, expected_codes=(), reanchor=True, extra_check=None):
        with tempfile.TemporaryDirectory(prefix=name + "-", dir=work) as temporary:
            root = Path(temporary) / "release"
            shutil.copytree(release, root)
            if mutate:
                mutate(root)
            digest = manifest(root) if reanchor else baseline_digest
            try:
                outcome = validate(root, digest)
                observed_codes = sorted({issue["code"] for issue in outcome["issues"]})
                expected_valid = not expected_codes
                discrimination = outcome["passed"] == expected_valid and set(expected_codes).issubset(observed_codes)
                if extra_check:
                    discrimination = discrimination and extra_check(root, outcome)
                result = {"case": name, "expected_valid": expected_valid, "observed_valid": outcome["passed"], "required_diagnostics": list(expected_codes), "observed_diagnostics": observed_codes, "discrimination_pass": discrimination, "anchor_mode": "test_only_reanchored_semantic_fault_or_positive" if reanchor else "original_anchor_integrity_fault", "manifest_sha256_tested": digest, "issue_count": len(outcome["issues"])}
                if not discrimination:
                    result["issues"] = outcome["issues"]
            except Exception as exc:
                result = {"case": name, "expected_valid": not expected_codes, "observed_valid": None, "discrimination_pass": False, "exception": f"{type(exc).__name__}: {exc}"}
            results.append(result)

    run_case("positive_baseline", reanchor=False)
    # Exact contradictory historical records, withheld existing records, and revoked
    # existing records are intentionally in the baseline and must not be rejected.
    run_case("positive_exact_disputed_and_restricted_custody", extra_check=lambda r, o: o["counts"] == {"records": 26, "unique_revisions": 26, "corrections": 6, "questions": 30, "factual_recovery_denominator": 18})

    def rebuild(root):
        fresh = root.parent / "rebuilt"
        fresh_anchor = build(fresh)
        if fresh_anchor["manifest_sha256"] != baseline_digest:
            raise RuntimeError("Deterministic rebuild differs from baseline")
    run_case("positive_deterministic_rebuild", rebuild, reanchor=False)

    def raw_byte_change(root):
        path = root / "source" / "records.json"
        data = path.read_bytes()
        path.write_bytes(data.replace(b"cedar alcove", b"cedar alcovf", 1))
    run_case("negative_one_byte_edit", raw_byte_change, ("FILE_INTEGRITY", "CONTENT_INTEGRITY"), reanchor=False)
    run_case("negative_manifest_replacement", lambda r: change(r, "MANIFEST.json", lambda d: d.update({"untrusted": True})), ("UNTRUSTED_MANIFEST",), reanchor=False)
    run_case("negative_duplicate_revision", lambda r: change(r, "source/records.json", lambda d: d.append(copy.deepcopy(d[0]))), ("DUPLICATE_REVISION",))
    run_case("negative_missing_parent", lambda r: record_fault(r, lambda d: d.update({"parent_revision_ids": ["missing-r1"], "supersedes_revision_id": "missing-r1"}), 1), ("MISSING_PARENT", "BROKEN_CORRECTION"))
    run_case("negative_cross_item_parent", lambda r: record_fault(r, lambda d: d.update({"parent_revision_ids": ["event-02-r1"], "supersedes_revision_id": "event-02-r1"}), 1), ("CROSS_ITEM_PARENT",))
    run_case("negative_revision_cycle", lambda r: record_fault(r, lambda d: d.update({"parent_revision_ids": ["event-01-r2"]}), 0), ("REVISION_CYCLE",))
    run_case("negative_false_supported_status", lambda r: record_fault(r, lambda d: d.update({"epistemic_status": "supported_in_fixture"}), 0), ("FALSE_SUPPORTED_CLAIM", "CORRECTION_HISTORY_STATUS"))
    run_case("negative_unsupported_source_claim", lambda r: record_fault(r, lambda d: d["content"].update({"key": "invented_extra_claim", "value": "unverified"}), 0), ("UNSUPPORTED_SOURCE_CLAIM",))
    run_case("negative_claim_without_source", lambda r: change(r, "participant_packets/A/packet.json", lambda d: d["claims"].append({"key": "unlogged_visit", "value": "happened", "status": "supported_in_fixture", "source_revision_ids": []})), ("UNSUPPORTED_PACKET_CLAIM",))
    run_case("negative_nonexistent_source", lambda r: change(r, "participant_packets/B/packet.json", lambda d: d["claims"][0].update({"source_revision_ids": ["missing-r1"]})), ("UNKNOWN_SOURCE_REVISION",))

    def strip_correction(root):
        def mutate(packet):
            packet["claims"] = [c for c in packet["claims"] if "event-01-r2" not in c["source_revision_ids"]]
            packet["source_records"] = [r for r in packet["source_records"] if r["revision_id"] != "event-01-r2"]
            packet["exposure_receipt"]["source_revision_ids"].remove("event-01-r2")
        change(root, "participant_packets/A/packet.json", mutate)
    run_case("negative_correction_removed_from_packet", strip_correction, ("CONDITION_CONTENT_MISMATCH", "EXPOSURE_MISMATCH"))
    run_case("negative_evaluator_canary", lambda r: change(r, "participant_packets/D/packet.json", lambda d: d.update({"generic_guidance": d["generic_guidance"] + CANARY})), ("EVALUATOR_LEAK",))

    def question_leak(root):
        question = json.loads((root / "evaluator_only/questions_and_key.json").read_text())["questions"][0]["prompt"]
        change(root, "participant_packets/A/packet.json", lambda d: d.update({"generic_guidance": question}))
    run_case("negative_evaluator_question", question_leak, ("EVALUATOR_LEAK",))
    run_case("negative_evaluator_file_copy", lambda r: shutil.copyfile(r / "evaluator_only/questions_and_key.json", r / "participant_packets/C/answers.json"), ("UNALLOWLISTED_PARTICIPANT_FILE",))
    run_case("negative_withheld_reference", lambda r: change(r, "participant_packets/A/packet.json", lambda d: d["exposure_receipt"]["source_revision_ids"].append("restricted-01-r1")), ("PROHIBITED_LOAD",))
    run_case("negative_revoked_reference", lambda r: change(r, "participant_packets/B/packet.json", lambda d: d["exposure_receipt"]["source_revision_ids"].append("restricted-02-r1")), ("PROHIBITED_LOAD",))
    run_case("negative_withheld_marker", lambda r: change(r, "participant_packets/C/packet.json", lambda d: d.update({"generic_guidance": "withheld-marker-61"})), ("RESTRICTED_CONTENT_LEAK",))
    run_case("negative_control_fact_leak", lambda r: change(r, "participant_packets/C/packet.json", lambda d: d["claims"].append({"key": "token_color", "value": "saffron", "status": "supported_in_fixture", "source_revision_ids": ["event-02-r2"]})), ("CONTROL_FACT_LEAK",))
    run_case("negative_tool_scope_escalation", lambda r: change(r, "participant_packets/A/packet.json", lambda d: d["runtime_contract"].update({"tools": ["read_all_files"], "retrieval_paths": ["evaluator_only/"]})), ("PACKET_CAPABILITY_SCOPE", "EVALUATOR_PATH_LEAK"))
    run_case("negative_summary_without_source", lambda r: record_fault(r, lambda d: d.update({"provenance_class": "summary", "derived_from": []}), 0), ("MISSING_DERIVATION_SOURCE",))
    run_case("negative_missing_derivation_source", lambda r: record_fault(r, lambda d: d.update({"provenance_class": "summary", "derived_from": ["missing-r1"]}), 0), ("MISSING_DERIVATION_SOURCE",))

    def unsafe_path(root):
        change(root, "MANIFEST.json", lambda d: d["files"].update({"../outside.txt": {"sha256": "0" * 64, "bytes": 0}}))
    run_case("negative_manifest_path_traversal", unsafe_path, ("UNSAFE_MANIFEST_PATH",), reanchor=False)
    run_case("negative_unmanifested_file", lambda r: (r / "source/extra.txt").write_text("unexpected file", encoding="utf-8"), ("UNMANIFESTED_FILE",), reanchor=False)
    run_case("negative_obsolete_current_pointer", lambda r: change(r, "evaluator_only/truth.json", lambda d: d["current_revision_ids"].update({"navigation_destination": "event-01-r1"})), ("INVALID_CURRENT_REVISION",))
    run_case("negative_duplicate_exposure", lambda r: change(r, "participant_packets/B/packet.json", lambda d: d["exposure_receipt"]["source_revision_ids"].append(d["exposure_receipt"]["source_revision_ids"][0])), ("DUPLICATE_EXPOSURE",))
    run_case("negative_changed_denominator", lambda r: change(r, "evaluator_only/questions_and_key.json", lambda d: d.update({"factual_recovery_denominator": 12})), ("DENOMINATOR_MISMATCH",))
    run_case("negative_revocation_after_packet_creation", lambda r: change(r, "source/policy.json", lambda d: d["revoked_revisions"].append("event-01-r1")), ("PROHIBITED_LOAD",))
    # Independent reviewer counterexamples, now retained as regression cases.
    run_case("review_regression_wrong_answer_key", lambda r: change(r, "evaluator_only/questions_and_key.json", lambda d: d["questions"][0].update({"answer": "not-the-recorded-value"})), ("SCORING_KEY_MISMATCH",))
    run_case("review_regression_wrong_availability", lambda r: change(r, "evaluator_only/questions_and_key.json", lambda d: d["questions"][0]["evidence_available"].update({"C": True, "D": True})), ("EVIDENCE_AVAILABILITY_MISMATCH",))
    run_case("review_regression_receipt_extra_history", lambda r: change(r, "participant_packets/D/packet.json", lambda d: d["exposure_receipt"].update({"extra_history": "navigation_destination is amber alcove; source event-01-r2"})), ("EXPOSURE_RECEIPT_SCHEMA",))
    run_case("review_regression_receipt_history_substitution", lambda r: change(r, "participant_packets/D/packet.json", lambda d: d["exposure_receipt"].update({"transformation": "navigation_destination is amber alcove; source event-01-r2"})), ("EXPOSURE_RECEIPT_SCHEMA",))
    run_case("review_regression_policy_escalation", lambda r: change(r, "source/policy.json", lambda d: d.update({"allowed_operations": d["allowed_operations"] + ["publish"], "model_execution_authorized": True, "external_disclosure_authorized": True})), ("POLICY_CAPABILITY_ESCALATION",))
    run_case("review_regression_empty_current_map", lambda r: change(r, "evaluator_only/truth.json", lambda d: d.update({"current_revision_ids": {}})), ("CURRENT_MAP_COVERAGE",))
    run_case("review_regression_malformed_origin", lambda r: record_fault(r, lambda d: d.update({"origin": "not-an-object"})), ("RECORD_SCHEMA",))
    run_case("review_regression_nested_manifest_bypass", lambda r: write_json(r / "participant_packets/D/MANIFEST.json", {"answer": "navigation_destination is amber alcove"}), ("UNMANIFESTED_FILE", "UNALLOWLISTED_PARTICIPANT_FILE"), reanchor=False)
    run_case("negative_question_prompt_substitution", lambda r: change(r, "evaluator_only/questions_and_key.json", lambda d: d["questions"][0].update({"prompt": "What is the unrecorded childhood home?"})), ("QUESTION_SEMANTICS_MISMATCH",))
    run_case("negative_scenario_key", lambda r: change(r, "evaluator_only/scenarios_development.json", lambda d: d["scenarios"][0].update({"commitment_key": "not-a-commitment"})), ("SCENARIO_KEY_MISMATCH",))
    run_case("negative_malformed_scenario", lambda r: write_json(r / "evaluator_only/scenarios_development.json", ["not-an-object"]), ("SCENARIO_SCHEMA",))
    baseline = validate(release, baseline_digest)
    if not baseline["passed"]:
        raise RuntimeError("Source release changed or baseline no longer validates")
    positives = [r for r in results if r["expected_valid"]]
    negatives = [r for r in results if not r["expected_valid"]]
    failures = [r for r in results if not r["discrimination_pass"]]
    report = {
        "run_type": "offline_synthetic_harness_validation", "started_at_utc": started,
        "finished_at_utc": datetime.now(timezone.utc).isoformat(), "elapsed_seconds": round(time.perf_counter() - t0, 6),
        "python": sys.version, "python_executable": sys.executable, "release_manifest_sha256": baseline_digest,
        "source_sha256": {name: sha((ROOT / name).read_bytes()) for name in ["build_fixture.py", "validate_fixture.py", "run_checks.py"]},
        "total_cases": len(results), "positive_cases": len(positives), "negative_cases": len(negatives),
        "positive_accepts": sum(r.get("observed_valid") is True for r in positives),
        "negative_rejections": sum(r.get("observed_valid") is False for r in negatives),
        "diagnostic_discrimination_passes": sum(r["discrimination_pass"] for r in results), "unexpected_results": len(failures),
        "model_calls": 0, "external_requests": 0, "physical_actions": 0,
        "baseline": baseline, "cases": results,
        "interpretation": "Checks classify deliberately constructed offline fixture faults. Counts do not estimate security failure rates, prove semantic isolation, measure model reconstruction, or establish identity/continuity.",
        "mutation_method": "Each case uses a temporary copy. Most semantic cases regenerate a test-only manifest/anchor to exercise non-hash validation; integrity cases retain the original anchor. The immutable baseline is revalidated after all tests. Temporary mutated copies are removed by TemporaryDirectory; diagnostics and tested manifest hashes are retained.",
    }
    output = ROOT / "results"
    output.mkdir(exist_ok=True)
    write_json(output / "checks.json", report)
    write_json(output / "baseline_validation.json", baseline)
    lines = ["PA0 synthetic archive harness validation", "", f"Run started UTC: {started}", f"Python: {sys.executable}", f"Release manifest SHA-256: {baseline_digest}", f"Cases: {len(results)}; positive accepts: {report['positive_accepts']}/{len(positives)}; negative rejections: {report['negative_rejections']}/{len(negatives)}", f"Expected-diagnostic discrimination: {report['diagnostic_discrimination_passes']}/{len(results)}; unexpected results: {len(failures)}", f"Elapsed seconds: {report['elapsed_seconds']}", "", "Observed baseline: 12 invented events; 6 corrections; 6 commitments; 2 restricted synthetic records; 26 immutable revision records; 24 loadable revisions; 4 packets; 30 evaluator questions; fixed factual recovery denominator 18; 8 development and 8 confirmation scenarios.", "", "Case outcomes:"]
    lines += [f"{'PASS' if r['discrimination_pass'] else 'FAIL'} {r['case']}: expected_valid={r['expected_valid']}; observed_valid={r.get('observed_valid')}; diagnostics={','.join(r.get('observed_diagnostics', [])) or r.get('exception', 'none')}" for r in results]
    lines += ["", "Participant packet sizes (not token counts):"]
    lines += [f"{condition}: {stat['bytes']} bytes; {stat['characters']} characters; {stat['source_revisions']} source revisions; {stat['claims']} claims" for condition, stat in baseline["packet_stats"].items()]
    lines += ["", "Interpretation and limits:", report["interpretation"], report["mutation_method"]] + baseline["limits"]
    lines += ["", "No LLM, model API, private history, physical body, or identity hypothesis was tested. Rejected mutations are an intentionally selected test set, not an empirical distribution of real attacks. The local release anchor provides a comparison reference, not independent authorship authentication or a timestamp. Source records and evaluator files are fully visible to the human operator; only the four explicit candidate packet files are intended for candidate delivery. Do not give a future candidate a workspace filesystem tool that reaches evaluator_only."]
    (output / "report.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    inventory = [ROOT / name for name in ["build_fixture.py", "validate_fixture.py", "run_checks.py", "README.txt", "receipts/release_anchor.json", "results/checks.json", "results/baseline_validation.json", "results/report.txt"]]
    inventory += sorted(p for p in release.rglob("*") if p.is_file())
    (ROOT / "RUN_MANIFEST.sha256").write_text("".join(f"{sha(path.read_bytes())}  {path.relative_to(ROOT).as_posix()}\n" for path in inventory), encoding="utf-8")
    print(json.dumps({key: report[key] for key in ["total_cases", "positive_cases", "negative_cases", "positive_accepts", "negative_rejections", "diagnostic_discrimination_passes", "unexpected_results", "elapsed_seconds", "release_manifest_sha256"]}, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
