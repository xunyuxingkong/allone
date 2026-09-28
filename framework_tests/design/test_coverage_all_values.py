from pathlib import Path

from xgtest.design.coverage import coverage_gap, required_coverage
from xgtest.design.model import load_test_model


ROOT = Path(__file__).resolve().parents[2]


def test_all_values_requirements_and_gap_count() -> None:
    model = load_test_model(ROOT / "models" / "query" / "join.yaml")
    required = required_coverage(model, "all_values")
    assert len(required) == sum(len(dimension.values) for dimension in model.dimensions.values())
    gap = coverage_gap(model, (), "all_values")
    assert gap["required"] == len(required)
    assert gap["covered"] == 0
    assert gap["missing"] == len(required)
