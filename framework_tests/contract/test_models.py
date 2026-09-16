import pytest
from pydantic import ValidationError

from xgtest.core.identity import compute_manifest_hash, compute_plan_hash, compute_target_id, target_identity_projection
from xgtest.core.manifest import content_sha256, verify_bundle, verify_source_snapshot
from xgtest.core.models import BundleRef, EffectiveMetadata, ExpectedError, ExpectedStatement, SourceInfo, Target, TestPlan as PlanModel
from xgtest.generated.registry_enums import CaseAssetStatus, FeatureKey, IsolationScope, Level


def test_effective_metadata_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        EffectiveMetadata(
            metadata_version="1.1",
            id="QUERY.JOIN.000001",
            title="join",
            module="query",
            feature=FeatureKey.JOIN,
            level=Level.P0,
            status=CaseAssetStatus.DRAFT,
            timeout="30s",
            isolation=IsolationScope.WORKER_SCHEMA,
            unexpected=True,
        )


def test_effective_metadata_rejects_implicit_bool() -> None:
    with pytest.raises(ValidationError):
        EffectiveMetadata(
            metadata_version="1.1",
            id="QUERY.JOIN.000001",
            title="join",
            module="query",
            feature=FeatureKey.JOIN,
            level=Level.P0,
            status=CaseAssetStatus.DRAFT,
            timeout="30s",
            isolation=IsolationScope.WORKER_SCHEMA,
            destructive="false",
        )


def test_target_id_is_derived_from_semantic_projection() -> None:
    payload = {
        "database_product": "xugu",
        "database_version": "7",
        "db_build": "b1",
        "driver_name": "xgcondb",
        "driver_version": "2.3.9",
        "os": "linux",
        "arch": "x86_64",
        "topology": "single",
        "mode": "default",
        "configuration_fingerprint": "a" * 64,
    }
    target = Target(target_id=compute_target_id(payload), **payload)
    assert target.target_id == compute_target_id(target)
    assert "target_id" not in target_identity_projection({**payload, "target_id": target.target_id, "host": "db-a"})
    with pytest.raises(ValidationError, match="TARGET_ID_MISMATCH"):
        Target(target_id="0" * 64, **payload)


def test_plan_hash_is_order_independent_for_target_entries() -> None:
    payload = {
        "database_product": "xugu", "database_version": "7", "db_build": "b1",
        "driver_name": "xgcondb", "driver_version": "2.3.9", "os": "linux",
        "arch": "x86_64", "topology": "single", "mode": "default",
        "configuration_fingerprint": "b" * 64,
    }
    first = Target(target_id=compute_target_id(payload), **payload)
    second_payload = {**payload, "db_build": "b2"}
    second = Target(target_id=compute_target_id(second_payload), **second_payload)
    plan_a = PlanModel(selector="mvp", targets=(first, second), expected_executions=())
    plan_b = PlanModel(selector="mvp", targets=(second, first), expected_executions=())
    assert compute_plan_hash(plan_a) == compute_plan_hash(plan_b)


def test_manifest_hash_sorts_set_like_entries() -> None:
    base = {
        "run_id": "run-1",
        "contract_set_id": "c" * 64,
        "plan": {"selector": "mvp", "targets": [], "expected_executions": []},
        "bundles": [{"content_hash": "b" * 64, "size": 2}, {"content_hash": "a" * 64, "size": 1}],
        "git_commit": "deadbeef",
        "dirty": False,
        "source_snapshot_hash": "d" * 64,
        "catalog_snapshot_id": "catalog-1",
        "plan_hash": "e" * 64,
        "case_entries": ["CASE.B", "CASE.A"],
        "target_entries": [],
        "runtime_versions": {"runner": "1", "compiler": "1"},
    }
    reordered = {**base, "bundles": list(reversed(base["bundles"])), "case_entries": list(reversed(base["case_entries"]))}
    assert compute_manifest_hash(base) == compute_manifest_hash(reordered)
    assert compute_manifest_hash(base) != compute_manifest_hash({**base, "run_id": "run-2"})


def test_source_and_bundle_snapshot_checks_detect_drift(tmp_path) -> None:
    source_path = tmp_path / "case.xgt"
    source_path.write_text("SELECT 1\n", encoding="utf-8")
    source = SourceInfo(relative_path="case.xgt", source_hash=content_sha256(source_path))
    verify_source_snapshot(tmp_path, (source,))
    source_path.write_text("SELECT 2\n", encoding="utf-8")
    with pytest.raises(ValueError, match="SOURCE_DRIFT"):
        verify_source_snapshot(tmp_path, (source,))
    bundle = tmp_path / "bundle.bin"
    bundle.write_bytes(b"bundle")
    expected = BundleRef(content_hash=content_sha256(bundle), size=bundle.stat().st_size)
    verify_bundle(bundle, expected)
    bundle.write_bytes(b"changed")
    with pytest.raises(ValueError, match="BUNDLE_(SIZE_MISMATCH|DRIFT)"):
        verify_bundle(bundle, expected)


def test_expected_error_and_statement_cannot_be_empty() -> None:
    with pytest.raises(ValidationError, match="EXPECTED_ERROR_EMPTY"):
        ExpectedError()
    with pytest.raises(ValidationError):
        ExpectedStatement()
