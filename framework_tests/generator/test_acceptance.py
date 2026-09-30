"""Acceptance scope and profile identity regressions."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from xgtest.generator.acceptance import verify_trial_artifact_index
from xgtest.generator.package import freeze_pre_promotion_manifest, preflight_promotion, verify_pre_promotion_package


ROOT = Path(__file__).resolve().parents[2]
INDEX = ROOT / "acceptance" / "query-generation-mvp" / "trial-run-index.json"
PROFILE = ROOT / "artifacts" / "runtime-profile-v9.json"
CURRENT_PROFILE = max(
    (ROOT / "artifacts").glob("runtime-profile-v*.json"),
    default=ROOT / "artifacts/runtime-profile-v13.json",
    key=lambda path: int(path.stem.rsplit("v", 1)[1]),
)


pytestmark = pytest.mark.skipif(not PROFILE.is_file() or not CURRENT_PROFILE.is_file(), reason="historical live acceptance artifacts are local; import a verified artifact bundle to run these checks")


@pytest.fixture(autouse=True)
def pinned_historical_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    historical = json.loads(INDEX.read_text(encoding="utf-8"))["contract_set_id"]
    monkeypatch.setattr("xgtest.generator.acceptance.build_contract_descriptor", lambda _: {"contract_set_id": historical})


def _verify(tmp_path: Path, index: object, profile: Path = PROFILE) -> dict:
    index_path = tmp_path / "trial-index.json"
    index_path.write_text(json.dumps(index), encoding="utf-8")
    return verify_trial_artifact_index(ROOT, index_path, profile)


@pytest.mark.parametrize("count", [0, 1])
def test_subset_is_not_whole_scope(tmp_path: Path, count: int) -> None:
    index = json.loads(INDEX.read_text(encoding="utf-8"))
    index["candidates"] = index["candidates"][:count]
    index["candidate_count"] = count
    index["double_run_pass_count"] = count
    result = _verify(tmp_path, index)
    assert result["status"] == "FAIL"
    assert result["expected_count"] == 21
    assert result["candidate_count"] == count
    assert any(error["code"] == "CANDIDATE_MISSING_FROM_INDEX" for error in result["errors"])


def test_invalid_index_shape_is_structured_failure(tmp_path: Path) -> None:
    result = _verify(tmp_path, [])
    assert result["status"] == "FAIL"
    assert result["details"] == "INDEX_SCHEMA_INVALID"


def test_profile_identity_tamper_is_rejected(tmp_path: Path) -> None:
    index = json.loads(INDEX.read_text(encoding="utf-8"))
    profile = json.loads(PROFILE.read_text(encoding="utf-8"))
    profile["identity"]["driver"]["version"] = [99, 99, 99]
    profile_path = tmp_path / "profile.json"
    profile_path.write_text(json.dumps(profile), encoding="utf-8")
    result = _verify(tmp_path, index, profile_path)
    assert result["status"] == "FAIL"
    assert result["error"] == "ACCEPTANCE_TRIAL_INDEX_INVALID"


def test_package_integrity_and_readiness_are_separate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    directory = INDEX.parent
    current_contract = json.loads(CURRENT_PROFILE.read_text(encoding="utf-8"))["identity"]["contract_set_id"]
    monkeypatch.setattr("xgtest.generator.acceptance.build_contract_descriptor", lambda _: {"contract_set_id": current_contract})
    manifest = freeze_pre_promotion_manifest(ROOT, directory, CURRENT_PROFILE)
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    result = verify_pre_promotion_package(ROOT, directory, CURRENT_PROFILE, path)
    assert result["package_integrity"] == "PASS"
    assert result["readiness"] == "WAITING_APPROVAL"
    assert result["verified_count"] == result["expected_count"] == 21
    manifest["members"][0]["asset_sha256"] = "0" * 64
    path.write_text(json.dumps(manifest), encoding="utf-8")
    assert verify_pre_promotion_package(ROOT, directory, CURRENT_PROFILE, path)["package_integrity"] == "FAIL"


def test_preflight_is_read_only_and_reports_missing_review(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    directory = INDEX.parent
    manifest = freeze_pre_promotion_manifest(ROOT, directory, CURRENT_PROFILE)
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    current_contract = json.loads(CURRENT_PROFILE.read_text(encoding="utf-8"))["identity"]["contract_set_id"]
    monkeypatch.setattr("xgtest.generator.acceptance.build_contract_descriptor", lambda _: {"contract_set_id": current_contract})
    monkeypatch.setattr("xgtest.generator.lifecycle.build_contract_descriptor", lambda _: {"contract_set_id": current_contract})
    before = {item.name: item.stat().st_mtime_ns for item in (ROOT / "candidates" / "query" / "join").glob("*.yaml")}
    result = preflight_promotion(ROOT, directory, CURRENT_PROFILE, path)
    after = {item.name: item.stat().st_mtime_ns for item in (ROOT / "candidates" / "query" / "join").glob("*.yaml")}
    assert result["readiness"] == "BLOCKED"
    assert result["blockers"]
    assert before == after
