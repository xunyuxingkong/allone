from pathlib import Path

import pytest

from xgtest.design.model import TestModel as QueryTestModel, load_test_model


ROOT = Path(__file__).resolve().parents[2]


def test_join_model_loads_with_declared_dimensions_and_strategies() -> None:
    model = load_test_model(ROOT / "models" / "query" / "join.yaml")
    assert model.model_id == "query.join"
    assert tuple(sorted(model.dimensions)) == ("datatype", "interaction", "join_type", "null_side", "predicate")
    assert {strategy.type for strategy in model.coverage["strategies"]} == {"all_values", "pairwise"}


@pytest.mark.parametrize("payload, message", [
    ({"model_id": "m", "model_version": "1", "module": "q", "feature": "q", "dimensions": {"x": {"values": ["a", "a"]}}, "coverage": {"strategies": [{"type": "all_values"}]}}, "MODEL_VALUE_DUPLICATED"),
    ({"model_id": "m", "model_version": "1", "module": "q", "feature": "q", "dimensions": {"x": {"values": ["a"]}}, "constraints": [{"if": {"missing": "a"}, "then": {"x": "a"}}], "coverage": {"strategies": [{"type": "all_values"}]}}, "MODEL_CONSTRAINT_UNKNOWN_DIMENSION"),
])
def test_invalid_model_is_rejected(payload: dict, message: str) -> None:
    payload["dimensions"] = {name: {"values": tuple(value["values"])} for name, value in payload["dimensions"].items()}
    payload["coverage"] = {"strategies": tuple(payload["coverage"]["strategies"])}
    if "constraints" in payload:
        payload["constraints"] = tuple(payload["constraints"])
    with pytest.raises(ValueError, match=message):
        QueryTestModel.model_validate(payload)
