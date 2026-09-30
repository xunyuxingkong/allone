"""A frozen feature scope owns paths and coverage policy, not generic services."""

from pathlib import Path
from typing import Literal, Any

from pydantic import field_validator

from xgtest.core.models import StrictModel


class AcceptanceScope(StrictModel):
    module: str
    feature: str
    candidate_root: str
    active_root: str
    active_suite_root: str
    model_ref: str
    coverage_strategy: Literal["pairwise", "all_values"] = "pairwise"

    @field_validator("module", "feature")
    @classmethod
    def name_is_identifier(cls, value: str) -> str:
        if not value or not value.replace("_", "").isalnum():
            raise ValueError("SCOPE_NAME_INVALID")
        return value

    @field_validator("candidate_root", "active_root", "active_suite_root", "model_ref")
    @classmethod
    def path_is_relative(cls, value: str) -> str:
        path = Path(value)
        if not value or value == "." or path.is_absolute() or ".." in path.parts or "\\" in value or ":" in value:
            raise ValueError("SCOPE_PATH_INVALID")
        return value

    @property
    def model_id(self) -> str:
        return f"{self.module}.{self.feature}"

    @property
    def scope_id(self) -> str:
        return f"{self.model_id}.review"

    def path(self, root: Path, role: str) -> Path:
        if role not in {"candidate_root", "active_root", "active_suite_root", "model_ref"}:
            raise ValueError("SCOPE_PATH_ROLE_INVALID")
        result = (root / getattr(self, role)).resolve()
        if not result.is_relative_to(root.resolve()):
            raise ValueError("SCOPE_PATH_OUTSIDE_PROJECT")
        return result

    def load_model(self, root: Path):
        from xgtest.design.model import load_test_model
        model = load_test_model(self.path(root, "model_ref"))
        if model.model_id != self.model_id:
            raise ValueError("SCOPE_MODEL_ID_MISMATCH")
        return model

    def asset_paths(self, root: Path, role: str) -> list[Path]:
        if role not in {"candidate_root", "active_suite_root"}:
            raise ValueError("SCOPE_ASSET_ROLE_INVALID")
        directory = self.path(root, role)
        return sorted((*directory.rglob("*.yaml"), *directory.rglob("*.yml")))


def resolve_scope(manifest: dict[str, Any] | None = None, scope: AcceptanceScope | None = None) -> AcceptanceScope:
    from xgtest.generator.plugins import FEATURE_PLUGINS
    if scope is not None:
        result = scope
    elif manifest is not None and "scope_definition" in manifest:
        result = AcceptanceScope.model_validate(manifest["scope_definition"])
    elif manifest is not None and "scope" in manifest:
        result = FEATURE_PLUGINS.for_scope(manifest["scope"]).scope
    else:
        result = FEATURE_PLUGINS.default_scope()
    FEATURE_PLUGINS.for_model(result.model_id)
    if manifest is not None and manifest.get("scope", result.scope_id) != result.scope_id:
        raise ValueError("SCOPE_ID_MISMATCH")
    if not Path(result.active_root).is_relative_to(Path(result.active_suite_root)):
        raise ValueError("SCOPE_ACTIVE_ROOT_OUTSIDE_SUITE")
    candidate = Path(result.candidate_root)
    suite = Path(result.active_suite_root)
    if candidate.is_relative_to(suite) or suite.is_relative_to(candidate):
        raise ValueError("SCOPE_CANDIDATES_OVERLAP_ACTIVE_SUITE")
    return result
