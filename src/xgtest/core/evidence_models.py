"""Evidence models; definitions owned by this layer."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator, model_validator
from xgtest.generated.registry_enums import (AttemptStatus, CaseAssetStatus, CaseExecutionStatus, FailureType, FeatureKey, IsolationScope, Level, ResourceAccessMode, StepStatus)
from .model_base import StrictModel


class CoverageClaim(StrictModel):
    claim_id: str = Field(pattern=r"^[a-z][a-z0-9_-]*$")
    model_id: str = Field(min_length=1)
    model_version: str = Field(min_length=1)
    assignment: dict[str, str]
    assertion_refs: tuple[str, ...] = Field(min_length=1)



class GenerationProvenance(StrictModel):
    generator: str = Field(min_length=1)
    generator_version: str = Field(min_length=1)
    model_id: str = Field(min_length=1)
    model_version: str = Field(min_length=1)
    template_id: str = Field(min_length=1)
    template_version: str = Field(min_length=1)
    strategy: str = Field(min_length=1)
    seed: int | None = None
    input_hash: str = Field(pattern=r"^[0-9a-f]{64}$")



class OracleProvenance(StrictModel):
    kind: Literal["manual", "reference_database", "known_result", "property"]
    reference: str | None = None
    reviewer: str | None = None
    evidence_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def known_result_requires_reference(self) -> "OracleProvenance":
        if self.kind == "known_result" and not self.reference:
            raise ValueError("ORACLE_REFERENCE_REQUIRED")
        return self



class ValidationEvidence(StrictModel):
    semantic_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    static_validation_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    trial_run_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    trial_artifact_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    trial_run_ref: str | None = None
    review_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")



class MutationCheck(StrictModel):
    mutation_id: str = Field(min_length=1)
    status: Literal[
        "KILLED", "NOT_APPLICABLE", "WEAK", "BASELINE_NOT_PASS",
        "BASELINE_NONDETERMINISTIC", "INCONCLUSIVE", "MUTATED_NONDETERMINISTIC",
    ]
    original_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    mutated_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def hashes_match_status(self) -> "MutationCheck":
        if self.status == "KILLED" and (
            self.original_hash is None
            or self.mutated_hash is None
            or self.original_hash == self.mutated_hash
        ):
            raise ValueError("MUTATION_KILLED_HASHES_REQUIRED")
        if self.status == "NOT_APPLICABLE" and (self.original_hash is not None or self.mutated_hash is not None):
            raise ValueError("MUTATION_NOT_APPLICABLE_HAS_RESULT")
        return self



class MutationValidationResult(MutationCheck):
    case_id: str = Field(min_length=1)
    execution: dict[str, Any] | None = None



class MutationEvidence(StrictModel):
    policy_version: str = Field(min_length=1)
    semantic_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    contract_set_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    runtime_profile_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    artifact_ref: str = Field(min_length=1)
    artifact_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    checks: tuple[MutationCheck, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def mutation_ids_are_unique(self) -> "MutationEvidence":
        identifiers = [check.mutation_id for check in self.checks]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("MUTATION_ID_DUPLICATED")
        return self



class CoverageReview(StrictModel):
    review_input_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    evidence_ref: str = Field(min_length=1)



class ReviewEvidence(StrictModel):
    review_input_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    semantic_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    trial_artifact_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    reviewer: str = Field(min_length=1)
    review_reference: str = Field(min_length=1)

