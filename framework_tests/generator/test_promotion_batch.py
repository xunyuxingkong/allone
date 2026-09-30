"""Recovery uses synthetic assets and approvals, never repository candidates."""

import json
from pathlib import Path

import pytest
import yaml

from xgtest.core.canonical import xgmj1_sha256
from xgtest.generator import promotion_batch as batch


def _setup(tmp_path, monkeypatch):
    root = tmp_path
    source = root / "candidates/query/join/QUERY.TEST.yaml"
    source.parent.mkdir(parents=True)
    source.write_bytes(yaml.safe_dump({"metadata": {"id": "QUERY.TEST", "status": "review"}}, sort_keys=False).encode())
    active = root / "cases/query/join"
    active.mkdir(parents=True)
    manifest = {"phase": "pre_promotion", "members": [{"case_id": "QUERY.TEST", "asset_path": source.relative_to(root).as_posix(), "asset_sha256": batch._sha(source)}]}
    manifest["manifest_id"] = xgmj1_sha256(manifest)
    manifest_path = root / "manifest.json"
    manifest_path.write_text(json.dumps(manifest))
    monkeypatch.setattr(batch, "preflight_promotion", lambda *a, **kw: {"readiness": "READY", "blockers": []})
    monkeypatch.setattr(batch.ApprovalService, "verify", lambda *a, **kw: {"status": "APPROVED", "principal": "synthetic-test"})
    monkeypatch.setattr("xgtest.generator.scope.AcceptanceScope.load_model", lambda *a: object())
    monkeypatch.setattr(batch, "load_profile", lambda *a: {"sql_runtime_profile_id": "a" * 64})
    (root / "synthetic-approval").write_text("synthetic approval fixture")
    return root, source, manifest_path


def _args(root, manifest_path):
    return (root, root / "acceptance", root / "profile.json", manifest_path, root / "synthetic-approval", root / "synthetic-trust")


def test_approval_is_rechecked_before_each_publish(tmp_path, monkeypatch):
    root, source, manifest = _setup(tmp_path, monkeypatch)
    decisions = iter([{"status": "APPROVED"}, {"status": "WAITING_APPROVAL", "reason": "APPROVAL_REVOKED"}])
    monkeypatch.setattr(batch.ApprovalService, "verify", lambda *a, **kw: next(decisions))
    with pytest.raises(ValueError, match="APPROVAL_REVOKED"):
        batch.execute_promotion_batch(*_args(root, manifest))
    assert source.is_file()
    assert not (root / "cases/query/join" / source.name).exists()


@pytest.mark.parametrize("after_unlink", [False, True])
def test_resume_after_asset_publish_is_idempotent(tmp_path, monkeypatch, after_unlink):
    root, source, manifest_path = _setup(tmp_path, monkeypatch)
    calls = []

    def interrupted_promote(path, model, destination_root, *args, **kwargs):
        calls.append(path)
        payload = yaml.safe_load(path.read_text())
        payload["metadata"]["status"] = "active"
        (destination_root / path.name).write_bytes(yaml.safe_dump(payload, sort_keys=False).encode())
        if after_unlink:
            path.unlink()
        raise RuntimeError("synthetic crash")

    monkeypatch.setattr(batch, "promote_candidate", interrupted_promote)
    with pytest.raises(RuntimeError, match="synthetic crash"):
        batch.execute_promotion_batch(*_args(root, manifest_path))
    assert batch.execute_promotion_batch(*_args(root, manifest_path))["status"] == "COMPLETE"
    assert batch.execute_promotion_batch(*_args(root, manifest_path))["count"] == 1
    assert len(calls) == 1
    assert not source.exists()


def test_resume_rejects_journal_and_active_drift(tmp_path, monkeypatch):
    root, source, manifest_path = _setup(tmp_path, monkeypatch)
    monkeypatch.setattr(batch, "promote_candidate", lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("crash")))
    with pytest.raises(RuntimeError):
        batch.execute_promotion_batch(*_args(root, manifest_path))
    journal_path = next((root / "artifacts/promotion-journal").glob("*.json"))
    journal = json.loads(journal_path.read_text())
    journal["members"][0]["destination"] = "../outside.yaml"
    batch._write_json_atomic(journal_path, journal)
    with pytest.raises(ValueError, match="JOURNAL_MEMBER_MISMATCH"):
        batch.execute_promotion_batch(*_args(root, manifest_path))
    journal["members"][0]["destination"] = "cases/query/join/QUERY.TEST.yaml"
    batch._write_json_atomic(journal_path, journal)
    (root / "cases/query/join/unexpected.yaml").write_text("metadata: {}")
    with pytest.raises(ValueError, match="ACTIVE_SNAPSHOT_DRIFT"):
        batch.execute_promotion_batch(*_args(root, manifest_path))


def test_legacy_cli_cannot_promote_without_signed_batch():
    from xgtest.cli import _candidate_promote
    with pytest.raises(ValueError, match="SIGNED_BATCH_PROMOTION_REQUIRED"):
        _candidate_promote(object())
