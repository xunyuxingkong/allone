"""Every legal Sort/Limit assignment must render exact, order-observable SQL."""

from pathlib import Path

import pytest
import yaml

from xgtest.core.models import CaseExecutionStatus, QueryCaseReport, QueryStepReport, StepStatus
from xgtest.design.coverage import valid_assignments
from xgtest.design.model import load_test_model
from xgtest.generator.candidate import case_payload, static_validate_candidate
from xgtest.generator.lifecycle import validate_candidate_mutation
from xgtest.generator.sort_limit_template import render_sort_limit


ROOT = Path(__file__).resolve().parents[2]


def test_every_valid_assignment_renders_exact_order() -> None:
    model = load_test_model(ROOT / "models/query/sort_limit.yaml")
    assignments = valid_assignments(model)
    assert assignments
    for assignment in assignments:
        rendered = render_sort_limit(model, assignment)
        sql, rows = rendered["sql"], rendered["expected"]["rows"]
        # Sort/limit must assert order, so comparison is exact, never rowsort.
        assert rendered["comparison"] == {"mode": "exact"}
        assert sql.startswith("SELECT q.label AS label, q.k AS k FROM (")
        assert ("ORDER BY" in sql) == (assignment["order_direction"] != "none")
        assert ("LIMIT" in sql) == (assignment["limit_kind"] != "none")
        if assignment["limit_kind"] == "limit_offset":
            assert "OFFSET" in sql
        assert rows and all(len(row) == 2 for row in rows)


def test_ascending_cases_reverse_under_desc() -> None:
    """The ASC -> DESC mutation changes the row order for every ascending case."""
    model = load_test_model(ROOT / "models/query/sort_limit.yaml")
    for assignment in valid_assignments(model):
        if assignment["order_direction"] != "asc":
            continue
        flipped = {**assignment, "order_direction": "desc"}
        assert render_sort_limit(model, assignment)["expected"]["rows"] != render_sort_limit(model, flipped)["expected"]["rows"], assignment


def test_limit_truncates_and_offset_shifts() -> None:
    model = load_test_model(ROOT / "models/query/sort_limit.yaml")
    pick = lambda **kw: next(row for row in valid_assignments(model) if all(row[k] == v for k, v in kw.items()))
    full = render_sort_limit(model, pick(order_direction="asc", limit_kind="none", composition="none"))
    limited = render_sort_limit(model, pick(order_direction="asc", limit_kind="limit_only", composition="none"))
    offset = render_sort_limit(model, pick(order_direction="asc", limit_kind="limit_offset", composition="none"))
    assert limited["expected"]["rows"] == full["expected"]["rows"][:2]
    assert offset["expected"]["rows"] == full["expected"]["rows"][1:3]


def test_asc_to_desc_mutation_must_change_trial_result(tmp_path: Path) -> None:
    model = load_test_model(ROOT / "models/query/sort_limit.yaml")
    assignment = next(row for row in valid_assignments(model) if row["order_direction"] == "asc")
    payload = case_payload(model, assignment, "pairwise")
    candidate = tmp_path / f"{payload['metadata']['id']}.yaml"
    candidate.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    static_validate_candidate(candidate, model)

    def runner(case, _config, _profile):
        flipped = "q.k DESC" in case.steps[0].sql
        digest = "b" * 64 if flipped else "a" * 64
        return QueryCaseReport(
            case_id=case.metadata.id, status=CaseExecutionStatus.PASS, duration_ms=1.0,
            steps=(QueryStepReport(id="q1", status=StepStatus.PASS, duration_ms=1.0, row_count=1, result_sha256=digest),),
        )

    result = validate_candidate_mutation(candidate, model, object(), {}, runner=runner)
    assert result["status"] == "KILLED"
    assert result["original_hash"] != result["mutated_hash"]


def test_static_validation_rejects_expected_that_disagrees_with_claim(tmp_path: Path) -> None:
    model = load_test_model(ROOT / "models/query/sort_limit.yaml")
    assignment = next(iter(valid_assignments(model)))
    payload = case_payload(model, assignment, "pairwise")
    candidate = tmp_path / f"{payload['metadata']['id']}.yaml"
    candidate.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    payload = yaml.safe_load(candidate.read_text(encoding="utf-8"))
    payload["steps"][0]["expected"]["rows"] = []
    candidate.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    with pytest.raises(ValueError, match="CANDIDATE_COVERAGE_SQL_EXPECTED_MISMATCH"):
        static_validate_candidate(candidate, model)
