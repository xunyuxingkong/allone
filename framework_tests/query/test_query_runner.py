from types import SimpleNamespace

import pytest

from xgtest.adapter.xugu import XuguConnectionConfig, XuguQueryResult
from xgtest.core.models import ExpectedError
from xgtest.query.loader import load_query_case
from xgtest.query.runner import QueryRunner, run_query_cases
from xgtest.runtime.comparator import rows_sha256


def case(tmp_path, mode="exact", expected="rows:\n        - [1]", sql="SELECT 1"):
    path = tmp_path / "case.yaml"
    path.write_text(f"""metadata:
  id: QUERY.RUNNER.0001
  title: query runner test
  feature: query
steps:
  - id: q1
    kind: query
    sql: {sql}
    comparison:
      mode: {mode}
    expected:
      {expected}
""", encoding="utf-8")
    return load_query_case(path)


class FakeSession:
    def __init__(self, rows=((1,),), types=("INTEGER",), error=None):
        self.rows = tuple(rows)
        self.types = tuple(types)
        self.error = error
        self.queries = []

    def query(self, sql, max_rows=None):
        self.queries.append(sql)
        if self.error:
            raise self.error
        return XuguQueryResult(("VALUE",), self.types, self.rows, ("int",))

    def query_stream(self, sql):
        self.queries.append(sql)
        if self.error:
            raise self.error
        return SimpleNamespace(columns=("VALUE",), column_types=self.types, logical_types=("int",), rows=iter(self.rows))


def test_exact_pass_and_fail_have_result_summary(tmp_path) -> None:
    report = QueryRunner(FakeSession()).run_case(case(tmp_path))
    assert report.status == "PASS"
    assert report.steps[0].row_count == 1
    assert len(report.steps[0].result_sha256) == 64
    mismatch = case(tmp_path, expected="rows:\n        - [2]")
    assert QueryRunner(FakeSession()).run_case(mismatch).status == "FAIL"


def test_rowsort_and_streaming_sha256_use_xgc1(tmp_path) -> None:
    rows = ((2,), (1,))
    row_case = case(tmp_path, "rowsort", "rows:\n        - [1]\n        - [2]")
    assert QueryRunner(FakeSession(rows)).run_case(row_case).status == "PASS"
    digest = rows_sha256([(1,), (2,)], ("INTEGER",), 1)
    hash_case = case(tmp_path, "sha256", f"sha256: {digest}")
    report = QueryRunner(FakeSession(((1,), (2,)))).run_case(hash_case)
    assert report.status == "PASS"
    assert report.steps[0].result_sha256 == digest


def test_expected_error_and_unexpected_error_statuses(tmp_path) -> None:
    class DatabaseError(Exception):
        code = "E5021"

    expected = case(tmp_path, "expected_error", "code: E5021", "SELECT * FROM MISSING_XGT_QUERY_MVP")
    assert QueryRunner(FakeSession(error=DatabaseError("[E5021] table missing"))).run_case(expected).status == "PASS"
    mismatch = case(tmp_path, "expected_error", "code: E5001", "SELECT * FROM MISSING_XGT_QUERY_MVP")
    mismatch_report = QueryRunner(FakeSession(error=DatabaseError("[E5021] table missing"))).run_case(mismatch)
    assert mismatch_report.status == "FAIL"
    assert mismatch_report.steps[0].error_code == "E5021"
    not_raised = case(tmp_path, "expected_error", "code: E5021", "SELECT 1")
    assert QueryRunner(FakeSession()).run_case(not_raised).status == "FAIL"
    ordinary = case(tmp_path)
    failed = QueryRunner(FakeSession(error=DatabaseError("[E5021] table missing"))).run_case(ordinary)
    assert failed.status == "ERROR"


def test_unsupported_driver_type_is_error(tmp_path) -> None:
    report = QueryRunner(FakeSession(types=("NUMERIC",))).run_case(case(tmp_path))
    assert report.status == "ERROR"
    assert report.failure_type == "UNSUPPORTED_TYPE"


