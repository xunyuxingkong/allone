import json
import threading
import multiprocessing
from pathlib import Path

import pytest

from xgtest.core.asset_lock import active_asset_lock
from xgtest.query.loader import load_query_directory_with_sources


def _process_read(root, started, acquired):
    started.set()
    with active_asset_lock(Path(root)):
        acquired.set()


def test_reader_in_another_process_waits_for_publisher(tmp_path: Path):
    context = multiprocessing.get_context("spawn")
    started, acquired = context.Event(), context.Event()
    process = context.Process(target=_process_read, args=(str(tmp_path), started, acquired))
    try:
        with active_asset_lock(tmp_path, publishing=True):
            process.start()
            assert started.wait(10)
            assert not acquired.wait(0.1)
        assert acquired.wait(10)
        process.join(10)
        assert process.exitcode == 0
    finally:
        if process.is_alive():
            process.terminate()
            process.join(10)


def test_reader_waits_for_batch_publisher(tmp_path: Path):
    entered = threading.Event()
    finished = threading.Event()
    failures = []

    def read():
        entered.set()
        try:
            with active_asset_lock(tmp_path):
                finished.set()
        except Exception as error:
            failures.append(error)

    with active_asset_lock(tmp_path, publishing=True):
        # Nested loader reads by the publisher must not deadlock.
        with active_asset_lock(tmp_path):
            pass
        worker = threading.Thread(target=read)
        worker.start()
        assert entered.wait(2)
        assert not finished.wait(0.05)
    worker.join(2)
    assert finished.is_set() and not failures


def test_interrupted_batch_blocks_directory_loader_until_recovery(tmp_path: Path):
    cases = tmp_path / "cases/query"
    cases.mkdir(parents=True)
    with active_asset_lock(tmp_path, publishing=True):
        journal = tmp_path / "artifacts/promotion-journal/fixture.json"
        journal.write_text(json.dumps({"state": "IN_PROGRESS"}))
    with pytest.raises(ValueError, match="ACTIVE_PUBLICATION_INCOMPLETE"):
        load_query_directory_with_sources(cases)
    with active_asset_lock(tmp_path, publishing=True):
        journal.write_text(json.dumps({"state": "COMPLETE"}))
    with active_asset_lock(tmp_path):
        pass
