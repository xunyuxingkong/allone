"""Synthetic isolated promotion fixtures; never human approval or live DB evidence."""

import copy
import hashlib
import json
import shutil
from pathlib import Path

import pytest
import yaml

from xgtest.core.canonical import xgmj1_sha256
from xgtest.design.model import load_test_model
from xgtest.generator import post_acceptance as post
from xgtest.generator.lifecycle import promote_candidate
from xgtest.generator.review import record_review
from xgtest.query.loader import load_query_directory_with_sources


ROOT = Path(__file__).resolve().parents[2]


def _write(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode())


def _fixture(tmp_path, monkeypatch):
    root = tmp_path
    from xgtest.runtime.profile import build_profile
    from xgtest.generator.candidate import generate_candidates, static_validate_candidate
    from xgtest.generator.lifecycle import trial_candidate, record_candidate_mutation_evidence
    from framework_tests.generator.test_lifecycle import _passing_report
    cid = "c" * 64
    profile = build_profile({"contract_set_id": cid, "target": {"database_product": "Xugu", "database_alias": "SYSTEM", "host_hash": "a" * 64}, "driver": {"module": "synthetic", "version": [0]}})
    monkeypatch.setattr(post, "build_contract_descriptor", lambda _: {"contract_set_id": cid})
    monkeypatch.setattr("xgtest.generator.lifecycle.build_contract_descriptor", lambda _: {"contract_set_id": cid})
    monkeypatch.setattr(post.ApprovalService, "verify", lambda *a, **kw: {"status": "APPROVED", "principal": "synthetic-test"})
    # Only the gate's collection arithmetic is isolated here; real coverage remains incomplete.
    monkeypatch.setattr(post, "coverage_gap", lambda *a: {"required": 1, "covered": 1, "missing": 0})
    model_path = root / "models/query/join.yaml"
    model_path.parent.mkdir(parents=True)
    shutil.copy2(ROOT / "models/query/join.yaml", model_path)
    model = load_test_model(model_path)
    source = generate_candidates(model, "pairwise", (), root / "candidates/query/join", limit=1)[0]
    static_validate_candidate(source, model)
    record_candidate_mutation_evidence(source, {"case_id": source.stem, "mutation_id": "replace_le_with_lt", "status": "NOT_APPLICABLE"}, root / "artifacts/mutations", profile)
    trial_candidate(source, model, object(), root / "artifacts/trial-runs", runtime_profile=profile, runner=lambda case, *a: _passing_report(case))
    candidate = yaml.safe_load(source.read_text(encoding="utf-8"))
    model = load_test_model(model_path)
    record_review(source, model=model, reviewer="synthetic-test", review_reference="synthetic://test-review", coverage_reference="synthetic://test-coverage")
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    profile_path = root / "artifacts/profile.json"
    _write(profile_path, profile)
    member = {"case_id": source.stem, "asset_path": source.relative_to(root).as_posix(), "asset_sha256": sha(source)}
    manifest = {"phase": "pre_promotion", "members": [member], "runtime_profile_id": profile["sql_runtime_profile_id"], "runtime_profile_sha256": sha(profile_path)}
    manifest["manifest_id"] = xgmj1_sha256(manifest)
    manifest_path = root / "manifest.json"
    _write(manifest_path, manifest)
    plan = {"schema_version": "1", "manifest_id": manifest["manifest_id"], "active_snapshot": [], "selected": [{"case_id": member["case_id"], "asset_sha256": member["asset_sha256"]}], "governance_policy_version": "1"}
    destination = promote_candidate(source, model, root / "cases/query/join", root / "artifacts/trial-runs", expected_runtime_profile_id=profile["sql_runtime_profile_id"])
    approval_path = root / "approval.json"
    _write(approval_path, {"fixture": "not a real approval"})
    receipt = {"schema_version": "2", "plan_hash": xgmj1_sha256(plan), "promotion_plan": plan, "manifest_id": manifest["manifest_id"], "completed": [member["case_id"]], "runtime_profile_id": profile["sql_runtime_profile_id"], "approval_sha256": sha(approval_path),
               "members": [{"case_id": member["case_id"], "source": member["asset_path"], "source_sha256": member["asset_sha256"], "destination": destination.relative_to(root).as_posix(), "destination_sha256": sha(destination)}],
               "active_snapshot_after": [{"path": destination.relative_to(root).as_posix(), "sha256": sha(destination)}]}
    receipt["receipt_id"] = xgmj1_sha256(receipt)
    receipt_path = root / "receipt.json"
    _write(receipt_path, receipt)
    trial = json.loads((root / "artifacts/trial-runs" / candidate["validation_evidence"]["trial_run_ref"]).read_text(encoding="utf-8"))
    asset = load_query_directory_with_sources(root / "cases/query")[0]
    case_report = copy.deepcopy(trial["run1"])
    case_report.update(source_file=asset.source.relative_path, case_source_hash=asset.source.source_hash)
    regression = {"schema_version": "1", "run_id": "synthetic", "started_at": "2026-09-30T00:00:00Z", "finished_at": "2026-09-30T00:00:01Z", "target": {"database_alias": "SYSTEM", "host_hash": "a" * 64, "sql_runtime_profile_id": profile["sql_runtime_profile_id"], "contract_set_id": cid}, "cases": [case_report], "status": "PASS"}
    regression_path = root / "regression.json"
    _write(regression_path, regression)
    package_path = root / "post-package.json"

    def freeze():
        _write(package_path, post.freeze_post_promotion_package(root, candidate_manifest=manifest_path, receipt=receipt_path, regression=regression_path, runtime_profile=profile_path, approval=approval_path))

    freeze()
    return root, package_path, receipt_path, regression_path, destination, freeze


