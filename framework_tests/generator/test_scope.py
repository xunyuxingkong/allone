from pathlib import Path

import pytest

from xgtest.generator.scope import AcceptanceScope, resolve_scope
from xgtest.generator.promotion_batch import _members


def test_scope_routes_the_existing_plugin_to_configured_paths(tmp_path: Path):
    scope = AcceptanceScope(module="query", feature="join", candidate_root="drafts/join", active_root="cases/custom/join", active_suite_root="cases/custom", model_ref="models/custom.yaml")
    source = tmp_path / "drafts/join/TEST.yaml"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"metadata:\n  id: TEST\n  status: review\n")
    import hashlib
    manifest = {"scope": scope.scope_id, "scope_definition": scope.model_dump(), "members": [{"case_id": "TEST", "asset_path": "drafts/join/TEST.yaml", "asset_sha256": hashlib.sha256(source.read_bytes()).hexdigest()}]}
    assert resolve_scope(manifest) == scope
    assert _members(tmp_path, manifest)[0]["destination"] == "cases/custom/join/TEST.yaml"


def test_scope_fails_closed_for_unknown_feature_and_escaping_paths():
    with pytest.raises(ValueError, match="SCOPE_PATH_INVALID"):
        AcceptanceScope(module="query", feature="join", candidate_root="../outside", active_root="cases/query/join", active_suite_root="cases/query", model_ref="model.yaml")
    scope = AcceptanceScope(module="query", feature="unknown", candidate_root="drafts", active_root="cases/query/x", active_suite_root="cases/query", model_ref="model.yaml")
    with pytest.raises(ValueError, match="FEATURE_PLUGIN_UNAVAILABLE"):
        resolve_scope(scope=scope)
