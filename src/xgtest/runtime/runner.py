"""Typed bootstrap SQL runner for the diagnostic MVP path."""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from xgtest.adapter.xugu import XuguConnectionConfig, XuguSession, extract_error
from xgtest.core.models import (
    BootstrapCaseInput,
    ComparisonProfile,
    EffectiveMetadata,
    ExpectedError,
    MvpCaseReport,
    MvpRunReport,
    MvpStepReport,
    MvpTargetReport,
    RawMetadata,
    SqlStep,
    decode_expected,
)
from xgtest.generated.registry_enums import CaseAssetStatus, CaseExecutionStatus, FailureType, FeatureKey, IsolationScope, Level, StepStatus
from xgtest.core.yaml_loader import load_yaml

from .comparator import compare_affected_rows, compare_error, compare_rows, is_expected_error
from .profile import validate_profile


def _load_bootstrap_case(path: Path) -> BootstrapCaseInput:
    """Decode the bootstrap YAML once, then expose only typed models to run."""
    raw = load_yaml(path)
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: case must be a mapping")
    metadata_raw = raw.get("metadata")
    if not isinstance(metadata_raw, dict):
        raise ValueError(f"{path}: metadata must be a mapping")
    metadata_input = dict(metadata_raw)
    for field, enum_type in {
        "feature": FeatureKey,
        "level": Level,
        "status": CaseAssetStatus,
        "isolation": IsolationScope,
    }.items():
        if isinstance(metadata_input.get(field), str):
            metadata_input[field] = enum_type(metadata_input[field])
    raw_metadata = RawMetadata.model_validate(metadata_input)
    metadata = raw_metadata.model_dump(exclude_none=True, mode="python")
    case_id = metadata.get("id")
    if not isinstance(case_id, str) or not case_id:
        raise ValueError(f"{path}: metadata.id is required")
    metadata.setdefault("metadata_version", "bootstrap-1")
    metadata.setdefault("title", case_id)
    metadata.setdefault("module", "mvp")
    metadata.setdefault("level", "P1")
    metadata.setdefault("status", "active")
    metadata.setdefault("timeout", "30s")
    metadata.setdefault("isolation", "case_schema")
    metadata["feature"] = FeatureKey(metadata["feature"])
    metadata["level"] = Level(metadata["level"])
    metadata["status"] = CaseAssetStatus(metadata["status"])
    metadata["isolation"] = IsolationScope(metadata["isolation"])
    effective_metadata = EffectiveMetadata.model_validate(metadata)
    steps = raw.get("steps")
    if not isinstance(steps, list) or not steps:
        raise ValueError(f"{path}: steps must be a non-empty list")
    typed_steps: list[SqlStep] = []
    for raw_step in steps:
        if not isinstance(raw_step, dict):
            raise ValueError(f"{path}: each step must be a mapping")
        step_payload = dict(raw_step)
        comparison = step_payload.get("comparison")
        if isinstance(comparison, dict):
            step_payload["comparison"] = ComparisonProfile.model_validate(comparison)
        expected = step_payload.get("expected")
        if isinstance(expected, dict):
            step_payload["expected"] = decode_expected(expected)
        typed_steps.append(SqlStep.model_validate(step_payload))
    return BootstrapCaseInput.model_validate({"metadata": effective_metadata, "steps": tuple(typed_steps)})


def _expected_payload(step: SqlStep) -> dict[str, Any] | None:
    if step.expected is None:
        return None
    return step.expected.model_dump(mode="python")


def _execute_step(session: XuguSession, step: SqlStep) -> dict[str, Any]:
    """Execute one typed bootstrap step and return its report payload."""
    kind = str(step.kind)
    step_started = time.perf_counter()
    item: dict[str, Any] = {"id": step.id, "kind": kind, "status": "PASS"}
    expected = _expected_payload(step)
    try:
        if kind == "query":
            query_result = session.query(step.sql)
            item["columns"], item["column_types"], item["logical_types"], item["rows"] = query_result.columns, query_result.column_types, query_result.logical_types, query_result.rows
            comparison = step.comparison
            mode = comparison.mode if comparison is not None else "exact"
            item["status"] = "FAIL" if is_expected_error(step.expected) else (
                "PASS" if compare_rows(
                    list(query_result.rows), expected, mode,
                    query_result.logical_types or query_result.column_types, len(query_result.columns),
                ) else "FAIL"
            )
        else:
            item["affected_rows"] = session.execute(step.sql)
            if is_expected_error(step.expected):
                # The statement succeeded even though the asset explicitly
                # required an error.
                item["status"] = "FAIL"
            elif expected is not None:
                item["status"] = "PASS" if compare_affected_rows(item["affected_rows"], expected) else "FAIL"
    except Exception as error:
        details = extract_error(error)
        if isinstance(step.expected, ExpectedError):
            item["status"] = "PASS" if compare_error(error, step.expected) else "FAIL"
        else:
            item["status"] = "ERROR"
        item.update({
            "error_type": type(error).__name__,
            "error": details["message"],
            "error_code": details["code"],
            "sqlstate": details["sqlstate"],
        })
    item["duration_ms"] = round((time.perf_counter() - step_started) * 1000, 3)
    return item


