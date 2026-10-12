"""Local operator tools for preparing and signing promotion approvals."""

from __future__ import annotations

import base64
import json
import re
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from xgtest.core.canonical import xgmj1_sha256
from xgtest.generator.approval import ApprovalService, approval_bytes


_PRINCIPAL = re.compile(r"^[A-Za-z0-9_.@+-]+$")


def _read_object(path: Path, code: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(code) from error
    if not isinstance(value, dict):
        raise ValueError(code)
    return value


def prepare_approval_payload(
    manifest_path: Path,
    plan_path: Path,
    output_path: Path,
    *,
    principal: str,
    expires_in_hours: int = 24,
    now: datetime | None = None,
) -> dict[str, str]:
    """Create the exact payload an operator will review and sign."""
    if not _PRINCIPAL.fullmatch(principal):
        raise ValueError("APPROVAL_PRINCIPAL_INVALID")
    if not 1 <= expires_in_hours <= 168:
        raise ValueError("APPROVAL_EXPIRY_INVALID")
    manifest = _read_object(manifest_path, "APPROVAL_MANIFEST_INVALID")
    plan = _read_object(plan_path, "APPROVAL_PLAN_INVALID")
    manifest_id = manifest.get("manifest_id")
    plan_hash = plan.get("plan_hash")
    if not isinstance(manifest_id, str) or not re.fullmatch(r"[0-9a-f]{64}", manifest_id):
        raise ValueError("APPROVAL_MANIFEST_ID_INVALID")
    if plan.get("manifest_id") != manifest_id or not isinstance(plan_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", plan_hash):
        raise ValueError("APPROVAL_PLAN_BINDING_INVALID")
    projection = {key: value for key, value in manifest.items() if key != "manifest_id"}
    if xgmj1_sha256(projection) != manifest_id:
        raise ValueError("APPROVAL_MANIFEST_HASH_INVALID")
    plan_projection = {key: value for key, value in plan.items() if key != "plan_hash"}
    if xgmj1_sha256(plan_projection) != plan_hash:
        raise ValueError("APPROVAL_PLAN_HASH_INVALID")
    issued = now or datetime.now(UTC)
    if issued.tzinfo is None:
        raise ValueError("APPROVAL_TIME_INVALID")
    payload = {
        "schema_version": "1",
        "principal": principal,
        "decision": "APPROVE",
        "manifest_id": manifest_id,
        "plan_hash": plan_hash,
        "issued_at": issued.isoformat(),
        "expires_at": (issued + timedelta(hours=expires_in_hours)).isoformat(),
        "governance_policy_version": "1",
    }
    approval_bytes(payload)  # validate the closed schema before persisting it
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(approval_bytes(payload))
    return {"payload": str(output_path), "manifest_id": manifest_id, "plan_hash": plan_hash}


def initialize_local_signer(principal: str, private_key_path: Path, allowed_signers_path: Path, *, project_root: Path) -> dict[str, str]:
    """Generate an operator key and register only its public key in the trust store."""
    if not _PRINCIPAL.fullmatch(principal):
        raise ValueError("APPROVAL_PRINCIPAL_INVALID")
    project_root = project_root.resolve()
    private_key_path = private_key_path.resolve()
    public_key_path = Path(str(private_key_path) + ".pub")
    allowed_signers_path = allowed_signers_path.resolve()
    if private_key_path.is_relative_to(project_root):
        raise ValueError("SIGNER_PRIVATE_KEY_MUST_BE_OUTSIDE_PROJECT")
    if private_key_path.exists() or public_key_path.exists():
        raise ValueError("SIGNER_KEY_ALREADY_EXISTS")
    if allowed_signers_path.is_file():
        for line in allowed_signers_path.read_text(encoding="utf-8").splitlines():
            if line.strip() and not line.lstrip().startswith("#") and line.split()[0] == principal:
                raise ValueError("SIGNER_PRINCIPAL_ALREADY_REGISTERED")
    private_key_path.parent.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(
        ["ssh-keygen", "-t", "ed25519", "-N", "", "-C", f"xgtest-promotion:{principal}", "-f", str(private_key_path)],
        check=False,
    )
    if completed.returncode != 0 or not public_key_path.is_file() or not private_key_path.is_file():
        raise ValueError("SIGNER_KEY_GENERATION_FAILED")
    fields = public_key_path.read_text(encoding="utf-8").strip().split()
    if len(fields) < 2 or not fields[0].startswith("ssh-ed25519"):
        raise ValueError("SIGNER_PUBLIC_KEY_INVALID")
    allowed_signers_path.parent.mkdir(parents=True, exist_ok=True)
    with allowed_signers_path.open("a", encoding="utf-8", newline="\n") as stream:
        if allowed_signers_path.stat().st_size:
            stream.write("\n")
        stream.write(f'{principal} namespaces="xgtest-promotion" {fields[0]} {fields[1]}\n')
    return {"principal": principal, "private_key": str(private_key_path), "public_key": str(public_key_path), "allowed_signers": str(allowed_signers_path)}


def sign_approval_payload(
    payload_path: Path,
    private_key_path: Path,
    output_path: Path,
    *,
    manifest_path: Path,
    plan_path: Path,
    project_root: Path,
) -> dict[str, str]:
    payload = _read_object(payload_path, "APPROVAL_PAYLOAD_SCHEMA_INVALID")
    signed = approval_bytes(payload)
    project_root = project_root.resolve()
    private_key_path = private_key_path.resolve()
    if private_key_path.is_relative_to(project_root):
        raise ValueError("SIGNER_PRIVATE_KEY_MUST_BE_OUTSIDE_PROJECT")
    manifest = _read_object(manifest_path, "APPROVAL_MANIFEST_INVALID")
    plan = _read_object(plan_path, "APPROVAL_PLAN_INVALID")
    if (payload.get("manifest_id") != manifest.get("manifest_id")
            or payload.get("plan_hash") != plan.get("plan_hash")
            or plan.get("manifest_id") != manifest.get("manifest_id")
            or xgmj1_sha256({key: value for key, value in manifest.items() if key != "manifest_id"}) != manifest.get("manifest_id")
            or xgmj1_sha256({key: value for key, value in plan.items() if key != "plan_hash"}) != plan.get("plan_hash")):
        raise ValueError("APPROVAL_INPUT_STALE")
    signature_path = Path(str(payload_path) + ".sig")
    completed = subprocess.run(
        ["ssh-keygen", "-Y", "sign", "-f", str(private_key_path), "-n", "xgtest-promotion", str(payload_path)],
        check=False,
    )
    if completed.returncode != 0 or not signature_path.is_file():
        raise ValueError("APPROVAL_SIGNING_FAILED")
    # ssh-keygen signs the payload file bytes. Require the input bytes to be
    # exactly the canonical content verified by Core before assembling output.
    if payload_path.read_bytes() != signed:
        signature_path.unlink(missing_ok=True)
        raise ValueError("APPROVAL_PAYLOAD_NOT_CANONICAL")
    approval = {"payload": payload, "signature_base64": base64.b64encode(signature_path.read_bytes()).decode("ascii")}
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(approval, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    signature_path.unlink(missing_ok=True)
    return {"approval": str(output_path), "principal": str(payload["principal"]), "manifest_id": str(payload["manifest_id"]), "plan_hash": str(payload["plan_hash"])}


def verify_operator_approval(approval_path: Path, allowed_signers_path: Path, *, manifest_path: Path, plan_path: Path, revoked_path: Path | None = None) -> dict[str, str]:
    manifest = _read_object(manifest_path, "APPROVAL_MANIFEST_INVALID")
    plan = _read_object(plan_path, "APPROVAL_PLAN_INVALID")
    manifest_id = manifest.get("manifest_id")
    plan_hash = plan.get("plan_hash")
    if (not isinstance(manifest_id, str)
            or xgmj1_sha256({key: value for key, value in manifest.items() if key != "manifest_id"}) != manifest_id):
        return {"status": "WAITING_APPROVAL", "reason": "APPROVAL_MANIFEST_HASH_INVALID"}
    if (plan.get("manifest_id") != manifest_id or not isinstance(plan_hash, str)
            or xgmj1_sha256({key: value for key, value in plan.items() if key != "plan_hash"}) != plan_hash):
        return {"status": "WAITING_APPROVAL", "reason": "APPROVAL_PLAN_HASH_INVALID"}
    return ApprovalService(allowed_signers_path, revoked_path).verify(
        approval_path,
        manifest_id=manifest_id,
        plan_hash=plan_hash,
    )