def test_canonical_errors_are_not_converted_to_assertion_failures(tmp_path) -> None:
    case_with_date = case(tmp_path)
    fake = FakeSession(rows=(("2026-09-24 10:00:00",),), types=("DATE",))
    report = QueryRunner(fake).run_case(case_with_date)
    assert report.status == "ERROR"


def test_runtime_profile_can_reject_a_declared_type(tmp_path) -> None:
    query = case(tmp_path)
    profile = {"identity": {"capabilities": {"type_mapping": {"integer": {"support_status": "UNSUPPORTED"}}}}}
    report = QueryRunner(FakeSession(), profile).run_case(query)
    assert report.status == "ERROR"
    assert report.failure_type == "UNSUPPORTED_TYPE"


def test_multi_step_case_executes_queries_in_order(tmp_path) -> None:
    source = tmp_path / "multi.yaml"
    source.write_text("""metadata:
  id: QUERY.RUNNER.MULTI
  feature: query
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
    expected: {rows: [[1]]}
""", encoding="utf-8")
    session = FakeSession()
    report = QueryRunner(session).run_case(load_query_case(source))
    assert report.status == "PASS"
    assert [step.id for step in report.steps] == ["first", "second"]
    assert session.queries == ["SELECT 1", "SELECT 2"]


def test_run_query_cases_rolls_back_closes_and_writes_typed_report(tmp_path, monkeypatch) -> None:
    import xgtest.query.runner as runner_module

    query_dir = tmp_path / "cases"
    query_dir.mkdir()
    source = query_dir / "case.yaml"
    source.write_text("""metadata:
  id: QUERY.LIFECYCLE.0001
  feature: query
steps:
  - id: q1
    kind: query
    sql: SELECT 1
    comparison: {mode: exact}
    expected: {rows: [[1]]}
""", encoding="utf-8")
    calls = []

    class ManagedSession(FakeSession):
        def __init__(self, config):
            super().__init__()

        def open(self):
            calls.append("open")
            return self

        def rollback_transaction(self):
            calls.append("rollback")

        def close(self):
            calls.append("close")

    monkeypatch.setattr(runner_module, "XuguSession", ManagedSession)
    output = tmp_path / "report.json"
    report = run_query_cases(
        XuguConnectionConfig("host", "1907", "SYSTEM", "user", "password"),
        query_dir,
        output,
    )
    assert calls == ["open", "rollback", "close"]
    assert report["status"] == "PASS"
    assert report["cases"][0]["steps"][0]["row_count"] == 1
    assert output.is_file()
    assert "password" not in output.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("failing_operation", "expected_error"),
    [("rollback", "QUERY_ROLLBACK_FAILED"), ("close", "QUERY_SESSION_CLOSE_FAILED")],
)
def test_run_query_cases_records_lifecycle_failures(tmp_path, monkeypatch, failing_operation, expected_error) -> None:
    import xgtest.query.runner as runner_module

    query_dir = tmp_path / "cases"
    query_dir.mkdir()
    (query_dir / "case.yaml").write_text("""metadata:
  id: QUERY.LIFECYCLE.FAILURE
  feature: query
steps:
  - id: q1
    kind: query
    sql: SELECT 1
    comparison: {mode: exact}
    expected: {rows: [[1]]}
""", encoding="utf-8")

    class FailingLifecycleSession(FakeSession):
        def __init__(self, config):
            super().__init__()

        def open(self):
            return self

        def rollback_transaction(self):
            if failing_operation == "rollback":
                raise RuntimeError("rollback failed")

        def close(self):
            if failing_operation == "close":
                raise RuntimeError("close failed")

    monkeypatch.setattr(runner_module, "XuguSession", FailingLifecycleSession)
    report = run_query_cases(
        XuguConnectionConfig("host", "1907", "SYSTEM", "user", "password"),
        query_dir,
        tmp_path / "report.json",
    )
    assert report["status"] == "ERROR"
    assert report["cases"][0]["failure_type"] == "INFRA_RESOURCE"
    assert report["cases"][0]["error"] == expected_error