def _skipped_step(step: SqlStep, reason: str) -> dict[str, Any]:
    return {
        "id": step.id,
        "kind": str(step.kind),
        "status": "SKIPPED",
        "duration_ms": 0.0,
        "error_type": "SetupBlocked",
        "error": reason,
    }


def _run_case(config: XuguConnectionConfig, path: Path) -> MvpCaseReport:
    case = _load_bootstrap_case(path)
    session = XuguSession(config).open()
    started = time.perf_counter()
    results: list[dict[str, Any]] = []
    case_status = "PASS"
    setup_failed = False
    setup_steps = [step for step in case.steps if str(step.kind) == "setup"]
    main_steps = [step for step in case.steps if str(step.kind) in {"statement", "query"}]
    cleanup_steps = [step for step in case.steps if str(step.kind) == "cleanup"]
    try:
        for index, step in enumerate(setup_steps):
            item = _execute_step(session, step)
            results.append(item)
            if item["status"] != "PASS":
                setup_failed = True
                case_status = "ERROR" if item["status"] == "ERROR" else "FAIL"
                for remaining in setup_steps[index + 1:]:
                    results.append(_skipped_step(remaining, "setup phase failed"))
                break
        if setup_failed:
            for step in main_steps:
                results.append(_skipped_step(step, "setup phase failed"))
        else:
            for step in main_steps:
                item = _execute_step(session, step)
                results.append(item)
                if item["status"] != "PASS":
                    case_status = "ERROR" if item["status"] == "ERROR" else "FAIL"
        # Preserve the business result before cleanup can change the final
        # outcome. Cleanup remains an independent phase.
        primary_status = CaseExecutionStatus(case_status)
        for step in cleanup_steps:
            item = _execute_step(session, step)
            results.append(item)
            if item["status"] != "PASS":
                case_status = "ERROR" if item["status"] == "ERROR" else "FAIL"
    finally:
        recovery_errors: list[str] = []
        try:
            session.rollback_transaction()
        except Exception as error:
            recovery_errors.append(f"{type(error).__name__}: {error}")
        try:
            session.close()
        except Exception as error:
            recovery_errors.append(f"{type(error).__name__}: {error}")
    cleanup_results = [item for item in results if item["kind"] == "cleanup"]
    cleanup_status = "PASS" if all(item["status"] == "PASS" for item in cleanup_results) else "FAILED"
    recovery_status = "FAILED" if recovery_errors else "PASS"
    if cleanup_status == "FAILED" or recovery_status == "FAILED":
        final_status = CaseExecutionStatus.ERROR
    else:
        final_status = primary_status
    if cleanup_status == "FAILED":
        failure_type: FailureType | None = FailureType.FIXTURE_CLEANUP
    elif recovery_status == "FAILED":
        failure_type = FailureType.INFRA_RESOURCE
    elif setup_failed:
        failure_type = FailureType.FIXTURE_SETUP
    elif primary_status == CaseExecutionStatus.FAIL:
        failure_type = FailureType.ASSERTION_FAILED
    elif primary_status == CaseExecutionStatus.ERROR:
        failure_type = FailureType.INFRA_RESOURCE
    else:
        failure_type = None
    return MvpCaseReport(
        case_id=case.metadata.id,
        status=final_status,
        primary_status=primary_status,
        cleanup_status=cleanup_status,
        recovery_status=recovery_status,
        failure_type=failure_type,
        duration_ms=round((time.perf_counter() - started) * 1000, 3),
        steps=tuple(
            MvpStepReport.model_validate({**item, "status": StepStatus(item["status"])})
            for item in results
        ),
    )


def run_cases(
    config: XuguConnectionConfig,
    case_dir: Path,
    output: Path,
    sql_runtime_profile_id: str | None = None,
    runtime_profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    paths = sorted(case_dir.glob("*.yaml"))
    if not paths:
        raise ValueError(f"no YAML cases found under {case_dir}")
    if runtime_profile is not None:
        import xgcondb
        validate_profile(runtime_profile, host=config.host, database=config.database, driver_version=tuple(xgcondb.version_info))
        sql_runtime_profile_id = runtime_profile["sql_runtime_profile_id"]
    started = datetime.now(UTC)
    results: list[MvpCaseReport] = []
    for path in paths:
        try:
            results.append(_run_case(config, path))
        except Exception as error:
            results.append(MvpCaseReport(
                case_id=path.stem,
                status=CaseExecutionStatus.ERROR,
                primary_status=CaseExecutionStatus.ERROR,
                cleanup_status="FAILED",
                recovery_status="FAILED",
                failure_type=FailureType.INFRA_RESOURCE,
                duration_ms=0.0,
                steps=(),
                error=f"{type(error).__name__}: {error}",
            ))
    report = MvpRunReport(
        run_id=uuid.uuid4().hex,
        started_at=started,
        finished_at=datetime.now(UTC),
        target=MvpTargetReport(
            database_alias=config.database,
            host_hash=hashlib.sha256(config.host.encode()).hexdigest(),
            sql_runtime_profile_id=sql_runtime_profile_id,
        ),
        cases=tuple(results),
        status=CaseExecutionStatus.PASS if all(item.status == "PASS" for item in results) else CaseExecutionStatus.FAIL,
    )
    serialized = report.model_dump(mode="json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(serialized, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return serialized
