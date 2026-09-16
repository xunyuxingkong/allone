"""Stable identity projections for Targets, Plans and Run Manifests."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from typing import Any

from .canonical import xgmj1_bytes


TARGET_IDENTITY_FIELDS = (
    "database_product", "database_version", "db_build", "driver_name",
    "driver_version", "os", "arch", "topology", "mode",
    "configuration_fingerprint", "dataset_fingerprint", "sql_runtime_profile_id",
)


def _dump(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="python")
    return value


def target_identity_projection(target: Mapping[str, Any] | Any) -> dict[str, Any]:
    data = _dump(target)
    if not isinstance(data, Mapping):
        raise TypeError("target identity input must be a mapping or model")
    return {
        key: _dump(data[key])
        for key in TARGET_IDENTITY_FIELDS
        if key in data and data[key] is not None
    }


def compute_target_id(target: Mapping[str, Any] | Any) -> str:
    """Compute the Target ID from semantic fields only, excluding target_id."""
    return hashlib.sha256(xgmj1_bytes(target_identity_projection(target))).hexdigest()


def validate_target_id(target: Mapping[str, Any] | Any) -> None:
    data = _dump(target)
    if not isinstance(data, Mapping) or data.get("target_id") != compute_target_id(data):
        raise ValueError("TARGET_ID_MISMATCH: target_id does not match identity projection")


def plan_identity_projection(plan: Mapping[str, Any] | Any) -> dict[str, Any]:
    data = _dump(plan)
    if not isinstance(data, Mapping):
        raise TypeError("plan identity input must be a mapping or model")
    targets = [_dump(item) for item in data.get("targets", ())]
    expected = [_dump(item) for item in data.get("expected_executions", ())]
    targets.sort(key=lambda item: str(item.get("target_id", "")))
    expected.sort(key=lambda item: (str(item.get("case_id", "")), str(item.get("target_id", ""))))
    return {
        "selector": data.get("selector"),
        "targets": targets,
        "expected_executions": expected,
    }


def compute_plan_hash(plan: Mapping[str, Any] | Any) -> str:
    return hashlib.sha256(xgmj1_bytes(plan_identity_projection(plan))).hexdigest()


def manifest_identity_projection(manifest: Mapping[str, Any] | Any) -> dict[str, Any]:
    data = _dump(manifest)
    if not isinstance(data, Mapping):
        raise TypeError("manifest identity input must be a mapping or model")
    plan = _dump(data.get("plan", {}))
    bundles = [_dump(item) for item in data.get("bundles", ())]
    target_entries = [_dump(item) for item in data.get("target_entries", ())]
    bundles.sort(key=lambda item: str(item.get("content_hash", "")))
    target_entries.sort(key=lambda item: str(item.get("target_id", "")))
    return {
        "run_id": data.get("run_id"),
        "contract_set_id": data.get("contract_set_id"),
        "plan": plan_identity_projection(plan),
        "bundles": bundles,
        "git_commit": data.get("git_commit"),
        "dirty": data.get("dirty"),
        "source_snapshot_hash": data.get("source_snapshot_hash"),
        "catalog_snapshot_id": data.get("catalog_snapshot_id"),
        "plan_hash": data.get("plan_hash"),
        "case_entries": sorted(data.get("case_entries", ())),
        "target_entries": target_entries,
        "runtime_versions": dict(sorted((data.get("runtime_versions") or {}).items())),
    }


def compute_manifest_hash(manifest: Mapping[str, Any] | Any) -> str:
    return hashlib.sha256(xgmj1_bytes(manifest_identity_projection(manifest))).hexdigest()
