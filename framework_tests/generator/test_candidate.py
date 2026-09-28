from pathlib import Path

from xgtest.design.coverage import coverage_gap
from xgtest.design.model import load_test_model
from xgtest.generator.candidate import generate_candidates
from xgtest.query.loader import load_query_directory


ROOT = Path(__file__).resolve().parents[2]


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
    assert repeated == candidates
