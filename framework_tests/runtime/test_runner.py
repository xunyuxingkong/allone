from pathlib import Path

from xgtest.core.yaml_loader import load_yaml
from xgtest.runtime.runner import _compare_rows


def test_compare_rows_supports_exact_and_rowsort() -> None:
    expected = {"rows": [[1], [2]]}
    assert _compare_rows([(1,), (2,)], expected)
    assert _compare_rows([(2,), (1,)], expected, "rowsort")
    assert not _compare_rows([(2,), (1,)], expected)


def test_mvp_case_yaml_is_readable() -> None:
    path = Path(__file__).resolve().parents[2] / "cases" / "mvp" / "join.yaml"
    loaded = load_yaml(path)
    assert loaded["metadata"]["id"] == "MVP.JOIN.000001"
    assert len(loaded["steps"]) == 7
