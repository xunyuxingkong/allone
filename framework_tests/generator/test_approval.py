"""A review label alone must not satisfy promotion approval."""

from __future__ import annotations

import base64
import json
import shutil
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from xgtest.generator.approval import approval_bytes, verify_promotion_approval


def test_signed_approval_binds_exact_plan(tmp_path: Path) -> None:
    if shutil.which("ssh-keygen") is None:
        pytest.skip("OpenSSH signing tool unavailable")
    key = tmp_path / "operator-key"
    subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(key)], check=True, capture_output=True)
    allowed = tmp_path / "allowed-signers"
    allowed.write_text("reviewer " + key.with_suffix(".pub").read_text(encoding="utf-8"), encoding="utf-8")
    now = datetime.now(timezone.utc)
    payload = {
        "schema_version": "1", "principal": "reviewer", "decision": "APPROVE",
        "manifest_id": "a" * 64, "plan_hash": "b" * 64,
        "issued_at": (now - timedelta(minutes=1)).isoformat(),
        "expires_at": (now + timedelta(hours=1)).isoformat(),
        "governance_policy_version": "1",
    }
    signed_file = tmp_path / "decision.json"
    signed_file.write_bytes(approval_bytes(payload))
    subprocess.run(["ssh-keygen", "-Y", "sign", "-f", str(key), "-n", "xgtest-promotion", str(signed_file)], check=True, capture_output=True)
    approval = tmp_path / "approval.json"
    approval.write_text(json.dumps({
        "payload": payload,
        "signature_base64": base64.b64encode(signed_file.with_suffix(".json.sig").read_bytes()).decode("ascii"),
    }), encoding="utf-8")
    assert verify_promotion_approval(approval, allowed, manifest_id="a" * 64, plan_hash="b" * 64)["status"] == "APPROVED"
    assert verify_promotion_approval(approval, allowed, manifest_id="a" * 64, plan_hash="c" * 64)["status"] == "WAITING_APPROVAL"
    data = json.loads(approval.read_text(encoding="utf-8"))
    data["payload"]["principal"] = "other"
    approval.write_text(json.dumps(data), encoding="utf-8")
    assert verify_promotion_approval(approval, allowed, manifest_id="a" * 64, plan_hash="b" * 64)["status"] == "WAITING_APPROVAL"
