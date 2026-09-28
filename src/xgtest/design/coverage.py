"""Deterministic all-values and pairwise coverage requirement calculation."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations, product
from typing import Iterable, Protocol

from xgtest.core.models import CoverageClaim
from xgtest.core.canonical import xgmj1_sha256

from .constraint import validate_assignment
from .model import TestModel


@dataclass(frozen=True, order=True)
class CoverageRequirement:
    requirement_id: str
    strategy: str
    selections: tuple[tuple[str, str], ...]


class CoverageSource(Protocol):
    def active_claims(self, model_id: str) -> Iterable[CoverageClaim]: ...


class FileCoverageSource:
    def __init__(self, cases: Iterable[object]) -> None:
        self._cases = tuple(cases)

    def active_claims(self, model_id: str) -> Iterable[CoverageClaim]:
        for case in self._cases:
            if case.metadata.status.value != "active":
                continue
            for claim in case.coverage:
                if claim.model_id == model_id:
                    yield claim


def valid_assignments(model: TestModel) -> tuple[dict[str, str], ...]:
    names = tuple(sorted(model.dimensions))
    values = [model.dimensions[name].values for name in names]
    result = []
    for combination in product(*values):
        assignment = dict(zip(names, combination, strict=True))
        try:
            validate_assignment(model, assignment)
        except ValueError:
            continue
        result.append(assignment)
    return tuple(result)


def required_coverage(model: TestModel, strategy: str) -> tuple[CoverageRequirement, ...]:
    if strategy not in {item.type for item in model.coverage["strategies"]}:
        raise ValueError(f"COVERAGE_STRATEGY_UNDECLARED: {strategy}")
    if strategy not in {"all_values", "pairwise"}:
        raise ValueError(f"COVERAGE_STRATEGY_NOT_IMPLEMENTED: {strategy}")
    feasible = valid_assignments(model)
    requirements: set[tuple[tuple[str, str], ...]] = set()
    if strategy == "all_values":
        for name in sorted(model.dimensions):
            for value in model.dimensions[name].values:
                if any(assignment[name] == value for assignment in feasible):
                    requirements.add(((name, value),))
    else:
        names = tuple(sorted(model.dimensions))
        for left, right in combinations(names, 2):
            for a, b in product(model.dimensions[left].values, model.dimensions[right].values):
                if any(row[left] == a and row[right] == b for row in feasible):
                    requirements.add(((left, a), (right, b)))
    return tuple(
        CoverageRequirement(_requirement_id(model, strategy, selections), strategy, selections)
        for selections in sorted(requirements)
    )


def _requirement_id(model: TestModel, strategy: str, selections: tuple[tuple[str, str], ...]) -> str:
    return xgmj1_sha256({"model_id": model.model_id, "model_version": model.model_version, "strategy": strategy, "selections": selections})


def assignment_requirements(model: TestModel, assignment: dict[str, str], strategy: str) -> frozenset[str]:
    validate_assignment(model, assignment)
    if strategy not in {"all_values", "pairwise"}:
        raise ValueError(f"COVERAGE_STRATEGY_NOT_IMPLEMENTED: {strategy}")
    if strategy not in {item.type for item in model.coverage["strategies"]}:
        raise ValueError(f"COVERAGE_STRATEGY_UNDECLARED: {strategy}")
    names = tuple(sorted(model.dimensions))
    groups = (
        (((name, assignment[name]),) for name in names)
        if strategy == "all_values"
        else (tuple((name, assignment[name]) for name in pair) for pair in combinations(names, 2))
    )
    return frozenset(_requirement_id(model, strategy, selections) for selections in groups)


def coverage_gap(model: TestModel, claims: Iterable[CoverageClaim] | CoverageSource, strategy: str) -> dict[str, object]:
    if hasattr(claims, "active_claims"):
        claims = claims.active_claims(model.model_id)
    required = required_coverage(model, strategy)
    required_ids = {item.requirement_id for item in required}
    covered: set[str] = set()
    for claim in claims:
        if claim.model_id != model.model_id or claim.model_version != model.model_version:
            continue
        covered.update(assignment_requirements(model, claim.assignment, strategy))
    covered &= required_ids
    missing = tuple(item for item in required if item.requirement_id not in covered)
    return {
        "model_id": model.model_id,
        "model_version": model.model_version,
        "strategy": strategy,
        "required": len(required),
        "covered": len(covered),
        "missing": len(missing),
        "requirements": required,
        "missing_requirements": missing,
    }

