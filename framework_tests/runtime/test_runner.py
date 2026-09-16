from pathlib import Path

from xgtest.adapter.xugu import XuguConnectionConfig, XuguQueryResult
from xgtest.core.yaml_loader import load_yaml
from xgtest.runtime.comparator import compare_rows
from xgtest.runtime import runner


def test_compare_rows_supports_exact_and_rowsort() -> None:
    expected = {"rows": [[1], [2]]}
    assert compare_rows([(1,), (2,)], expected)
    assert compare_rows([(2,), (1,)], expected, "rowsort")
    assert not compare_rows([(2,), (1,)], expected)


def test_mvp_case_yaml_is_readable() -> None:
    path = Path(__file__).resolve().parents[2] / "cases" / "mvp" / "join.yaml"
    loaded = load_yaml(path)
    assert loaded["metadata"]["id"] == "MVP.JOIN.000001"
    assert len(loaded["steps"]) == 7


def test_bootstrap_case_is_decoded_to_typed_models() -> None:
    path = Path(__file__).resolve().parents[2] / "cases" / "mvp" / "join.yaml"
    case = runner._load_bootstrap_case(path)
    assert case.metadata.id == "MVP.JOIN.000001"
    assert case.steps[0].kind == "setup"
    assert case.steps[4].expected.rows == ((2, "two", 20),)


def test_setup_failure_skips_main_but_always_runs_cleanup(monkeypatch, tmp_path: Path) -> None:
    case_path = tmp_path / "case.yaml"
    case_path.write_text(
        """metadata:\n  id: MVP.FAILURE.000001\n  title: setup failure\n  feature: join\nsteps:\n  - id: setup\n    kind: setup\n    sql: CREATE TABLE FAIL\n  - id: query\n    kind: query\n    sql: SELECT 1\n    comparison:\n      mode: exact\n    expected:\n      rows:\n        - [1]\n  - id: cleanup\n    kind: cleanup\n    sql: DROP TABLE FAIL\n""",
        encoding="utf-8",
    )
    calls: list[str] = []

    class FakeSession:
        def __init__(self, config):
            pass

        def open(self):
            return self

        def execute(self, sql):
            calls.append(sql)
            if sql.startswith("CREATE"):
                raise RuntimeError("setup failed")
            return 0

        def query(self, sql):
            calls.append(sql)
            return XuguQueryResult(("value",), ("int",), ((1,),))

        def rollback_transaction(self):
            calls.append("rollback")

        def close(self):
            calls.append("close")

    monkeypatch.setattr(runner, "XuguSession", FakeSession)
    report = runner._run_case(XuguConnectionConfig("h", "1", "d", "u", "p"), case_path)
    assert report.status == "ERROR"
    assert [step.status for step in report.steps] == ["ERROR", "SKIPPED", "PASS"]
    assert calls == ["CREATE TABLE FAIL", "DROP TABLE FAIL", "rollback", "close"]
