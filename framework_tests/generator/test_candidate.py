from pathlib import Path

import pytest

from xgtest.design.coverage import coverage_gap
from xgtest.design.model import load_test_model
from xgtest.generator.candidate import generate_candidates
from xgtest.query.loader import load_query_directory


ROOT = Path(__file__).resolve().parents[2]


def test_unregistered_model_fails_closed_without_creating_output(tmp_path: Path) -> None:
    model = load_test_model(ROOT / "models" / "query" / "join.yaml").model_copy(update={"model_id": "query.unknown"})
    output = tmp_path / "candidates"
    with pytest.raises(ValueError, match="FEATURE_PLUGIN_UNAVAILABLE"):
        generate_candidates(model, "pairwise", (), output)
    # The plugin is resolved before any directory is created.
    assert not output.exists()


def test_pairwise_generation_targets_gap_and_closes_designed_coverage(tmp_path: Path) -> None:
    model = load_test_model(ROOT / "models" / "query" / "join.yaml")
    active = load_query_directory(ROOT / "cases" / "query")
    output = tmp_path / "candidates"
    candidates = generate_candidates(model, "pairwise", active, output)
    generated = load_query_directory(output)
    active_claims = [claim for case in active if case.metadata.status.value == "active" for claim in case.coverage]
    generated_claims = [claim for case in generated for claim in case.coverage]
    result = coverage_gap(model, active_claims + generated_claims, "pairwise")
    assert len(candidates) == len(generated)
    assert result["covered"] == result["required"]
    assert result["missing"] == 0
    repeated = generate_candidates(model, "pairwise", active, output)
    assert repeated == ()


def test_limited_generation_continues_without_repeating_prior_batch(tmp_path: Path) -> None:
    model = load_test_model(ROOT / "models" / "query" / "join.yaml")
    active = load_query_directory(ROOT / "cases" / "query")
    output = tmp_path / "candidates"
    first = generate_candidates(model, "pairwise", active, output, limit=2)
    second = generate_candidates(model, "pairwise", active, output, limit=2)
    assert len(first) == 2 and len(second) == 2
    assert {path.name for path in first}.isdisjoint(path.name for path in second)


def test_unowned_candidates_are_reserved_for_ids_but_do_not_reduce_job_coverage(tmp_path: Path) -> None:
    model = load_test_model(ROOT / "models" / "query" / "join.yaml")
    active = load_query_directory(ROOT / "cases" / "query")
    output = tmp_path / "candidates"
    stale = generate_candidates(model, "pairwise", active, output, limit=1)

    selected = generate_candidates(model, "pairwise", active, output, limit=1, reserved_case_ids=set())

    assert len(stale) == 1 and len(selected) == 1
    # The existing deterministic candidate is selected into this Job, so its
    # evidence can be reused without silently counting every shared-root file.
    assert stale[0] == selected[0]
