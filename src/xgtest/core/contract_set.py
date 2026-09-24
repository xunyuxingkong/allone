"""Deterministic G0A core contract descriptor and content identity."""

from __future__ import annotations

import hashlib
from pathlib import Path

from .canonical import xgmj1_sha256


DESCRIPTOR_VERSION = "1"
CONTRACT_VERSION = "1.1"
_SOURCE_DIRS = ("registry", "src/xgtest/core", "src/xgtest/query", "framework_tests/contract")
_SOURCE_FILES = (
    "src/xgtest/cli.py",
    "src/xgtest/runtime/profile.py",
    "src/xgtest/runtime/comparator.py",
    "src/xgtest/adapter/xugu.py",
)
_GENERATED_DIRS = ("schemas",)
_GENERATED_FILES = ("src/xgtest/generated/registry_enums.py",)


def _content_hashes(root: Path, directories: tuple[str, ...], files: tuple[str, ...]) -> dict[str, str]:
    paths = [root / name for name in files]
    for directory in directories:
        paths.extend(path for path in (root / directory).rglob("*") if path.is_file() and path.suffix in {".py", ".yaml", ".json"})
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(
            path.read_bytes().replace(b"\r\n", b"\n")
        ).hexdigest()
        for path in sorted(paths)
    }


def build_contract_descriptor(root: Path) -> dict[str, object]:
    """Build an immutable content identity without paths, time, or Git state."""
    root = root.resolve()
    sources = _content_hashes(root, _SOURCE_DIRS, _SOURCE_FILES)
    generated = _content_hashes(root, _GENERATED_DIRS, _GENERATED_FILES)
    identity = {
        "descriptor_version": DESCRIPTOR_VERSION,
        "contract_version": CONTRACT_VERSION,
        "generator": "xgtest.schema_export.v1",
        "sources": sources,
        "generated": generated,
    }
    return {**identity, "contract_set_id": xgmj1_sha256(identity)}