def test_complete_post_package_and_tampered_regression(tmp_path, monkeypatch):
    root, package, receipt, regression, destination, freeze = _fixture(tmp_path, monkeypatch)
    initial = post.verify_post_promotion_package(root, package, allowed_signers_path=root / "synthetic-trust")
    assert initial["package_integrity"] == "PASS", initial["errors"]
    payload = json.loads(regression.read_text(encoding="utf-8"))
    payload["cases"] = []
    _write(regression, payload)
    freeze()  # Rebinding an outer SHA must not hide a missing execution.
    result = post.verify_post_promotion_package(root, package, allowed_signers_path=root / "synthetic-trust")
    assert result["package_integrity"] == "FAIL"
    assert any(item["code"] == "POST_REGRESSION_SCOPE_MISMATCH" for item in result["errors"])


@pytest.mark.parametrize("damage", ["receipt", "active", "source_hash", "coverage", "revoked"])
def test_post_package_refuses_invalid_receipt_state_and_evidence(tmp_path, monkeypatch, damage):
    root, package, receipt, regression, destination, freeze = _fixture(tmp_path, monkeypatch)
    if damage == "receipt":
        payload = json.loads(receipt.read_text(encoding="utf-8"))
        payload["completed"] = []
        payload["receipt_id"] = xgmj1_sha256({k: v for k, v in payload.items() if k != "receipt_id"})
        _write(receipt, payload)
    elif damage == "active":
        destination.write_bytes(destination.read_bytes() + b"\n# changed revision\n")
    elif damage == "source_hash":
        payload = json.loads(regression.read_text(encoding="utf-8"))
        payload["cases"][0]["case_source_hash"] = "0" * 64
        _write(regression, payload)
    elif damage == "coverage":
        monkeypatch.setattr(post, "coverage_gap", lambda *a: {"required": 2, "covered": 1, "missing": 1})
    else:
        monkeypatch.setattr(post.ApprovalService, "verify", lambda *a, **kw: {"status": "WAITING_APPROVAL", "reason": "APPROVAL_REVOKED"})
    freeze()
    assert post.verify_post_promotion_package(root, package, allowed_signers_path=root / "synthetic-trust")["package_integrity"] == "FAIL"


