"""Recoverable, signed batch promotion over the current directory loader.

Cooperating readers wait for the publisher lock and reject interrupted batches.
Receipts remain RECOVERABLE_BATCH; no atomic version pointer is claimed.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import re
from pathlib import Path
from typing import Any

import yaml

from xgtest.generator.approval import ApprovalService
from xgtest.generator.scope import resolve_scope
from xgtest.generator.lifecycle import promote_candidate
from xgtest.generator.package import build_promotion_plan, preflight_promotion
from xgtest.design.model import load_test_model
from xgtest.runtime.profile import load_profile
from xgtest.core.canonical import xgmj1_sha256
from xgtest.core.asset_lock import active_asset_lock


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".promotion-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write((json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8"))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def _promotion_lock(root: Path):
    return active_asset_lock(root, publishing=True)


def _members(root: Path, manifest: dict[str, Any]) -> list[dict[str, str]]:
    scope = resolve_scope(manifest)
    members: list[dict[str, str]] = []
    for item in manifest["members"]:
        case_id = item["case_id"]
        if not isinstance(case_id, str) or not re.fullmatch(r"[A-Za-z0-9_.-]+", case_id):
            raise ValueError("PROMOTION_CASE_ID_INVALID")
        source = (root / item["asset_path"]).resolve()
        if not source.is_relative_to(scope.path(root, "candidate_root")):
            raise ValueError("PROMOTION_SOURCE_PATH_INVALID")
        if _sha(source) != item["asset_sha256"]:
            raise ValueError(f"PROMOTION_INPUT_DRIFT:{item['case_id']}")
        payload = yaml.safe_load(source.read_text(encoding="utf-8"))
        payload["metadata"]["status"] = "active"
        active_bytes = yaml.safe_dump(payload, sort_keys=False, allow_unicode=True).encode("utf-8")
        destination = scope.path(root, "active_root") / f"{item['case_id']}.yaml"
        members.append({
            "case_id": item["case_id"], "source": item["asset_path"],
            "source_sha256": item["asset_sha256"],
            "destination": destination.relative_to(root).as_posix(),
            "destination_sha256": hashlib.sha256(active_bytes).hexdigest(),
        })
    return members


def _verify_approval(approval_path: Path, allowed_signers_path: Path, manifest_id: str, plan_hash: str, revoked_path: Path | None = None) -> None:
    decision = ApprovalService(allowed_signers_path, revoked_path).verify(
        approval_path, manifest_id=manifest_id, plan_hash=plan_hash,
    )
    if decision["status"] != "APPROVED":
        raise ValueError(f"PROMOTION_APPROVAL_REQUIRED:{decision.get('reason', '')}")


def _validate_resume(root: Path, manifest: dict[str, Any], journal: dict[str, Any]) -> None:
    """Reconstruct the approved plan rather than trusting recovery metadata."""
    if xgmj1_sha256({key: value for key, value in manifest.items() if key != "manifest_id"}) != manifest.get("manifest_id"):
        raise ValueError("PROMOTION_MANIFEST_HASH_MISMATCH")
    scope = resolve_scope(manifest)
    projection = {
        "schema_version": "1", "manifest_id": manifest["manifest_id"],
        "active_snapshot": journal["active_snapshot"],
        "selected": [{"case_id": item["case_id"], "asset_sha256": item["asset_sha256"]} for item in manifest["members"]],
        "governance_policy_version": "1",
    }
    if xgmj1_sha256(projection) != journal.get("plan_hash"):
        raise ValueError("PROMOTION_JOURNAL_PLAN_MISMATCH")
    members = journal.get("members")
    completed = journal.get("completed")
    if not isinstance(members, list) or not isinstance(completed, list):
        raise ValueError("PROMOTION_JOURNAL_SCHEMA_INVALID")
    expected = {item["case_id"]: item for item in manifest["members"]}
    if len(expected) != len(manifest["members"]) or [item["case_id"] for item in members] != list(expected):
        raise ValueError("PROMOTION_JOURNAL_MEMBER_MISMATCH")
    if len(set(completed)) != len(completed) or not set(completed).issubset(expected):
        raise ValueError("PROMOTION_JOURNAL_COMPLETED_INVALID")
    for item in members:
        case_id = item["case_id"]
        if not isinstance(case_id, str) or not re.fullmatch(r"[A-Za-z0-9_.-]+", case_id):
            raise ValueError("PROMOTION_JOURNAL_PATH_INVALID")
        source = (root / expected[case_id]["asset_path"]).resolve()
        destination = (scope.path(root, "active_root") / f"{case_id}.yaml").resolve()
        if not source.is_relative_to(scope.path(root, "candidate_root")):
            raise ValueError("PROMOTION_JOURNAL_PATH_INVALID")
        if item["source"] != expected[case_id]["asset_path"] or item["source_sha256"] != expected[case_id]["asset_sha256"] or (root / item["destination"]).resolve() != destination:
            raise ValueError("PROMOTION_JOURNAL_MEMBER_MISMATCH")
        if source.is_file():
            original = source.read_bytes()
        elif destination.is_file():
            payload = yaml.safe_load(destination.read_text(encoding="utf-8"))
            payload["metadata"]["status"] = "review"
            original = yaml.safe_dump(payload, sort_keys=False, allow_unicode=True).encode("utf-8")
        else:
            raise ValueError(f"PROMOTION_INPUT_MISSING:{case_id}")
        if hashlib.sha256(original).hexdigest() != item["source_sha256"]:
            raise ValueError(f"PROMOTION_INPUT_DRIFT:{case_id}")
        payload = yaml.safe_load(original)
        payload["metadata"]["status"] = "active"
        active = yaml.safe_dump(payload, sort_keys=False, allow_unicode=True).encode("utf-8")
        if hashlib.sha256(active).hexdigest() != item["destination_sha256"]:
            raise ValueError(f"PROMOTION_JOURNAL_DESTINATION_HASH_INVALID:{case_id}")
    baseline = {item["path"]: item["sha256"] for item in journal["active_snapshot"]}
    if len(baseline) != len(journal["active_snapshot"]):
        raise ValueError("PROMOTION_ACTIVE_SNAPSHOT_INVALID")
    for relative, digest in baseline.items():
        path = (root / relative).resolve()
        if not path.is_relative_to(scope.path(root, "active_suite_root")) or _sha(path) != digest:
            raise ValueError("PROMOTION_ACTIVE_SNAPSHOT_DRIFT")
    expected_paths = set(baseline) | {item["destination"] for item in members if (root / item["destination"]).exists()}
    actual_paths = {path.relative_to(root).as_posix() for path in scope.asset_paths(root, "active_suite_root")}
    if actual_paths != expected_paths:
        raise ValueError("PROMOTION_ACTIVE_SNAPSHOT_DRIFT")


def execute_promotion_batch(
    root: Path, acceptance_dir: Path, profile_path: Path, manifest_path: Path,
    approval_path: Path, allowed_signers_path: Path,
    *, revoked_path: Path | None = None,
) -> dict[str, Any]:
    """Start or resume a reviewed batch; every file move is journaled."""
    root = root.resolve()
    with _promotion_lock(root):
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        scope = resolve_scope(manifest)
        journal_root = root / "artifacts" / "promotion-journal"
        matching = []
        for path in journal_root.glob("*.json"):
            if path.name.startswith("receipt-"):
                continue
            candidate = json.loads(path.read_text(encoding="utf-8"))
            if candidate.get("manifest_id") == manifest["manifest_id"]:
                matching.append(path)
        if len(matching) > 1:
            raise ValueError("PROMOTION_JOURNAL_AMBIGUOUS")
        if matching:
            journal_path = matching[0]
            journal = json.loads(journal_path.read_text(encoding="utf-8"))
            plan_hash = journal["plan_hash"]
        else:
            plan = build_promotion_plan(root, manifest_path)
            plan_hash = plan["plan_hash"]
            journal_path = journal_root / f"{plan_hash}.json"
            preflight = preflight_promotion(
                root, acceptance_dir, profile_path, manifest_path,
                approval_path=approval_path, allowed_signers_path=allowed_signers_path,
                revoked_path=revoked_path,
            )
            if preflight["readiness"] != "READY" or preflight["blockers"]:
                raise ValueError("PROMOTION_PREFLIGHT_BLOCKED")
            journal = {
                "schema_version": "1", "plan_hash": plan_hash,
                "manifest_id": manifest["manifest_id"],
                "visibility": "RECOVERABLE_BATCH", "state": "IN_PROGRESS",
                "active_snapshot": plan["active_snapshot"],
                "members": _members(root, manifest), "completed": [],
            }
            _write_json_atomic(journal_path, journal)
        if journal.get("plan_hash") != plan_hash or journal.get("manifest_id") != manifest["manifest_id"]:
            raise ValueError("PROMOTION_JOURNAL_PLAN_MISMATCH")
        _verify_approval(approval_path, allowed_signers_path, manifest["manifest_id"], plan_hash, revoked_path)
        _validate_resume(root, manifest, journal)
        baseline = {item["path"]: item["sha256"] for item in journal["active_snapshot"]}
        for relative, digest in baseline.items():
            if _sha(root / relative) != digest:
                raise ValueError("PROMOTION_ACTIVE_SNAPSHOT_DRIFT")
        model = scope.load_model(root)
        profile_id = load_profile(profile_path)["sql_runtime_profile_id"]
        completed = set(journal["completed"])
        for item in journal["members"]:
            _verify_approval(approval_path, allowed_signers_path, manifest["manifest_id"], plan_hash, revoked_path)
            case_id = item["case_id"]
            source = root / item["source"]
            destination = root / item["destination"]
            if case_id in completed:
                if not destination.is_file() or _sha(destination) != item["destination_sha256"] or source.exists():
                    raise ValueError(f"PROMOTION_COMPLETED_ASSET_DRIFT:{case_id}")
                continue
            if destination.exists():
                if _sha(destination) != item["destination_sha256"]:
                    raise ValueError(f"PROMOTION_DESTINATION_CONFLICT:{case_id}")
                if source.exists():
                    if _sha(source) != item["source_sha256"]:
                        raise ValueError(f"PROMOTION_INPUT_DRIFT:{case_id}")
                    source.unlink()
            else:
                if not source.exists() or _sha(source) != item["source_sha256"]:
                    raise ValueError(f"PROMOTION_INPUT_DRIFT:{case_id}")
                promote_candidate(
                    source, model, destination.parent, root / "artifacts" / "trial-runs",
                    expected_runtime_profile_id=profile_id,
                    mutation_artifact_root=root / "artifacts" / "mutations",
                )
                if _sha(destination) != item["destination_sha256"]:
                    raise ValueError(f"PROMOTION_DESTINATION_HASH_MISMATCH:{case_id}")
            journal["completed"].append(case_id)
            _write_json_atomic(journal_path, journal)
        receipt = {
            "schema_version": "2", "plan_hash": plan_hash,
            "manifest_id": manifest["manifest_id"],
            "visibility": "RECOVERABLE_BATCH", "completed": journal["completed"],
            "promotion_plan": {
                "schema_version": "1", "manifest_id": manifest["manifest_id"],
                "active_snapshot": journal["active_snapshot"],
                "selected": [{"case_id": item["case_id"], "asset_sha256": item["asset_sha256"]} for item in manifest["members"]],
                "governance_policy_version": "1",
            },
            "members": journal["members"], "runtime_profile_id": profile_id,
            "approval_sha256": _sha(approval_path),
            "active_snapshot_after": [
                {"path": path.relative_to(root).as_posix(), "sha256": _sha(path)}
                for path in sorted(scope.asset_paths(root, "active_suite_root"))
            ],
        }
        receipt["receipt_id"] = xgmj1_sha256(receipt)
        receipt_path = journal_path.with_name(f"receipt-{plan_hash}.json")
        _write_json_atomic(receipt_path, receipt)
        journal["state"] = "COMPLETE"
        _write_json_atomic(journal_path, journal)
        return {"status": "COMPLETE", "receipt": str(receipt_path), "visibility": "RECOVERABLE_BATCH", "count": len(journal["completed"])}
