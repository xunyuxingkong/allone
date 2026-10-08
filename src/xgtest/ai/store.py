"""File-backed job checkpoints with replayable, locked append-first events."""
import json
import os
import re
import tempfile
import threading
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from xgtest.ai.models import JobEvent, TestJob

_locks_guard = threading.Lock()
_locks: dict[str, threading.Lock] = {}


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".job-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, sort_keys=True, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


class JobStore:
    def __init__(self, root: Path):
        self.root = root.resolve()

    def directory(self, job_id: str) -> Path:
        if not re.fullmatch(r"[0-9a-f]{32}", job_id):
            raise ValueError("JOB_ID_INVALID")
        path = (self.root / job_id).resolve()
        if not path.is_relative_to(self.root):
            raise ValueError("JOB_PATH_INVALID")
        return path

    @contextmanager
    def lock(self, job_id: str):
        directory = self.directory(job_id)
        with self.directory_lock(directory):
            yield

    @contextmanager
    def execution_lock(self):
        with self.directory_lock(self.root):
            yield

    @contextmanager
    def directory_lock(self, directory):
        directory.mkdir(parents=True, exist_ok=True)
        key = str(directory)
        with _locks_guard:
            guard = _locks.setdefault(key, threading.Lock())
        if not guard.acquire(blocking=False):
            raise ValueError("JOB_BUSY")
        try:
            with (directory / "job.lock").open("a+b") as stream:
                if stream.tell() == 0:
                    stream.write(b"0"); stream.flush()
                stream.seek(0)
                try:
                    if os.name == "nt":
                        import msvcrt
                        msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                    else:
                        import fcntl
                        fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                except OSError as error:
                    raise ValueError("JOB_BUSY") from error
                try:
                    yield
                finally:
                    if os.name == "nt":
                        stream.seek(0); msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
                    else:
                        fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
        finally:
            guard.release()

    def load(self, job_id: str) -> TestJob:
        directory = self.directory(job_id)
        events = directory / "events.jsonl"
        # A killed writer may leave one partial trailing event. Never replay it.
        if events.is_file():
            latest = None
            for raw in events.read_bytes().splitlines(keepends=True):
                if not raw.endswith(b"\n"):
                    break
                event = JobEvent.model_validate_json(raw)
                if event.sequence != (1 if latest is None else latest.revision + 1) or event.checkpoint.revision != event.sequence or event.checkpoint.job_id != job_id:
                    raise ValueError("JOB_EVENT_SEQUENCE_INVALID")
                latest = event.checkpoint
            if latest is not None:
                return latest
        return TestJob.model_validate_json((directory / "state.json").read_bytes())

    def save(self, job: TestJob, event: str) -> TestJob:
        directory = self.directory(job.job_id)
        directory.mkdir(parents=True, exist_ok=True)
        checkpoint = job.model_copy(update={"revision": job.revision + 1})
        record = JobEvent(sequence=checkpoint.revision, event=event, timestamp=datetime.now(UTC).isoformat(), checkpoint=checkpoint)
        events = directory / "events.jsonl"
        with events.open("a+b") as stream:
            stream.seek(0); content = stream.read()
            if content and not content.endswith(b"\n"):
                stream.truncate(content.rfind(b"\n") + 1)
            stream.seek(0, os.SEEK_END)
            stream.write((record.model_dump_json() + "\n").encode()); stream.flush(); os.fsync(stream.fileno())
        write_json(directory / "state.json", checkpoint.model_dump(mode="json"))
        write_json(directory / "intent.json", checkpoint.intent.model_dump(mode="json"))
        write_json(directory / "plan.json", checkpoint.plan.model_dump(mode="json"))
        return checkpoint

    def list(self) -> list[dict]:
        if not self.root.exists():
            return []
        items = []
        for directory in sorted(self.root.iterdir(), key=lambda item: item.stat().st_mtime, reverse=True):
            if directory.is_dir() and re.fullmatch(r"[0-9a-f]{32}", directory.name):
                try:
                    job = self.load(directory.name)
                    items.append({"job_id": job.job_id, "goal": job.plan.goal, "state": job.state, "revision": job.revision})
                except (OSError, ValueError):
                    items.append({"job_id": directory.name, "goal": "", "state": "BLOCKED", "error": "JOB_STATE_INVALID"})
        return items
