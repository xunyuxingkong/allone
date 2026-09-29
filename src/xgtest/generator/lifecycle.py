"""Evidence-gated candidate lifecycle and promotion."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

import yaml

from xgtest.core.canonical import xgmj1_sha256
from xgtest.core.contract_set import build_contract_descriptor
from xgtest.design.constraint import validate_assignment
from xgtest.design.model import TestModel
from xgtest.design.signature import candidate_signature
from xgtest.generator.template import TEMPLATE_ID, TEMPLATE_VERSION
from xgtest.generator.template import semantic_hash
from xgtest.generator.review import current_review_input_hash
from xgtest.query.loader import load_query_case


def _write_payload(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True), encoding="utf-8")


def _case_payload(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("CANDIDATE_INVALID")
    return payload


def _trial_projection(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "case_id": report["case_id"],
        "status": report["status"],
        "steps": [
            {
                "id": step["id"],
                "status": step["status"],
                "columns": step.get("columns", []),
                "column_types": step.get("column_types", []),
                "logical_types": step.get("logical_types", []),
                "row_count": step.get("row_count"),
                "result_rows": step.get("result_rows"),
                "result_sha256": step.get("result_sha256"),
            }
            for step in report["steps"]
        ],
    }


def trial_candidate(
    path: Path,
    model: TestModel,
    config: Any,
    artifact_root: Path,
    *,
    runtime_profile: dict[str, Any] | None = None,
    runner: Any = None,
) -> dict[str, Any]:
    from xgtest.core.models import CaseExecutionStatus
    from xgtest.query.runner import run_query_case_isolated
    from xgtest.generator.candidate import static_validate_candidate

    if runner is None:
        if runtime_profile is None:
            raise ValueError("RUNTIME_PROFILE_REQUIRED_FOR_CANDIDATE_TRIAL")
        from xgtest.runtime.profile import validate_profile

        contract_set_id = str(build_contract_descriptor(Path(__file__).resolve().parents[3])["contract_set_id"])
        try:
            import xgcondb
        except ImportError as error:
            raise RuntimeError("Xugu Python driver xgcondb is unavailable in this environment") from error
        validate_profile(
            runtime_profile,
            host=config.host,
            database=config.database,
            driver_version=tuple(xgcondb.version_info),
            contract_set_id=contract_set_id,
        )
    run = runner or run_query_case_isolated
    case = load_query_case(path)
    if case.metadata.status.value != "draft":
        raise ValueError("CANDIDATE_STATUS_INVALID: trial expects draft status")
    if case.validation_evidence is None or case.validation_evidence.static_validation_hash is None:
        raise ValueError("CANDIDATE_STATIC_EVIDENCE_REQUIRED")
    static_result = static_validate_candidate(path, model)
    if static_result["static_validation_hash"] != case.validation_evidence.static_validation_hash:
        raise ValueError("CANDIDATE_STATIC_EVIDENCE_STALE")
    case = load_query_case(path)
    if len(case.coverage) != 1:
        raise ValueError("CANDIDATE_COVERAGE_REQUIRED")
    validate_assignment(model, case.coverage[0].assignment)
    payload = _case_payload(path)
    semantic = semantic_hash(payload)
    if case.validation_evidence.semantic_hash != semantic:
        raise ValueError("CANDIDATE_SEMANTIC_HASH_STALE")
    if runner is None:
        reports = [
            run(case, config, runtime_profile, capture_result_rows=True),
            run(case, config, runtime_profile, capture_result_rows=True),
        ]
    else:
        reports = [run(case, config, runtime_profile), run(case, config, runtime_profile)]
    if any(report.status != CaseExecutionStatus.PASS for report in reports):
        raise ValueError("CANDIDATE_TRIAL_FAILED")
    if runner is None and any(
        step.result_rows is None or step.row_count != len(step.result_rows)
        for report in reports
        for step in report.steps
    ):
        raise ValueError("CANDIDATE_TRIAL_RAW_ROWS_MISSING")
    projected = [_trial_projection(report.model_dump(mode="json")) for report in reports]
    if projected[0] != projected[1]:
        raise ValueError("CANDIDATE_TRIAL_NONDETERMINISTIC")
    artifact_hash = xgmj1_sha256(projected)
    profile_identity = (runtime_profile or {}).get("identity", {})
    profile_target = profile_identity.get("target", {}) if isinstance(profile_identity, dict) else {}
    artifact = {
        "case_id": case.metadata.id,
        "semantic_hash": semantic,
        "runtime_profile_id": runtime_profile.get("sql_runtime_profile_id") if runtime_profile else None,
        "contract_set_id": build_contract_descriptor(Path(__file__).resolve().parents[3])["contract_set_id"],
        "database_product": profile_target.get("database_product"),
        "database_version": profile_target.get("database_version"),
        "database_build_time": profile_target.get("db_build"),
        "driver_version": (runtime_profile or {}).get("driver", {}).get("version"),
        "run1": reports[0].model_dump(mode="json"),
        "run2": reports[1].model_dump(mode="json"),
        "result_hash": artifact_hash,
        "status": "PASS",
    }
    artifact_path = artifact_root / case.metadata.id / f"{semantic}.json"
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_bytes = (json.dumps(artifact, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    artifact_path.write_bytes(artifact_bytes)
    artifact_sha256 = hashlib.sha256(artifact_bytes).hexdigest()
    payload["metadata"]["status"] = "review"
    evidence = payload["validation_evidence"]
    evidence.pop("review_hash", None)
    evidence["trial_run_hash"] = artifact_hash
    evidence["trial_artifact_sha256"] = artifact_sha256
    evidence["trial_run_ref"] = artifact_path.relative_to(artifact_root).as_posix()
    payload.pop("review_evidence", None)
    payload.pop("coverage_review", None)
    _write_payload(path, payload)
    return {"case_id": case.metadata.id, "status": "review", "artifact": str(artifact_path), "trial_run_hash": artifact_hash, "trial_artifact_sha256": artifact_sha256}


def validate_candidate_mutation(
    path: Path,
    model: TestModel,
    config: Any,
    runtime_profile: dict[str, Any],
    *,
    runner: Any = None,
) -> dict[str, Any]:
    """Check that replacing <= with < changes a static-validated JOIN result."""
    from xgtest.core.models import CaseExecutionStatus, QueryCaseInput
    from xgtest.query.runner import run_query_case_isolated

    from xgtest.generator.candidate import static_validate_candidate

    if runner is None:
        if not runtime_profile:
            raise ValueError("RUNTIME_PROFILE_REQUIRED_FOR_MUTATION_VALIDATION")
        import xgcondb

        from xgtest.runtime.profile import validate_profile

        validate_profile(
            runtime_profile,
            host=config.host,
            database=config.database,
            driver_version=tuple(xgcondb.version_info),
            contract_set_id=str(build_contract_descriptor(Path(__file__).resolve().parents[3])["contract_set_id"]),
        )

    case = load_query_case(path)
    if case.metadata.status.value != "draft":
        raise ValueError("CANDIDATE_STATUS_INVALID: mutation validation expects draft status")
    if not any(claim.assignment.get("predicate") == "less_equal" for claim in case.coverage):
        return {"case_id": case.metadata.id, "mutation_id": "replace_le_with_lt", "status": "NOT_APPLICABLE"}
    static_validate_candidate(path, model)
    case = load_query_case(path)
    payload = case.model_dump(mode="python")
    occurrences = 0
    for step in payload["steps"]:
        count = step["sql"].count("a.k <= b.k")
        occurrences += count
        step["sql"] = step["sql"].replace("a.k <= b.k", "a.k < b.k")
    if occurrences == 0:
        raise ValueError("CANDIDATE_MUTATION_TARGET_MISSING")
    mutated_case = QueryCaseInput.model_validate(payload)
    run = runner or run_query_case_isolated
    original_reports = [run(case, config, runtime_profile), run(case, config, runtime_profile)]
    if any(report.status != CaseExecutionStatus.PASS for report in original_reports):
        return {"case_id": case.metadata.id, "mutation_id": "replace_le_with_lt", "status": "BASELINE_NOT_PASS"}
    original = [_trial_projection(report.model_dump(mode="json")) for report in original_reports]
    if original[0] != original[1]:
        return {"case_id": case.metadata.id, "mutation_id": "replace_le_with_lt", "status": "BASELINE_NONDETERMINISTIC"}
    mutated_reports = [run(mutated_case, config, runtime_profile), run(mutated_case, config, runtime_profile)]
    if any(report.status in {CaseExecutionStatus.ERROR, CaseExecutionStatus.TIMEOUT} for report in mutated_reports):
        return {
            "case_id": case.metadata.id,
            "mutation_id": "replace_le_with_lt",
            "status": "INCONCLUSIVE",
            "original_hash": xgmj1_sha256(original[0]),
        }
    mutated = [_trial_projection(report.model_dump(mode="json")) for report in mutated_reports]
    if mutated[0] != mutated[1]:
        return {"case_id": case.metadata.id, "mutation_id": "replace_le_with_lt", "status": "MUTATED_NONDETERMINISTIC"}
    original_hash = xgmj1_sha256(original[0])
    mutated_hash = xgmj1_sha256(mutated[0])
    return {
        "case_id": case.metadata.id,
        "mutation_id": "replace_le_with_lt",
        "status": "KILLED" if original_hash != mutated_hash or mutated_reports[0].status != CaseExecutionStatus.PASS else "WEAK",
        "original_hash": original_hash,
        "mutated_hash": mutated_hash,
    }


def record_candidate_mutation_evidence(
    path: Path,
    result: dict[str, Any],
    artifact_root: Path,
    runtime_profile: dict[str, Any],
) -> dict[str, Any]:
    """Persist a mutation result and bind it to a candidate and runtime identity."""
    from xgtest.core.models import MutationEvidence

    case = load_query_case(path)
    if case.metadata.status.value != "draft":
        raise ValueError("CANDIDATE_STATUS_INVALID: mutation evidence expects draft status")
    payload = _case_payload(path)
    semantic = semantic_hash(payload)
    if case.validation_evidence is None or case.validation_evidence.semantic_hash != semantic:
        raise ValueError("CANDIDATE_SEMANTIC_HASH_STALE")
    contract_id = str(build_contract_descriptor(Path(__file__).resolve().parents[3])["contract_set_id"])
    profile_id = str(runtime_profile.get("sql_runtime_profile_id", ""))
    if not re.fullmatch(r"[0-9a-f]{64}", profile_id):
        raise ValueError("CANDIDATE_RUNTIME_PROFILE_REQUIRED")
    checks = [{
        "mutation_id": result["mutation_id"],
        "status": result["status"],
        "original_hash": result.get("original_hash"),
        "mutated_hash": result.get("mutated_hash"),
    }]
    artifact = {
        "case_id": case.metadata.id,
        "semantic_hash": semantic,
        "policy_version": "1",
        "contract_set_id": contract_id,
        "runtime_profile_id": profile_id,
        "checks": checks,
    }
    artifact_path = artifact_root / case.metadata.id / f"{semantic}.json"
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_bytes = (json.dumps(artifact, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    artifact_path.write_bytes(artifact_bytes)
    artifact_sha256 = hashlib.sha256(artifact_bytes).hexdigest()
    evidence = MutationEvidence.model_validate({
        "policy_version": "1",
        "semantic_hash": semantic,
        "contract_set_id": contract_id,
        "runtime_profile_id": profile_id,
        "artifact_ref": artifact_path.relative_to(artifact_root).as_posix(),
        "artifact_sha256": artifact_sha256,
        "checks": tuple(checks),
    })
    payload["mutation_evidence"] = evidence.model_dump(mode="json", exclude_none=True)
    _write_payload(path, payload)
    return {"case_id": case.metadata.id, "mutation_artifact": str(artifact_path), "mutation_artifact_sha256": artifact_sha256}


def promote_candidate(
    path: Path,
    model: TestModel,
    active_dir: Path,
    artifact_root: Path,
    *,
    expected_runtime_profile_id: str,
    mutation_artifact_root: Path | None = None,
) -> Path:
    from xgtest.generator.candidate import static_validate_candidate

    if not re.fullmatch(r"[0-9a-f]{64}", expected_runtime_profile_id):
        raise ValueError("CANDIDATE_RUNTIME_PROFILE_REQUIRED")
    case = load_query_case(path)
    if case.metadata.status.value != "review":
        raise ValueError("CANDIDATE_STATUS_INVALID: promote expects review status")
    if case.oracle is None or case.validation_evidence is None or case.review_evidence is None or case.coverage_review is None:
        raise ValueError("CANDIDATE_PROMOTION_EVIDENCE_REQUIRED")
    payload = _case_payload(path)
    semantic = semantic_hash(payload)
    evidence = case.validation_evidence
    if evidence.semantic_hash != semantic or case.review_evidence.semantic_hash != semantic:
        raise ValueError("CANDIDATE_SEMANTIC_HASH_STALE")
    if not evidence.static_validation_hash or not evidence.trial_run_hash or not evidence.trial_artifact_sha256 or not evidence.review_hash:
        raise ValueError("CANDIDATE_PROMOTION_EVIDENCE_INCOMPLETE")
    mutation = case.mutation_evidence
    if mutation is None:
        raise ValueError("CANDIDATE_MUTATION_EVIDENCE_REQUIRED")
    expected_static_hash = xgmj1_sha256({
        "case_id": case.metadata.id,
        "semantic_hash": semantic,
        "assignment": case.coverage[0].assignment,
    }) if case.coverage else None
    if evidence.static_validation_hash != expected_static_hash:
        raise ValueError("CANDIDATE_STATIC_EVIDENCE_STALE")
    if not evidence.trial_run_ref:
        raise ValueError("CANDIDATE_TRIAL_ARTIFACT_REFERENCE_REQUIRED")
    artifact_ref = Path(evidence.trial_run_ref)
    if artifact_ref.is_absolute() or ".." in artifact_ref.parts:
        raise ValueError("CANDIDATE_TRIAL_ARTIFACT_REFERENCE_INVALID")
    artifact_path = artifact_root / artifact_ref
    try:
        artifact_bytes = artifact_path.read_bytes()
        artifact_payload = json.loads(artifact_bytes)
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("CANDIDATE_TRIAL_ARTIFACT_MISSING_OR_INVALID") from error
    if artifact_payload.get("case_id") != case.metadata.id or artifact_payload.get("semantic_hash") != semantic or artifact_payload.get("status") != "PASS":
        raise ValueError("CANDIDATE_TRIAL_ARTIFACT_STALE")
    if hashlib.sha256(artifact_bytes).hexdigest() != evidence.trial_artifact_sha256:
        raise ValueError("CANDIDATE_TRIAL_ARTIFACT_HASH_MISMATCH")
    current_contract_set_id = build_contract_descriptor(Path(__file__).resolve().parents[3])["contract_set_id"]
    if artifact_payload.get("contract_set_id") != current_contract_set_id:
        raise ValueError("CANDIDATE_CONTRACT_SET_STALE")
    if artifact_payload.get("runtime_profile_id") != expected_runtime_profile_id:
        raise ValueError("CANDIDATE_RUNTIME_PROFILE_MISMATCH")
    if mutation.policy_version != "1" or mutation.semantic_hash != semantic:
        raise ValueError("CANDIDATE_MUTATION_EVIDENCE_STALE")
    if mutation.contract_set_id != current_contract_set_id:
        raise ValueError("CANDIDATE_MUTATION_EVIDENCE_STALE")
    if mutation.runtime_profile_id != expected_runtime_profile_id:
        raise ValueError("CANDIDATE_MUTATION_EVIDENCE_STALE")
    mutation_root = mutation_artifact_root or (artifact_root.parent / "mutations")
    mutation_ref = Path(mutation.artifact_ref)
    if mutation_ref.is_absolute() or ".." in mutation_ref.parts:
        raise ValueError("CANDIDATE_MUTATION_EVIDENCE_STALE")
    mutation_path = (mutation_root / mutation_ref).resolve()
    if not mutation_path.is_relative_to(mutation_root.resolve()):
        raise ValueError("CANDIDATE_MUTATION_EVIDENCE_STALE")
    try:
        mutation_bytes = mutation_path.read_bytes()
        mutation_payload = json.loads(mutation_bytes)
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("CANDIDATE_MUTATION_EVIDENCE_STALE") from error
    if hashlib.sha256(mutation_bytes).hexdigest() != mutation.artifact_sha256:
        raise ValueError("CANDIDATE_MUTATION_EVIDENCE_STALE")
    if (
        mutation_payload.get("case_id") != case.metadata.id
        or mutation_payload.get("semantic_hash") != semantic
        or mutation_payload.get("contract_set_id") != current_contract_set_id
        or mutation_payload.get("runtime_profile_id") != expected_runtime_profile_id
        or mutation_payload.get("checks") != [check.model_dump(mode="json") for check in mutation.checks]
    ):
        raise ValueError("CANDIDATE_MUTATION_EVIDENCE_STALE")
    applicable = [check for check in mutation.checks if check.mutation_id == "replace_le_with_lt"]
    requires_kill = any(claim.assignment.get("predicate") == "less_equal" for claim in case.coverage)
    if not applicable:
        raise ValueError("CANDIDATE_MUTATION_EVIDENCE_REQUIRED")
    if requires_kill and any(check.status != "KILLED" for check in applicable):
        raise ValueError("CANDIDATE_MUTATION_GATE_FAILED")
    if not requires_kill and any(check.status not in {"NOT_APPLICABLE", "KILLED"} for check in applicable):
        raise ValueError("CANDIDATE_MUTATION_GATE_FAILED")
    result_hash = xgmj1_sha256([_trial_projection(artifact_payload["run1"]), _trial_projection(artifact_payload["run2"])])
    if result_hash != evidence.trial_run_hash or artifact_payload.get("result_hash") != evidence.trial_run_hash:
        raise ValueError("CANDIDATE_TRIAL_ARTIFACT_HASH_MISMATCH")
    if case.review_evidence.trial_artifact_sha256 != evidence.trial_artifact_sha256:
        raise ValueError("CANDIDATE_TRIAL_EVIDENCE_STALE")
    if case.review_evidence.review_input_hash != case.coverage_review.review_input_hash:
        raise ValueError("CANDIDATE_COVERAGE_REVIEW_STALE")
    if case.coverage_review.review_input_hash != evidence.review_hash or current_review_input_hash(case, semantic) != evidence.review_hash:
        raise ValueError("CANDIDATE_REVIEW_INPUT_STALE")
    if case.oracle.kind not in {"manual", "reference_database", "known_result", "property"}:
        raise ValueError("CANDIDATE_ORACLE_INVALID")
    if len(case.coverage) != 1:
        raise ValueError("CANDIDATE_COVERAGE_REQUIRED")
    validate_assignment(model, case.coverage[0].assignment)
    expected_id = f"QUERY.JOIN.{candidate_signature(model, case.coverage[0].assignment, TEMPLATE_ID, TEMPLATE_VERSION)[:8].upper()}"
    if case.metadata.id != expected_id:
        raise ValueError("CANDIDATE_ID_MISMATCH")
    static_validate_candidate(path, model)
    active_dir.mkdir(parents=True, exist_ok=True)
    destination = active_dir / f"{case.metadata.id}.yaml"
    if destination.exists():
        raise ValueError(f"ACTIVE_CASE_EXISTS: {destination}")
    payload["metadata"]["status"] = "active"
    _write_payload(destination, payload)
    path.unlink()
    return destination
