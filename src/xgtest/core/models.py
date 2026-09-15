"""Strict shared SQL MVP data models."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from xgtest.generated.registry_enums import (
    AttemptStatus, CaseAssetStatus, CaseExecutionStatus, FeatureKey,
    IsolationScope, Level, ResourceAccessMode, StepStatus,
)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class RawMetadata(StrictModel):
    metadata_version: str | None = None
    id: str | None = Field(default=None, pattern=r"^[A-Z][A-Z0-9_.-]*$")
    title: str | None = None
    module: str | None = None
    feature: FeatureKey | None = None
    subfeature: str | None = None
    level: Level | None = None
    status: CaseAssetStatus | None = None
    tags: tuple[str, ...] = ()
    timeout: str | None = Field(default=None, pattern=r"^\d+(ms|s|m|h)$")
    isolation: IsolationScope | None = None
    destructive: bool | None = None
    scenario: str | None = None
    complexity: str | None = None
    execution_class: str | None = None
    parallel: bool | None = None
    idempotency: str | None = None
    retry: int | None = Field(default=None, ge=0)
    reset_contract: str | None = None
    cleanup_timeout: str | None = Field(default=None, pattern=r"^\d+(ms|s|m|h)$")
    owner: str | None = None
    since: str | None = None
    until: str | None = None
    generated_by: str | None = None
    disabled_reason: str | None = None
    replaced_by: str | None = None


class EffectiveMetadata(StrictModel):
    metadata_version: str
    id: str = Field(pattern=r"^[A-Z][A-Z0-9_.-]*$")
    title: str
    module: str
    feature: FeatureKey
    subfeature: str | None = None
    scenario: str | None = None
    complexity: str | None = None
    level: Level
    status: CaseAssetStatus
    tags: tuple[str, ...] = ()
    timeout: str = Field(pattern=r"^\d+(ms|s|m|h)$")
    isolation: IsolationScope
    destructive: bool = False
    execution_class: str = "sql"
    parallel: bool = False
    idempotency: str = "idempotent"
    retry: int = Field(default=0, ge=0)
    reset_contract: str = "default"
    cleanup_timeout: str = Field(default="30s", pattern=r"^\d+(ms|s|m|h)$")
    requirements: tuple["EnvironmentRequirement", ...] = ()
    resources: tuple["ResourceRequest", ...] = ()
    owner: str | None = None
    since: str | None = None
    until: str | None = None
    generated_by: str | None = None
    disabled_reason: str | None = None
    replaced_by: str | None = None


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
    error_profile: str | None = None
    normalization_profile: str | None = None
    float_policy: str = "canonical_ieee754"
    timestamp_policy: str = "rfc3339"


class FixtureRef(StrictModel):
    fixture_id: str
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class ExpectedRows(StrictModel):
    rows: tuple[tuple[Any, ...], ...]


class ExpectedHash(StrictModel):
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class ExpectedError(StrictModel):
    code: str | None = None
    sqlstate: str | None = None
    message_pattern: str | None = None


class ExpectedStatement(StrictModel):
    affected_rows: int | None = Field(default=None, ge=0)


class SqlStep(StrictModel):
    id: str = Field(pattern=r"^[a-z][a-z0-9_-]*$")
    kind: Literal["setup", "statement", "query", "cleanup"]
    sql: str = Field(min_length=1)
    comparison: ComparisonProfile | None = None
    expected: ExpectedRows | ExpectedHash | ExpectedError | ExpectedStatement | None = None


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
    target_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    database_product: str
    database_version: str
    db_build: str
    driver_name: str
    driver_version: str
    os: str
    arch: str
    topology: str
    mode: str
    configuration_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    dataset_fingerprint: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    sql_runtime_profile_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")


class ResourceRequest(StrictModel):
    resource_type: str
    resource_id: str
    scope: IsolationScope
    access_mode: ResourceAccessMode
    quantity: int = Field(default=1, ge=1)
    impact_scope: str
    parent_identity: str | None = None


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
    git_commit: str
    dirty: bool
    source_snapshot_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    catalog_snapshot_id: str
    plan_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    case_entries: tuple[str, ...] = ()
    target_entries: tuple[Target, ...] = ()
    runtime_versions: dict[str, str]


class Run(StrictModel):
    run_id: str
    manifest_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class CaseExecution(StrictModel):
    run_id: str
    case_id: str
    target_id: str
    status: CaseExecutionStatus


class Attempt(StrictModel):
    attempt_id: str
    case_execution_id: str
    status: AttemptStatus


class StepResult(StrictModel):
    step_id: str
    status: StepStatus


class ArtifactRef(StrictModel):
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    size: int = Field(ge=0)


class ResultEvent(StrictModel):
    schema_version: str = "1"
    event_id: str
    run_id: str
    case_id: str
    attempt_id: str
    target_id: str
    environment_id: str
    producer_epoch: int = Field(ge=0)
    assignment_epoch: int | None = Field(default=None, ge=0)
    sequence: int = Field(ge=1)
    fencing_token: str | None = None
    timestamp: datetime
    event_type: str
    payload: dict[str, Any]


class MvpStepReport(StrictModel):
    id: str
    kind: str
    status: Literal["PASS", "FAIL", "ERROR"]
    duration_ms: float = Field(ge=0)
    columns: tuple[str, ...] = ()
    column_types: tuple[str | None, ...] = ()
    rows: tuple[tuple[Any, ...], ...] = ()
    affected_rows: int | None = None
    error_type: str | None = None
    error_code: str | None = None
    sqlstate: str | None = None
    error: str | None = None


class MvpCaseReport(StrictModel):
    case_id: str
    status: Literal["PASS", "FAIL", "ERROR"]
    cleanup_status: Literal["PASS", "FAILED"]
    duration_ms: float = Field(ge=0)
    steps: tuple[MvpStepReport, ...]
    error: str | None = None


class MvpRunReport(StrictModel):
    schema_version: Literal["1"] = "1"
    run_id: str
    started_at: datetime
    finished_at: datetime
    target: dict[str, str]
    cases: tuple[MvpCaseReport, ...]
    status: Literal["PASS", "FAIL"]


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
        MvpStepReport,
        MvpCaseReport,
        MvpRunReport,
    )
}
