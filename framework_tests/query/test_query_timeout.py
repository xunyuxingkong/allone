import time

import pytest

from xgtest.core.models import CaseExecutionStatus, StepStatus
from xgtest.query.loader import load_query_case
from xgtest.query.runner import _timeout_report
from xgtest.query.timeout import QueryTimeoutError, parse_timeout_seconds, supervise_worker


def _blocking_worker(channel):
    channel.send(("step_started", "slow"))
    time.sleep(5)


def _quick_worker(channel):
    channel.send(("result", {"status": "PASS"}))


def test_timeout_units_parse_to_seconds() -> None:
    assert parse_timeout_seconds("500ms") == 0.5
    assert parse_timeout_seconds("2s") == 2
    assert parse_timeout_seconds("3m") == 180
    assert parse_timeout_seconds("1h") == 3600


def test_supervisor_terminates_blocked_worker_and_next_worker_runs(tmp_path) -> None:
    with pytest.raises(QueryTimeoutError) as raised:
        supervise_worker(_blocking_worker, (), timeout_seconds=3)
    assert raised.value.current_step_id == "slow"

    assert supervise_worker(_quick_worker, (), timeout_seconds=5) == {"status": "PASS"}


def test_timeout_is_recorded_and_remaining_steps_are_skipped(tmp_path) -> None:
    source = tmp_path / "case.yaml"
    source.write_text("""metadata:
  id: QUERY.TIMEOUT.0001
  feature: query
  timeout: 10ms
steps:
  - id: first
    kind: query
    sql: SELECT 1
    comparison: {mode: exact}
    expected: {rows: [[1]]}
  - id: second
    kind: query
    sql: SELECT 2
    comparison: {mode: exact}
    expected: {rows: [[2]]}
""", encoding="utf-8")
    case = load_query_case(source)
    timeout = QueryTimeoutError(0.01, "first")
    report = _timeout_report(case, timeout, time.monotonic() - 0.01)

    assert report.status == CaseExecutionStatus.TIMEOUT
    assert report.failure_type == "INFRA_TIMEOUT"
    assert report.steps[0].status == StepStatus.TIMEOUT
    assert report.steps[1].status == StepStatus.SKIPPED
