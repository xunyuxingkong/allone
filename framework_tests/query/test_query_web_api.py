import json
import asyncio
from datetime import UTC, datetime
from pathlib import Path

import httpx

from xgtest.core.models import (
    CaseExecutionStatus,
    QueryCaseReport,
    QueryRunReport,
    QueryStepReport,
    QueryTargetReport,
    StepStatus,
)
from xgtest.query.history import QueryRunHistory
from xgtest.query.loader import load_query_directory_with_sources
from xgtest.runtime.profile import build_profile
from xgtest.web.app import create_app
from xgtest.web.service import QueryReadService


def api_get(app, path: str, params: dict | None = None) -> httpx.Response:
    async def request() -> httpx.Response:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            return await client.get(path, params=params)
    return asyncio.run(request())


def test_read_only_api_exposes_runs_case_source_runtime_and_no_secrets(tmp_path: Path) -> None:
    cases_dir = tmp_path / "cases"
    cases_dir.mkdir()
    case_text = """metadata:
  id: QUERY.WEB.JOIN
  title: join example
  feature: join
  tags: [integration]
steps:
  - id: q1
    kind: query
    sql: SELECT 1
    comparison: {mode: exact}
    expected: {rows: [[1]]}
"""
    (cases_dir / "join.yaml").write_text(case_text, encoding="utf-8")
    asset = load_query_directory_with_sources(cases_dir)[0]
    run_report = QueryRunReport(
        run_id="run-web-1",
        started_at=datetime(2026, 9, 24, tzinfo=UTC),
        finished_at=datetime(2026, 9, 24, tzinfo=UTC),
        target=QueryTargetReport(database_alias="SYSTEM", host_hash="a" * 64, contract_set_id="b" * 64),
        git_commit="c" * 40,
        cases=(QueryCaseReport(
            case_id=asset.case.metadata.id,
            title=asset.case.metadata.title,
            feature=asset.case.metadata.feature.value,
            tags=asset.case.metadata.tags,
            source_file=asset.source.relative_path,
            case_source_hash=asset.source.source_hash,
            status=CaseExecutionStatus.PASS,
            duration_ms=1,
            steps=(QueryStepReport(id="q1", status=StepStatus.PASS, duration_ms=1),),
        ),),
        status=CaseExecutionStatus.PASS,
    ).model_dump(mode="json")
    runs_dir = tmp_path / "runs"
    QueryRunHistory(runs_dir).record(run_report)
    profile_path = tmp_path / "runtime-profile.json"
    profile = build_profile({
        "target": {"host_hash": "a" * 64, "database_alias": "SYSTEM"},
        "driver": {"module": "xgcondb", "version": [2, 3, 9]},
        "contract_set_id": "b" * 64,
        "capabilities": {"type_mapping": {"integer": {
            "mapping_fidelity": "EXACT",
            "canonical_encoding": "VERIFIED",
            "support_status": "SUPPORTED",
            "logical_type": "int",
        }}},
    })
    profile_path.write_text(json.dumps(profile), encoding="utf-8")
    service = QueryReadService(runs_dir, cases_dir, profile_path=profile_path, project_root=Path(__file__).resolve().parents[2])
    app = create_app(service)

    assert api_get(app, "/api/health").json() == {"status": "ok"}
    runs_response = api_get(app, "/api/runs")
    assert runs_response.status_code == 200, runs_response.text
    assert runs_response.json()["items"][0]["run_id"] == "run-web-1"
    run = api_get(app, "/api/runs/run-web-1").json()
    assert run["target"]["database_alias"] == "SYSTEM"
    assert api_get(app, "/api/runs/run-web-1/cases", {"feature": "join"}).json()["total"] == 1
    assert api_get(app, "/api/runs/run-web-1/cases", {"sort_by": "duration_ms", "sort_dir": "desc"}).status_code == 200
    assert api_get(app, "/api/runs/run-web-1/cases", {"sort_by": "unknown"}).status_code == 400
    detail = api_get(app, "/api/runs/run-web-1/cases/QUERY.WEB.JOIN").json()
    assert detail["source_available"] is True
    assert detail["case_definition"]["steps"][0]["sql"] == "SELECT 1"
    assert api_get(app, "/api/runtime/profile").json()["sql_runtime_profile_id"] == profile["sql_runtime_profile_id"]
    assert api_get(app, "/api/runtime/types").json()["items"][0]["driver_type"] == "integer"
    assert api_get(app, "/api/runtime/types").json()["items"][0]["logical_type"] == "int"
    assert api_get(app, "/api/runtime/contract").json()["contract_set_id"]
    assert "password" not in api_get(app, "/api/runtime/profile").text.lower()


def test_case_api_does_not_show_modified_source_as_original(tmp_path: Path) -> None:
    cases_dir = tmp_path / "cases"
    cases_dir.mkdir()
    source = cases_dir / "case.yaml"
    source.write_text("""metadata:
  id: QUERY.WEB.SOURCE
  feature: query
steps:
  - id: q1
    kind: query
    sql: SELECT 1
    comparison: {mode: exact}
    expected: {rows: [[1]]}
""", encoding="utf-8")
    asset = load_query_directory_with_sources(cases_dir)[0]
    history_report = QueryRunReport(
        run_id="run-web-2",
        started_at=datetime(2026, 9, 24, tzinfo=UTC),
        finished_at=datetime(2026, 9, 24, tzinfo=UTC),
        target=QueryTargetReport(database_alias="SYSTEM", host_hash="a" * 64, contract_set_id="b" * 64),
        cases=(QueryCaseReport(
            case_id=asset.case.metadata.id,
            source_file=asset.source.relative_path,
            case_source_hash=asset.source.source_hash,
            status=CaseExecutionStatus.PASS,
            duration_ms=1,
            steps=(),
        ),),
        status=CaseExecutionStatus.PASS,
    ).model_dump(mode="json")
    history = QueryRunHistory(tmp_path / "runs")
    history.record(history_report)
    source.write_text(source.read_text(encoding="utf-8").replace("SELECT 1", "SELECT 2"), encoding="utf-8")
    app = create_app(QueryReadService(tmp_path / "runs", cases_dir))
    detail_response = api_get(app, "/api/runs/run-web-2/cases/QUERY.WEB.SOURCE")
    assert detail_response.status_code == 200, detail_response.text
    detail = detail_response.json()
    assert detail["source_available"] is False
    assert detail["case_definition"] is None
