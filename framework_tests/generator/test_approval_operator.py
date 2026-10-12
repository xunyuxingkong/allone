import json
from datetime import UTC, datetime

import pytest

from xgtest.core.canonical import xgmj1_sha256
from xgtest.generator.approval_operator import prepare_approval_payload


def _freeze(value: dict, id_key: str) -> dict:
    digest = xgmj1_sha256(value)
    return {**value, id_key: digest}


def test_prepare_approval_payload_binds_frozen_manifest_and_plan(tmp_path):
    manifest = _freeze({"phase": "pre_promotion", "members": [{"case_id": "QUERY.JOIN.ABCDEF12"}]}, "manifest_id")
    plan = _freeze({"manifest_id": manifest["manifest_id"], "selected": ["QUERY.JOIN.ABCDEF12"]}, "plan_hash")
    manifest_path, plan_path, output = (tmp_path / name for name in ("manifest.json", "plan.json", "payload.json"))
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    plan_path.write_text(json.dumps(plan), encoding="utf-8")

    result = prepare_approval_payload(
        manifest_path, plan_path, output, principal="reviewer@example.test",
        now=datetime(2026, 10, 12, tzinfo=UTC),
    )

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert result["manifest_id"] == manifest["manifest_id"]
    assert payload["plan_hash"] == plan["plan_hash"]
    assert payload["principal"] == "reviewer@example.test"
    assert payload["issued_at"] == "2026-10-12T00:00:00+00:00"


def test_prepare_approval_payload_rejects_stale_plan(tmp_path):
    manifest = _freeze({"phase": "pre_promotion"}, "manifest_id")
    plan = _freeze({"manifest_id": "0" * 64, "selected": []}, "plan_hash")
    manifest_path, plan_path = tmp_path / "manifest.json", tmp_path / "plan.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    plan_path.write_text(json.dumps(plan), encoding="utf-8")

    with pytest.raises(ValueError, match="APPROVAL_PLAN_BINDING_INVALID"):
        prepare_approval_payload(manifest_path, plan_path, tmp_path / "payload.json", principal="reviewer")


def test_prepare_approval_payload_requires_short_expiration(tmp_path):
    manifest = _freeze({"phase": "pre_promotion"}, "manifest_id")
    plan = _freeze({"manifest_id": manifest["manifest_id"]}, "plan_hash")
    manifest_path, plan_path = tmp_path / "manifest.json", tmp_path / "plan.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    plan_path.write_text(json.dumps(plan), encoding="utf-8")

    with pytest.raises(ValueError, match="APPROVAL_EXPIRY_INVALID"):
        prepare_approval_payload(manifest_path, plan_path, tmp_path / "payload.json", principal="reviewer", expires_in_hours=0)
