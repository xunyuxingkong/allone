import pytest

from xgtest.core.models import CaseExecutionStatus, QueryRunReport, StepStatus
from xgtest.query.history import QueryRunHistory


def report(run_id: str, status: CaseExecutionStatus) -> dict:
    value = QueryRunReport.model_validate_json(f"""{{
      "run_id": "{run_id}",
      "started_at": "2026-09-24T00:00:00Z",
      "finished_at": "2026-09-24T00:00:01Z",
      "target": {{"database_alias":"SYSTEM","host_hash":"{'a' * 64}","contract_set_id":"{'b' * 64}"}},
      "cases": [{{"case_id":"QUERY.HISTORY.0001","status":"{status.value}","duration_ms":1000,
        "steps":[{{"id":"q1","status":"{StepStatus.PASS.value}","duration_ms":1}}]}}],
      "status": "{status.value}"
    }}""")
    return value.model_dump(mode="json")


def test_history_records_runs_filters_pages_and_reads_case(tmp_path) -> None:
    history = QueryRunHistory(tmp_path)
    history.record(report("run-a", CaseExecutionStatus.PASS))
    history.record(report("run-b", CaseExecutionStatus.TIMEOUT))

    assert [entry["run_id"] for entry in history.list_runs()] == ["run-b", "run-a"]
    assert [entry["run_id"] for entry in history.list_runs(status="TIMEOUT")] == ["run-b"]
    assert history.list_runs(offset=1, limit=1)[0]["run_id"] == "run-a"
    assert history.get_run("run-a")["status"] == "PASS"
    assert history.get_case("run-b", "QUERY.HISTORY.0001")["status"] == "TIMEOUT"
    assert history.get_run("missing") is None


def test_history_rejects_path_traversal_and_invalid_pagination(tmp_path) -> None:
    history = QueryRunHistory(tmp_path)
    with pytest.raises(ValueError, match="RUN_ID_INVALID"):
        history.get_run("../outside")
    with pytest.raises(ValueError, match="PAGINATION_INVALID"):
        history.list_runs(offset=-1)
