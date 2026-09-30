"""Evidence-gated candidate lifecycle and promotion."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

import yaml

from xgtest.core.canonical import xgmj1_sha256
from xgtest.core.row_codec import decode_rows
from xgtest.core.contract_set import build_contract_descriptor
from xgtest.design.constraint import validate_assignment
from xgtest.design.model import TestModel
from xgtest.generator.artifact_store import LocalArtifactStore
from xgtest.generator.evidence import trial_projection as _trial_projection, validate_trial_artifact
from xgtest.generator.plugins import FEATURE_PLUGINS
from xgtest.generator.template import semantic_hash
from xgtest.generator.review import current_review_input_hash
from xgtest.query.loader import load_query_case
from xgtest.runtime.comparator import rows_semantic_sha256, rows_sha256


def _write_payload(path: Path, payload: dict[str, Any]) -> None:
    content = yaml.safe_dump(payload, sort_keys=False, allow_unicode=True).encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".candidate-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def _case_payload(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("CANDIDATE_INVALID")
    return payload


def _mutation_result_digest(report: dict[str, Any], case: Any, *, require_rows: bool) -> str:
    steps = report.get("steps")
    if not isinstance(steps, list) or not all(isinstance(step, dict) for step in steps) or tuple(step.get("id") for step in steps if isinstance(step, dict)) != tuple(step.id for step in case.steps):
        raise ValueError("MUTATION_EXECUTION_STEPS_INVALID")
    projected: list[dict[str, Any]] = []
    for definition, step in zip(case.steps, steps):
        if not isinstance(step, dict):
            raise ValueError("MUTATION_EXECUTION_STEP_INVALID")
        rows = step.get("result_rows")
        column_types = step.get("column_types")
        columns = step.get("columns")
        if rows is None and not require_rows:
            digest = step.get("result_sha256")
        else:
            if not isinstance(rows, list) or not isinstance(columns, list) or not isinstance(column_types, list):
                raise ValueError("MUTATION_EXECUTION_RAW_ROWS_MISSING")
            if len(columns) != len(column_types) or any(not isinstance(row, list) or len(row) != len(columns) for row in rows):
                raise ValueError("MUTATION_EXECUTION_ROW_WIDTH_INVALID")
            if len(rows) != step.get("row_count"):
                raise ValueError("MUTATION_EXECUTION_ROW_COUNT_INVALID")
            tuples = list(decode_rows(rows))
            if rows_sha256(tuples, column_types, len(columns)) != step.get("result_sha256"):
                raise ValueError("MUTATION_EXECUTION_ROW_HASH_INVALID")
            digest = rows_semantic_sha256(
                tuples, column_types, len(columns),
                mode=definition.comparison.mode if definition.comparison else "exact",
            )
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError("MUTATION_EXECUTION_RESULT_HASH_MISSING")
        projected.append({"id": definition.id, "row_count": step.get("row_count"), "result_sha256": digest})
    return xgmj1_sha256(projected)


def _validate_mutation_execution(case: Any, execution: Any, original_hash: str, mutated_hash: str, expected_build: str | None = None) -> None:
    if not isinstance(execution, dict):
        raise ValueError("MUTATION_EXECUTION_EVIDENCE_REQUIRED")
    plugin = FEATURE_PLUGINS.for_case(case)
    original_sql = [step.sql for step in case.steps]
    mutated_sql = [plugin.mutated_sql(sql) for sql in original_sql]
    if mutated_sql == original_sql or execution.get("original_sql_sha256") != xgmj1_sha256(original_sql) or execution.get("mutated_sql_sha256") != xgmj1_sha256(mutated_sql):
        raise ValueError("MUTATION_EXECUTION_SQL_MISMATCH")
    baseline = execution.get("baseline_runs")
    mutated = execution.get("mutated_runs")
    if not isinstance(baseline, list) or not isinstance(mutated, list) or len(baseline) != 2 or len(mutated) != 2:
        raise ValueError("MUTATION_EXECUTION_RUNS_REQUIRED")
    baseline_hashes: list[str] = []
    mutated_hashes: list[str] = []
    for report in baseline:
        if not isinstance(report, dict) or report.get("case_id") != case.metadata.id or report.get("status") != "PASS":
            raise ValueError("MUTATION_BASELINE_NOT_PASS")
        baseline_hashes.append(_mutation_result_digest(report, case, require_rows=True))
    for report in mutated:
        if not isinstance(report, dict) or report.get("case_id") != case.metadata.id or report.get("status") not in {"PASS", "FAIL"}:
            raise ValueError("MUTATION_MUTATED_RUN_INVALID")
        mutated_hashes.append(_mutation_result_digest(report, case, require_rows=True))
    if baseline_hashes != [original_hash, original_hash] or mutated_hashes != [mutated_hash, mutated_hash] or original_hash == mutated_hash:
        raise ValueError("MUTATION_EXECUTION_RESULT_MISMATCH")
    observations = execution.get("build_observations")
    if not isinstance(observations, list) or len(observations) != 2 or any(
        not isinstance(item, dict) or item.get("query") != "SHOW build_time;"
        or not isinstance(item.get("captured_at"), str) or not isinstance(item.get("raw_value"), str)
        for item in observations
    ):
        raise ValueError("MUTATION_BUILD_OBSERVATION_REQUIRED")
    if observations[0]["raw_value"] != observations[1]["raw_value"] or (expected_build is not None and observations[0]["raw_value"] != expected_build):
        raise ValueError("MUTATION_DATABASE_BUILD_DRIFT")


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
    build_before = None
    if runner is None:
        from xgtest.runtime.profile import observe_database_build
        build_before = observe_database_build(config, runtime_profile)
        reports = [
            run(case, config, runtime_profile, capture_result_rows=True),
            run(case, config, runtime_profile, capture_result_rows=True),
        ]
    else:
        reports = [run(case, config, runtime_profile), run(case, config, runtime_profile)]
    build_after = observe_database_build(config, runtime_profile) if runner is None else None
    if any(report.status != CaseExecutionStatus.PASS for report in reports):
        raise ValueError("CANDIDATE_TRIAL_FAILED")
    if runner is None and any(
        step.result_rows is None or step.row_count != len(step.result_rows)
        for report in reports
        for step in report.steps
    ):
        raise ValueError("CANDIDATE_TRIAL_RAW_ROWS_MISSING")
    projected = [_trial_projection(report.model_dump(mode="json")) for report in reports]
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
        "build_observations": [build_before, build_after] if runner is None else None,
        "run1": reports[0].model_dump(mode="json"),
        "run2": reports[1].model_dump(mode="json"),
        "result_hash": artifact_hash,
        "status": "PASS",
    }
    trial_validation = validate_trial_artifact(
        artifact,
        case_id=case.metadata.id,
        semantic_hash=semantic,
        step_ids=tuple(step.id for step in case.steps),
        step_modes={step.id: step.comparison.mode if step.comparison else "exact" for step in case.steps},
        contract_set_id=artifact["contract_set_id"],
        runtime_profile_id=artifact["runtime_profile_id"],
    )
    if trial_validation["errors"]:
        raise ValueError(f"CANDIDATE_TRIAL_INVALID: {','.join(trial_validation['errors'])}")
    artifact_bytes = (json.dumps(artifact, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    artifact_ref = LocalArtifactStore(artifact_root).put(artifact_bytes)
    artifact_path = artifact_root / artifact_ref.uri
    artifact_sha256 = artifact_ref.sha256
    payload["metadata"]["status"] = "review"
    evidence = payload["validation_evidence"]
    evidence.pop("review_hash", None)
    evidence["trial_run_hash"] = artifact_hash
    evidence["trial_artifact_sha256"] = artifact_sha256
    evidence["trial_run_ref"] = artifact_ref.uri
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
    """Execute the registered feature mutation against a validated candidate."""
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
    plugin = FEATURE_PLUGINS.for_model(model.model_id)
    if not plugin.mutation_applies(case):
        return {"case_id": case.metadata.id, "mutation_id": plugin.mutation_id, "status": "NOT_APPLICABLE"}
    static_validate_candidate(path, model)
    case = load_query_case(path)
    payload = case.model_dump(mode="python")
    occurrences = 0
    for step in payload["steps"]:
        changed = plugin.mutated_sql(step["sql"])
        occurrences += int(changed != step["sql"])
        step["sql"] = changed
    if occurrences == 0:
        raise ValueError("CANDIDATE_MUTATION_TARGET_MISSING")
    mutated_case = QueryCaseInput.model_validate(payload)
    run = runner or run_query_case_isolated
    build_before = None
    if runner is None:
        from xgtest.runtime.profile import observe_database_build
        build_before = observe_database_build(config, runtime_profile)
    original_reports = [
        run(case, config, runtime_profile, capture_result_rows=True) if runner is None else run(case, config, runtime_profile)
        for _ in range(2)
    ]
    if any(report.status != CaseExecutionStatus.PASS for report in original_reports):
        return {"case_id": case.metadata.id, "mutation_id": plugin.mutation_id, "status": "BASELINE_NOT_PASS"}
    original = [report.model_dump(mode="json") for report in original_reports]
    original_hashes = [_mutation_result_digest(report, case, require_rows=runner is None) for report in original]
    if original_hashes[0] != original_hashes[1]:
        return {"case_id": case.metadata.id, "mutation_id": plugin.mutation_id, "status": "BASELINE_NONDETERMINISTIC"}
    mutated_reports = [
        run(mutated_case, config, runtime_profile, capture_result_rows=True) if runner is None else run(mutated_case, config, runtime_profile)
        for _ in range(2)
    ]
    build_after = observe_database_build(config, runtime_profile) if runner is None else None
    if any(report.status in {CaseExecutionStatus.ERROR, CaseExecutionStatus.TIMEOUT} for report in mutated_reports):
        return {
            "case_id": case.metadata.id,
            "mutation_id": plugin.mutation_id,
            "status": "INCONCLUSIVE",
            "original_hash": original_hashes[0],
        }
    mutated = [report.model_dump(mode="json") for report in mutated_reports]
    mutated_hashes = [_mutation_result_digest(report, case, require_rows=runner is None) for report in mutated]
    if mutated_hashes[0] != mutated_hashes[1]:
        return {"case_id": case.metadata.id, "mutation_id": plugin.mutation_id, "status": "MUTATED_NONDETERMINISTIC"}
    original_hash = original_hashes[0]
    mutated_hash = mutated_hashes[0]
    return {
        "case_id": case.metadata.id,
        "mutation_id": plugin.mutation_id,
        "status": "KILLED" if original_hash != mutated_hash else "WEAK",
        "original_hash": original_hash,
        "mutated_hash": mutated_hash,
        "execution": {
            "original_sql_sha256": xgmj1_sha256([step.sql for step in case.steps]),
            "mutated_sql_sha256": xgmj1_sha256([step.sql for step in mutated_case.steps]),
            "baseline_runs": original,
            "mutated_runs": mutated,
            "build_observations": [build_before, build_after],
        } if runner is None else None,
    }


def record_candidate_mutation_evidence(
    path: Path,
    result: dict[str, Any],
    artifact_root: Path,
    runtime_profile: dict[str, Any],
) -> dict[str, Any]:
    """Persist a mutation result and bind it to a candidate and runtime identity."""
    from xgtest.core.models import MutationEvidence, MutationValidationResult

    case = load_query_case(path)
    if case.metadata.status.value != "draft":
        raise ValueError("CANDIDATE_STATUS_INVALID: mutation evidence expects draft status")
    payload = _case_payload(path)
    semantic = semantic_hash(payload)
    if case.validation_evidence is None or case.validation_evidence.semantic_hash != semantic:
        raise ValueError("CANDIDATE_SEMANTIC_HASH_STALE")
    if result.get("case_id") != case.metadata.id:
        raise ValueError("CANDIDATE_MUTATION_CASE_ID_MISMATCH")
    checked_result = MutationValidationResult.model_validate(result)
    plugin = FEATURE_PLUGINS.for_case(case)
    if checked_result.mutation_id != plugin.mutation_id:
        raise ValueError("CANDIDATE_MUTATION_ID_UNSUPPORTED")
    requires_kill = plugin.mutation_applies(case)
    if (checked_result.status == "NOT_APPLICABLE") != (not requires_kill):
        raise ValueError("CANDIDATE_MUTATION_APPLICABILITY_MISMATCH")
    if checked_result.status == "KILLED":
        target = runtime_profile.get("identity", {}).get("target", {})
        expected_build = f"{target.get('db_build', '')} {target.get('database_version', '')}".strip() if target.get("db_build") else None
        _validate_mutation_execution(
            case, checked_result.execution, checked_result.original_hash or "", checked_result.mutated_hash or "", expected_build,
        )
    contract_id = str(build_contract_descriptor(Path(__file__).resolve().parents[3])["contract_set_id"])
    profile_id = str(runtime_profile.get("sql_runtime_profile_id", ""))
    if not re.fullmatch(r"[0-9a-f]{64}", profile_id):
        raise ValueError("CANDIDATE_RUNTIME_PROFILE_REQUIRED")
    checks = [checked_result.model_dump(mode="json", exclude={"case_id", "execution"})]
    artifact = {
        "case_id": case.metadata.id,
        "semantic_hash": semantic,
        "policy_version": "1",
        "contract_set_id": contract_id,
        "runtime_profile_id": profile_id,
        "database_build_time": runtime_profile.get("identity", {}).get("target", {}).get("db_build"),
        "database_version": runtime_profile.get("identity", {}).get("target", {}).get("database_version"),
        "checks": checks,
        "execution": checked_result.execution if checked_result.status == "KILLED" else None,
    }
    artifact_bytes = (json.dumps(artifact, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    artifact_ref = LocalArtifactStore(artifact_root).put(artifact_bytes)
    artifact_path = artifact_root / artifact_ref.uri
    artifact_sha256 = artifact_ref.sha256
    evidence = MutationEvidence.model_validate({
        "policy_version": "1",
        "semantic_hash": semantic,
        "contract_set_id": contract_id,
        "runtime_profile_id": profile_id,
        "artifact_ref": artifact_ref.uri,
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
    dry_run: bool = False,
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
    artifact_path = (artifact_root / artifact_ref).resolve()
    if not artifact_path.is_relative_to(artifact_root.resolve()):
        raise ValueError("CANDIDATE_TRIAL_ARTIFACT_REFERENCE_INVALID")
    try:
        artifact_bytes = artifact_path.read_bytes()
        artifact_payload = json.loads(artifact_bytes)
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("CANDIDATE_TRIAL_ARTIFACT_MISSING_OR_INVALID") from error
    if not isinstance(artifact_payload, dict):
        raise ValueError("CANDIDATE_TRIAL_ARTIFACT_MISSING_OR_INVALID")
    if artifact_payload.get("case_id") != case.metadata.id or artifact_payload.get("semantic_hash") != semantic or artifact_payload.get("status") != "PASS":
        raise ValueError("CANDIDATE_TRIAL_ARTIFACT_STALE")
    if hashlib.sha256(artifact_bytes).hexdigest() != evidence.trial_artifact_sha256:
        raise ValueError("CANDIDATE_TRIAL_ARTIFACT_HASH_MISMATCH")
    current_contract_set_id = build_contract_descriptor(Path(__file__).resolve().parents[3])["contract_set_id"]
    if artifact_payload.get("contract_set_id") != current_contract_set_id:
        raise ValueError("CANDIDATE_CONTRACT_SET_STALE")
    if artifact_payload.get("runtime_profile_id") != expected_runtime_profile_id:
        raise ValueError("CANDIDATE_RUNTIME_PROFILE_MISMATCH")
    trial_validation = validate_trial_artifact(
        artifact_payload,
        case_id=case.metadata.id,
        semantic_hash=semantic,
        step_ids=tuple(step.id for step in case.steps),
        step_modes={step.id: step.comparison.mode if step.comparison else "exact" for step in case.steps},
        contract_set_id=current_contract_set_id,
        runtime_profile_id=expected_runtime_profile_id,
    )
    if trial_validation["errors"]:
        raise ValueError(f"CANDIDATE_TRIAL_EVIDENCE_INVALID: {','.join(trial_validation['errors'])}")
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
    if not isinstance(mutation_payload, dict) or hashlib.sha256(mutation_bytes).hexdigest() != mutation.artifact_sha256:
        raise ValueError("CANDIDATE_MUTATION_EVIDENCE_STALE")
    if (
        mutation_payload.get("case_id") != case.metadata.id
        or mutation_payload.get("policy_version") != mutation.policy_version
        or mutation_payload.get("semantic_hash") != semantic
        or mutation_payload.get("contract_set_id") != current_contract_set_id
        or mutation_payload.get("runtime_profile_id") != expected_runtime_profile_id
        or mutation_payload.get("checks") != [check.model_dump(mode="json") for check in mutation.checks]
    ):
        raise ValueError("CANDIDATE_MUTATION_EVIDENCE_STALE")
    plugin = FEATURE_PLUGINS.for_model(model.model_id)
    applicable = [check for check in mutation.checks if check.mutation_id == plugin.mutation_id]
    requires_kill = plugin.mutation_applies(case)
    if len(applicable) != 1 or len(mutation.checks) != 1:
        raise ValueError("CANDIDATE_MUTATION_EVIDENCE_REQUIRED")
    if requires_kill and any(check.status != "KILLED" for check in applicable):
        raise ValueError("CANDIDATE_MUTATION_GATE_FAILED")
    if not requires_kill and any(check.status != "NOT_APPLICABLE" for check in applicable):
        raise ValueError("CANDIDATE_MUTATION_GATE_FAILED")
    if requires_kill:
        check = applicable[0]
        _validate_mutation_execution(
            case, mutation_payload.get("execution"), check.original_hash or "", check.mutated_hash or "",
            f"{mutation_payload.get('database_build_time', '')} {mutation_payload.get('database_version', '')}".strip() if mutation_payload.get("database_build_time") else None,
        )
    result_hash = trial_validation["trial_hash"]
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
    expected_id = plugin.expected_id(model, case.coverage[0].assignment)
    if case.metadata.id != expected_id:
        raise ValueError("CANDIDATE_ID_MISMATCH")
    static_validate_candidate(path, model)
    destination = active_dir / f"{case.metadata.id}.yaml"
    if destination.exists():
        raise ValueError(f"ACTIVE_CASE_EXISTS: {destination}")
    if dry_run:
        return destination
    active_dir.mkdir(parents=True, exist_ok=True)
    payload["metadata"]["status"] = "active"
    _write_payload(destination, payload)
    path.unlink()
    return destination
