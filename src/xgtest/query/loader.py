"""Load Query YAML assets into strict Core QueryCaseInput models."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import ValidationError

from xgtest.core.errors import ContractError
from xgtest.core.models import (
    ComparisonProfile,
    EffectiveMetadata,
    QueryCaseInput,
    QueryStep,
    RawMetadata,
    decode_expected,
)
from xgtest.core.yaml_loader import load_yaml
from xgtest.generated.registry_enums import CaseAssetStatus, FeatureKey, IsolationScope, Level


def _source_error(path: Path, error: Exception) -> ValueError:
    if isinstance(error, ContractError) and error.source is not None:
        span = error.source
        location = f"{span.file}:{span.line}:{span.column}"
        return ValueError(f"{location} {error.code}: {error}")
    return ValueError(f"{path}: {error}")


def load_query_case(path: Path) -> QueryCaseInput:
    """Parse and validate one query case without connecting to a database."""
    path = path.resolve()
    try:
        raw = load_yaml(path)
        if not isinstance(raw, dict):
            raise ValueError("QUERY_CASE_INVALID: case must be a mapping")
        if set(raw) != {"metadata", "steps"}:
            raise ValueError("QUERY_CASE_FIELDS_INVALID: only metadata and steps are allowed")
        metadata_raw = raw.get("metadata")
        if not isinstance(metadata_raw, dict):
            raise ValueError("QUERY_METADATA_INVALID: metadata must be a mapping")
        metadata_input = dict(metadata_raw)
        if not metadata_input.get("id"):
            raise ValueError("QUERY_METADATA_ID_REQUIRED")
        metadata_input.setdefault("metadata_version", "query-1")
        metadata_input.setdefault("title", metadata_input["id"])
        metadata_input.setdefault("module", "query")
        metadata_input.setdefault("level", "P1")
        metadata_input.setdefault("status", "active")
        metadata_input.setdefault("timeout", "30s")
        metadata_input.setdefault("isolation", "session")
        metadata_input.setdefault("feature", "query")
        metadata_input["tags"] = tuple(metadata_input.get("tags", ()))
        for field, enum_type in {
            "feature": FeatureKey,
            "level": Level,
            "status": CaseAssetStatus,
            "isolation": IsolationScope,
        }.items():
            if isinstance(metadata_input.get(field), str):
                metadata_input[field] = enum_type(metadata_input[field])
        metadata = EffectiveMetadata.model_validate(
            RawMetadata.model_validate(metadata_input).model_dump(exclude_none=True, mode="python")
        )

        raw_steps = raw.get("steps")
        if not isinstance(raw_steps, list) or not raw_steps:
            raise ValueError("QUERY_STEPS_REQUIRED: steps must be a non-empty list")
        steps: list[QueryStep] = []
        for raw_step in raw_steps:
            if not isinstance(raw_step, dict):
                raise ValueError("QUERY_STEP_INVALID: each step must be a mapping")
            payload: dict[str, Any] = dict(raw_step)
            comparison = payload.get("comparison", {"mode": "exact"})
            if not isinstance(comparison, dict):
                raise ValueError("QUERY_COMPARISON_INVALID: comparison must be a mapping")
            payload["comparison"] = ComparisonProfile.model_validate(comparison)
            expected = payload.get("expected")
            if not isinstance(expected, dict):
                raise ValueError("QUERY_EXPECTED_REQUIRED: expected must be a mapping")
            payload["expected"] = decode_expected(expected)
            steps.append(QueryStep.model_validate(payload))
        return QueryCaseInput(metadata=metadata, steps=tuple(steps))
    except (ContractError, ValidationError, TypeError, ValueError) as error:
        raise _source_error(path, error) from error


def validate_query_directory(directory: Path) -> dict[str, Any]:
    paths = sorted((*directory.rglob("*.yaml"), *directory.rglob("*.yml")))
    if not paths:
        return {"status": "FAIL", "cases": 0, "invalid": 0, "errors": [f"no YAML cases found under {directory}"]}
    cases: list[tuple[Path, QueryCaseInput]] = []
    errors: list[str] = []
    for path in paths:
        try:
            cases.append((path, load_query_case(path)))
        except ValueError as error:
            errors.append(str(error))
    seen: set[str] = set()
    for path, case in cases:
        if case.metadata.id in seen:
            errors.append(f"{path}: QUERY_CASE_ID_DUPLICATED: {case.metadata.id}")
        seen.add(case.metadata.id)
    return {"status": "PASS" if not errors else "FAIL", "cases": len(paths) - len(errors), "invalid": len(errors), "errors": errors}


def load_query_directory(directory: Path) -> tuple[QueryCaseInput, ...]:
    result = validate_query_directory(directory)
    if result["status"] != "PASS":
        raise ValueError("\n".join(result["errors"]))
    paths = sorted((*directory.rglob("*.yaml"), *directory.rglob("*.yml")))
    return tuple(load_query_case(path) for path in paths)
