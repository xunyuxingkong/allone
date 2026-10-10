"""Feature plugin registry: resolution, case-id routing and fail-closed defaults."""

from pathlib import Path

import pytest

from xgtest.generator.plugins import FEATURE_PLUGINS, AggregatePlugin, FilterPlugin, JoinPlugin, PluginRegistry, SortLimitPlugin, SubqueryPlugin


ROOT = Path(__file__).resolve().parents[2]


def test_registered_features_resolve_and_unknown_fails_closed():
    assert FEATURE_PLUGINS.for_model("query.join").id_prefix == "QUERY.JOIN"
    assert FEATURE_PLUGINS.for_model("query.filter").id_prefix == "QUERY.FILTER"
    assert FEATURE_PLUGINS.for_model("query.aggregate").id_prefix == "QUERY.AGGREGATE"
    assert FEATURE_PLUGINS.for_model("query.subquery").id_prefix == "QUERY.SUBQUERY"
    assert FEATURE_PLUGINS.for_model("query.sort_limit").id_prefix == "QUERY.SORT_LIMIT"
    assert FEATURE_PLUGINS.for_scope("query.filter.review").model_id == "query.filter"
    with pytest.raises(ValueError, match="FEATURE_PLUGIN_UNAVAILABLE"):
        FEATURE_PLUGINS.for_model("query.unknown")


def test_default_scope_is_join_but_an_explicit_default_is_required_for_several():
    assert FEATURE_PLUGINS.default_scope() == JoinPlugin().scope
    # A multi-plugin registry without a stated default must not guess.
    with pytest.raises(ValueError, match="EXPLICIT_FEATURE_SCOPE_REQUIRED"):
        PluginRegistry((JoinPlugin(), FilterPlugin())).default_scope()
    # A single-plugin registry stays unambiguous.
    assert PluginRegistry((FilterPlugin(),)).default_scope() == FilterPlugin().scope


def test_case_id_routing_covers_every_registered_prefix():
    # matches_case_id answers "is this a known feature prefix?"; the shape of the
    # suffix is enforced by the application/db-worker layers.
    assert FEATURE_PLUGINS.matches_case_id("QUERY.JOIN.ABCD1234")
    assert FEATURE_PLUGINS.matches_case_id("QUERY.FILTER.ABCD1234")
    assert FEATURE_PLUGINS.matches_case_id("QUERY.AGGREGATE.ABCD1234")
    assert FEATURE_PLUGINS.matches_case_id("QUERY.SUBQUERY.ABCD1234")
    assert FEATURE_PLUGINS.matches_case_id("QUERY.SORT_LIMIT.ABCD1234")
    assert not FEATURE_PLUGINS.matches_case_id("QUERY.UNKNOWN.ABCD1234")
    assert set(FEATURE_PLUGINS.id_prefixes()) == {"QUERY.AGGREGATE", "QUERY.FILTER", "QUERY.JOIN", "QUERY.SORT_LIMIT", "QUERY.SUBQUERY"}


def test_mutation_specs_are_well_formed_for_every_plugin():
    import re
    for plugin in (JoinPlugin(), FilterPlugin(), AggregatePlugin(), SubqueryPlugin(), SortLimitPlugin()):
        specs = plugin.mutation_specs()
        assert specs
        for spec in specs:
            assert re.fullmatch(r"[a-z][a-z0-9_]*", spec.mutation_id)
            assert spec.version
