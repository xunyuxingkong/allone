"""Verify an operator-signed promotion decision for an exact frozen plan."""

from __future__ import annotations

import base64
import json
import subprocess
import tempfile
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


_FIELDS = {
    "schema_version", "principal", "decision", "manifest_id", "plan_hash",
    "issued_at", "expires_at", "governance_policy_version",
}


def approval_bytes(payload: dict[str, Any]) -> bytes:
    if set(payload) != _FIELDS or payload.get("schema_version") != "1":
        raise ValueError("APPROVAL_PAYLOAD_SCHEMA_INVALID")
    return (json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def verify_promotion_approval(
    approval_path: Path, allowed_signers_path: Path, *, manifest_id: str, plan_hash: str,
    revoked_path: Path | None = None,
    clock: Callable[[], datetime] | None = None,
) -> dict[str, str]:
    try:
        approval = json.loads(approval_path.read_text(encoding="utf-8"))
        if not isinstance(approval, dict) or not isinstance(approval.get("payload"), dict):
            raise ValueError("APPROVAL_SCHEMA_INVALID")
        payload = approval["payload"]
        signed = approval_bytes(payload)
        if not isinstance(payload["principal"], str) or not re.fullmatch(r"[A-Za-z0-9_.@+-]+", payload["principal"]):
            raise ValueError("APPROVAL_PRINCIPAL_INVALID")
        if any(not isinstance(payload[key], str) or not re.fullmatch(r"[0-9a-f]{64}", payload[key]) for key in ("manifest_id", "plan_hash")):
            raise ValueError("APPROVAL_IDENTITY_INVALID")
        if payload["manifest_id"] != manifest_id or payload["plan_hash"] != plan_hash:
            raise ValueError("APPROVAL_INPUT_STALE")
        if payload["decision"] != "APPROVE" or payload["governance_policy_version"] != "1":
            raise ValueError("APPROVAL_DECISION_INVALID")
        issued = datetime.fromisoformat(payload["issued_at"])
        expires = datetime.fromisoformat(payload["expires_at"])
        now = clock() if clock else datetime.now(timezone.utc)
        if issued.tzinfo is None or expires.tzinfo is None or now.tzinfo is None or not issued <= now < expires:
            raise ValueError("APPROVAL_EXPIRED_OR_TIME_INVALID")
        if revoked_path is not None:
            revoked = json.loads(revoked_path.read_text(encoding="utf-8"))
            if not isinstance(revoked, list) or any(not isinstance(item, str) or not re.fullmatch(r"[0-9a-f]{64}", item) for item in revoked):
                raise ValueError("APPROVAL_REVOCATION_STORE_INVALID")
            if plan_hash in revoked or manifest_id in revoked:
                raise ValueError("APPROVAL_REVOKED")
        signature = base64.b64decode(approval["signature_base64"], validate=True)
        if not allowed_signers_path.is_file():
            raise ValueError("APPROVAL_TRUST_STORE_MISSING")
        with tempfile.TemporaryDirectory(prefix="xgtest-approval-") as directory:
            signature_path = Path(directory) / "approval.sig"
            signature_path.write_bytes(signature)
            result = subprocess.run(
                ["ssh-keygen", "-Y", "verify", "-f", str(allowed_signers_path),
                 "-I", str(payload["principal"]), "-n", "xgtest-promotion",
                 "-s", str(signature_path)],
                input=signed, capture_output=True, timeout=10, check=False,
            )
        if result.returncode != 0:
            raise ValueError("APPROVAL_SIGNATURE_INVALID")
        return {"status": "APPROVED", "principal": str(payload["principal"]), "plan_hash": plan_hash}
    except (OSError, ValueError, TypeError, KeyError, subprocess.TimeoutExpired) as error:
        return {"status": "WAITING_APPROVAL", "reason": str(error)}


@dataclass(frozen=True)
class ApprovalService:
    """One configured trust/revocation/clock boundary for all entry points."""

    allowed_signers_path: Path
    revoked_path: Path | None = None
    clock: Callable[[], datetime] | None = None

    def verify(self, approval_path: Path, *, manifest_id: str, plan_hash: str) -> dict[str, str]:
        return verify_promotion_approval(
            approval_path, self.allowed_signers_path, manifest_id=manifest_id,
            plan_hash=plan_hash, revoked_path=self.revoked_path, clock=self.clock,
        )
