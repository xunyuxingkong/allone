"""Coverage claims must match observable JOIN behavior for every legal v2 assignment."""

from pathlib import Path

import pytest
import yaml

from xgtest.core.models import CaseExecutionStatus, QueryCaseReport, QueryStepReport, StepStatus
from xgtest.design.coverage import valid_assignments
from xgtest.design.model import load_test_model
from xgtest.generator.candidate import case_payload, generate_candidates, static_validate_candidate
from xgtest.generator.template import TEMPLATE_VERSION, _source_rows, render_join
from xgtest.generator.lifecycle import validate_candidate_mutation
from xgtest.query.loader import load_query_directory


ROOT = Path(__file__).resolve().parents[2]


def test_every_valid_assignment_expresses_its_null_and_predicate_semantics() -> None:
    model = load_test_model(ROOT / "models/query/join.yaml")
    assert model.model_version == "2"
    assert TEMPLATE_VERSION == "4"
    operators = {"inner": " JOIN ", "left": " LEFT JOIN ", "right": " RIGHT JOIN ", "full": " FULL OUTER JOIN ", "cross": " CROSS JOIN "}
    predicates = {"equality": " ON a.k = b.k", "inequality": " ON a.k <> b.k", "less_equal": " ON a.k <= b.k"}
    assignments = valid_assignments(model)
    assert assignments
    for assignment in assignments:
        rendered = render_join(model, assignment)
        sql = rendered["sql"]
        rows = rendered["expected"]["rows"]
        assert operators[assignment["join_type"]] in sql
        if assignment["predicate"] == "none":
            assert assignment["join_type"] == "cross"
            assert " ON " not in sql
        else:
            assert predicates[assignment["predicate"]] in sql
        if assignment["predicate"] == "less_equal":
            left, right = _source_rows(assignment["join_type"], "less_equal", assignment["null_side"])
            relations = {"lt" if a < b else "eq" if a == b else "gt" for a in left for b in right}
            assert relations == {"lt", "eq", "gt"}, assignment
        if assignment["datatype"] == "date":
            assert "DATE '2020-01-" in sql
        elif assignment["datatype"] == "varchar":
            assert " AS k" in sql and "'right-row'" in sql
        elif assignment["datatype"] == "int":
            assert "CAST(2 AS INTEGER)" in sql
            assert "SELECT 2 AS k" not in sql

        left_null = any(row[0] is None and row[1] is not None for row in rows)
        right_null = any(row[0] is not None and row[1] is None for row in rows)
        observed = "both" if left_null and right_null else "left" if left_null else "right" if right_null else "none"
        assert observed == assignment["null_side"], assignment

        if assignment["interaction"] == "where":
            assert "'drop-row'" in sql and " WHERE q.label = 'right-row' OR q.label IS NULL" in sql
        elif assignment["interaction"] == "group_by":
            assert " UNION ALL " in sql and " GROUP BY q.left_key, q.right_key, q.label" in sql
        elif assignment["interaction"] == "subquery":
            assert "'drop-row'" in sql and "WHERE EXISTS (SELECT 1" in sql and "q.label" in sql
        assert all(row[2] in {None, "right-row"} for row in rows)


def test_less_equal_mutation_must_change_trial_result(tmp_path: Path) -> None:
    model = load_test_model(ROOT / "models/query/join.yaml")
    assignment = next(
        row for row in valid_assignments(model)
        if row["predicate"] == "less_equal" and row["null_side"] == "none"
    )
    payload = case_payload(model, assignment, "pairwise")
    candidate = tmp_path / f"{payload['metadata']['id']}.yaml"
    candidate.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    static_validate_candidate(candidate, model)

    def runner(case, _config, _profile):
        mutated = "a.k < b.k" in case.steps[0].sql
        digest = "b" * 64 if mutated else "a" * 64
        return QueryCaseReport(
            case_id=case.metadata.id,
            status=CaseExecutionStatus.PASS,
            duration_ms=1.0,
            steps=(QueryStepReport(id="q1", status=StepStatus.PASS, duration_ms=1.0, row_count=1, result_sha256=digest),),
        )

    result = validate_candidate_mutation(candidate, model, object(), {}, runner=runner)
    assert result["status"] == "KILLED"
    assert result["original_hash"] != result["mutated_hash"]


def test_weak_less_equal_mutation_is_rejected(tmp_path: Path) -> None:
    model = load_test_model(ROOT / "models/query/join.yaml")
    assignment = next(
        row for row in valid_assignments(model)
        if row["predicate"] == "less_equal" and row["null_side"] == "none"
    )
    payload = case_payload(model, assignment, "pairwise")
    candidate = tmp_path / f"{payload['metadata']['id']}.yaml"
    candidate.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    static_validate_candidate(candidate, model)

    def runner(case, _config, _profile):
        return QueryCaseReport(
            case_id=case.metadata.id,
            status=CaseExecutionStatus.PASS,
            duration_ms=1.0,
            steps=(QueryStepReport(id="q1", status=StepStatus.PASS, duration_ms=1.0, row_count=1, result_sha256="a" * 64),),
        )

    result = validate_candidate_mutation(candidate, model, object(), {}, runner=runner)
    assert result["status"] == "WEAK"


def test_static_validation_rejects_expected_that_disagrees_with_claim(tmp_path: Path) -> None:
    model = load_test_model(ROOT / "models/query/join.yaml")
    active = load_query_directory(ROOT / "cases/query")
    candidate = generate_candidates(model, "pairwise", active, tmp_path, limit=1)[0]
    payload = yaml.safe_load(candidate.read_text(encoding="utf-8"))
    payload["steps"][0]["expected"]["rows"] = []
    candidate.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    with pytest.raises(ValueError, match="CANDIDATE_COVERAGE_SQL_EXPECTED_MISMATCH"):
        static_validate_candidate(candidate, model)
