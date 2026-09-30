"""Consistency checks for candidate trial acceptance evidence."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import yaml

from xgtest.core.contract_set import build_contract_descriptor
from xgtest.generator.evidence import validate_trial_artifact
from xgtest.generator.scope import AcceptanceScope, resolve_scope
from xgtest.generator.template import semantic_hash
from xgtest.query.loader import load_query_case
from xgtest.runtime.profile import load_profile


def _safe_path(root: Path, value: str) -> Path:
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError("path escapes project root")
    resolved = (root / path).resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise ValueError("path escapes project root")
    return resolved


def verify_trial_artifact_index(
    project_root: Path,
    index_path: Path,
    runtime_profile_path: Path,
    *, scope: AcceptanceScope | None = None,
) -> dict[str, Any]:
    """Verify index, candidate, trial artifact, contract and runtime identities."""
    root = project_root.resolve()
    scope = resolve_scope(scope=scope)
    errors: list[dict[str, str]] = []

    def fail(case_id: str, code: str) -> None:
        errors.append({"case_id": case_id, "code": code})

    def invalid(details: str) -> dict[str, Any]:
        error = {"case_id": "*", "code": details}
        return {"status": "FAIL", "error": "ACCEPTANCE_TRIAL_INDEX_INVALID", "details": details,
                "expected_count": 0, "candidate_count": 0, "verified_count": 0,
                "failed_count": 0, "case_verified_count": 0, "case_failed_count": 0, "package_error_count": 1, "failed_cases": [], "global_errors": [error], "errors": [error]}

    try:
        index = json.loads(index_path.read_text(encoding="utf-8"))
        profile = load_profile(runtime_profile_path)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        return invalid(str(error))

    if not isinstance(index, dict):
        return invalid("INDEX_SCHEMA_INVALID")
    entries = index.get("candidates")
    if not isinstance(entries, list) or not all(isinstance(entry, dict) for entry in entries):
        return invalid("INDEX_SCHEMA_INVALID")
    if index.get("candidate_count") != len(entries):
        return invalid("candidate_count_mismatch")

    contract_id = str(build_contract_descriptor(root)["contract_set_id"])
    profile_id = profile.get("sql_runtime_profile_id")
    identity = profile.get("identity", {})
    target = identity.get("target", {}) if isinstance(identity, dict) else {}
    database_version = target.get("database_version")
    database_build_time = target.get("db_build")
    if not database_version or not database_build_time:
        fail("*", "RUNTIME_PROFILE_DATABASE_BUILD_REQUIRED")
    if index.get("contract_set_id") != contract_id:
        fail("*", "INDEX_CONTRACT_SET_STALE")
    if index.get("runtime_profile_id") != profile_id:
        fail("*", "INDEX_RUNTIME_PROFILE_STALE")
    if not isinstance(identity, dict) or identity.get("contract_set_id") != contract_id:
        fail("*", "RUNTIME_PROFILE_CONTRACT_SET_STALE")

    candidate_dir = scope.path(root, "candidate_root")
    expected_ids: set[str] = set()
    for candidate_path in scope.asset_paths(root, "candidate_root"):
        try:
            if load_query_case(candidate_path).metadata.status.value == "review":
                expected_ids.add(candidate_path.stem)
        except ValueError:
            fail(candidate_path.stem, "SCOPE_CANDIDATE_INVALID")
    if not expected_ids:
        fail("*", "ACCEPTANCE_SCOPE_EMPTY")
    indexed_ids = {str(entry.get("case_id", "<missing>")) for entry in entries}
    for missing_id in sorted(expected_ids - indexed_ids):
        fail(missing_id, "CANDIDATE_MISSING_FROM_INDEX")
    for extra_id in sorted(indexed_ids - expected_ids):
        fail(extra_id, "CANDIDATE_NOT_IN_ACCEPTANCE_SCOPE")

    seen: set[str] = set()
    verified_count = 0
    for entry in entries:
        case_id = str(entry.get("case_id", "<missing>"))
        prior_errors = len(errors)
        if case_id in seen:
            fail(case_id, "INDEX_DUPLICATE_CASE_ID")
            continue
        seen.add(case_id)
        try:
            candidate_path = _safe_path(root, entry["candidate_path"])
            artifact_root = _safe_path(root, entry["artifact_root"])
            artifact_path = _safe_path(artifact_root, entry["artifact_ref"])
            candidate = yaml.safe_load(candidate_path.read_text(encoding="utf-8"))
            case = load_query_case(candidate_path)
            artifact_bytes = artifact_path.read_bytes()
            artifact = json.loads(artifact_bytes)
        except (KeyError, OSError, ValueError, yaml.YAMLError, json.JSONDecodeError):
            fail(case_id, "CANDIDATE_OR_TRIAL_ARTIFACT_MISSING_OR_INVALID")
            continue

        if not isinstance(candidate, dict) or not isinstance(artifact, dict):
            fail(case_id, "CANDIDATE_OR_TRIAL_ARTIFACT_MISSING_OR_INVALID")
            continue
        if candidate_path.parent != candidate_dir or candidate_path.name != f"{case_id}.yaml":
            fail(case_id, "CANDIDATE_PATH_OUTSIDE_SCOPE")

        evidence = candidate.get("validation_evidence") or {}
        computed_sha = hashlib.sha256(artifact_bytes).hexdigest()
        if computed_sha != entry.get("artifact_sha256") or computed_sha != evidence.get("trial_artifact_sha256"):
            fail(case_id, "TRIAL_ARTIFACT_SHA256_MISMATCH")
        if artifact.get("case_id") != case_id or candidate.get("metadata", {}).get("id") != case_id:
            fail(case_id, "CASE_ID_MISMATCH")
        try:
            semantic = semantic_hash(candidate)
        except (KeyError, TypeError, ValueError):
            fail(case_id, "CANDIDATE_SEMANTIC_INVALID")
            continue
        if artifact.get("semantic_hash") != semantic or evidence.get("semantic_hash") != semantic or entry.get("semantic_hash") != semantic:
            fail(case_id, "SEMANTIC_HASH_MISMATCH")
        if candidate.get("metadata", {}).get("status") != "review":
            fail(case_id, "CANDIDATE_NOT_IN_REVIEW")
        if entry.get("artifact_ref") != evidence.get("trial_run_ref"):
            fail(case_id, "CANDIDATE_ARTIFACT_REFERENCE_MISMATCH")
        if artifact.get("contract_set_id") != contract_id or entry.get("contract_set_id") != contract_id:
            fail(case_id, "CONTRACT_SET_MISMATCH")
        if artifact.get("runtime_profile_id") != profile_id or entry.get("runtime_profile_id") != profile_id:
            fail(case_id, "RUNTIME_PROFILE_MISMATCH")
        if artifact.get("database_version") != database_version or entry.get("database_version") != database_version:
            fail(case_id, "DATABASE_VERSION_MISMATCH")
        if artifact.get("database_build_time") != database_build_time or entry.get("database_build_time") != database_build_time:
            fail(case_id, "DATABASE_BUILD_TIME_MISMATCH")
        if artifact.get("status") != "PASS" or entry.get("status") != "PASS":
            fail(case_id, "TRIAL_STATUS_NOT_PASS")

        validation = validate_trial_artifact(
            artifact,
            case_id=case_id,
            semantic_hash=semantic,
            step_ids=tuple(step.id for step in case.steps),
            step_modes={step.id: step.comparison.mode if step.comparison else "exact" for step in case.steps},
            contract_set_id=contract_id,
            runtime_profile_id=profile_id,
            database_version=database_version,
            database_build_time=database_build_time,
        )
        for code in validation["errors"]:
            fail(case_id, code)
        if not entry.get("raw_result_rows"):
            fail(case_id, "INDEX_RAW_ROWS_NOT_DECLARED")
        for run_name in ("run1", "run2"):
            if entry.get(f"{run_name}_row_count") != validation["run_row_counts"].get(run_name):
                fail(case_id, f"{run_name.upper()}_INDEX_ROW_COUNT_MISMATCH")
        if validation["trial_hash"] != evidence.get("trial_run_hash") or validation["trial_hash"] != entry.get("trial_result_hash"):
            fail(case_id, "TRIAL_RESULT_HASH_MISMATCH")
        if len(errors) == prior_errors:
            verified_count += 1

    if index.get("double_run_pass_count") != len(entries):
        fail("*", "DOUBLE_RUN_PASS_COUNT_MISMATCH")
    failed_cases = sorted({error["case_id"] for error in errors if error["case_id"] != "*"})
    return {
        "status": "PASS" if not errors else "FAIL",
        "error": None if not errors else "ACCEPTANCE_TRIAL_INDEX_INVALID",
        "expected_count": len(expected_ids),
        "candidate_count": len(entries),
        "verified_count": verified_count,
        "failed_count": len(failed_cases),
        "failed_cases": failed_cases,
        "global_errors": [error for error in errors if error["case_id"] == "*"],
        "errors": errors,
    }
