"""Cooperating directory readers and publishers share one project lock.

This provides consistent reads for the recoverable batch protocol. It is not
an atomic version pointer: an interrupted publication blocks readers until
the signed batch is recovered.
"""

from contextlib import contextmanager
from functools import wraps
from pathlib import Path
import json
import os
import threading


_local = threading.local()
_guard = threading.Lock()
_locks: dict[str, threading.RLock] = {}


@contextmanager
def active_asset_lock(root: Path, *, publishing: bool = False):
    root = root.resolve()
    key = str(root)
    held = getattr(_local, "held", {})
    if key in held:
        if publishing and not held[key]:
            raise ValueError("ACTIVE_LOCK_UPGRADE_FORBIDDEN")
        yield
        return
    with _guard:
        lock = _locks.setdefault(key, threading.RLock())
    with lock:
        directory = root / "artifacts/promotion-journal"
        directory.mkdir(parents=True, exist_ok=True)
        with (directory / "promotion.lock").open("a+b") as stream:
            if stream.tell() == 0:
                stream.write(b"0")
                stream.flush()
            stream.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_LOCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX if publishing else fcntl.LOCK_SH)
            held[key] = publishing
            _local.held = held
            try:
                if not publishing:
                    for path in directory.glob("*.json"):
                        if path.name.startswith("receipt-"):
                            continue
                        journal = json.loads(path.read_text(encoding="utf-8"))
                        if journal.get("state") != "COMPLETE":
                            raise ValueError("ACTIVE_PUBLICATION_INCOMPLETE: recover signed batch before reading")
                yield
            finally:
                del held[key]
                if os.name == "nt":
                    stream.seek(0)
                    msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def consistent_active_read(function):
    @wraps(function)
    def wrapped(directory: Path, *args, **kwargs):
        path = directory.resolve()
        cases = next((parent for parent in (path, *path.parents) if parent.name == "cases"), None)
        if cases is None:
            return function(directory, *args, **kwargs)
        with active_asset_lock(cases.parent):
            return function(directory, *args, **kwargs)
    return wrapped