def test_missing_package_derives_hold_instead_of_believing_old_final_json(tmp_path):
    policy = tmp_path / "policy.json"
    _write(policy, {"schema_version": "1", "ci_disposition": "DEFERRED_BY_USER", "ci_decision_reference": "synthetic user instruction", "allow_release_with_ci_exception": False})
    _write(tmp_path / "final-acceptance.json", {"status": "PASS"})
    state = post.generate_final_acceptance(tmp_path, tmp_path / "missing-post.json", allowed_signers_path=tmp_path / "trust", policy_path=policy)
    assert state["status"] == "HOLD"
    assert state["source_state_id"] == xgmj1_sha256({k: v for k, v in state.items() if k != "source_state_id"})


def test_final_requires_explicit_ci_exception_even_when_post_checks_pass(tmp_path, monkeypatch):
    root, package, receipt, regression, destination, freeze = _fixture(tmp_path, monkeypatch)
    monkeypatch.setattr(post, "verify_release_checks", lambda *a: {"status": "PASS", "framework": {"passed": 1, "skipped": 0}, "errors": []})
    policy = root / "policy.json"
    payload = {"schema_version": "1", "ci_disposition": "DEFERRED_BY_USER", "ci_decision_reference": "synthetic authorized exception", "allow_release_with_ci_exception": False}
    _write(policy, payload)
    arguments = {"allowed_signers_path": root / "synthetic-trust", "policy_path": policy, "release_checks_path": root / "synthetic-checks.json"}
    assert post.generate_final_acceptance(root, package, **arguments)["status"] == "HOLD"

    payload["allow_release_with_ci_exception"] = True
    _write(policy, payload)
    assert post.generate_final_acceptance(root, package, **arguments)["status"] == "PASS_WITH_EXCEPTION"
    # A bare CI_PASS declaration is not independent CI evidence.
    payload["ci_disposition"] = "CI_PASS"
    _write(policy, payload)
    assert post.generate_final_acceptance(root, package, **arguments)["status"] == "HOLD"


def test_post_binds_regression_build_before_and_after_execution(tmp_path, monkeypatch):
    root, package, receipt, regression, destination, freeze = _fixture(tmp_path, monkeypatch)
    load = post.load_profile

    def profile_with_build(path):
        profile = load(path)
        # Synthetic observation fixture isolates build gating from trial generation.
        profile["identity"]["target"].update(db_build="2026-05-18 12:11:00", database_version="SYNTHETIC")
        return profile

    monkeypatch.setattr(post, "load_profile", profile_with_build)
    result = post.verify_post_promotion_package(root, package, allowed_signers_path=root / "synthetic-trust")
    assert any(issue["code"] == "POST_REGRESSION_BUILD_EVIDENCE_REQUIRED" for issue in result["errors"])
    observations = root / "regression-build.json"
    value = "2026-05-18 12:11:00 SYNTHETIC"
    _write(observations, {"before": {"captured_at": "2026-09-29T23:59:59Z", "query": "SHOW build_time;", "raw_value": value}, "after": {"captured_at": "2026-09-30T00:00:02Z", "query": "SHOW build_time;", "raw_value": value}})
    references = json.loads(package.read_text())["inputs"]
    kwargs = {role: root / ref["path"] for role, ref in references.items()}
    kwargs["regression_build"] = observations
    _write(package, post.freeze_post_promotion_package(root, **kwargs))
    assert post.verify_post_promotion_package(root, package, allowed_signers_path=root / "synthetic-trust")["package_integrity"] == "PASS"
    payload = json.loads(observations.read_text())
    payload["after"]["raw_value"] = "different build"
    _write(observations, payload)
    _write(package, post.freeze_post_promotion_package(root, **kwargs))
    assert post.verify_post_promotion_package(root, package, allowed_signers_path=root / "synthetic-trust")["package_integrity"] == "FAIL"
