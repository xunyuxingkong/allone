from pathlib import Path

from xgtest.query.compiler import compile_query_asset
from xgtest.query.loader import load_query_directory


ROOT = Path(__file__).resolve().parents[2]


def test_all_legacy_assets_compile_without_governance_fields():
    for asset in load_query_directory(ROOT / "cases/query") + load_query_directory(ROOT / "candidates/query"):
        executable = compile_query_asset(asset)
        payload = executable.model_dump(mode="json")
        assert set(payload) == {"schema_version", "metadata", "steps"}
        assert set(payload["metadata"]) == {"id", "timeout"}
        assert executable.steps == asset.steps
        assert executable.execution_hash == compile_query_asset(asset).execution_hash
        changed = asset.model_copy(update={"coverage": (), "oracle": None, "validation_evidence": None})
        assert compile_query_asset(changed).execution_hash == executable.execution_hash
