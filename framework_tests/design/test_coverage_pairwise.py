from pathlib import Path

from xgtest.design.coverage import required_coverage, valid_assignments
from xgtest.design.model import load_test_model


ROOT = Path(__file__).resolve().parents[2]


def test_pairwise_requirements_are_feasible_and_deterministic() -> None:
    model = load_test_model(ROOT / "models" / "query" / "join.yaml")
    first = required_coverage(model, "pairwise")
    second = required_coverage(model, "pairwise")
    assignments = valid_assignments(model)
    assert first == second
    assert len(assignments) < 1000
    assert all(any(all(row[name] == value for name, value in req.selections) for row in assignments) for req in first)
