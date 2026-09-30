"""Immutable, local content addressed storage for acceptance evidence."""

from __future__ import annotations

import hashlib
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class ArtifactRef:
    uri: str
    sha256: str
    size_bytes: int
    media_type: str
    schema_version: str = "1"

    def as_dict(self) -> dict[str, str | int]:
        return asdict(self)


class LocalArtifactStore:
    def __init__(self, root: Path) -> None:
        self.root = Path(root).resolve()

    def put(self, content: bytes, *, media_type: str = "application/json") -> ArtifactRef:
        digest = hashlib.sha256(content).hexdigest()
        relative = Path("objects") / digest[:2] / f"{digest}.json"
        destination = self.root / relative
        reference = ArtifactRef(relative.as_posix(), digest, len(content), media_type)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            self.verify(reference)
            return reference
        descriptor, temporary = tempfile.mkstemp(prefix=".artifact-", dir=destination.parent)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            try:
                os.link(temporary, destination)
            except FileExistsError:
                self.verify(reference)
        finally:
            Path(temporary).unlink(missing_ok=True)
        return reference

    def get(self, reference: ArtifactRef) -> bytes:
        path = Path(reference.uri)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("ARTIFACT_REFERENCE_OUTSIDE_STORE")
        resolved = (self.root / path).resolve()
        if not resolved.is_relative_to(self.root):
            raise ValueError("ARTIFACT_REFERENCE_OUTSIDE_STORE")
        content = resolved.read_bytes()
        if len(content) != reference.size_bytes or hashlib.sha256(content).hexdigest() != reference.sha256:
            raise ValueError("ARTIFACT_HASH_MISMATCH")
        return content

    def verify(self, reference: ArtifactRef) -> None:
        self.get(reference)
