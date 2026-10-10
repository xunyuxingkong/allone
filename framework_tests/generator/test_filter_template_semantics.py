"""Every legal Filter assignment must render observable, mutation-viable SQL."""

from pathlib import Path

from xgtest.design.coverage import valid_assignments
from xgtest.design.model import load_test_model
from xgtest.generator.filter_template import _fixture, render_filter


ROOT = Path(__file__).resolve().parents[2]


def test_every_valid_assignment_renders_observable_rows() -> None:
    model = load_test_model(ROOT / "models/query/filter.yaml")
    assignments = valid_assignments(model)
    assert assignments
    for assignment in assignments:
        rendered = render_filter(model, assignment)
        sql = rendered["sql"]
        rows = rendered["expected"]["rows"]
        assert sql.startswith("SELECT d.k AS k, d.label AS label FROM (")
        assert " WHERE " in sql
        assert rendered["comparison"] == {"mode": "rowsort"}
        # Never empty and never the whole fixture: a predicate mutation must be
        # observable, otherwise the mutation would be WEAK and ungated.
        ranks, with_null = _fixture(assignment["null_handling"])
        universe = len(ranks) + (1 if with_null else 0)
        assert 0 < len(rows) < universe, assignment
        # Under a bare predicate, the NULL row is kept only by IS NULL (three-valued
        # logic drops it for every comparison). `or` adds `d.k IS NULL` and `not`
        # inverts, so the invariant is scoped to `interaction == "none"`.
        null_kept = any(row[0] is None for row in rows)
        if assignment["interaction"] == "none":
            assert null_kept == (assignment["predicate"] == "is_null"), assignment
        # Datatype literal encoding is datatype-specific.
        if assignment["datatype"] == "date":
            assert "DATE '2020-01-" in sql
        elif assignment["datatype"] == "varchar":
            assert "'a' AS k" in sql
        else:
            assert "CAST(2 AS INTEGER)" in sql


def test_less_than_comparison_assignment_drops_the_boundary_row() -> None:
    """The `<` mutation (d.k < 2 -> d.k <= 2) must change the result.

    Only `predicate == comparison` renders that exact literal, so the boundary
    invariant applies there: with a bare or ANDed clause the boundary value must
    be absent under `<`, hence would appear under `<=`.
    """
    model = load_test_model(ROOT / "models/query/filter.yaml")
    boundary = {"int": 2, "varchar": "b", "date": "2020-01-02"}
    for assignment in valid_assignments(model):
        if assignment["operator"] != "less_than" or assignment["predicate"] != "comparison":
            continue
        if assignment["interaction"] not in {"none", "and"}:
            continue
        rows = render_filter(model, assignment)["expected"]["rows"]
        assert not any(row[0] == boundary[assignment["datatype"]] for row in rows), assignment
