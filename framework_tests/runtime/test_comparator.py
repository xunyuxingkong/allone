from types import SimpleNamespace

from xgtest.runtime.comparator import compare_affected_rows, compare_error, compare_rows, rows_sha256


def test_compare_rows_exact_rowsort_and_hash() -> None:
    rows = [(1,), (2,)]
    assert compare_rows(rows, {"rows": [[1], [2]]})
    assert compare_rows(list(reversed(rows)), {"rows": [[1], [2]]}, "rowsort")
    assert compare_rows(rows, {"sha256": rows_sha256(rows)})


def test_compare_statement_count_and_error() -> None:
    assert compare_affected_rows(2, {"affected_rows": 2})
    error = SimpleNamespace(code="E5021", sqlstate=None)
    error.__str__ = lambda self: "missing table E5021"
    assert compare_error(error, {"code": "E5021"})
