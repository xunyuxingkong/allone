"""Evidence-gated candidate lifecycle and promotion."""

from __future__ import annotations

import json
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
            {"id": step["id"], "status": step["status"], "row_count": step.get("row_count"), "result_sha256": step.get("result_sha256")}
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
    reports = [run(case, config, runtime_profile), run(case, config, runtime_profile)]
    if any(report.status != CaseExecutionStatus.PASS for report in reports):
        raise ValueError("CANDIDATE_TRIAL_FAILED")
    projected = [
        {
            "case_id": report.case_id,
            "status": report.status.value,
            "steps": [
                {"id": step.id, "status": step.status.value, "row_count": step.row_count, "result_sha256": step.result_sha256}
                for step in report.steps
            ],
        }
        for report in reports
    ]
    if projected[0] != projected[1]:
        raise ValueError("CANDIDATE_TRIAL_NONDETERMINISTIC")
    artifact_hash = xgmj1_sha256(projected)
    artifact = {
        "case_id": case.metadata.id,
        "semantic_hash": semantic,
        "runtime_profile_id": runtime_profile.get("sql_runtime_profile_id") if runtime_profile else None,
        "contract_set_id": build_contract_descriptor(Path(__file__).resolve().parents[3])["contract_set_id"],
        "database_version": (runtime_profile or {}).get("target", {}).get("database_version"),
        "driver_version": (runtime_profile or {}).get("driver", {}).get("version"),
        "run1": reports[0].model_dump(mode="json"),
        "run2": reports[1].model_dump(mode="json"),
        "result_hash": artifact_hash,
        "status": "PASS",
    }
    artifact_path = artifact_root / case.metadata.id / f"{semantic}.json"
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    payload["metadata"]["status"] = "review"
    evidence = payload["validation_evidence"]
    evidence["trial_run_hash"] = artifact_hash
    evidence["trial_run_ref"] = artifact_path.relative_to(artifact_root).as_posix()
    _write_payload(path, payload)
    return {"case_id": case.metadata.id, "status": "review", "artifact": str(artifact_path), "trial_run_hash": artifact_hash}


def promote_candidate(path: Path, model: TestModel, active_dir: Path, artifact_root: Path) -> Path:
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
    if not evidence.static_validation_hash or not evidence.trial_run_hash or not evidence.review_hash:
        raise ValueError("CANDIDATE_PROMOTION_EVIDENCE_INCOMPLETE")
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
        artifact_payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("CANDIDATE_TRIAL_ARTIFACT_MISSING_OR_INVALID") from error
    if artifact_payload.get("case_id") != case.metadata.id or artifact_payload.get("semantic_hash") != semantic or artifact_payload.get("status") != "PASS":
        raise ValueError("CANDIDATE_TRIAL_ARTIFACT_STALE")
    result_hash = xgmj1_sha256([_trial_projection(artifact_payload["run1"]), _trial_projection(artifact_payload["run2"])])
    if result_hash != evidence.trial_run_hash or artifact_payload.get("result_hash") != evidence.trial_run_hash:
        raise ValueError("CANDIDATE_TRIAL_ARTIFACT_HASH_MISMATCH")
    if case.review_evidence.trial_run_artifact_hash != evidence.trial_run_hash:
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
    active_dir.mkdir(parents=True, exist_ok=True)
    destination = active_dir / f"{case.metadata.id}.yaml"
    if destination.exists():
        raise ValueError(f"ACTIVE_CASE_EXISTS: {destination}")
    payload["metadata"]["status"] = "active"
    _write_payload(destination, payload)
    path.unlink()
    return destination
