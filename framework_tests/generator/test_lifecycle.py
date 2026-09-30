from pathlib import Path

import pytest
import yaml

from xgtest.core.models import CaseExecutionStatus, QueryCaseReport, QueryStepReport, StepStatus
from xgtest.design.coverage import coverage_gap
from xgtest.design.model import load_test_model
from xgtest.generator.candidate import generate_candidates, static_validate_candidate
from xgtest.generator.lifecycle import promote_candidate, record_candidate_mutation_evidence, trial_candidate
from xgtest.generator.review import record_review
from xgtest.query.loader import load_query_case, load_query_directory
from xgtest.runtime.comparator import rows_sha256


ROOT = Path(__file__).resolve().parents[2]


def _passing_report(case) -> QueryCaseReport:
    rows = ((1,),)
    return QueryCaseReport(
        case_id=case.metadata.id, status=CaseExecutionStatus.PASS, duration_ms=1.0,
        steps=(QueryStepReport(
            id="q1", status=StepStatus.PASS, duration_ms=1.0,
            columns=("k",), column_types=("INTEGER",), logical_types=("int",),
            row_count=1, result_rows=rows,
            result_sha256=rows_sha256(list(rows), ("INTEGER",), 1),
        ),),
    )


def _record_not_applicable_mutation(candidate: Path, mutation_root: Path) -> None:
    case_id = load_query_case(candidate).metadata.id
    record_candidate_mutation_evidence(
        candidate,
        {"case_id": case_id, "mutation_id": "replace_le_with_lt", "status": "NOT_APPLICABLE"},
        mutation_root,
        {"sql_runtime_profile_id": "a" * 64},
    )


def test_gap_to_candidate_to_review_to_active_closes_requirement(tmp_path: Path) -> None:
    model = load_test_model(ROOT / "models" / "query" / "join.yaml")
    active = load_query_directory(ROOT / "cases" / "query")
    before = coverage_gap(model, [claim for case in active for claim in case.coverage], "pairwise")
    candidates = generate_candidates(model, "pairwise", active, tmp_path / "candidates", limit=1)
    assert len(candidates) == 1
    assert not (tmp_path / "active").exists()
    static_validate_candidate(candidates[0], model)
    assert load_query_case(candidates[0]).metadata.status.value == "draft"

    def passing_runner(case, config, profile):
        return _passing_report(case)

    _record_not_applicable_mutation(candidates[0], tmp_path / "mutations")
    trial_candidate(candidates[0], model, object(), tmp_path / "trial-runs", runtime_profile={"sql_runtime_profile_id": "a" * 64}, runner=passing_runner)
    record_review(candidates[0], model=model, reviewer="reviewer@example.test", review_reference="PR-1", coverage_reference="PR-1#coverage")
    promoted = promote_candidate(candidates[0], model, tmp_path / "active", tmp_path / "trial-runs", expected_runtime_profile_id="a" * 64)
    active_case = load_query_case(promoted)
    assert active_case.metadata.status.value == "active"
    assert not candidates[0].exists()
    after = coverage_gap(model, [claim for case in active for claim in case.coverage] + list(active_case.coverage), "pairwise")
    assert after["missing"] < before["missing"]


def test_modified_candidate_cannot_be_promoted_after_evidence(tmp_path: Path) -> None:
    model = load_test_model(ROOT / "models" / "query" / "join.yaml")
    active = load_query_directory(ROOT / "cases" / "query")
    candidate = generate_candidates(model, "pairwise", active, tmp_path / "candidates", limit=1)[0]
    static_validate_candidate(candidate, model)

    def passing_runner(case, config, profile):
        return _passing_report(case)

    _record_not_applicable_mutation(candidate, tmp_path / "mutations")
    trial_candidate(candidate, model, object(), tmp_path / "trial-runs", runtime_profile={"sql_runtime_profile_id": "a" * 64}, runner=passing_runner)
    record_review(candidate, model=model, reviewer="reviewer", review_reference="PR-1", coverage_reference="PR-1#coverage")
    text = candidate.read_text(encoding="utf-8").replace("SELECT a.k", "SELECT 99 AS changed, a.k")
    candidate.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError, match="SEMANTIC_HASH_STALE"):
        promote_candidate(candidate, model, tmp_path / "active", tmp_path / "trial-runs", expected_runtime_profile_id="a" * 64)


