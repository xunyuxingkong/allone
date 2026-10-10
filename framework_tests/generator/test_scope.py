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


def test_feature_coverage_excludes_other_feature_paths_and_claims():
    from types import SimpleNamespace as Item
    scope = resolve_scope()
    root = Path(__file__).resolve().parents[2]
    model = scope.load_model(root)
    valid = Item(model_id=model.model_id, model_version=model.model_version, assignment={})
    foreign = Item(model_id="query.filter", model_version="1", assignment={"not_join": "value"})
    def asset(path, claims):
        return Item(source=Item(relative_path=path), case=Item(metadata=Item(status=Item(value="active")), coverage=claims))
    assets = [asset("join/JOIN.yaml", (valid, foreign)), asset("filter/FILTER.yaml", (valid, foreign)), asset("join_01_inner.yaml", (valid,))]
    assert scope.feature_claims(root, model, assets) == [valid, valid]


def test_both_features_scope_their_own_claims_without_interference():
    from types import SimpleNamespace as Item
    from xgtest.generator.plugins import FilterPlugin
    root = Path(__file__).resolve().parents[2]
    join_scope = resolve_scope()  # default = join
    filter_scope = resolve_scope(scope=FilterPlugin().scope)
    join_model = join_scope.load_model(root)
    filter_model = filter_scope.load_model(root)
    join_claim = Item(model_id=join_model.model_id, model_version=join_model.model_version, assignment={})
    filter_claim = Item(model_id=filter_model.model_id, model_version=filter_model.model_version, assignment={})

    def asset(path, claims):
        return Item(source=Item(relative_path=path), case=Item(metadata=Item(status=Item(value="active")), coverage=claims))

    assets = [asset("join/JOIN.yaml", (join_claim, filter_claim)), asset("filter/FILTER.yaml", (join_claim, filter_claim))]
    # Each feature sees only the assets under its own root, and only its own claims.
    assert join_scope.feature_claims(root, join_model, assets) == [join_claim]
    assert filter_scope.feature_claims(root, filter_model, assets) == [filter_claim]
