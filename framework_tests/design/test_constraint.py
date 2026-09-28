from pathlib import Path

import pytest

from xgtest.design.constraint import validate_assignment
from xgtest.design.model import load_test_model


ROOT = Path(__file__).resolve().parents[2]


def model():
    return load_test_model(ROOT / "models" / "query" / "join.yaml")


def test_valid_cross_assignment_passes_and_forbidden_assignment_fails() -> None:
    valid_assignment = {"join_type": "cross", "predicate": "none", "datatype": "int", "null_side": "none", "interaction": "where"}
    validate_assignment(model(), valid_assignment)
    with pytest.raises(ValueError, match="THEN_FAILED"):
        validate_assignment(model(), {**valid_assignment, "predicate": "equality"})


def test_unknown_dimensions_values_and_excluded_subquery_fail() -> None:
    subject = model()
    base = {"join_type": "cross", "predicate": "none", "datatype": "int", "null_side": "none", "interaction": "none"}
    with pytest.raises(ValueError, match="UNKNOWN_DIMENSION"):
        validate_assignment(subject, {**base, "extra": "x"})
    with pytest.raises(ValueError, match="UNKNOWN_VALUE"):
        validate_assignment(subject, {**base, "datatype": "money"})
    with pytest.raises(ValueError, match="EXCLUDED"):
        validate_assignment(subject, {**base, "interaction": "subquery"})
