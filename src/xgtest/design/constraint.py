"""Pure deterministic constraint evaluation."""

from __future__ import annotations

from collections.abc import Mapping

from .model import TestModel


def validate_assignment(model: TestModel, assignment: Mapping[str, str]) -> None:
    expected = set(model.dimensions)
    received = set(assignment)
    if received - expected:
        raise ValueError(f"ASSIGNMENT_UNKNOWN_DIMENSION: {sorted(received - expected)}")
    if expected - received:
        raise ValueError(f"ASSIGNMENT_DIMENSION_MISSING: {sorted(expected - received)}")
    for name, value in assignment.items():
        if value not in model.dimensions[name].values:
            raise ValueError(f"ASSIGNMENT_UNKNOWN_VALUE: {name}={value}")
    for rule in model.constraints:
        if all(assignment[key] == value for key, value in rule.if_.items()):
            if rule.then is not None and any(assignment[key] != value for key, value in rule.then.items()):
                raise ValueError("ASSIGNMENT_CONSTRAINT_THEN_FAILED")
            if rule.exclude is not None and any(assignment[key] in values for key, values in rule.exclude.items()):
                raise ValueError("ASSIGNMENT_CONSTRAINT_EXCLUDED")


def satisfies_constraints(model: TestModel, assignment: Mapping[str, str]) -> bool:
    try:
        validate_assignment(model, assignment)
    except ValueError:
        return False
    return True

