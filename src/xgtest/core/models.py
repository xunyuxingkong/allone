"""Compatibility exports. Runtime models live in execution_models, not here."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator, model_validator
from xgtest.generated.registry_enums import (AttemptStatus, CaseAssetStatus, CaseExecutionStatus, FailureType, FeatureKey, IsolationScope, Level, ResourceAccessMode, StepStatus)
from .model_base import (StrictModel)
from .execution_models import (CapabilityOutcome, ComparisonProfile, ErrorMappingProfile, ExpectedError, ExpectedHash, ExpectedRows, ExpectedStatement, MvpCaseReport, MvpRunReport, MvpStepReport, MvpTargetReport, QueryCaseReport, QueryRunReport, QueryStep, QueryStepReport, QueryTargetReport, RuntimeCapabilitiesIdentity, RuntimeDriverIdentity, RuntimeProfile, RuntimeProfileIdentity, RuntimeTargetIdentity, SqlStep, TYPED_EXPECTED_VERSION, TransactionSemantics, TypeMappingProfile, _QUERY_MUTATION_KEYWORDS, _query_sql_tokens, _validate_read_only_query_sql, decode_expected)
from .evidence_models import (CoverageClaim, CoverageReview, GenerationProvenance, MutationCheck, MutationEvidence, MutationValidationResult, OracleProvenance, ReviewEvidence, ValidationEvidence)
from .governance_models import (ArtifactRef, Attempt, BundleRef, CaseExecution, EnvironmentRequirement, ExpectedExecution, Manifest, ResourceRequest, ResultEvent, Run, StepResult, Target, TestPlan)
from .control_models import (BootstrapCaseInput, EffectiveMetadata, FixtureRef, QueryCaseInput, RawMetadata, SourceInfo, UnifiedCase)


MODEL_EXPORTS: dict[str, type[BaseModel]] = {
    model.__name__: model
    for model in (
        RawMetadata,
        EffectiveMetadata,
        UnifiedCase,
        BootstrapCaseInput,
        QueryStep,
        QueryCaseInput,
        CoverageClaim,
        GenerationProvenance,
        OracleProvenance,
        ValidationEvidence,
        MutationCheck,
        MutationValidationResult,
        MutationEvidence,
        CoverageReview,
        ReviewEvidence,
        TestPlan,
        Target,
        EnvironmentRequirement,
        ResourceRequest,
        Manifest,
        RuntimeTargetIdentity,
        RuntimeDriverIdentity,
        TypeMappingProfile,
        TransactionSemantics,
        ErrorMappingProfile,
        CapabilityOutcome,
        RuntimeCapabilitiesIdentity,
        RuntimeProfileIdentity,
        RuntimeProfile,
        ResultEvent,
        MvpStepReport,
        MvpCaseReport,
        MvpTargetReport,
        MvpRunReport,
        QueryStepReport,
        QueryCaseReport,
        QueryTargetReport,
        QueryRunReport,
    )
}
