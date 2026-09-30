"""Feature policy registry. Unknown features fail closed before execution."""

from dataclasses import dataclass
from typing import Any, Protocol

from xgtest.design.signature import candidate_signature
from xgtest.generator.template import TEMPLATE_ID, TEMPLATE_VERSION
from xgtest.generator.scope import AcceptanceScope


class FeaturePlugin(Protocol):
    model_id: str
    template_id: str
    mutation_id: str
    scope: AcceptanceScope

    def mutation_applies(self, case: Any) -> bool: ...
    def mutated_sql(self, sql: str) -> str: ...
    def expected_id(self, model: Any, assignment: dict[str, str]) -> str: ...
    def static_validate(self, path: Any, model: Any) -> dict[str, Any]: ...
    def generate(self, model: Any, strategy: str, existing_cases: Any, output: Any, *, limit: int | None = None) -> Any: ...


@dataclass(frozen=True)
class JoinPlugin:
    model_id: str = "query.join"
    template_id: str = TEMPLATE_ID
    mutation_id: str = "replace_le_with_lt"
    scope: AcceptanceScope = AcceptanceScope(module="query", feature="join", candidate_root="candidates/query/join", active_root="cases/query/join", active_suite_root="cases/query", model_ref="models/query/join.yaml")

    def static_validate(self, path: Any, model: Any) -> dict[str, Any]:
        from xgtest.generator.candidate import static_validate_candidate
        return static_validate_candidate(path, model)

    def generate(self, model: Any, strategy: str, existing_cases: Any, output: Any, *, limit: int | None = None) -> Any:
        from xgtest.generator.candidate import generate_candidates
        return generate_candidates(model, strategy, existing_cases, output, limit=limit)

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

    def for_scope(self, scope_id: str) -> FeaturePlugin:
        matches = [plugin for plugin in self._plugins.values() if plugin.scope.scope_id == scope_id]
        if len(matches) != 1:
            raise ValueError(f"FEATURE_SCOPE_UNAVAILABLE:{scope_id}")
        return matches[0]

    def default_scope(self) -> AcceptanceScope:
        if len(self._plugins) != 1:
            raise ValueError("EXPLICIT_FEATURE_SCOPE_REQUIRED")
        return next(iter(self._plugins.values())).scope

    def for_case(self, case: Any) -> FeaturePlugin:
        if case.generation is None:
            raise ValueError("FEATURE_PLUGIN_PROVENANCE_REQUIRED")
        matches = [plugin for plugin in self._plugins.values() if plugin.template_id == case.generation.template_id]
        if len(matches) != 1:
            raise ValueError("FEATURE_PLUGIN_UNAVAILABLE")
        return matches[0]


FEATURE_PLUGINS = PluginRegistry((JoinPlugin(),))
