"""Sequential single target Query Runner."""

from __future__ import annotations

import hashlib
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

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

from .loader import load_query_directory
from .result import write_query_report


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
            if isinstance(observed, dict) and observed.get("support_status") == "UNSUPPORTED":
                raise UnsupportedQueryTypeError(f"{declared_type}: runtime profile marks this type unsupported")


class QueryRunner:
    def __init__(self, session: XuguSession, runtime_profile: dict[str, Any] | None = None) -> None:
        self.session = session
        self.runtime_profile = runtime_profile

    def run_step(self, step: QueryStep) -> QueryStepReport:
        started = time.perf_counter()
        fields: dict[str, Any] = {"id": step.id, "status": StepStatus.RUNNING}
        failure_type: str | None = None
        query_succeeded = False
        try:
            expected = step.expected.model_dump(mode="python")
            if step.comparison.mode == "sha256":
                stream = self.session.query_stream(step.sql)
                query_succeeded = True
                fields.update({"columns": stream.columns, "column_types": stream.column_types, "logical_types": stream.logical_types})
                _validate_result_types(stream.column_types, stream.logical_types, self.runtime_profile)
                row_count = 0

                def counted_rows():
                    nonlocal row_count
                    for row in stream.rows:
                        row_count += 1
                        yield row

                digest = rows_sha256_stream(counted_rows(), stream.column_types, len(stream.columns))
                fields.update({"row_count": row_count, "result_sha256": digest})
                fields["status"] = StepStatus.PASS if digest == expected["sha256"] else StepStatus.FAIL
            else:
                result = self.session.query(step.sql, max_rows=MAX_MATERIALIZED_QUERY_ROWS)
                query_succeeded = True
                fields.update({"columns": result.columns, "column_types": result.column_types, "logical_types": result.logical_types})
                _validate_result_types(result.column_types, result.logical_types, self.runtime_profile)
                fields["row_count"] = len(result.rows)
                fields["result_sha256"] = rows_sha256(list(result.rows), result.column_types, len(result.columns))
                if isinstance(step.expected, ExpectedError):
                    fields["status"] = StepStatus.FAIL
                    fields["error"] = "EXPECTED_ERROR_NOT_RAISED"
                    failure_type = "ASSERTION_FAILED"
                else:
                    matches = compare_rows(
                        list(result.rows), expected, step.comparison.mode,
                        result.logical_types, len(result.columns), strict=True,
                    )
                    fields["status"] = StepStatus.PASS if matches else StepStatus.FAIL
            if fields["status"] == StepStatus.FAIL and failure_type is None:
                failure_type = "ASSERTION_FAILED"
        except Exception as error:
            details = extract_error(error)
            if isinstance(step.expected, ExpectedError) and not query_succeeded:
                matched = compare_error(error, step.expected)
                fields["status"] = StepStatus.PASS if matched else StepStatus.FAIL
                if not matched:
                    failure_type = "ASSERTION_FAILED"
            else:
                fields["status"] = StepStatus.ERROR
                failure_type = "UNSUPPORTED_TYPE" if isinstance(error, UnsupportedQueryTypeError) else "INFRA_RESOURCE"
            fields.update({
                "error_type": type(error).__name__,
                "error_code": details["code"],
                "sqlstate": details["sqlstate"],
                "error": details["message"],
            })
        fields["duration_ms"] = round((time.perf_counter() - started) * 1000, 3)
        return QueryStepReport.model_validate(fields), failure_type

    def run_case(self, case: QueryCaseInput) -> QueryCaseReport:
        started = time.perf_counter()
        reports: list[QueryStepReport] = []
        failure_types: list[str] = []
        for step in case.steps:
            report, failure_type = self.run_step(step)
            reports.append(report)
            if failure_type:
                failure_types.append(failure_type)
        if any(step.status == StepStatus.ERROR for step in reports):
            status = CaseExecutionStatus.ERROR
        elif any(step.status == StepStatus.FAIL for step in reports):
            status = CaseExecutionStatus.FAIL
        else:
            status = CaseExecutionStatus.PASS
        if status == CaseExecutionStatus.ERROR:
            failure_type = next((FailureType(value) for value in failure_types if value in {FailureType.UNSUPPORTED_TYPE.value, FailureType.INFRA_RESOURCE.value}), FailureType.INFRA_RESOURCE)
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


def run_query_cases(
    config: XuguConnectionConfig,
    case_dir: Path,
    output: Path,
    *,
    runtime_profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cases = load_query_directory(case_dir)
    profile_id = runtime_profile.get("sql_runtime_profile_id") if runtime_profile else None
    if runtime_profile is not None:
        import xgcondb

        from xgtest.runtime.profile import validate_profile

        validate_profile(runtime_profile, host=config.host, database=config.database, driver_version=tuple(xgcondb.version_info))
    root = Path(__file__).resolve().parents[3]
    contract_set_id = str(build_contract_descriptor(root)["contract_set_id"])
    started = datetime.now(UTC)
    case_reports: list[QueryCaseReport] = []
    for case in cases:
        session: XuguSession | None = None
        try:
            session = XuguSession(config).open()
            case_reports.append(QueryRunner(session, runtime_profile).run_case(case))
        except Exception as error:
            details = extract_error(error)
            case_reports.append(QueryCaseReport(
                case_id=case.metadata.id,
                status=CaseExecutionStatus.ERROR,
                failure_type="INFRA_RESOURCE",
                duration_ms=0.0,
                steps=(),
                error=f"{type(error).__name__}: {details['message']}",
            ))
        finally:
            if session is not None:
                try:
                    session.rollback_transaction()
                except Exception:
                    if case_reports and case_reports[-1].case_id == case.metadata.id:
                        case_reports[-1] = case_reports[-1].model_copy(update={"status": CaseExecutionStatus.ERROR, "failure_type": FailureType.INFRA_RESOURCE, "error": "QUERY_ROLLBACK_FAILED"})
                try:
                    session.close()
                except Exception:
                    if case_reports and case_reports[-1].case_id == case.metadata.id:
                        case_reports[-1] = case_reports[-1].model_copy(update={"status": CaseExecutionStatus.ERROR, "failure_type": FailureType.INFRA_RESOURCE, "error": "QUERY_SESSION_CLOSE_FAILED"})

    status = (
        CaseExecutionStatus.ERROR if any(case.status == CaseExecutionStatus.ERROR for case in case_reports)
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
        cases=tuple(case_reports),
        status=status,
    )
    return write_query_report(report, output)
