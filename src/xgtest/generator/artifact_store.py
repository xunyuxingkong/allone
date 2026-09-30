"""Immutable, local content addressed storage for acceptance evidence."""

from __future__ import annotations

import hashlib
import os
import tempfile
import errno
import json
import zipfile
import re
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class ArtifactRef:
    uri: str
    sha256: str
    size_bytes: int
    media_type: str
    schema_version: str = "1"

    def __post_init__(self) -> None:
        if not isinstance(self.sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", self.sha256) or type(self.size_bytes) is not int or self.size_bytes < 0 or not isinstance(self.uri, str) or not isinstance(self.media_type, str) or not self.media_type or self.schema_version != "1":
            raise ValueError("ARTIFACT_REFERENCE_INVALID")

    def as_dict(self) -> dict[str, str | int]:
        return asdict(self)


@runtime_checkable
class ArtifactStore(Protocol):
    def put(self, content: bytes, *, media_type: str = "application/json") -> ArtifactRef: ...
    def get(self, reference: ArtifactRef) -> bytes: ...
    def verify(self, reference: ArtifactRef) -> None: ...
    def exists(self, reference: ArtifactRef) -> bool: ...


@contextmanager
def _publish_lock(path: Path):
    with path.open("a+b") as stream:
        stream.seek(0)
        stream.write(b"0")
        stream.flush()
        if os.name == "nt":
            import msvcrt
            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            if os.name == "nt":
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


class LocalArtifactStore:
    def __init__(self, root: Path) -> None:
        self.root = Path(root).resolve()

    def put(self, content: bytes, *, media_type: str = "application/json") -> ArtifactRef:
        digest = hashlib.sha256(content).hexdigest()
        relative = Path("objects") / digest[:2] / f"{digest}.json"
        destination = self.root / relative
        reference = ArtifactRef(relative.as_posix(), digest, len(content), media_type)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.resolve().is_relative_to(self.root):
            raise ValueError("ARTIFACT_REFERENCE_OUTSIDE_STORE")
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
            except OSError as error:
                if error.errno not in {errno.EXDEV, errno.EPERM, errno.ENOSYS, errno.EOPNOTSUPP, errno.EACCES}:
                    raise
                # Keep the target invisible until complete, with no O_EXCL partial file.
                with _publish_lock(destination.with_suffix(".publish-lock")):
                    if destination.exists():
                        self.verify(reference)
                    else:
                        os.replace(temporary, destination)
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

    def exists(self, reference: ArtifactRef) -> bool:
        try:
            self.verify(reference)
        except FileNotFoundError:
            return False
        return True


def export_artifact_bundle(store: ArtifactStore, references: tuple[ArtifactRef, ...], output: Path) -> None:
    """Portable complete originals; checksum every object before export."""
    objects = {reference.sha256: (reference, store.get(reference)) for reference in references}
    manifest = {"schema_version": "1", "artifacts": [reference.as_dict() for reference, _ in objects.values()]}
    output.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".bundle-", dir=output.parent)
    os.close(descriptor)
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, sort_keys=True))
            for digest, (_, content) in objects.items():
                archive.writestr(f"objects/{digest}", content)
        os.replace(temporary, output)
    finally:
        Path(temporary).unlink(missing_ok=True)


def import_artifact_bundle(store: ArtifactStore, source: Path, *, max_bytes: int = 64 * 1024 * 1024) -> tuple[ArtifactRef, ...]:
    """Validate the entire bundle before publishing; never extract archive paths."""
    with zipfile.ZipFile(source) as archive:
        infos = archive.infolist()
        if len(infos) > 10_000 or sum(item.file_size for item in infos) > max_bytes:
            raise ValueError("ARTIFACT_BUNDLE_LIMIT_EXCEEDED")
        names = [item.filename for item in infos]
        if len(names) != len(set(names)) or "manifest.json" not in names:
            raise ValueError("ARTIFACT_BUNDLE_ENTRIES_INVALID")
        manifest = json.loads(archive.read("manifest.json"))
        if not isinstance(manifest, dict) or manifest.get("schema_version") != "1" or not isinstance(manifest.get("artifacts"), list):
            raise ValueError("ARTIFACT_BUNDLE_MANIFEST_INVALID")
        references = tuple(ArtifactRef(**item) for item in manifest["artifacts"])
        if len({ref.sha256 for ref in references}) != len(references) or set(names) != {"manifest.json", *(f"objects/{ref.sha256}" for ref in references)}:
            raise ValueError("ARTIFACT_BUNDLE_SCOPE_INVALID")
        contents = []
        for reference in references:
            content = archive.read(f"objects/{reference.sha256}")
            if len(content) != reference.size_bytes or hashlib.sha256(content).hexdigest() != reference.sha256:
                raise ValueError("ARTIFACT_BUNDLE_HASH_MISMATCH")
            contents.append(content)
    imported = []
    for reference, content in zip(references, contents):
        imported.append(store.put(content, media_type=reference.media_type))
    return tuple(imported)
