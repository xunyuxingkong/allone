"""Feature policy registry. Unknown features fail closed before execution."""

from dataclasses import dataclass
from typing import Any, Protocol, Callable
import re

from xgtest.design.signature import candidate_signature
from xgtest.generator.template import TEMPLATE_ID, TEMPLATE_VERSION
from xgtest.generator.scope import AcceptanceScope


@dataclass(frozen=True)
class MutationSpec:
    mutation_id: str
    version: str
    applies: Callable[[Any], bool]
    rewrite: Callable[[str], str]


@dataclass(frozen=True)
class MutationPolicy:
    version: str = "1"

    def validate(self, case: Any, checks: Any, specs: tuple[MutationSpec, ...], *, artifact: dict[str, Any] | None = None) -> None:
        if artifact is not None:
            versions = {spec.mutation_id: spec.version for spec in specs}
            if artifact.get("policy_version") != self.version or (
                artifact.get("spec_versions") != versions
                and not (len(specs) == 1 and self.version == "1" and specs[0].version == "1" and "spec_versions" not in artifact)
            ):
                raise ValueError("CANDIDATE_MUTATION_POLICY_VERSION_MISMATCH")
        by_id = {check.mutation_id: check for check in checks}
        if len(by_id) != len(checks) or set(by_id) != {spec.mutation_id for spec in specs}:
            reason = ":ID_UNSUPPORTED" if set(by_id) - {spec.mutation_id for spec in specs} else ""
            raise ValueError(f"CANDIDATE_MUTATION_SPEC_SET_MISMATCH{reason}")
        for spec in specs:
            expected = "KILLED" if spec.applies(case) else "NOT_APPLICABLE"
            if by_id[spec.mutation_id].status != expected:
                raise ValueError(f"CANDIDATE_MUTATION_GATE_FAILED:APPLICABILITY_MISMATCH:{spec.mutation_id}")


def mutation_specs_for(plugin: Any) -> tuple[MutationSpec, ...]:
    specs = tuple(plugin.mutation_specs())
    if not specs or len({spec.mutation_id for spec in specs}) != len(specs) or any(
        not re.fullmatch(r"[a-z][a-z0-9_]*", spec.mutation_id) or not spec.version
        or not callable(spec.applies) or not callable(spec.rewrite) for spec in specs
    ):
        raise ValueError("FEATURE_MUTATION_SPECS_INVALID")
    return tuple(sorted(specs, key=lambda spec: spec.mutation_id))


def mutation_spec_for(plugin: Any, mutation_id: str | None = None) -> MutationSpec:
    specs = mutation_specs_for(plugin)
    if mutation_id is None:
        if len(specs) != 1:
            raise ValueError("MUTATION_ID_REQUIRED: feature defines multiple rules")
        return specs[0]
    for spec in specs:
        if spec.mutation_id == mutation_id:
            return spec
    raise ValueError(f"CANDIDATE_MUTATION_ID_UNSUPPORTED:{mutation_id}")


class FeaturePlugin(Protocol):
    model_id: str
    template_id: str
    scope: AcceptanceScope
    mutation_policy: MutationPolicy

    def mutation_specs(self) -> tuple[MutationSpec, ...]: ...

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
    mutation_policy: MutationPolicy = MutationPolicy()
    scope: AcceptanceScope = AcceptanceScope(module="query", feature="join", candidate_root="candidates/query/join", active_root="cases/query/join", active_suite_root="cases/query", model_ref="models/query/join.yaml", legacy_feature_assets=("cases/query/join_01_inner.yaml", "cases/query/join_02_left.yaml"))

    def static_validate(self, path: Any, model: Any) -> dict[str, Any]:
        from xgtest.generator.candidate import static_validate_candidate
        return static_validate_candidate(path, model)

    def generate(self, model: Any, strategy: str, existing_cases: Any, output: Any, *, limit: int | None = None) -> Any:
        from xgtest.generator.candidate import generate_candidates
        return generate_candidates(model, strategy, existing_cases, output, limit=limit)

    def mutation_applies(self, case: Any) -> bool:
        return any(claim.assignment.get("predicate") == "less_equal" for claim in case.coverage)

    def mutation_specs(self) -> tuple[MutationSpec, ...]:
        return (MutationSpec(self.mutation_id, "1", self.mutation_applies, self.mutated_sql),)

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
