"""Control models; definitions owned by this layer."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator, model_validator
from xgtest.generated.registry_enums import (AttemptStatus, CaseAssetStatus, CaseExecutionStatus, FailureType, FeatureKey, IsolationScope, Level, ResourceAccessMode, StepStatus)
from .model_base import StrictModel
from .execution_models import QueryStep, SqlStep
from .evidence_models import CoverageClaim, CoverageReview, GenerationProvenance, MutationCheck, MutationEvidence, MutationValidationResult, OracleProvenance, ReviewEvidence, ValidationEvidence
from .governance_models import EnvironmentRequirement, ResourceRequest


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



class FixtureRef(StrictModel):
    fixture_id: str
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")



class BootstrapCaseInput(StrictModel):
    """Typed boundary for the temporary SQL MVP bootstrap asset format."""

    metadata: EffectiveMetadata
    steps: tuple[SqlStep, ...] = Field(min_length=1)



class QueryCaseInput(StrictModel):
    metadata: EffectiveMetadata
    steps: tuple[QueryStep, ...] = Field(min_length=1)
    coverage: tuple[CoverageClaim, ...] = ()
    generation: GenerationProvenance | None = None
    oracle: OracleProvenance | None = None
    validation_evidence: ValidationEvidence | None = None
    mutation_evidence: MutationEvidence | None = None
    review_evidence: ReviewEvidence | None = None
    coverage_review: CoverageReview | None = None

    @model_validator(mode="after")
    def step_ids_are_unique(self) -> "QueryCaseInput":
        ids = [step.id for step in self.steps]
        if len(ids) != len(set(ids)):
            raise ValueError("QUERY_STEP_ID_DUPLICATED: step IDs must be unique")
        return self



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

