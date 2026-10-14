import json
import shutil
import subprocess
from datetime import UTC, datetime

import pytest

from xgtest.core.canonical import xgmj1_sha256
from xgtest.generator.approval_operator import (
    initialize_local_signer, prepare_approval_payload,
    sign_approval_payload, verify_operator_approval,
)


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


def test_operator_approval_full_local_flow_and_fail_closed_cases(tmp_path):
    if shutil.which("ssh-keygen") is None:
        pytest.skip("OpenSSH signing tool unavailable")
    project_root = tmp_path / "project"
    project_root.mkdir()
    operator_root = tmp_path / "operator"
    private_key = operator_root / "reviewer-key"
    allowed = operator_root / "allowed-signers"
    manifest = _freeze({"phase": "pre_promotion", "members": [{"case_id": "QUERY.JOIN.ABCDEF12"}]}, "manifest_id")
    plan = _freeze({"manifest_id": manifest["manifest_id"], "selected": ["QUERY.JOIN.ABCDEF12"]}, "plan_hash")
    manifest_path, plan_path = tmp_path / "manifest.json", tmp_path / "plan.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    plan_path.write_text(json.dumps(plan), encoding="utf-8")

    initialize_local_signer("reviewer", private_key, allowed, project_root=project_root, passphrase="")
    payload_path, approval_path = tmp_path / "payload.json", tmp_path / "approval.json"
    prepare_approval_payload(manifest_path, plan_path, payload_path, principal="reviewer")
    sign_approval_payload(payload_path, private_key, approval_path,
        manifest_path=manifest_path, plan_path=plan_path, project_root=project_root)
    assert verify_operator_approval(approval_path, allowed, manifest_path=manifest_path,
        plan_path=plan_path)["status"] == "APPROVED"

    revoked = tmp_path / "revoked.json"
    revoked.write_text(json.dumps([manifest["manifest_id"]]), encoding="utf-8")
    assert verify_operator_approval(approval_path, allowed, manifest_path=manifest_path,
        plan_path=plan_path, revoked_path=revoked)["reason"] == "APPROVAL_REVOKED"

    stale_plan = {**plan, "selected": ["QUERY.JOIN.OTHER"]}
    stale_plan = _freeze({key: value for key, value in stale_plan.items() if key != "plan_hash"}, "plan_hash")
    plan_path.write_text(json.dumps(stale_plan), encoding="utf-8")
    with pytest.raises(ValueError, match="APPROVAL_INPUT_STALE"):
        sign_approval_payload(payload_path, private_key, tmp_path / "stale.json",
            manifest_path=manifest_path, plan_path=plan_path, project_root=project_root)

    past_payload = tmp_path / "expired-payload.json"
    expired_approval = tmp_path / "expired-approval.json"
    plan_path.write_text(json.dumps(plan), encoding="utf-8")
    prepare_approval_payload(manifest_path, plan_path, past_payload, principal="reviewer",
        now=datetime(2020, 1, 1, tzinfo=UTC))
    sign_approval_payload(past_payload, private_key, expired_approval,
        manifest_path=manifest_path, plan_path=plan_path, project_root=project_root)
    assert verify_operator_approval(expired_approval, allowed, manifest_path=manifest_path,
        plan_path=plan_path)["status"] == "WAITING_APPROVAL"

    wrong_key = operator_root / "untrusted-key"
    subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(wrong_key)], check=True, capture_output=True)
    wrong_approval = tmp_path / "wrong-key-approval.json"
    sign_approval_payload(payload_path, wrong_key, wrong_approval,
        manifest_path=manifest_path, plan_path=plan_path, project_root=project_root)
    assert verify_operator_approval(wrong_approval, allowed, manifest_path=manifest_path,
        plan_path=plan_path)["status"] == "WAITING_APPROVAL"
