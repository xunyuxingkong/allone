"""Every legal Filter assignment must render observable, mutation-viable SQL."""

from pathlib import Path

import pytest
import yaml

from xgtest.core.models import CaseExecutionStatus, QueryCaseReport, QueryStepReport, StepStatus
from xgtest.design.coverage import valid_assignments
from xgtest.design.model import load_test_model
from xgtest.generator.candidate import case_payload, static_validate_candidate
from xgtest.generator.filter_template import _fixture, render_filter
from xgtest.generator.lifecycle import validate_candidate_mutation


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


def test_lt_mutation_must_change_trial_result(tmp_path: Path) -> None:
    model = load_test_model(ROOT / "models/query/filter.yaml")
    assignment = next(row for row in valid_assignments(model)
                      if row["operator"] == "less_than" and row["predicate"] == "comparison")
    payload = case_payload(model, assignment, "pairwise")
    candidate = tmp_path / f"{payload['metadata']['id']}.yaml"
    candidate.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    static_validate_candidate(candidate, model)

    def runner(case, _config, _profile):
        mutated = "d.k <= " in case.steps[0].sql
        digest = "b" * 64 if mutated else "a" * 64
        return QueryCaseReport(
            case_id=case.metadata.id, status=CaseExecutionStatus.PASS, duration_ms=1.0,
            steps=(QueryStepReport(id="q1", status=StepStatus.PASS, duration_ms=1.0, row_count=1, result_sha256=digest),),
        )

    result = validate_candidate_mutation(candidate, model, object(), {}, runner=runner)
    assert result["status"] == "KILLED"
    assert result["original_hash"] != result["mutated_hash"]


def test_static_validation_rejects_expected_that_disagrees_with_claim(tmp_path: Path) -> None:
    model = load_test_model(ROOT / "models/query/filter.yaml")
    assignment = next(iter(valid_assignments(model)))
    payload = case_payload(model, assignment, "pairwise")
    candidate = tmp_path / f"{payload['metadata']['id']}.yaml"
    candidate.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    payload = yaml.safe_load(candidate.read_text(encoding="utf-8"))
    payload["steps"][0]["expected"]["rows"] = []
    candidate.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    with pytest.raises(ValueError, match="CANDIDATE_COVERAGE_SQL_EXPECTED_MISMATCH"):
        static_validate_candidate(candidate, model)
