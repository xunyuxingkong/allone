"""Build a reviewable SQL Runtime Profile from sanitized probe evidence."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")


def build_profile(evidence: dict[str, Any]) -> dict[str, Any]:
    target = evidence.get("target") if isinstance(evidence.get("target"), dict) else {}
    driver = evidence.get("driver") if isinstance(evidence.get("driver"), dict) else {}
    capabilities = evidence.get("capabilities") if isinstance(evidence.get("capabilities"), dict) else {}
    evidence_hash = hashlib.sha256(_canonical_bytes(evidence)).hexdigest()
    profile_body = {
        "profile_schema_version": "0.1",
        "target": {key: target[key] for key in sorted(target) if key in {"host_hash", "database_alias"}},
        "driver": {key: driver[key] for key in sorted(driver)},
        "capabilities": {key: capabilities[key] for key in sorted(capabilities)},
        "evidence_sha256": evidence_hash,
    }
    profile_id = hashlib.sha256(_canonical_bytes(profile_body)).hexdigest()
    return {**profile_body, "sql_runtime_profile_id": profile_id}


def build_profile_file(evidence_path: Path, output: Path) -> dict[str, Any]:
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    if not isinstance(evidence, dict):
        raise ValueError("probe evidence must be a JSON object")
    profile = build_profile(evidence)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(profile, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return profile
