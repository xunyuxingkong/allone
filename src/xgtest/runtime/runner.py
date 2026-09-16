"""YAML case loader and single-process SQL MVP runner."""

from __future__ import annotations

import hashlib
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from xgtest.adapter.xugu import XuguConnectionConfig, XuguSession, extract_error
from xgtest.core.yaml_loader import load_yaml
from xgtest.core.models import MvpCaseReport, MvpRunReport, MvpStepReport
from .comparator import compare_affected_rows, compare_error, compare_rows
from .profile import validate_profile


def _case_id(case: dict[str, Any], path: Path) -> str:
    metadata = case.get("metadata", case)
    value = metadata.get("id") if isinstance(metadata, dict) else None
    if not isinstance(value, str) or not value:
        raise ValueError(f"{path}: metadata.id is required")
    return value


def _run_case(config: XuguConnectionConfig, path: Path) -> MvpCaseReport:
    raw = load_yaml(path)
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: case must be a mapping")
    case_id = _case_id(raw, path)
    steps = raw.get("steps")
    if not isinstance(steps, list) or not steps:
        raise ValueError(f"{path}: steps must be a non-empty list")
    session = XuguSession(config).open()
    started = time.perf_counter()
    results: list[dict[str, Any]] = []
    case_status = "PASS"
    try:
        for step in steps:
            if not isinstance(step, dict):
                raise ValueError(f"{path}: each step must be a mapping")
            step_id, kind, sql = step.get("id"), step.get("kind"), step.get("sql")
            if not all(isinstance(value, str) and value for value in (step_id, kind, sql)):
                raise ValueError(f"{path}: step requires id, kind and sql")
            step_started = time.perf_counter()
            item: dict[str, Any] = {"id": step_id, "kind": kind, "status": "PASS"}
            try:
                if kind == "query":
                    query_result = session.query(sql)
                    item["columns"], item["column_types"], item["rows"] = query_result.columns, query_result.column_types, query_result.rows
                    comparison = step.get("comparison") or {}
                    item["status"] = "PASS" if compare_rows(list(query_result.rows), step.get("expected"), comparison.get("mode", "exact")) else "FAIL"
                else:
                    item["affected_rows"] = session.execute(sql)
                    expected = step.get("expected")
                    if expected is not None:
                        item["status"] = "PASS" if compare_affected_rows(item["affected_rows"], expected) else "FAIL"
                if item["status"] != "PASS":
                    case_status = "FAIL"
            except Exception as error:
                details = extract_error(error)
                item.update({
                    "status": "PASS" if compare_error(error, step.get("expected")) else "ERROR",
                    "error_type": type(error).__name__,
                    "error": details["message"],
                    "error_code": details["code"],
                    "sqlstate": details["sqlstate"],
                })
                if item["status"] != "PASS":
                    case_status = "ERROR"
            item["duration_ms"] = round((time.perf_counter() - step_started) * 1000, 3)
            results.append(item)
    finally:
        try:
            session.rollback()
        finally:
            session.close()
    cleanup_steps = [item for item in results if item["kind"] == "cleanup"]
    cleanup_status = "PASS" if all(item["status"] == "PASS" for item in cleanup_steps) else "FAILED"
    if cleanup_status == "FAILED":
        case_status = "ERROR"
    report = MvpCaseReport(
        case_id=case_id,
        status=case_status,
        cleanup_status=cleanup_status,
        duration_ms=round((time.perf_counter() - started) * 1000, 3),
        steps=tuple(MvpStepReport.model_validate(item) for item in results),
    )
    return report


def run_cases(config: XuguConnectionConfig, case_dir: Path, output: Path, sql_runtime_profile_id: str | None = None, runtime_profile: dict[str, Any] | None = None) -> dict[str, Any]:
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
                status="ERROR",
                cleanup_status="FAILED",
                duration_ms=0.0,
                steps=(),
                error=f"{type(error).__name__}: {error}",
            ))
    report = MvpRunReport(
        run_id=hashlib.sha256(started.isoformat().encode()).hexdigest()[:16],
        started_at=started,
        finished_at=datetime.now(UTC),
        target={
            "database_alias": config.database,
            "host_hash": hashlib.sha256(config.host.encode()).hexdigest(),
            **({"sql_runtime_profile_id": sql_runtime_profile_id} if sql_runtime_profile_id else {}),
        },
        cases=tuple(results),
        status="PASS" if all(item.status == "PASS" for item in results) else "FAIL",
    )
    serialized = report.model_dump(mode="json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(serialized, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return serialized
