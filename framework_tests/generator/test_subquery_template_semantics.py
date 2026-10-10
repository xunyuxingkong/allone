"""Every legal Subquery assignment must render well-formed, discriminating SQL."""

from pathlib import Path

import pytest
import yaml

from xgtest.core.models import CaseExecutionStatus, QueryCaseReport, QueryStepReport, StepStatus
from xgtest.design.coverage import valid_assignments
from xgtest.design.model import load_test_model
from xgtest.generator.candidate import case_payload, static_validate_candidate
from xgtest.generator.subquery_template import _OUTER, is_mutation_observable, render_subquery
from xgtest.generator.lifecycle import validate_candidate_mutation


ROOT = Path(__file__).resolve().parents[2]


def test_every_valid_assignment_renders_a_read_only_subquery() -> None:
    model = load_test_model(ROOT / "models/query/subquery.yaml")
    assignments = valid_assignments(model)
    assert assignments
    for assignment in assignments:
        rendered = render_subquery(model, assignment)
        sql, rows = rendered["sql"], rendered["expected"]["rows"]
        assert sql.startswith("SELECT o.label AS label FROM (")
        assert " WHERE " in sql
        assert rendered["comparison"] == {"mode": "rowsort"}
        # Every rendered row labels a real outer row, and no row repeats.
        labels = [row[0] for row in rows]
        assert len(labels) == len(set(labels))
        assert set(labels) <= {label for label, _ in _OUTER}


def test_mutation_observability_matches_partial_results() -> None:
    """The plugin's mutation applies exactly where the result is partial."""
    from xgtest.generator.plugins import SubqueryPlugin
    model = load_test_model(ROOT / "models/query/subquery.yaml")
    plugin = SubqueryPlugin()
    for assignment in valid_assignments(model):
        rows = render_subquery(model, assignment)["expected"]["rows"]
        partial = 0 < len(rows) < len(_OUTER)
        if is_mutation_observable(model, assignment):
            assert partial, assignment
        # The plugin's predicate is keyed on IN/NOT IN shapes only.
        applies = (assignment["predicate"] == "in" and assignment["subquery_result"] in {"matching", "with_null"}) or (
            assignment["predicate"] == "not_in" and assignment["subquery_result"] == "matching")
        if assignment["predicate"] in {"in", "not_in"} and applies:
            assert partial, assignment


def test_in_flip_mutation_must_change_trial_result(tmp_path: Path) -> None:
    model = load_test_model(ROOT / "models/query/subquery.yaml")
    assignment = next(row for row in valid_assignments(model)
                      if row["predicate"] == "in" and row["subquery_result"] == "matching")
    payload = case_payload(model, assignment, "pairwise")
    candidate = tmp_path / f"{payload['metadata']['id']}.yaml"
    candidate.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    static_validate_candidate(candidate, model)

    def runner(case, _config, _profile):
        flipped = " NOT IN " in case.steps[0].sql
        digest = "b" * 64 if flipped else "a" * 64
        return QueryCaseReport(
            case_id=case.metadata.id, status=CaseExecutionStatus.PASS, duration_ms=1.0,
            steps=(QueryStepReport(id="q1", status=StepStatus.PASS, duration_ms=1.0, row_count=1, result_sha256=digest),),
        )

    result = validate_candidate_mutation(candidate, model, object(), {}, runner=runner)
    assert result["status"] == "KILLED"
    assert result["original_hash"] != result["mutated_hash"]


def test_static_validation_rejects_expected_that_disagrees_with_claim(tmp_path: Path) -> None:
    model = load_test_model(ROOT / "models/query/subquery.yaml")
    assignment = next(iter(valid_assignments(model)))
    payload = case_payload(model, assignment, "pairwise")
    candidate = tmp_path / f"{payload['metadata']['id']}.yaml"
    candidate.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    payload = yaml.safe_load(candidate.read_text(encoding="utf-8"))
    payload["steps"][0]["expected"]["rows"] = []
    candidate.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    with pytest.raises(ValueError, match="CANDIDATE_COVERAGE_SQL_EXPECTED_MISMATCH"):
        static_validate_candidate(candidate, model)
