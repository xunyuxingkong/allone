"""Every legal Aggregate assignment must render observable, mutation-viable SQL."""

from pathlib import Path

import pytest
import yaml

from xgtest.core.models import CaseExecutionStatus, QueryCaseReport, QueryStepReport, StepStatus
from xgtest.design.coverage import valid_assignments
from xgtest.design.model import load_test_model
from xgtest.generator.candidate import case_payload, static_validate_candidate
from xgtest.generator.aggregate_template import is_mutation_observable, render_aggregate
from xgtest.generator.lifecycle import validate_candidate_mutation


ROOT = Path(__file__).resolve().parents[2]


def test_every_valid_assignment_renders_observable_aggregate() -> None:
    model = load_test_model(ROOT / "models/query/aggregate.yaml")
    assignments = valid_assignments(model)
    assert assignments
    for assignment in assignments:
        rendered = render_aggregate(model, assignment)
        sql, rows = rendered["sql"], rendered["expected"]["rows"]
        assert sql.startswith("SELECT ") and " FROM " in sql
        assert rendered["comparison"] == {"mode": "rowsort"}
        # Ungrouped aggregates always return exactly one row; grouped aggregates
        # return one row per surviving group, which is empty only for an empty input.
        if assignment["grouping"] == "none":
            assert len(rows) == 1, assignment
        else:
            assert rows or assignment["cardinality"] == "empty", assignment
        # HAVING must be present iff declared, and appear only with a GROUP BY.
        assert ("HAVING" in sql) == (assignment["grouping"] == "group_by_having")
        if assignment["grouping"] == "group_by_having":
            assert "GROUP BY" in sql


def test_mutation_observability_matches_rendered_rows() -> None:
    """The predicate the plugin uses to gate the mutation must not be vacuous."""
    model = load_test_model(ROOT / "models/query/aggregate.yaml")
    for assignment in valid_assignments(model):
        rendered_rows = render_aggregate(model, assignment)["expected"]["rows"]
        if is_mutation_observable(assignment):
            assert rendered_rows, assignment


def test_count_null_mutation_must_change_trial_result(tmp_path: Path) -> None:
    model = load_test_model(ROOT / "models/query/aggregate.yaml")
    assignment = next(row for row in valid_assignments(model)
                      if row["function"] == "count" and row["null_handling"] == "with_nulls" and row["grouping"] == "none")
    payload = case_payload(model, assignment, "pairwise")
    candidate = tmp_path / f"{payload['metadata']['id']}.yaml"
    candidate.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    static_validate_candidate(candidate, model)

    def runner(case, _config, _profile):
        mutated = "COUNT(*)" in case.steps[0].sql
        digest = "b" * 64 if mutated else "a" * 64
        return QueryCaseReport(
            case_id=case.metadata.id, status=CaseExecutionStatus.PASS, duration_ms=1.0,
            steps=(QueryStepReport(id="q1", status=StepStatus.PASS, duration_ms=1.0, row_count=1, result_sha256=digest),),
        )

    result = validate_candidate_mutation(candidate, model, object(), {}, runner=runner)
    assert result["status"] == "KILLED"
    assert result["original_hash"] != result["mutated_hash"]


def test_static_validation_rejects_expected_that_disagrees_with_claim(tmp_path: Path) -> None:
    model = load_test_model(ROOT / "models/query/aggregate.yaml")
    assignment = next(iter(valid_assignments(model)))
    payload = case_payload(model, assignment, "pairwise")
    candidate = tmp_path / f"{payload['metadata']['id']}.yaml"
    candidate.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    payload = yaml.safe_load(candidate.read_text(encoding="utf-8"))
    payload["steps"][0]["expected"]["rows"] = []
    candidate.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    with pytest.raises(ValueError, match="CANDIDATE_COVERAGE_SQL_EXPECTED_MISMATCH"):
        static_validate_candidate(candidate, model)
