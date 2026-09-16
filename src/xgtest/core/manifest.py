"""Input snapshot checks shared by Manifest and Bundle publishers."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from pathlib import Path

from .models import BundleRef, SourceInfo


def content_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _under_root(root: Path, relative_path: str) -> Path:
    root = root.resolve()
    candidate = (root / relative_path).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as error:
        raise ValueError("SOURCE_PATH_OUTSIDE_ROOT: source path escapes snapshot root") from error
    return candidate


def verify_source_snapshot(root: Path, sources: Iterable[SourceInfo]) -> None:
    """Reject missing or changed source files before a frozen run executes."""
    for source in sources:
        path = _under_root(root, source.relative_path)
        if not path.is_file():
            raise ValueError(f"SOURCE_MISSING: {source.relative_path}")
        observed = content_sha256(path)
        if observed != source.source_hash:
            raise ValueError(f"SOURCE_DRIFT: {source.relative_path}")


def verify_bundle(path: Path, expected: BundleRef) -> None:
    """Verify a compiled bundle's size and content hash before loading it."""
    if not path.is_file():
        raise ValueError(f"BUNDLE_MISSING: {path}")
    if path.stat().st_size != expected.size:
        raise ValueError(f"BUNDLE_SIZE_MISMATCH: {path}")
    if content_sha256(path) != expected.content_hash:
        raise ValueError(f"BUNDLE_DRIFT: {path}")
