"""Feature policy registry. Unknown features fail closed before execution."""

from dataclasses import dataclass
from typing import Any, Protocol

from xgtest.design.signature import candidate_signature
from xgtest.generator.template import TEMPLATE_ID, TEMPLATE_VERSION


class FeaturePlugin(Protocol):
    model_id: str
    template_id: str
    mutation_id: str

    def mutation_applies(self, case: Any) -> bool: ...
    def mutated_sql(self, sql: str) -> str: ...
    def expected_id(self, model: Any, assignment: dict[str, str]) -> str: ...


@dataclass(frozen=True)
class JoinPlugin:
    model_id: str = "query.join"
    template_id: str = TEMPLATE_ID
    mutation_id: str = "replace_le_with_lt"

    def mutation_applies(self, case: Any) -> bool:
        return any(claim.assignment.get("predicate") == "less_equal" for claim in case.coverage)

    def mutated_sql(self, sql: str) -> str:
        return sql.replace("a.k <= b.k", "a.k < b.k")

    def expected_id(self, model: Any, assignment: dict[str, str]) -> str:
        return f"QUERY.JOIN.{candidate_signature(model, assignment, TEMPLATE_ID, TEMPLATE_VERSION)[:8].upper()}"


class PluginRegistry:
    def __init__(self, plugins: tuple[FeaturePlugin, ...]):
        self._plugins = {plugin.model_id: plugin for plugin in plugins}
        if len(self._plugins) != len(plugins):
            raise ValueError("PLUGIN_MODEL_DUPLICATE")

    def for_model(self, model_id: str) -> FeaturePlugin:
        try:
            return self._plugins[model_id]
        except KeyError as error:
            raise ValueError(f"FEATURE_PLUGIN_UNAVAILABLE:{model_id}") from error

    def for_case(self, case: Any) -> FeaturePlugin:
        if case.generation is None:
            raise ValueError("FEATURE_PLUGIN_PROVENANCE_REQUIRED")
        matches = [plugin for plugin in self._plugins.values() if plugin.template_id == case.generation.template_id]
        if len(matches) != 1:
            raise ValueError("FEATURE_PLUGIN_UNAVAILABLE")
        return matches[0]


FEATURE_PLUGINS = PluginRegistry((JoinPlugin(),))
