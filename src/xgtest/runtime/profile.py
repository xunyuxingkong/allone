"""Build a reviewable SQL Runtime Profile from sanitized probe evidence."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from xgtest.core.canonical import xgmj1_bytes
from xgtest.core.models import RuntimeProfile


def _canonical_bytes(value: Any) -> bytes:
    """Encode evidence for its audit hash (identity uses XGMJ1 below)."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")


_RUNTIME_ONLY_KEYS = {
    "started_at", "finished_at", "timestamp", "run_id", "probe_run_id",
    "table_name", "random_table", "artifact", "duration_ms", "host",
    "port", "host_hash", "database_alias", "evidence_sha256",
}
_SEMANTIC_TARGET_KEYS = {
    "database_product", "database_version", "db_build", "driver_name",
    "driver_version", "os", "arch", "topology", "mode",
    "configuration_fingerprint", "dataset_fingerprint",
}


def _strip_runtime_fields(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: cleaned
            for key, item in sorted(value.items())
            if key not in _RUNTIME_ONLY_KEYS
            and (cleaned := _strip_runtime_fields(item)) is not None
        }
    if isinstance(value, list):
        return [_strip_runtime_fields(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_strip_runtime_fields(item) for item in value)
    return value


def _profile_identity(evidence: dict[str, Any]) -> dict[str, Any]:
    target = evidence.get("target") if isinstance(evidence.get("target"), dict) else {}
    driver = evidence.get("driver") if isinstance(evidence.get("driver"), dict) else {}
    capabilities = evidence.get("capabilities") if isinstance(evidence.get("capabilities"), dict) else {}
    return {
        "profile_schema_version": "0.2",
        "target": {
            key: _strip_runtime_fields(target[key])
            for key in sorted(target)
            if key in _SEMANTIC_TARGET_KEYS and _strip_runtime_fields(target[key]) is not None
        },
        "driver": _strip_runtime_fields(driver),
        "capabilities": _strip_runtime_fields(capabilities),
    }


def build_profile(evidence: dict[str, Any]) -> dict[str, Any]:
    target = evidence.get("target") if isinstance(evidence.get("target"), dict) else {}
    driver = evidence.get("driver") if isinstance(evidence.get("driver"), dict) else {}
    evidence_hash = hashlib.sha256(_canonical_bytes(evidence)).hexdigest()
    identity = _profile_identity(evidence)
    profile_body = {
        "profile_schema_version": "0.2",
        "identity": identity,
        # Physical target values are evidence context used to prevent an
        # operator from applying a profile to the wrong database.  They are
        # deliberately excluded from the semantic profile identity.
        "target": {key: target[key] for key in sorted(target) if key in {"host_hash", "database_alias"}},
        "driver": {key: driver[key] for key in sorted(driver)},
        "evidence_sha256": evidence_hash,
    }
    profile_id = hashlib.sha256(xgmj1_bytes(identity)).hexdigest()
    return RuntimeProfile(
        **profile_body,
        sql_runtime_profile_id=profile_id,
    ).model_dump(mode="python")


def load_profile(path: Path) -> dict[str, Any]:
    profile = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(profile, dict) or not isinstance(profile.get("sql_runtime_profile_id"), str):
        raise ValueError("runtime profile must contain sql_runtime_profile_id")
    try:
        return RuntimeProfile.model_validate(profile).model_dump(mode="python")
    except ValueError as error:
        raise ValueError(str(error)) from error


def validate_profile(profile: dict[str, Any], *, host: str, database: str, driver_version: tuple[Any, ...]) -> None:
    target = profile.get("target", {})
    driver = profile.get("driver", {})
    host_hash = hashlib.sha256(host.encode()).hexdigest()
    if target.get("host_hash") != host_hash or target.get("database_alias") != database:
        raise ValueError("RUNTIME_PROFILE_MISMATCH: target identity differs")
    identity = profile.get("identity") if isinstance(profile.get("identity"), dict) else {}
    identity_driver = identity.get("driver") if isinstance(identity.get("driver"), dict) else {}
    recorded_version = tuple(identity_driver.get("version", driver.get("version", ())))
    if recorded_version and recorded_version != tuple(driver_version):
        raise ValueError("RUNTIME_PROFILE_MISMATCH: driver version differs")


def build_profile_file(evidence_path: Path, output: Path) -> dict[str, Any]:
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    if not isinstance(evidence, dict):
        raise ValueError("probe evidence must be a JSON object")
    profile = build_profile(evidence)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(profile, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return profile
