"""Offline PA0 integrity/provenance/permission checks; no LLM inference."""
from __future__ import annotations

import argparse
import json
from pathlib import Path, PurePosixPath

from build_fixture import DISCLOSURE, GENERIC, STYLE, canonical, sha


def validate(root: Path, trusted_manifest_sha256: str):
    issues = []

    def fail(code, detail):
        issues.append({"code": code, "detail": detail})

    def read(relative):
        target = root / relative
        if target.is_symlink() or not target.resolve().is_relative_to(root.resolve()):
            fail("UNSAFE_READ_PATH", relative)
            return None
        try:
            return json.loads(target.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            fail("UNREADABLE_FILE", f"{relative}: {exc.__class__.__name__}")
            return None

    try:
        manifest_bytes = (root / "MANIFEST.json").read_bytes()
    except OSError:
        return {"passed": False, "issues": [{"code": "MISSING_MANIFEST", "detail": "MANIFEST.json"}]}
    if sha(manifest_bytes) != trusted_manifest_sha256:
        fail("UNTRUSTED_MANIFEST", "Release manifest differs from the separately supplied local anchor.")
    doc = read("MANIFEST.json")
    if not isinstance(doc, dict) or not isinstance(doc.get("files"), dict):
        return {"passed": False, "issues": issues + [{"code": "MANIFEST_SCHEMA", "detail": "files must be a mapping"}]}
    expected_paths = set(doc["files"])
    for relative, entry in doc["files"].items():
        path = PurePosixPath(relative)
        if path.is_absolute() or ".." in path.parts or "\\" in relative or ":" in relative:
            fail("UNSAFE_MANIFEST_PATH", relative)
            continue
        target = root / relative
        if target.is_symlink() or not target.resolve().is_relative_to(root.resolve()):
            fail("UNSAFE_MANIFEST_PATH", relative)
            continue
        try:
            content = target.read_bytes()
        except OSError:
            fail("MISSING_FILE", relative)
            continue
        if not isinstance(entry, dict) or sha(content) != entry.get("sha256") or len(content) != entry.get("bytes"):
            fail("FILE_INTEGRITY", relative)
    actual_paths = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file() and p != root / "MANIFEST.json"}
    for extra in sorted(actual_paths - expected_paths):
        fail("UNMANIFESTED_FILE", extra)
    records = read("source/records.json")
    policy = read("source/policy.json")
    truth_doc = read("evaluator_only/truth.json")
    key_doc = read("evaluator_only/questions_and_key.json")
    if not isinstance(records, list) or not isinstance(policy, dict) or not isinstance(truth_doc, dict) or not isinstance(key_doc, dict):
        return {"passed": False, "issues": issues + [{"code": "REQUIRED_SCHEMA", "detail": "missing source, policy or evaluator structures"}]}
    def strings(value):
        return isinstance(value, list) and all(isinstance(v, str) for v in value)

    schema_bad = False
    for index, rec in enumerate(records):
        okay = isinstance(rec, dict)
        if okay:
            okay = (isinstance(rec.get("origin"), dict) and isinstance(rec.get("content"), dict)
                and strings(rec.get("parent_revision_ids")) and strings(rec.get("derived_from"))
                and isinstance(rec.get("revision_id"), str) and isinstance(rec.get("item_id"), str)
                and isinstance(rec.get("content", {}).get("key"), str)
                and isinstance(rec.get("content", {}).get("text"), str)
                and isinstance(rec.get("content", {}).get("value"), (str, int, float, bool))
                and (rec.get("supersedes_revision_id") is None or isinstance(rec.get("supersedes_revision_id"), str)))
        if not okay:
            fail("RECORD_SCHEMA", f"record index {index}: invalid or missing nested field types")
            schema_bad = True
    if not isinstance(truth_doc.get("truth"), dict) or not isinstance(truth_doc.get("current_revision_ids"), dict) or not all(isinstance(v, str) for v in truth_doc.get("current_revision_ids", {}).values()):
        fail("TRUTH_SCHEMA", "truth and current_revision_ids must be mappings with string revision IDs")
        schema_bad = True
    if not strings(policy.get("withheld_revisions")) or not strings(policy.get("revoked_revisions")):
        fail("POLICY_SCHEMA", "restriction sets must be arrays of revision IDs")
        schema_bad = True
    if not isinstance(key_doc.get("questions"), list) or not all(isinstance(q, dict) and isinstance(q.get("id"), str) and isinstance(q.get("key"), str) and isinstance(q.get("prompt"), str) and strings(q.get("source_revision_ids")) and isinstance(q.get("evidence_available"), dict) for q in key_doc.get("questions", [])):
        fail("EVALUATOR_SCHEMA", "invalid question or answer-key field types")
        schema_bad = True
    if schema_bad:
        return {"passed": False, "issues": issues}
    if policy.get("allowed_operations") != ["offline_validate", "prepare_candidate_packet"] or policy.get("model_execution_authorized") is not False or policy.get("external_disclosure_authorized") is not False or policy.get("synthetic") is not True:
        fail("POLICY_CAPABILITY_ESCALATION", "This synthetic fixture cannot grant model execution, publication, or external disclosure.")
    truth = truth_doc.get("truth", {})
    by_revision = {}
    for rec in records:
        if not isinstance(rec, dict):
            fail("RECORD_SCHEMA", "record must be an object")
            continue
        revision = rec.get("revision_id")
        if not isinstance(revision, str):
            fail("RECORD_SCHEMA", "revision_id is required")
            continue
        if revision in by_revision:
            fail("DUPLICATE_REVISION", revision)
        by_revision[revision] = rec
        if rec.get("synthetic") is not True or rec.get("origin", {}).get("kind") != "synthetic_authoring":
            fail("SYNTHETIC_BOUNDARY", revision)
        content = rec.get("content", {})
        if sha(canonical(content)) != rec.get("content_sha256"):
            fail("CONTENT_INTEGRITY", revision)
        if rec.get("policy_id") != policy.get("policy_id"):
            fail("UNKNOWN_POLICY", revision)
        key, value = content.get("key"), content.get("value")
        status = rec.get("epistemic_status")
        if key not in truth:
            fail("UNSUPPORTED_SOURCE_CLAIM", revision)
        elif status == "supported_in_fixture" and value != truth[key]:
            fail("FALSE_SUPPORTED_CLAIM", revision)
        elif status == "contradicted_in_fixture" and value == truth[key]:
            fail("FALSE_CONTRADICTION_LABEL", revision)
        elif status not in {"supported_in_fixture", "contradicted_in_fixture", "unknown_in_fixture"}:
            fail("EPISTEMIC_SCHEMA", revision)
        if rec.get("provenance_class") not in {"exact_record", "summary", "inference", "reconstruction", "fiction", "uncertain"}:
            fail("PROVENANCE_SCHEMA", revision)
    graph = {}
    corrections = 0
    for revision, rec in by_revision.items():
        parents = rec.get("parent_revision_ids", [])
        if not isinstance(parents, list):
            fail("RECORD_SCHEMA", f"{revision}: parents")
            parents = []
        graph[revision] = parents
        for parent in parents:
            if parent not in by_revision:
                fail("MISSING_PARENT", f"{revision} -> {parent}")
            elif by_revision[parent].get("item_id") != rec.get("item_id"):
                fail("CROSS_ITEM_PARENT", f"{revision} -> {parent}")
        corrected = rec.get("supersedes_revision_id")
        if corrected:
            corrections += 1
            if corrected not in parents or corrected not in by_revision:
                fail("BROKEN_CORRECTION", revision)
            elif by_revision[corrected].get("epistemic_status") != "contradicted_in_fixture":
                fail("CORRECTION_HISTORY_STATUS", revision)
        for source in rec.get("derived_from", []):
            if source not in by_revision:
                fail("MISSING_DERIVATION_SOURCE", f"{revision} -> {source}")
        if rec.get("provenance_class") in {"summary", "reconstruction"} and not rec.get("derived_from") and not rec.get("origin", {}).get("source_unavailable"):
            fail("MISSING_DERIVATION_SOURCE", revision)
    visited, active = set(), set()

    def visit(node):
        if node in active:
            fail("REVISION_CYCLE", node)
            return
        if node in visited:
            return
        active.add(node)
        for parent in graph.get(node, []):
            if parent in graph:
                visit(parent)
        active.remove(node)
        visited.add(node)

    for node in graph:
        visit(node)
    expected_current_keys = {rec["content"]["key"] for rec in records if rec.get("load_state") == "loadable"}
    if set(truth_doc.get("current_revision_ids", {})) != expected_current_keys:
        fail("CURRENT_MAP_COVERAGE", "Current revision map must cover every loadable logical fact and commitment exactly.")
    for key, revision in truth_doc.get("current_revision_ids", {}).items():
        rec = by_revision.get(revision)
        if rec is None or rec.get("content", {}).get("key") != key or rec.get("content", {}).get("value") != truth.get(key) or rec.get("epistemic_status") != "supported_in_fixture":
            fail("INVALID_CURRENT_REVISION", key)
    prohibited = set(policy.get("withheld_revisions", [])) | set(policy.get("revoked_revisions", []))
    loadable = [r for r in records if isinstance(r, dict) and r.get("load_state") == "loadable" and r.get("revision_id") not in prohibited]
    expected_claims = [{"key": r["content"]["key"], "value": r["content"]["value"], "status": r["epistemic_status"], "source_revision_ids": [r["revision_id"]]} for r in loadable]
    expected_claim_hashes = sorted(sha(canonical(c)) for c in expected_claims)
    protected_needles = [truth_doc.get("evaluator_canary", "")]
    protected_needles += [q.get("prompt", "") for q in key_doc.get("questions", [])]
    for phase in ["development", "confirmation"]:
        scenarios = read(f"evaluator_only/scenarios_{phase}.json") or {}
        if not isinstance(scenarios, dict) or not isinstance(scenarios.get("scenarios"), list) or not all(isinstance(s, dict) and isinstance(s.get("id"), str) and isinstance(s.get("prompt"), str) for s in scenarios.get("scenarios", [])):
            fail("SCENARIO_SCHEMA", phase)
            continue
        entries = scenarios["scenarios"]
        commitment_keys = {r["content"]["key"] for r in records if r["item_id"].startswith("commitment-")}
        if len(entries) != 8 or len({s["id"] for s in entries}) != 8:
            fail("SCENARIO_COVERAGE", phase)
        for scenario in entries:
            if scenario.get("commitment_key") not in commitment_keys or not isinstance(scenario.get("rubric"), str):
                fail("SCENARIO_KEY_MISMATCH", scenario["id"])
        protected_needles += [s["prompt"] for s in entries]
    packets = {}
    packet_stats = {}
    for condition in "ABCD":
        relative = f"participant_packets/{condition}/packet.json"
        packet = read(relative)
        if not isinstance(packet, dict):
            fail("PACKET_SCHEMA", condition)
            continue
        receipt = packet.get("exposure_receipt")
        if (not isinstance(receipt, dict) or not strings(receipt.get("source_revision_ids"))
            or not isinstance(packet.get("claims"), list) or not all(isinstance(c, dict) and strings(c.get("source_revision_ids")) for c in packet.get("claims", []))
            or not isinstance(packet.get("source_records"), list) or not isinstance(packet.get("runtime_contract"), dict)):
            fail("PACKET_SCHEMA", f"{condition}: invalid nested packet structure")
            continue
        expected_receipt_fields = {"source_revision_ids", "order", "truncation", "transformation"}
        expected_transform = "exact selected records" if condition == "A" else "neutral structured claims" if condition == "B" else "style and generic guidance" if condition == "C" else "generic guidance"
        if set(receipt) != expected_receipt_fields or receipt.get("order") != "source order as encoded" or receipt.get("truncation") != "none" or receipt.get("transformation") != expected_transform:
            fail("EXPOSURE_RECEIPT_SCHEMA", f"{condition}: receipt field or content substitution")
        packets[condition] = packet
        raw = canonical(packet).decode("utf-8")
        packet_stats[condition] = {"bytes": len(canonical(packet)), "characters": len(raw), "source_revisions": len(packet.get("exposure_receipt", {}).get("source_revision_ids", [])), "claims": len(packet.get("claims", []))}
        if packet.get("condition") != condition or packet.get("synthetic") is not True or packet.get("disclosure") != DISCLOSURE:
            fail("PACKET_DISCLOSURE", condition)
        if packet.get("runtime_contract") != {"tools": [], "retrieval_paths": [], "network": "disabled", "identity_claim": "none"}:
            fail("PACKET_CAPABILITY_SCOPE", condition)
        allowed_keys = {"schema", "condition", "synthetic", "disclosure", "source_records", "claims", "style_examples", "generic_guidance", "exposure_receipt", "runtime_contract"}
        if set(packet) != allowed_keys:
            fail("PACKET_SCHEMA", f"{condition}: unexpected or missing top-level keys")
        references = packet.get("exposure_receipt", {}).get("source_revision_ids", [])
        if len(references) != len(set(references)):
            fail("DUPLICATE_EXPOSURE", condition)
        for revision in references:
            if revision not in by_revision:
                fail("UNKNOWN_SOURCE_REVISION", f"{condition}: {revision}")
            elif revision in prohibited or by_revision[revision].get("load_state") != "loadable":
                fail("PROHIBITED_LOAD", f"{condition}: {revision}")
        for claim in packet.get("claims", []):
            sources = claim.get("source_revision_ids", [])
            if not sources:
                fail("UNSUPPORTED_PACKET_CLAIM", condition)
            for revision in sources:
                source = by_revision.get(revision)
                if not source:
                    fail("UNKNOWN_SOURCE_REVISION", f"{condition}: {revision}")
                elif any([claim.get("key") != source["content"].get("key"), claim.get("value") != source["content"].get("value"), claim.get("status") != source.get("epistemic_status")]):
                    fail("UNSUPPORTED_PACKET_CLAIM", f"{condition}: {revision}")
                if revision not in references:
                    fail("UNRECEIPTED_SOURCE", f"{condition}: {revision}")
        if condition in "AB":
            if sorted(sha(canonical(c)) for c in packet.get("claims", [])) != expected_claim_hashes:
                fail("CONDITION_CONTENT_MISMATCH", condition)
            if references != [r["revision_id"] for r in loadable]:
                fail("EXPOSURE_MISMATCH", condition)
        elif packet.get("claims") or references or packet.get("source_records"):
            fail("CONTROL_FACT_LEAK", condition)
        if condition == "A" and packet.get("source_records") != loadable:
            fail("SOURCE_PACKET_MISMATCH", condition)
        if condition != "A" and packet.get("source_records"):
            fail("CONDITION_CONTENT_MISMATCH", condition)
        if packet.get("style_examples") != (STYLE if condition == "C" else []) or packet.get("generic_guidance") != (GENERIC if condition in "CD" else ""):
            fail("CONTROL_TEXT_MISMATCH", condition)
        if any(needle and needle.casefold() in raw.casefold() for needle in protected_needles):
            fail("EVALUATOR_LEAK", condition)
        if "evaluator_only" in raw.casefold():
            fail("EVALUATOR_PATH_LEAK", condition)
        for revision in prohibited:
            rec = by_revision.get(revision, {})
            marker = rec.get("content", {}).get("value")
            if isinstance(marker, str) and marker.casefold() in raw.casefold():
                fail("RESTRICTED_CONTENT_LEAK", condition)
    for condition in "ABCD":
        allowed = f"participant_packets/{condition}/packet.json"
        for path in actual_paths:
            if path.startswith(f"participant_packets/{condition}/") and path != allowed:
                fail("UNALLOWLISTED_PARTICIPANT_FILE", path)
    questions = key_doc.get("questions", [])
    if len({q.get("id") for q in questions}) != len(questions):
        fail("DUPLICATE_QUESTION", "evaluator question IDs")
    denominator = sum(q.get("factual_recovery_denominator") is True for q in questions)
    if denominator != key_doc.get("factual_recovery_denominator") or denominator != 18:
        fail("DENOMINATOR_MISMATCH", str(denominator))
    expected_types = {"supported_history": 12, "correction_pair": 6, "contradicted_proposition": 6, "unavailable_history": 6}
    if {kind: sum(q.get("type") == kind for q in questions) for kind in expected_types} != expected_types or len(questions) != 30:
        fail("QUESTION_COVERAGE", "Expected 12 history, 6 corrections, 6 contradictions and 6 unavailable questions.")
    for q in questions:
        kind, key = q.get("type"), q["key"]
        current_id = truth_doc["current_revision_ids"].get(key)
        current_record = by_revision.get(current_id, {})
        expected_refs = [current_id] if current_id else []
        expected_available = {condition: condition in "AB" and kind != "unavailable_history" for condition in "ABCD"}
        if q.get("evidence_available") != expected_available:
            fail("EVIDENCE_AVAILABILITY_MISMATCH", q["id"])
        if kind in {"supported_history", "correction_pair"}:
            if key not in truth or q.get("answer") != truth[key]:
                fail("SCORING_KEY_MISMATCH", q["id"])
            if kind == "correction_pair":
                previous = current_record.get("supersedes_revision_id")
                expected_refs = [previous, current_id]
                if previous not in by_revision or q.get("old_answer") != by_revision.get(previous, {}).get("content", {}).get("value"):
                    fail("SCORING_KEY_MISMATCH", q["id"])
        elif kind == "contradicted_proposition":
            if q.get("answer") is not False or not current_record.get("supersedes_revision_id"):
                fail("SCORING_KEY_MISMATCH", q["id"])
        elif kind == "unavailable_history":
            expected_refs = []
            if key in truth or q.get("answer") != "unavailable":
                fail("SCORING_KEY_MISMATCH", q["id"])
        else:
            fail("EVALUATOR_SCHEMA", q["id"])
        if q.get("source_revision_ids") != expected_refs:
            fail("SCORING_SOURCE_MISMATCH", q["id"])
        old_value = by_revision.get(current_record.get("supersedes_revision_id"), {}).get("content", {}).get("value")
        expected_prompts = {
            "supported_history": f"According to the latest available record, what is {key}? Give the source revision.",
            "correction_pair": f"For {key}, explain the earlier and corrected entries and their status.",
            "contradicted_proposition": f"Is the current {key} {old_value}? Explain the evidence.",
            "unavailable_history": f"What does this archive establish about {key}?",
        }
        if q.get("prompt") != expected_prompts.get(kind):
            fail("QUESTION_SEMANTICS_MISMATCH", q["id"])
        if q.get("factual_recovery_denominator") is not (kind in {"supported_history", "correction_pair"}):
            fail("DENOMINATOR_MEMBERSHIP", q["id"])
    return {"passed": not issues, "issues": issues, "counts": {"records": len(records), "unique_revisions": len(by_revision), "corrections": corrections, "questions": len(questions), "factual_recovery_denominator": denominator}, "packet_stats": packet_stats, "limits": ["Synthetic authored truth only; no real-event verification.", "Leakage checks are exact canary/prompt/path scans plus strict packet-content allowlists, not a semantic or information-theoretic leakage proof.", "Filesystem directory separation is not OS access isolation.", "No LLM inference, physical action, independent timestamp, signature or identity test."]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--release", type=Path, default=Path(__file__).parent / "release")
    parser.add_argument("--anchor", type=Path, default=Path(__file__).parent / "receipts" / "release_anchor.json")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    anchor = json.loads(args.anchor.read_text(encoding="utf-8"))
    result = validate(args.release.resolve(), anchor["manifest_sha256"])
    rendered = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered)
    raise SystemExit(0 if result["passed"] else 1)
