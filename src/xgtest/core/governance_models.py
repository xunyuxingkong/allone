"""Governance models; definitions owned by this layer."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator, model_validator
from xgtest.generated.registry_enums import (AttemptStatus, CaseAssetStatus, CaseExecutionStatus, FailureType, FeatureKey, IsolationScope, Level, ResourceAccessMode, StepStatus)
from .model_base import StrictModel
from .identity import compute_plan_hash, validate_target_id


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

    @model_validator(mode="after")
    def target_id_must_match_identity(self) -> "Target":
        try:
            validate_target_id(self)
        except ValueError as error:
            raise ValueError(str(error)) from error
        return self



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

    @model_validator(mode="after")
    def identity_fields_must_match(self) -> "Manifest":
        for target in self.plan.targets + self.target_entries:
            validate_target_id(target)
        expected_plan_hash = compute_plan_hash(self.plan)
        if self.plan_hash != expected_plan_hash:
            raise ValueError("PLAN_HASH_MISMATCH: plan_hash does not match plan identity projection")
        return self



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

