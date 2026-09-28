"""Versioned declarative test-model contract."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from xgtest.core.models import StrictModel
from xgtest.core.yaml_loader import load_yaml


class ConstraintRule(StrictModel):
    if_: dict[str, str] = Field(alias="if")
    then: dict[str, str] | None = None
    exclude: dict[str, tuple[str, ...]] | None = None

    @model_validator(mode="after")
    def has_one_action(self) -> "ConstraintRule":
        if (self.then is None) == (self.exclude is None):
            raise ValueError("MODEL_CONSTRAINT_ACTION_INVALID: exactly one of then/exclude is required")
        return self


class CoverageStrategy(StrictModel):
    type: Literal["all_values", "pairwise", "boundary", "negative", "interaction"]
    strength: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def supported_strength(self) -> "CoverageStrategy":
        if self.type == "pairwise" and self.strength not in {None, 2}:
            raise ValueError("MODEL_PAIRWISE_STRENGTH_UNSUPPORTED")
        if self.type != "pairwise" and self.strength is not None:
            raise ValueError("MODEL_STRATEGY_STRENGTH_UNSUPPORTED")
        return self


class Dimension(StrictModel):
    values: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_values(self) -> "Dimension":
        if len(self.values) != len(set(self.values)):
            raise ValueError("MODEL_VALUE_DUPLICATED")
        return self


class TestModel(StrictModel):
    model_id: str
    model_version: str
    module: str
    feature: str
    subfeature: str | None = None
    dimensions: dict[str, Dimension]
    constraints: tuple[ConstraintRule, ...] = ()
    coverage: dict[str, tuple[CoverageStrategy, ...]]

    @model_validator(mode="after")
    def validate_references(self) -> "TestModel":
        names = set(self.dimensions)
        if not names:
            raise ValueError("MODEL_DIMENSIONS_REQUIRED")
        if any(not name for name in names):
            raise ValueError("MODEL_DIMENSION_NAME_INVALID")
        for rule in self.constraints:
            references = set(rule.if_)
            if rule.then is not None:
                references |= set(rule.then)
            if rule.exclude is not None:
                references |= set(rule.exclude)
            unknown = references - names
            if unknown:
                raise ValueError(f"MODEL_CONSTRAINT_UNKNOWN_DIMENSION: {sorted(unknown)}")
            for condition in (rule.if_, rule.then or {}):
                for dimension, value in condition.items():
                    if value not in self.dimensions[dimension].values:
                        raise ValueError(f"MODEL_CONSTRAINT_UNKNOWN_VALUE: {dimension}={value}")
            for dimension, values in (rule.exclude or {}).items():
                if set(values) - set(self.dimensions[dimension].values):
                    raise ValueError(f"MODEL_CONSTRAINT_UNKNOWN_VALUE: {dimension}")
        if "strategies" not in self.coverage or not self.coverage["strategies"]:
            raise ValueError("MODEL_STRATEGIES_REQUIRED")
        strategy_names = [strategy.type for strategy in self.coverage["strategies"]]
        if len(strategy_names) != len(set(strategy_names)):
            raise ValueError("MODEL_STRATEGY_DUPLICATED")
        return self


def load_test_model(path: Path) -> TestModel:
    raw = load_yaml(path)
    if not isinstance(raw, dict):
        raise ValueError("MODEL_INVALID: expected a mapping")
    dimensions = raw.get("dimensions")
    if not isinstance(dimensions, dict):
        raise ValueError("MODEL_DIMENSIONS_INVALID")
    normalized = dict(raw)
    normalized["dimensions"] = {
        name: Dimension.model_validate({**value, "values": tuple(value.get("values", ()))})
        for name, value in dimensions.items()
    }
    normalized["constraints"] = tuple(
        {
            **rule,
            **({"exclude": {name: tuple(values) for name, values in rule["exclude"].items()}} if rule.get("exclude") is not None else {}),
        }
        for rule in raw.get("constraints", ())
    )
    normalized["coverage"] = {
        name: tuple(strategies)
        for name, strategies in raw.get("coverage", {}).items()
    }
    return TestModel.model_validate(normalized)

