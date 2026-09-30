"""Frozen pre-promotion package and read-only integrity checks."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from xgtest.core.canonical import xgmj1_sha256
from xgtest.design.coverage import coverage_gap
from xgtest.design.model import load_test_model
from xgtest.generator.acceptance import verify_trial_artifact_index
from xgtest.generator.approval import verify_promotion_approval
from xgtest.generator.lifecycle import _validate_mutation_execution, promote_candidate
from xgtest.generator.plugins import FEATURE_PLUGINS
from xgtest.generator.template import semantic_hash
from xgtest.query.loader import load_query_case, load_query_directory
from xgtest.runtime.profile import load_profile


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _candidate_paths(root: Path) -> list[Path]:
    return sorted((root / "candidates" / "query" / "join").glob("*.yaml"))


def freeze_pre_promotion_manifest(root: Path, acceptance_dir: Path, profile_path: Path) -> dict[str, Any]:
    """Describe an exact review snapshot; caller decides when to save it."""
    root = root.resolve()
    profile = load_profile(profile_path)
    profile_suffix = profile_path.stem.removeprefix("runtime-profile-")
    evidence_path = profile_path.parent / "capabilities" / f"runtime-profile-evidence-{profile_suffix}.json"
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    evidence_digest = hashlib.sha256(json.dumps(evidence, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")).hexdigest()
    if profile.get("evidence_sha256") != evidence_digest:
        raise ValueError("RUNTIME_PROFILE_PROBE_HASH_MISMATCH")
    names = ("trial-run-index.json", "mutation-validation-index.json", "coverage-summary.json")
    inputs = {name: _sha(acceptance_dir / name) for name in names}
    members: list[dict[str, str]] = []
    for path in _candidate_paths(root):
        case = load_query_case(path)
        if case.metadata.status.value != "review":
            continue
        import yaml
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or case.validation_evidence is None or case.mutation_evidence is None:
            raise ValueError(f"PACKAGE_MEMBER_INVALID: {path.name}")
        members.append({
            "case_id": case.metadata.id,
            "asset_path": path.relative_to(root).as_posix(),
            "asset_sha256": _sha(path),
            "semantic_hash": semantic_hash(payload),
            "trial_artifact_sha256": case.validation_evidence.trial_artifact_sha256 or "",
            "mutation_artifact_sha256": case.mutation_evidence.artifact_sha256,
        })
    if not members:
        raise ValueError("ACCEPTANCE_SCOPE_EMPTY")
    descriptor = {
        "schema_version": "1", "phase": "pre_promotion", "scope": "query.join.review",
        "runtime_profile_id": profile["sql_runtime_profile_id"],
        "runtime_profile_sha256": _sha(profile_path),
        "runtime_profile_evidence_ref": evidence_path.relative_to(root).as_posix(),
        "runtime_profile_evidence_sha256": _sha(evidence_path),
        "inputs": inputs, "members": members,
        "ci_disposition": "DEFERRED_BY_USER",
    }
    return {**descriptor, "manifest_id": xgmj1_sha256(descriptor)}


def verify_pre_promotion_package(
    root: Path, acceptance_dir: Path, profile_path: Path, manifest_path: Path,
    *, approval_path: Path | None = None, allowed_signers_path: Path | None = None,
) -> dict[str, Any]:
    """Verify a frozen package without changing candidates or evidence."""
    errors: list[dict[str, str]] = []

    def fail(case_id: str, code: str) -> None:
        errors.append({"case_id": case_id, "code": code})

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if not isinstance(manifest, dict):
            raise ValueError("MANIFEST_SCHEMA_INVALID")
        manifest_id = manifest.get("manifest_id")
        projection = {key: value for key, value in manifest.items() if key != "manifest_id"}
        if manifest_id != xgmj1_sha256(projection):
            fail("*", "MANIFEST_HASH_MISMATCH")
        if manifest.get("phase") != "pre_promotion" or manifest.get("scope") != "query.join.review":
            fail("*", "MANIFEST_SCOPE_INVALID")
        if manifest.get("runtime_profile_sha256") != _sha(profile_path):
            fail("*", "MANIFEST_PROFILE_BYTES_CHANGED")
        evidence_ref = manifest.get("runtime_profile_evidence_ref")
        if not isinstance(evidence_ref, str):
            raise ValueError("MANIFEST_PROFILE_PROBE_REFERENCE_INVALID")
        evidence_path = (root.resolve() / evidence_ref).resolve()
        if not evidence_path.is_relative_to((root / "artifacts" / "capabilities").resolve()):
            raise ValueError("MANIFEST_PROFILE_PROBE_REFERENCE_INVALID")
        if manifest.get("runtime_profile_evidence_sha256") != _sha(evidence_path):
            fail("*", "MANIFEST_PROFILE_PROBE_BYTES_CHANGED")
        evidence_payload = json.loads(evidence_path.read_text(encoding="utf-8"))
        evidence_digest = hashlib.sha256(json.dumps(evidence_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")).hexdigest()
        if load_profile(profile_path).get("evidence_sha256") != evidence_digest:
            fail("*", "MANIFEST_PROFILE_PROBE_HASH_MISMATCH")
        inputs = manifest.get("inputs")
        if not isinstance(inputs, dict):
            raise ValueError("MANIFEST_INPUTS_INVALID")
        for name in ("trial-run-index.json", "mutation-validation-index.json", "coverage-summary.json"):
            if inputs.get(name) != _sha(acceptance_dir / name):
                fail("*", f"MANIFEST_INPUT_CHANGED:{name}")
        members = manifest.get("members")
        if not isinstance(members, list) or not all(isinstance(item, dict) for item in members):
            raise ValueError("MANIFEST_MEMBERS_INVALID")
    except (OSError, ValueError, TypeError, KeyError) as error:
        return {
            "schema_version": "1", "phase": "pre_promotion", "package_integrity": "FAIL",
            "readiness": "BLOCKED", "global_errors": [{"case_id": "*", "code": str(error)}],
            "expected_count": 0, "observed_count": 0, "verified_count": 0, "failed_count": 0,
            "failed_cases": [], "manifest_id": None,
        }

    expected_ids: set[str] = set()
    for item in members:
        case_id = str(item.get("case_id", "<missing>"))
        if case_id in expected_ids:
            fail(case_id, "MANIFEST_DUPLICATE_CASE")
        expected_ids.add(case_id)
        try:
            asset = (root.resolve() / item["asset_path"]).resolve()
            if not asset.is_relative_to((root / "candidates" / "query" / "join").resolve()):
                raise ValueError("MANIFEST_ASSET_OUTSIDE_SCOPE")
            case = load_query_case(asset)
            if case.metadata.id != case_id or case.metadata.status.value != "review":
                fail(case_id, "MANIFEST_ASSET_ID_OR_STATUS_CHANGED")
            if _sha(asset) != item.get("asset_sha256"):
                fail(case_id, "MANIFEST_ASSET_BYTES_CHANGED")
            if case.validation_evidence is None or case.mutation_evidence is None:
                fail(case_id, "MANIFEST_EVIDENCE_MISSING")
            else:
                if case.validation_evidence.semantic_hash != item.get("semantic_hash"):
                    fail(case_id, "MANIFEST_SEMANTIC_CHANGED")
                if case.validation_evidence.trial_artifact_sha256 != item.get("trial_artifact_sha256"):
                    fail(case_id, "MANIFEST_TRIAL_CHANGED")
                if case.mutation_evidence.artifact_sha256 != item.get("mutation_artifact_sha256"):
                    fail(case_id, "MANIFEST_MUTATION_CHANGED")
        except (OSError, ValueError, KeyError):
            fail(case_id, "MANIFEST_ASSET_INVALID")
    current_ids: set[str] = set()
    for path in _candidate_paths(root):
        try:
            case = load_query_case(path)
            if case.metadata.status.value == "review":
                current_ids.add(case.metadata.id)
        except ValueError:
            fail(path.stem, "CURRENT_CANDIDATE_INVALID")
    for missing in sorted(current_ids - expected_ids):
        fail(missing, "MANIFEST_CASE_MISSING")
    for extra in sorted(expected_ids - current_ids):
        fail(extra, "MANIFEST_CASE_EXTRA")

    trial = verify_trial_artifact_index(root, acceptance_dir / "trial-run-index.json", profile_path)
    if trial["status"] != "PASS":
        for item in trial.get("errors", []):
            fail(item["case_id"], f"TRIAL:{item['code']}")
        if not trial.get("errors"):
            fail("*", f"TRIAL:{trial.get('details', trial.get('error', 'INVALID'))}")
    try:
        mutation = json.loads((acceptance_dir / "mutation-validation-index.json").read_text(encoding="utf-8"))
        entries = mutation["candidates"]
        if not isinstance(entries, list) or mutation.get("candidate_count") != len(entries):
            raise ValueError("MUTATION_INDEX_SCHEMA_INVALID")
        mutation_ids = [str(item["case_id"]) for item in entries]
        if len(mutation_ids) != len(set(mutation_ids)):
            fail("*", "MUTATION_INDEX_DUPLICATE")
        for missing in sorted(expected_ids - set(mutation_ids)):
            fail(missing, "MUTATION_INDEX_CASE_MISSING")
        for extra in sorted(set(mutation_ids) - expected_ids):
            fail(extra, "MUTATION_INDEX_CASE_EXTRA")
        for entry in entries:
            case_id = str(entry["case_id"])
            if case_id not in current_ids:
                continue
            case = load_query_case(root / "candidates" / "query" / "join" / f"{case_id}.yaml")
            evidence = case.mutation_evidence
            if evidence is None:
                fail(case_id, "MUTATION_EVIDENCE_MISSING")
                continue
            if (
                entry.get("semantic_hash") != evidence.semantic_hash
                or entry.get("contract_set_id") != evidence.contract_set_id
                or entry.get("runtime_profile_id") != evidence.runtime_profile_id
                or evidence.runtime_profile_id != load_profile(profile_path)["sql_runtime_profile_id"]
            ):
                fail(case_id, "MUTATION_INDEX_IDENTITY_MISMATCH")
            if entry.get("artifact_ref") != evidence.artifact_ref or entry.get("artifact_sha256") != evidence.artifact_sha256:
                fail(case_id, "MUTATION_INDEX_REFERENCE_MISMATCH")
            artifact = (root / "artifacts" / "mutations" / evidence.artifact_ref).resolve()
            artifact_payload: Any = None
            if not artifact.is_relative_to((root / "artifacts" / "mutations").resolve()) or _sha(artifact) != evidence.artifact_sha256:
                fail(case_id, "MUTATION_ARTIFACT_HASH_MISMATCH")
            else:
                artifact_payload = json.loads(artifact.read_text(encoding="utf-8"))
                if (
                    not isinstance(artifact_payload, dict)
                    or artifact_payload.get("case_id") != case_id
                    or artifact_payload.get("semantic_hash") != evidence.semantic_hash
                    or artifact_payload.get("contract_set_id") != evidence.contract_set_id
                    or artifact_payload.get("runtime_profile_id") != evidence.runtime_profile_id
                    or artifact_payload.get("policy_version") != evidence.policy_version
                    or artifact_payload.get("checks") != [check.model_dump(mode="json") for check in evidence.checks]
                ):
                    fail(case_id, "MUTATION_ARTIFACT_CONTENT_MISMATCH")
            plugin = FEATURE_PLUGINS.for_case(case)
            requires_kill = plugin.mutation_applies(case)
            expected_status = "KILLED" if requires_kill else "NOT_APPLICABLE"
            if len(evidence.checks) != 1 or evidence.checks[0].mutation_id != plugin.mutation_id or evidence.checks[0].status != expected_status:
                fail(case_id, "MUTATION_APPLICABILITY_INVALID")
            if entry.get("status") != expected_status:
                fail(case_id, "MUTATION_INDEX_STATUS_MISMATCH")
            if len(evidence.checks) == 1 and (
                entry.get("mutation_id") != evidence.checks[0].mutation_id
                or entry.get("original_hash") != evidence.checks[0].original_hash
                or entry.get("mutated_hash") != evidence.checks[0].mutated_hash
            ):
                fail(case_id, "MUTATION_INDEX_RESULT_MISMATCH")
            if requires_kill and isinstance(artifact_payload, dict) and len(evidence.checks) == 1:
                try:
                    check = evidence.checks[0]
                    target = load_profile(profile_path)["identity"]["target"]
                    _validate_mutation_execution(
                        case, artifact_payload.get("execution"), check.original_hash or "", check.mutated_hash or "",
                        f"{target.get('db_build', '')} {target.get('database_version', '')}".strip(),
                    )
                except (ValueError, TypeError, OverflowError):
                    fail(case_id, "MUTATION_EXECUTION_EVIDENCE_INVALID")
    except (OSError, ValueError, KeyError, TypeError) as error:
        fail("*", f"MUTATION_INDEX_INVALID:{error}")

    try:
        model = load_test_model(root / "models" / "query" / "join.yaml")
        active = [case for case in load_query_directory(root / "cases" / "query") if case.metadata.status.value == "active"]
        candidates = [load_query_case(path) for path in _candidate_paths(root) if load_query_case(path).metadata.status.value == "review"]
        active_gap = coverage_gap(model, [claim for case in active for claim in case.coverage], "pairwise")
        provisional = coverage_gap(model, [claim for case in active + candidates for claim in case.coverage], "pairwise")
        summary = json.loads((acceptance_dir / "coverage-summary.json").read_text(encoding="utf-8"))
        if not all(summary.get(key) == value for key, value in {
            "required": active_gap["required"], "active_covered": active_gap["covered"],
            "active_missing": active_gap["missing"],
            "provisional_covered_if_promoted": provisional["covered"],
            "provisional_missing_if_promoted": provisional["missing"],
            "review_candidate_count": len(candidates),
        }.items()):
            fail("*", "COVERAGE_SUMMARY_STALE")
    except (OSError, ValueError, KeyError, TypeError) as error:
        fail("*", f"COVERAGE_INVALID:{error}")

    failed_cases = sorted({item["case_id"] for item in errors if item["case_id"] != "*"})
    global_errors = [item for item in errors if item["case_id"] == "*"]
    integrity = "PASS" if not errors else "FAIL"
    readiness = "WAITING_APPROVAL" if integrity == "PASS" else "BLOCKED"
    approval_status: dict[str, str] | None = None
    if integrity == "PASS" and approval_path is not None and allowed_signers_path is not None:
        plan = build_promotion_plan(root, manifest_path)
        approval_status = verify_promotion_approval(
            approval_path, allowed_signers_path, manifest_id=manifest_id,
            plan_hash=plan["plan_hash"],
        )
        if approval_status["status"] == "APPROVED":
            readiness = "READY"
    return {
        "schema_version": "1", "scope_id": manifest_id, "manifest_id": manifest_id,
        "phase": "pre_promotion", "package_integrity": integrity,
        "readiness": readiness, "approval": approval_status,
        "ci_disposition": manifest.get("ci_disposition"),
        "expected_count": len(expected_ids), "observed_count": len(current_ids),
        "verified_count": min(trial.get("verified_count", 0), len(expected_ids - set(failed_cases))),
        "failed_count": len(failed_cases), "failed_cases": failed_cases,
        "global_errors": global_errors, "errors": errors,
    }


def preflight_promotion(
    root: Path, acceptance_dir: Path, profile_path: Path, manifest_path: Path,
    *, approval_path: Path | None = None, allowed_signers_path: Path | None = None,
) -> dict[str, Any]:
    """Check the frozen batch and every destination without publishing files."""
    package = verify_pre_promotion_package(
        root, acceptance_dir, profile_path, manifest_path,
        approval_path=approval_path, allowed_signers_path=allowed_signers_path,
    )
    blockers: list[dict[str, str]] = []
    if package["package_integrity"] != "PASS":
        blockers.append({"case_id": "*", "code": "PACKAGE_INTEGRITY_FAILED"})
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        profile_id = load_profile(profile_path)["sql_runtime_profile_id"]
        model = load_test_model(root / "models" / "query" / "join.yaml")
        destinations: set[Path] = set()
        for item in manifest["members"]:
            case_id = item["case_id"]
            path = root / item["asset_path"]
            try:
                destination = promote_candidate(
                    path, model, root / "cases" / "query" / "join",
                    root / "artifacts" / "trial-runs",
                    expected_runtime_profile_id=profile_id,
                    mutation_artifact_root=root / "artifacts" / "mutations",
                    dry_run=True,
                )
                if destination in destinations:
                    blockers.append({"case_id": case_id, "code": "DUPLICATE_PROMOTION_DESTINATION"})
                destinations.add(destination)
            except (OSError, ValueError) as error:
                blockers.append({"case_id": case_id, "code": str(error)})
    except (OSError, ValueError, KeyError, TypeError) as error:
        blockers.append({"case_id": "*", "code": f"PREFLIGHT_INPUT_INVALID:{error}"})
    return {
        "manifest_id": package.get("manifest_id"),
        "package_integrity": package["package_integrity"],
        "readiness": package["readiness"] if not blockers else "BLOCKED",
        "promotable_count": package["expected_count"] - len({item["case_id"] for item in blockers if item["case_id"] != "*"}),
        "blockers": blockers,
    }


def build_promotion_plan(root: Path, manifest_path: Path) -> dict[str, Any]:
    """Bind selected candidates to the current Active file snapshot."""
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or manifest.get("phase") != "pre_promotion":
        raise ValueError("PROMOTION_MANIFEST_INVALID")
    active_root = root / "cases" / "query"
    active = [
        {"path": path.relative_to(root).as_posix(), "sha256": _sha(path)}
        for path in sorted(active_root.rglob("*.yaml"))
    ]
    selected = [
        {"case_id": item["case_id"], "asset_sha256": item["asset_sha256"]}
        for item in manifest["members"]
    ]
    if len({item["case_id"] for item in selected}) != len(selected):
        raise ValueError("PROMOTION_PLAN_DUPLICATE_CASE")
    projection = {
        "schema_version": "1", "manifest_id": manifest["manifest_id"],
        "active_snapshot": active, "selected": selected,
        "governance_policy_version": "1",
    }
    return {**projection, "plan_hash": xgmj1_sha256(projection)}
