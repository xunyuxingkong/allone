"""Strict shared SQL MVP data models."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class RawMetadata(StrictModel):
    id: str | None = Field(default=None, pattern=r"^[A-Z][A-Z0-9_.-]*$")
    title: str | None = None
    module: str | None = None
    feature: str | None = None
    subfeature: str | None = None
    level: str | None = None
    status: str | None = None
    tags: tuple[str, ...] = ()
    timeout: str | None = Field(default=None, pattern=r"^\d+(ms|s|m|h)$")
    isolation: str | None = None
    destructive: bool | None = None


class EffectiveMetadata(StrictModel):
    id: str = Field(pattern=r"^[A-Z][A-Z0-9_.-]*$")
    title: str
    module: str
    feature: str
    level: str
    status: Literal["draft", "review", "active", "disabled", "deprecated"]
    tags: tuple[str, ...] = ()
    timeout: str = Field(pattern=r"^\d+(ms|s|m|h)$")
    isolation: str
    destructive: bool = False


class SourceInfo(StrictModel):
    relative_path: str = Field(min_length=1)
    source_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @field_validator("relative_path")
    @classmethod
    def relative_path_must_stay_within_snapshot(cls, value: str) -> str:
        if value.startswith("/") or ".." in value.split("/"):
            raise ValueError("relative_path must remain under the snapshot root")
        return value


class ComparisonProfile(StrictModel):
    mode: Literal["exact", "rowsort", "expected_error"]
    canonical_version: Literal["1"] = "1"


class FixtureRef(StrictModel):
    fixture_id: str
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class SqlStep(StrictModel):
    id: str = Field(pattern=r"^[a-z][a-z0-9_-]*$")
    kind: Literal["setup", "statement", "query", "cleanup"]
    sql: str = Field(min_length=1)
    comparison: ComparisonProfile | None = None
    expected: Any | None = None


class QueryStep(SqlStep):
    kind: Literal["query"] = "query"
    comparison: ComparisonProfile


class CoverageClaim(StrictModel):
    claim_id: str = Field(pattern=r"^[a-z][a-z0-9_-]*$")
    model_id: str
    model_version: str
    assignment: dict[str, str]
    assertion_refs: tuple[str, ...]


class CoverageReview(StrictModel):
    review_input_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    evidence_ref: str


class UnifiedCase(StrictModel):
    metadata: EffectiveMetadata
    source: SourceInfo
    steps: tuple[SqlStep, ...]
    fixtures: tuple[FixtureRef, ...] = ()
    coverage: tuple[CoverageClaim, ...] = ()
    coverage_review: CoverageReview | None = None
    dependency_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    compiled_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    semantic_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class EnvironmentRequirement(StrictModel):
    capability: str
    required: bool = True


class Target(StrictModel):
    target_id: str
    db_build: str
    driver_version: str
    sql_runtime_profile_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")


class ResourceRequest(StrictModel):
    resource_id: str
    scope: str
    access_mode: Literal["shared_read", "exclusive"]
    capacity: int = Field(default=1, ge=1)


class ExpectedExecution(StrictModel):
    case_id: str
    target_id: str
    reason_code: str


class TestPlan(StrictModel):
    selector: str
    targets: tuple[Target, ...]
    expected_executions: tuple[ExpectedExecution, ...]


class BundleRef(StrictModel):
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    size: int = Field(ge=0)


class Manifest(StrictModel):
    run_id: str
    contract_set_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    plan: TestPlan
    bundles: tuple[BundleRef, ...]


class Run(StrictModel):
    run_id: str
    manifest_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class CaseExecution(StrictModel):
    run_id: str
    case_id: str
    target_id: str
    status: str


class Attempt(StrictModel):
    attempt_id: str
    case_execution_id: str
    status: str


class StepResult(StrictModel):
    step_id: str
    status: str


class ArtifactRef(StrictModel):
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    size: int = Field(ge=0)


class ResultEvent(StrictModel):
    attempt_id: str
    producer_epoch: int = Field(ge=0)
    sequence: int = Field(ge=1)
    event_type: str
    payload: dict[str, Any]


MODEL_EXPORTS: dict[str, type[BaseModel]] = {
    model.__name__: model
    for model in (
        RawMetadata,
        EffectiveMetadata,
        UnifiedCase,
        TestPlan,
        Target,
        EnvironmentRequirement,
        ResourceRequest,
        Manifest,
        ResultEvent,
    )
}