def test_modified_coverage_claim_invalidates_review_evidence(tmp_path: Path) -> None:
    model = load_test_model(ROOT / "models" / "query" / "join.yaml")
    active = load_query_directory(ROOT / "cases" / "query")
    candidate = generate_candidates(model, "pairwise", active, tmp_path / "candidates", limit=1)[0]
    static_validate_candidate(candidate, model)

    def passing_runner(case, config, profile):
        return _passing_report(case)

    _record_not_applicable_mutation(candidate, tmp_path / "mutations")
    trial_candidate(candidate, model, object(), tmp_path / "trial-runs", runtime_profile={"sql_runtime_profile_id": "a" * 64}, runner=passing_runner)
    record_review(candidate, model=model, reviewer="reviewer", review_reference="PR-1", coverage_reference="PR-1#coverage")
    payload = yaml.safe_load(candidate.read_text(encoding="utf-8"))
    payload["coverage"][0]["claim_id"] = "revised_claim"
    candidate.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    with pytest.raises(ValueError, match="REVIEW_INPUT_STALE"):
        promote_candidate(candidate, model, tmp_path / "active", tmp_path / "trial-runs", expected_runtime_profile_id="a" * 64)


def _reviewed_candidate(tmp_path: Path):
    model = load_test_model(ROOT / "models" / "query" / "join.yaml")
    active = load_query_directory(ROOT / "cases" / "query")
    candidate = generate_candidates(model, "pairwise", active, tmp_path / "candidates", limit=1)[0]
    static_validate_candidate(candidate, model)

    def passing_runner(case, config, profile):
        return _passing_report(case)

    _record_not_applicable_mutation(candidate, tmp_path / "mutations")
    result = trial_candidate(candidate, model, object(), tmp_path / "trial-runs", runtime_profile={"sql_runtime_profile_id": "a" * 64}, runner=passing_runner)
    record_review(candidate, model=model, reviewer="reviewer", review_reference="PR-1", coverage_reference="PR-1#coverage")
    return model, candidate, Path(result["artifact"])


def test_promotion_rejects_wrong_runtime_profile(tmp_path: Path) -> None:
    model, candidate, _ = _reviewed_candidate(tmp_path)
    with pytest.raises(ValueError, match="CANDIDATE_RUNTIME_PROFILE_MISMATCH"):
        promote_candidate(candidate, model, tmp_path / "active", tmp_path / "trial-runs", expected_runtime_profile_id="b" * 64)


def test_promotion_rejects_stale_contract_set(tmp_path: Path, monkeypatch) -> None:
    model, candidate, _ = _reviewed_candidate(tmp_path)
    monkeypatch.setattr("xgtest.generator.lifecycle.build_contract_descriptor", lambda root: {"contract_set_id": "b" * 64})
    with pytest.raises(ValueError, match="CANDIDATE_CONTRACT_SET_STALE"):
        promote_candidate(candidate, model, tmp_path / "active", tmp_path / "trial-runs", expected_runtime_profile_id="a" * 64)


def test_promotion_rejects_modified_trial_artifact(tmp_path: Path) -> None:
    model, candidate, artifact = _reviewed_candidate(tmp_path)
    artifact.write_bytes(artifact.read_bytes() + b" ")
    with pytest.raises(ValueError, match="CANDIDATE_TRIAL_ARTIFACT_HASH_MISMATCH"):
        promote_candidate(candidate, model, tmp_path / "active", tmp_path / "trial-runs", expected_runtime_profile_id="a" * 64)
