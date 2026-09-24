"""Serialization and schema boundary for Query Run reports."""

import json
import copy
from datetime import UTC, datetime
from pathlib import Path

import jsonschema
import pytest

from xgtest.core.models import (
    CaseExecutionStatus,
    QueryCaseReport,
    QueryRunReport,
    QueryStepReport,
    QueryTargetReport,
    StepStatus,
)


ROOT = Path(__file__).resolve().parents[2]


def test_query_report_serializes_without_result_rows_and_round_trips(tmp_path) -> None:
    report = QueryRunReport(
        run_id="run-1",
        started_at=datetime(2026, 9, 24, tzinfo=UTC),
        finished_at=datetime(2026, 9, 24, tzinfo=UTC),
        target=QueryTargetReport(
            database_alias="SYSTEM",
            host_hash="a" * 64,
            contract_set_id="b" * 64,
        ),
        cases=(QueryCaseReport(
            case_id="QUERY.RESULT.0001",
            status=CaseExecutionStatus.PASS,
            duration_ms=1,
            steps=(QueryStepReport(
                id="q1",
                status=StepStatus.PASS,
                duration_ms=1,
                columns=("VALUE",),
                column_types=("INTEGER",),
                logical_types=("int",),
                row_count=1,
                result_sha256="c" * 64,
            ),),
        ),),
        status=CaseExecutionStatus.PASS,
    )
    output = tmp_path / "report.json"
    output.write_text(json.dumps(report.model_dump(mode="json")), encoding="utf-8")

    payload = json.loads(output.read_text(encoding="utf-8"))
    restored = QueryRunReport.model_validate_json(output.read_bytes())
    assert restored == report
    assert "rows" not in payload["cases"][0]["steps"][0]


def test_query_report_schema_matches_model_export() -> None:
    expected = QueryRunReport.model_json_schema()
    expected["$id"] = "xgtest://schema/1.1/QueryRunReport"
    expected["x-xg-contract-version"] = "1.1"
    schema_path = ROOT / "schemas" / "QueryRunReport.schema.json"
    actual = json.loads(schema_path.read_text(encoding="utf-8"))
    assert actual == expected
    assert "rows" not in actual["$defs"]["QueryStepReport"]["properties"]


def test_query_report_json_schema_accepts_valid_report_and_rejects_rows(tmp_path) -> None:
    report = QueryRunReport(
        run_id="run-1",
        started_at=datetime(2026, 9, 24, tzinfo=UTC),
        finished_at=datetime(2026, 9, 24, tzinfo=UTC),
        target=QueryTargetReport(database_alias="SYSTEM", host_hash="a" * 64, contract_set_id="b" * 64),
        cases=(QueryCaseReport(
            case_id="QUERY.RESULT.0001",
            status=CaseExecutionStatus.PASS,
            duration_ms=1,
            steps=(QueryStepReport(id="q1", status=StepStatus.PASS, duration_ms=1),),
        ),),
        status=CaseExecutionStatus.PASS,
    )
    payload = report.model_dump(mode="json")
    schema = json.loads((ROOT / "schemas" / "QueryRunReport.schema.json").read_text(encoding="utf-8"))
    jsonschema.validate(payload, schema)

    invalid_payload = copy.deepcopy(payload)
    invalid_payload["cases"][0]["steps"][0]["rows"] = [["should not be serialized"]]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(invalid_payload, schema)
