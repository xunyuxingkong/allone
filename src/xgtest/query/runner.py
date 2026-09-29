"""Sequential single target Query Runner."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from multiprocessing.connection import Connection
from typing import Any, Callable, Literal

from xgtest.adapter.xugu import XuguConnectionConfig, XuguSession, extract_error
from xgtest.core.contract_set import build_contract_descriptor
from xgtest.core.logical_types import query_type_support
from xgtest.core.models import (
    CaseExecutionStatus,
    ExpectedError,
    QueryCaseInput,
    QueryCaseReport,
    QueryRunReport,
    QueryStep,
    QueryStepReport,
    QueryTargetReport,
    StepStatus,
)
from xgtest.runtime.comparator import (
    UnsupportedQueryTypeError,
    compare_error,
    compare_rows,
    rows_sha256,
    rows_sha256_stream,
)
from xgtest.generated.registry_enums import FailureType

from .loader import load_query_directory_with_sources
from .history import QueryRunHistory
from .result import write_query_report
from .timeout import QueryTimeoutError, QueryWorkerError, parse_timeout_seconds, supervise_worker


MAX_MATERIALIZED_QUERY_ROWS = 10_000


def _validate_result_types(
    column_types: tuple[str | None, ...],
    logical_types: tuple[str | None, ...],
    runtime_profile: dict[str, Any] | None = None,
) -> None:
    if len(column_types) != len(logical_types):
        raise ValueError("QUERY_COLUMN_METADATA_INVALID: driver type metadata width mismatch")
    for declared_type, observed_logical_type in zip(column_types, logical_types):
        expected_logical_type, supported = query_type_support(declared_type)
        if not supported or expected_logical_type is None:
            raise UnsupportedQueryTypeError(str(declared_type))
        if observed_logical_type != expected_logical_type:
            raise UnsupportedQueryTypeError(f"{declared_type}: inconsistent logical type mapping")
        if runtime_profile is not None:
            identity = runtime_profile.get("identity", {})
            capabilities = identity.get("capabilities", {}) if isinstance(identity, dict) else {}
            mappings = capabilities.get("type_mapping", {}) if isinstance(capabilities, dict) else {}
            base = str(declared_type).lower().split("(", 1)[0].strip()
            observed = mappings.get(base) if isinstance(mappings, dict) else None
            if not isinstance(observed, dict) and isinstance(mappings, dict):
                observed = mappings.get(expected_logical_type)
            if (
                not isinstance(observed, dict)
                or observed.get("support_status") != "SUPPORTED"
                or observed.get("mapping_fidelity") != "EXACT"
                or observed.get("canonical_encoding") != "VERIFIED"
                or observed.get("logical_type") != expected_logical_type
            ):
                raise UnsupportedQueryTypeError(
                    f"{declared_type}: runtime profile lacks verified exact type-mapping evidence"
                )


class QueryRunner:
    def __init__(
        self,
        session: XuguSession,
        runtime_profile: dict[str, Any] | None = None,
        *,
        observer: Callable[[tuple[str, Any]], None] | None = None,
        capture_result_rows: bool = False,
    ) -> None:
        if isinstance(session, XuguSession) and not session.read_only:
            raise RuntimeError("QUERY_SESSION_NOT_READ_ONLY")
        self.session = session
        self.runtime_profile = runtime_profile
        self.observer = observer
        self.capture_result_rows = capture_result_rows

    def run_step(self, step: QueryStep) -> tuple[QueryStepReport, FailureType | None]:
        started = time.perf_counter()
        if self.observer is not None:
            self.observer(("step_started", step.id))
        fields: dict[str, Any] = {"id": step.id, "status": StepStatus.RUNNING}
        failure_type: FailureType | None = None
        query_succeeded = False
        try:
            expected = step.expected.model_dump(mode="python")
            if step.comparison.mode == "sha256":
                stream = self.session.query_stream(step.sql)
                query_succeeded = True
                fields.update({"columns": stream.columns, "column_types": stream.column_types, "logical_types": stream.logical_types})
                _validate_result_types(stream.column_types, stream.logical_types, self.runtime_profile)
                row_count = 0
                captured_rows: list[tuple[Any, ...]] = []

                def counted_rows():
                    nonlocal row_count
                    for row in stream.rows:
                        row_count += 1
                        if self.capture_result_rows:
                            captured_rows.append(tuple(row))
                        yield row

                digest = rows_sha256_stream(counted_rows(), stream.column_types, len(stream.columns))
                fields.update({"row_count": row_count, "result_sha256": digest})
                if self.capture_result_rows:
                    fields["result_rows"] = tuple(captured_rows)
                fields["status"] = StepStatus.PASS if digest == expected["sha256"] else StepStatus.FAIL
            else:
                result = self.session.query(step.sql, max_rows=MAX_MATERIALIZED_QUERY_ROWS)
                query_succeeded = True
                fields.update({"columns": result.columns, "column_types": result.column_types, "logical_types": result.logical_types})
                _validate_result_types(result.column_types, result.logical_types, self.runtime_profile)
                fields["row_count"] = len(result.rows)
                fields["result_sha256"] = rows_sha256(list(result.rows), result.column_types, len(result.columns))
                if self.capture_result_rows:
                    fields["result_rows"] = tuple(tuple(row) for row in result.rows)
                if isinstance(step.expected, ExpectedError):
                    fields["status"] = StepStatus.FAIL
                    fields["error"] = "EXPECTED_ERROR_NOT_RAISED"
                    failure_type = FailureType.ASSERTION_FAILED
                else:
                    matches = compare_rows(
                        list(result.rows), expected, step.comparison.mode,
                        result.logical_types, len(result.columns), strict=True,
                    )
                    fields["status"] = StepStatus.PASS if matches else StepStatus.FAIL
            if fields["status"] == StepStatus.FAIL and failure_type is None:
                failure_type = FailureType.ASSERTION_FAILED
        except Exception as error:
            details = extract_error(error)
            if isinstance(step.expected, ExpectedError) and not query_succeeded:
                matched = compare_error(error, step.expected)
                fields["status"] = StepStatus.PASS if matched else StepStatus.FAIL
                if not matched:
                    failure_type = FailureType.ASSERTION_FAILED
            else:
                fields["status"] = StepStatus.ERROR
                failure_type = FailureType.UNSUPPORTED_TYPE if isinstance(error, UnsupportedQueryTypeError) else FailureType.INFRA_RESOURCE
            fields.update({
                "error_type": type(error).__name__,
                "error_code": details["code"],
                "sqlstate": details["sqlstate"],
                "error": details["message"],
            })
        fields["duration_ms"] = round((time.perf_counter() - started) * 1000, 3)
        report = QueryStepReport.model_validate(fields)
        if self.observer is not None:
            self.observer(("step_completed", report.model_dump(mode="json")))
        return report, failure_type

    def run_case(self, case: QueryCaseInput) -> QueryCaseReport:
        started = time.perf_counter()
        reports: list[QueryStepReport] = []
        failure_types: list[FailureType] = []
        for step in case.steps:
            report, failure_type = self.run_step(step)
            reports.append(report)
            if failure_type is not None:
                failure_types.append(failure_type)
        if any(step.status == StepStatus.ERROR for step in reports):
            status = CaseExecutionStatus.ERROR
        elif any(step.status == StepStatus.FAIL for step in reports):
            status = CaseExecutionStatus.FAIL
        else:
            status = CaseExecutionStatus.PASS
        if status == CaseExecutionStatus.ERROR:
            failure_type = next((value for value in failure_types if value in {FailureType.UNSUPPORTED_TYPE, FailureType.INFRA_RESOURCE}), FailureType.INFRA_RESOURCE)
        elif status == CaseExecutionStatus.FAIL:
            failure_type = FailureType.ASSERTION_FAILED
        else:
            failure_type = None
        return QueryCaseReport(
            case_id=case.metadata.id,
            status=status,
            failure_type=failure_type,
            duration_ms=round((time.perf_counter() - started) * 1000, 3),
            steps=tuple(reports),
        )


def _case_worker(
    case_payload: dict[str, Any],
    config_payload: dict[str, str],
    runtime_profile: dict[str, Any] | None,
    capture_result_rows: bool,
    channel: Connection,
) -> None:
    """Child-process entry point. A terminated worker owns and loses its session."""
    case = QueryCaseInput.model_validate_json(json.dumps(case_payload))
    config = XuguConnectionConfig(**config_payload)
    session: XuguSession | None = None
    try:
        session = XuguSession(config).open(read_only=True)
        report = _run_case_on_session(
            case,
            session,
            runtime_profile,
            observer=lambda event: channel.send(event),
            capture_result_rows=capture_result_rows,
        )
        session = None
        channel.send(("result", report.model_dump(mode="json")))
    except Exception as error:
        details = extract_error(error)
        channel.send(("fatal", type(error).__name__, details["message"] or "query worker failed"))
    finally:
        if session is not None:
            try:
                session.close()
            except Exception:
                pass
        channel.close()


def _timeout_report(case: QueryCaseInput, timeout: QueryTimeoutError, started: float) -> QueryCaseReport:
    completed = [QueryStepReport.model_validate_json(json.dumps(value)) for value in timeout.completed_steps]
    completed_ids = {step.id for step in completed}
    active_id = timeout.current_step_id
    now_ms = max(0.0, (time.monotonic() - started) * 1000)
    reports = list(completed)
    for step in case.steps:
        if step.id in completed_ids:
            continue
        if step.id == active_id:
            reports.append(QueryStepReport(
                id=step.id,
                status=StepStatus.TIMEOUT,
                duration_ms=round(now_ms, 3),
                error_type="QueryTimeoutError",
                error="QUERY_TIMEOUT",
            ))
        else:
            reports.append(QueryStepReport(id=step.id, status=StepStatus.SKIPPED, duration_ms=0.0))
    return QueryCaseReport(
        case_id=case.metadata.id,
        status=CaseExecutionStatus.TIMEOUT,
        failure_type=FailureType.INFRA_TIMEOUT,
        duration_ms=round(now_ms, 3),
        steps=tuple(reports),
        error="QUERY_TIMEOUT",
    )


def _run_case_on_session(
    case: QueryCaseInput,
    session: XuguSession,
    runtime_profile: dict[str, Any] | None,
    *,
    observer: Callable[[tuple[str, Any]], None] | None = None,
    capture_result_rows: bool = False,
) -> QueryCaseReport:
    try:
        report = QueryRunner(
            session,
            runtime_profile,
            observer=observer,
            capture_result_rows=capture_result_rows,
        ).run_case(case)
    except Exception as error:
        details = extract_error(error)
        report = QueryCaseReport(
            case_id=case.metadata.id,
            status=CaseExecutionStatus.ERROR,
            failure_type=FailureType.INFRA_RESOURCE,
            duration_ms=0.0,
            steps=(),
            error=details["message"],
        )
    try:
        session.rollback_transaction()
    except Exception:
        report = report.model_copy(update={
            "status": CaseExecutionStatus.ERROR,
            "failure_type": FailureType.INFRA_RESOURCE,
            "error": "QUERY_ROLLBACK_FAILED",
        })
    try:
        session.close()
    except Exception:
        report = report.model_copy(update={
            "status": CaseExecutionStatus.ERROR,
            "failure_type": FailureType.INFRA_RESOURCE,
            "error": "QUERY_SESSION_CLOSE_FAILED",
        })
    return report


def run_query_case_isolated(
    case: QueryCaseInput,
    config: XuguConnectionConfig,
    runtime_profile: dict[str, Any] | None,
    *,
    capture_result_rows: bool = False,
) -> QueryCaseReport:
    started = time.monotonic()
    try:
        payload = supervise_worker(
            _case_worker,
            (case.model_dump(mode="json"), config.__dict__, runtime_profile, capture_result_rows),
            timeout_seconds=parse_timeout_seconds(case.metadata.timeout),
        )
        return QueryCaseReport.model_validate_json(json.dumps(payload))
    except QueryTimeoutError as timeout:
        return _timeout_report(case, timeout, started)
    except QueryWorkerError as error:
        return QueryCaseReport(
            case_id=case.metadata.id,
            status=CaseExecutionStatus.ERROR,
            failure_type=FailureType.INFRA_RESOURCE,
            duration_ms=round((time.monotonic() - started) * 1000, 3),
            steps=(),
            error=str(error),
        )


def run_query_cases(
    config: XuguConnectionConfig,
    case_dir: Path,
    output: Path,
    *,
    runtime_profile: dict[str, Any] | None = None,
    mode: Literal["diagnostic", "regression"] = "regression",
) -> dict[str, Any]:
    assets = load_query_directory_with_sources(case_dir)
    cases = tuple(asset.case for asset in assets)
    if mode not in {"diagnostic", "regression"}:
        raise ValueError("QUERY_RUN_MODE_INVALID")
    if mode == "regression" and runtime_profile is None:
        raise ValueError("RUNTIME_PROFILE_REQUIRED_FOR_REGRESSION")
    root = Path(__file__).resolve().parents[3]
    contract_set_id = str(build_contract_descriptor(root)["contract_set_id"])
    profile_id = runtime_profile.get("sql_runtime_profile_id") if runtime_profile else None
    if runtime_profile is not None:
        import xgcondb

        from xgtest.runtime.profile import validate_profile

        validate_profile(
            runtime_profile,
            host=config.host,
            database=config.database,
            driver_version=tuple(xgcondb.version_info),
            contract_set_id=contract_set_id if mode == "regression" else None,
        )
    started = datetime.now(UTC)
    case_reports: list[QueryCaseReport] = []
    for asset in assets:
        case_report = run_query_case_isolated(asset.case, config, runtime_profile)
        case_reports.append(case_report.model_copy(update={
            "title": asset.case.metadata.title,
            "feature": asset.case.metadata.feature.value,
            "tags": asset.case.metadata.tags,
            "source_file": asset.source.relative_path,
            "case_source_hash": asset.source.source_hash,
        }))

    status = (
        CaseExecutionStatus.TIMEOUT if any(case.status == CaseExecutionStatus.TIMEOUT for case in case_reports)
        else CaseExecutionStatus.ERROR if any(case.status == CaseExecutionStatus.ERROR for case in case_reports)
        else CaseExecutionStatus.FAIL if any(case.status == CaseExecutionStatus.FAIL for case in case_reports)
        else CaseExecutionStatus.PASS
    )
    report = QueryRunReport(
        run_id=uuid.uuid4().hex,
        started_at=started,
        finished_at=datetime.now(UTC),
        target=QueryTargetReport(
            database_alias=config.database,
            host_hash=hashlib.sha256(config.host.encode()).hexdigest(),
            sql_runtime_profile_id=profile_id,
            contract_set_id=contract_set_id,
        ),
        git_commit=_git_commit(root),
        cases=tuple(case_reports),
        status=status,
    )
    payload = write_query_report(report, output)
    QueryRunHistory(Path(output).parent).record(payload)
    return payload


def _git_commit(root: Path) -> str | None:
    supplied = os.environ.get("XGTEST_GIT_COMMIT", "").strip()
    if re.fullmatch(r"[0-9a-f]{40,64}", supplied):
        return supplied
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    commit = result.stdout.strip()
    return commit if len(commit) in {40, 64} else None
