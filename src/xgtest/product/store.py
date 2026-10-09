"""File-backed test missions. Missions are small, durable product records."""
import json
import os
import re
import tempfile
import threading
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from xgtest.product.contracts import TestMission

_locks_guard = threading.Lock()
_locks: dict[str, threading.Lock] = {}


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".mission-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, sort_keys=True, indent=2)
            stream.write("\n"); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


class MissionStore:
    def __init__(self, root: Path):
        self.root = root.resolve()

    def directory(self, mission_id: str) -> Path:
        if not re.fullmatch(r"[0-9a-f]{32}", mission_id):
            raise ValueError("MISSION_ID_INVALID")
        path = (self.root / mission_id).resolve()
        if not path.is_relative_to(self.root):
            raise ValueError("MISSION_PATH_INVALID")
        return path

    @contextmanager
    def lock(self, mission_id: str):
        directory = self.directory(mission_id)
        directory.mkdir(parents=True, exist_ok=True)
        with _locks_guard:
            guard = _locks.setdefault(str(directory), threading.Lock())
        if not guard.acquire(blocking=False):
            raise ValueError("MISSION_BUSY")
        try:
            with (directory / "mission.lock").open("a+b") as stream:
                if stream.tell() == 0:
                    stream.write(b"0"); stream.flush()
                stream.seek(0)
                try:
                    # Advisory lock mirrors JobStore: reject concurrent writers, no silent merge.
                    if os.name == "nt":
                        import msvcrt
                        msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                    else:
                        import fcntl
                        fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                except OSError as error:
                    raise ValueError("MISSION_BUSY") from error
                try:
                    yield
                finally:
                    if os.name == "nt":
                        stream.seek(0); msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
                    else:
                        fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
        finally:
            guard.release()

    def load(self, mission_id: str) -> TestMission:
        return TestMission.model_validate_json((self.directory(mission_id) / "mission.json").read_bytes())

    def save(self, mission: TestMission) -> TestMission:
        write_json(self.directory(mission.mission_id) / "mission.json", mission.model_dump(mode="json"))
        return mission

    def list(self) -> list[dict]:
        if not self.root.exists():
            return []
        items = []
        for directory in sorted(self.root.iterdir(), key=lambda item: item.stat().st_mtime, reverse=True):
            if directory.is_dir() and re.fullmatch(r"[0-9a-f]{32}", directory.name):
                try:
                    mission = self.load(directory.name)
                    created = datetime.fromtimestamp((directory / "mission.json").stat().st_mtime, tz=UTC).isoformat()
                    items.append({"mission_id": mission.mission_id, "name": mission.name, "state": mission.state,
                                  "module": mission.module, "features": mission.features, "strategy": mission.strategy,
                                  "job_id": mission.job_id, "created_at": created})
                except (OSError, ValueError):
                    items.append({"mission_id": directory.name, "name": "", "state": "BLOCKED", "error": "MISSION_STATE_INVALID"})
        return items
