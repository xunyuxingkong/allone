"""Post-promotion verification and derived acceptance; never promotes assets."""

from __future__ import annotations

import hashlib
import json
import tempfile
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from xgtest.core.canonical import xgmj1_sha256
from xgtest.core.contract_set import build_contract_descriptor
from xgtest.core.models import QueryRunReport
from xgtest.design.coverage import coverage_gap
from xgtest.design.model import load_test_model
from xgtest.generator.approval import ApprovalService
from xgtest.generator.scope import resolve_scope
from xgtest.generator.lifecycle import promote_candidate
from xgtest.generator.package import load_governance_policy, contract_bindings, verify_pre_promotion_package, consistent_project_read
from xgtest.generator.release_checks import verify_release_checks
from xgtest.query.loader import load_query_directory_with_sources
from xgtest.runtime.profile import load_profile


def _sha(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _json(path: Path) -> dict[str, Any]:
    result = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(result, dict):
        raise ValueError("PACKAGE_OBJECT_REQUIRED")
    return result


def _path(root: Path, relative: str) -> Path:
    if not isinstance(relative, str) or Path(relative).is_absolute() or ".." in Path(relative).parts:
        raise ValueError("PACKAGE_REFERENCE_INVALID")
    result = (root / relative).resolve()
    if not result.is_relative_to(root.resolve()):
        raise ValueError("PACKAGE_REFERENCE_OUTSIDE_PROJECT")
    return result


@consistent_project_read
def freeze_post_promotion_package(
    root: Path, *, candidate_manifest: Path, receipt: Path, regression: Path,
    runtime_profile: Path, approval: Path,
    regression_build: Path | None = None,
) -> dict[str, Any]:
    root = root.resolve()
    inputs = {}
    references = {"candidate_manifest": candidate_manifest, "receipt": receipt,
                  "regression": regression, "runtime_profile": runtime_profile, "approval": approval}
    if regression_build is not None:
        references["regression_build"] = regression_build
    for role, path in references.items():
        resolved = path.resolve()
        if not resolved.is_relative_to(root):
            raise ValueError("PACKAGE_REFERENCE_OUTSIDE_PROJECT")
        inputs[role] = {"path": resolved.relative_to(root).as_posix(), "sha256": _sha(resolved.read_bytes())}
    projection = {"schema_version": "1", "phase": "post_promotion", "inputs": inputs}
    return {**projection, "package_id": xgmj1_sha256(projection)}


def _bound_inputs(root: Path, package: dict[str, Any]) -> dict[str, Path]:
    if package.get("package_id") != xgmj1_sha256({key: value for key, value in package.items() if key != "package_id"}):
        raise ValueError("PACKAGE_ID_MISMATCH")
    inputs = package.get("inputs")
    required = {"candidate_manifest", "receipt", "regression", "runtime_profile", "approval"}
    if not isinstance(inputs, dict) or not required <= set(inputs) or set(inputs) - required - {"regression_build"}:
        raise ValueError("POST_PACKAGE_INPUTS_INVALID")
    paths = {}
    for role, reference in inputs.items():
        if not isinstance(reference, dict) or set(reference) != {"path", "sha256"}:
            raise ValueError("PACKAGE_REFERENCE_INVALID")
        path = _path(root, reference["path"])
        if _sha(path.read_bytes()) != reference["sha256"]:
            raise ValueError(f"PACKAGE_INPUT_HASH_MISMATCH:{role}")
        paths[role] = path
    return paths


@consistent_project_read
def verify_post_promotion_package(
    root: Path, package_path: Path, *, allowed_signers_path: Path,
    revoked_path: Path | None = None,
) -> dict[str, Any]:
    root = root.resolve()
    errors: list[dict[str, str]] = []
    expected_ids: set[str] = set()
    verified_ids: set[str] = set()
    coverage: dict[str, int] | None = None
    package_id = None
    approval_status = None

    def fail(code: str, case_id: str = "*") -> None:
        errors.append({"case_id": case_id, "code": code})

    try:
        package = _json(package_path)
        package_id = package.get("package_id")
        if package.get("schema_version") != "1" or package.get("phase") != "post_promotion":
            raise ValueError("POST_PACKAGE_SCHEMA_INVALID")
        inputs = _bound_inputs(root, package)
        manifest = _json(inputs["candidate_manifest"])
        scope = resolve_scope(manifest)
        if manifest.get("phase") != "pre_promotion" or manifest.get("manifest_id") != xgmj1_sha256({k: v for k, v in manifest.items() if k != "manifest_id"}):
            raise ValueError("CANDIDATE_MANIFEST_INVALID")
        if "contract_bindings" in manifest and manifest["contract_bindings"] != contract_bindings(root):
            fail("POST_GOVERNANCE_OR_DESIGN_CONTRACT_STALE")
        profile = load_profile(inputs["runtime_profile"])
        if "acceptance_root" in manifest:
            acceptance_root = _path(root, manifest["acceptance_root"])
            for name, digest in manifest["inputs"].items():
                reference = _path(root, f"{manifest['acceptance_root']}/{name}")
                if reference.parent != acceptance_root or _sha(reference.read_bytes()) != digest:
                    fail("POST_FROZEN_PRE_INPUT_CHANGED")
            evidence_path = _path(root, manifest["runtime_profile_evidence_ref"])
            if _sha(evidence_path.read_bytes()) != manifest["runtime_profile_evidence_sha256"]:
                fail("POST_PROFILE_PROBE_BYTES_CHANGED")
            evidence = _json(evidence_path)
            evidence_digest = _sha(json.dumps(evidence, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8"))
            if evidence_digest != profile.get("evidence_sha256"):
                fail("POST_PROFILE_PROBE_HASH_MISMATCH")
        profile_id = profile["sql_runtime_profile_id"]
        contract_id = str(build_contract_descriptor(root)["contract_set_id"])
        if profile_id != manifest.get("runtime_profile_id") or _sha(inputs["runtime_profile"].read_bytes()) != manifest.get("runtime_profile_sha256"):
            fail("POST_PROFILE_MISMATCH")
        if profile["identity"].get("contract_set_id") != contract_id:
            fail("POST_CONTRACT_STALE")
        receipt = _json(inputs["receipt"])
        if receipt.get("schema_version") != "2" or receipt.get("receipt_id") != xgmj1_sha256({k: v for k, v in receipt.items() if k != "receipt_id"}):
            raise ValueError("PROMOTION_RECEIPT_INVALID")
        plan = receipt["promotion_plan"]
        if not isinstance(plan, dict) or receipt["plan_hash"] != xgmj1_sha256(plan) or plan.get("manifest_id") != manifest["manifest_id"] or receipt.get("manifest_id") != manifest["manifest_id"]:
            raise ValueError("PROMOTION_PLAN_BINDING_INVALID")
        selected = [{"case_id": item["case_id"], "asset_sha256": item["asset_sha256"]} for item in manifest["members"]]
        if not selected or plan.get("selected") != selected or len({item["case_id"] for item in selected}) != len(selected):
            raise ValueError("PROMOTION_SELECTION_INVALID")
        selected_ids = {item["case_id"] for item in selected}
        completed = receipt.get("completed")
        if not isinstance(completed, list) or len(completed) != len(set(completed)) or set(completed) != selected_ids:
            fail("PROMOTION_NOT_COMPLETE")
        if receipt.get("runtime_profile_id") != profile_id or receipt.get("approval_sha256") != _sha(inputs["approval"].read_bytes()):
            fail("PROMOTION_EXECUTION_BINDING_INVALID")
        approval_status = ApprovalService(allowed_signers_path, revoked_path).verify(
            inputs["approval"], manifest_id=manifest["manifest_id"], plan_hash=receipt["plan_hash"],
        )
        if approval_status["status"] != "APPROVED":
            fail(f"PROMOTION_APPROVAL_INVALID:{approval_status.get('reason', '')}")
        before = {item["path"]: item["sha256"] for item in plan["active_snapshot"]}
        after = {item["path"]: item["sha256"] for item in receipt["active_snapshot_after"]}
        members = {item["case_id"]: item for item in receipt["members"]}
        if len(before) != len(plan["active_snapshot"]) or len(after) != len(receipt["active_snapshot_after"]) or len(members) != len(receipt["members"]) or set(members) != selected_ids:
            raise ValueError("PROMOTION_SNAPSHOT_DUPLICATE_OR_MISSING")
        expected_after = dict(before)
        model = scope.load_model(root)
        with tempfile.TemporaryDirectory(prefix="xgtest-post-review-") as temporary:
            for item in manifest["members"]:
                case_id = item["case_id"]
                if not isinstance(case_id, str) or not re.fullmatch(r"[A-Za-z0-9_.-]+", case_id):
                    raise ValueError("PROMOTION_CASE_ID_INVALID")
                member = members[case_id]
                destination = f"{scope.active_root}/{case_id}.yaml"
                if member["source"] != item["asset_path"] or member["source_sha256"] != item["asset_sha256"] or member["destination"] != destination or destination in before:
                    raise ValueError("PROMOTION_MEMBER_BINDING_INVALID")
                source = _path(root, item["asset_path"])
                if not source.is_relative_to(scope.path(root, "candidate_root")) or source.exists():
                    fail("PROMOTION_SOURCE_NOT_REMOVED_OR_INVALID", case_id)
                expected_after[destination] = member["destination_sha256"]
                path = _path(root, destination)
                try:
                    raw = path.read_bytes()
                    payload = yaml.safe_load(raw)
                    if not isinstance(payload, dict) or payload["metadata"]["status"] != "active" or _sha(raw) != member["destination_sha256"]:
                        raise ValueError("PROMOTED_ASSET_INVALID")
                    payload["metadata"]["status"] = "review"
                    review_bytes = yaml.safe_dump(payload, sort_keys=False, allow_unicode=True).encode("utf-8")
                    if _sha(review_bytes) != item["asset_sha256"]:
                        raise ValueError("PROMOTED_ASSET_REVISION_CHANGED")
                    review_path = Path(temporary) / f"{case_id}.yaml"
                    review_path.write_bytes(review_bytes)
                    promote_candidate(
                        review_path, model, Path(temporary) / "active", root / "artifacts/trial-runs",
                        expected_runtime_profile_id=profile_id, mutation_artifact_root=root / "artifacts/mutations", dry_run=True,
                    )
                except (OSError, ValueError, TypeError, KeyError, yaml.YAMLError) as error:
                    fail(str(error), case_id)
        if after != expected_after:
            fail("PROMOTION_ACTIVE_DELTA_INVALID")
        actual = {path.relative_to(root).as_posix(): _sha(path.read_bytes()) for path in scope.asset_paths(root, "active_suite_root")}
        if actual != after:
            fail("POST_ACTIVE_SNAPSHOT_CHANGED")
        assets = load_query_directory_with_sources(scope.path(root, "active_suite_root"))
        if any(asset.case.metadata.status.value != "active" for asset in assets):
            fail("POST_LOADER_NON_ACTIVE_ASSET")
        expected_ids = {asset.case.metadata.id for asset in assets}
        report = QueryRunReport.model_validate_json(inputs["regression"].read_bytes())
        if report.target.contract_set_id != contract_id or report.target.sql_runtime_profile_id != profile_id or report.status.value != "PASS":
            fail("POST_REGRESSION_CONTEXT_OR_STATUS_INVALID")
        if report.target.host_hash != profile.get("target", {}).get("host_hash") or report.target.database_alias != profile.get("target", {}).get("database_alias"):
            fail("POST_REGRESSION_TARGET_MISMATCH")
        target = profile["identity"].get("target", {})
        if target.get("db_build"):
            if "regression_build" not in inputs:
                fail("POST_REGRESSION_BUILD_EVIDENCE_REQUIRED")
            else:
                observations = _json(inputs["regression_build"])
                expected_build = f"{target['db_build']} {target.get('database_version', '')}".strip()
                before_build, after_build = observations["before"], observations["after"]
                before_time = datetime.fromisoformat(before_build["captured_at"])
                after_time = datetime.fromisoformat(after_build["captured_at"])
                if any(item.get("query") != "SHOW build_time;" or item.get("raw_value") != expected_build for item in (before_build, after_build)) or before_time.tzinfo is None or after_time.tzinfo is None or not before_time <= report.started_at <= report.finished_at <= after_time:
                    fail("POST_REGRESSION_BUILD_DRIFT_OR_TIME_INVALID")
        reports = {case.case_id: case for case in report.cases}
        if len(reports) != len(report.cases) or set(reports) != expected_ids:
            fail("POST_REGRESSION_SCOPE_MISMATCH")
        for asset in assets:
            case_id = asset.case.metadata.id
            observed = reports.get(case_id)
            if observed is None or observed.status.value != "PASS" or observed.case_source_hash != asset.source.source_hash or observed.source_file != asset.source.relative_path or tuple(step.id for step in observed.steps) != tuple(step.id for step in asset.case.steps) or any(step.status.value != "PASS" for step in observed.steps):
                fail("POST_REGRESSION_CASE_INVALID", case_id)
            else:
                verified_ids.add(case_id)
        gap = coverage_gap(model, scope.feature_claims(root, model, assets), scope.coverage_strategy)
        coverage = {"required": gap["required"], "active_covered": gap["covered"], "active_missing": gap["missing"]}
        if gap["missing"] != 0:
            fail("POST_ACTIVE_COVERAGE_INCOMPLETE")
    except (OSError, ValueError, TypeError, KeyError, AttributeError, yaml.YAMLError) as error:
        fail(f"POST_PACKAGE_INVALID:{error}")
    failed_ids = {error["case_id"] for error in errors if error["case_id"] != "*"}
    return {
        "schema_version": "1", "phase": "post_promotion", "package_id": package_id, "scope": scope.model_id if "scope" in locals() else None,
        "package_integrity": "FAIL" if errors else "PASS", "readiness": "BLOCKED" if errors else "READY",
        "expected_count": len(expected_ids), "case_verified_count": len(verified_ids - failed_ids),
        "case_failed_count": len(failed_ids), "package_error_count": sum(error["case_id"] == "*" for error in errors),
        "coverage": coverage, "completion": {"feature": "DEFINED_SCOPE_COMPLETE" if coverage is not None and coverage["active_missing"] == 0 and not errors else "DEFINED_SCOPE_INCOMPLETE", "module": "MODULE_FULL_INCOMPLETE", "feature_coverage_root": scope.feature_coverage_root, "module_regression_root": scope.module_regression_root} if "scope" in locals() else None, "approval": approval_status, "errors": errors,
    }


@consistent_project_read
def generate_final_acceptance(
    root: Path, post_package_path: Path, *, allowed_signers_path: Path,
    policy_path: Path, revoked_path: Path | None = None,
    release_checks_path: Path | None = None,
    candidate_manifest_path: Path | None = None,
    acceptance_dir: Path | None = None,
    runtime_profile_path: Path | None = None,
) -> dict[str, Any]:
    """An acceptance decision is derived from current evidence, not prior JSON."""
    post = verify_post_promotion_package(root, post_package_path, allowed_signers_path=allowed_signers_path, revoked_path=revoked_path)
    blockers = list(post["errors"])
    pre = None
    if any(item is not None for item in (candidate_manifest_path, acceptance_dir, runtime_profile_path)):
        if any(item is None for item in (candidate_manifest_path, acceptance_dir, runtime_profile_path)):
            blockers.append({"case_id": "*", "code": "FINAL_PRE_PACKAGE_INPUTS_INCOMPLETE"})
        else:
            pre = verify_pre_promotion_package(root, acceptance_dir, runtime_profile_path, candidate_manifest_path)
            if pre["package_integrity"] != "PASS":
                blockers.extend(pre.get("errors", pre.get("global_errors", [])))
    policy: dict[str, Any] = {}
    try:
        policy = load_governance_policy(policy_path)
        disposition = policy["ci_disposition"]
        if disposition != "CI_PASS" and not (disposition.startswith("DEFERRED") and policy["allow_release_with_ci_exception"]):
            blockers.append({"case_id": "*", "code": "FINAL_CI_GATE_INCOMPLETE"})
        # CI_PASS is a policy declaration, not independent evidence of a CI run.
        if disposition == "CI_PASS":
            blockers.append({"case_id": "*", "code": "FINAL_CI_EVIDENCE_REQUIRED"})
    except (OSError, ValueError, TypeError) as error:
        blockers.append({"case_id": "*", "code": f"FINAL_POLICY_INVALID:{error}"})
    release = verify_release_checks(root, release_checks_path) if release_checks_path else {"status": "FAIL", "errors": ["RELEASE_CHECK_EVIDENCE_REQUIRED"]}
    if release["status"] != "PASS":
        blockers.extend({"case_id": "*", "code": code} for code in release["errors"])
    bindings = {role: _sha(path.read_bytes()) if path is not None and path.is_file() else None
                for role, path in {"post_package": post_package_path, "release_checks": release_checks_path,
                                   "governance_policy": policy_path, "candidate_manifest": candidate_manifest_path}.items()}
    state = {"schema_version": "2", "scope": post.get("scope") or (pre or {}).get("scope"), "status": "HOLD" if blockers else "PASS_WITH_EXCEPTION",
             "pre_promotion": pre, "post_promotion": post, "release_checks": release,
             "ci_disposition": policy.get("ci_disposition", "CI_NOT_CONFIGURED"), "governance_policy": policy,
             "evidence_bindings": bindings, "blockers": blockers}
    return {**state, "source_state_id": xgmj1_sha256(state)}
