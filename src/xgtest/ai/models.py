"""Small, closed contracts for the single-user AI control loop."""
from typing import Any, Literal
from pydantic import Field, model_validator
from xgtest.core.model_base import StrictModel
from xgtest.core.canonical import xgmj1_sha256

ActionName = Literal[
    "project.inspect", "project.preflight", "module.inspect", "module.regression", "feature.coverage",
    "candidate.generate", "candidate.validate", "candidate.mutation", "candidate.trial", "candidate.technical_review",
    "acceptance.inspect", "acceptance.preflight", "acceptance.promote", "acceptance.post_verify",
]
ActionStatus = Literal["PASS", "FAIL", "BLOCKED", "WAITING_APPROVAL", "SKIPPED"]


class TestIntent(StrictModel):
    intent: Literal["query.full_test", "query.join.verify", "query.status"]
    module: Literal["query"] = "query"
    requested_by: str = Field(default="user", min_length=1)
    mission_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{32}$")
    allow_candidate_generation: bool = True
    allow_trial: bool = True
    allow_promotion: bool = True
    # One Job owns one feature scope. A parent Mission may coordinate several child Jobs.
    features: list[Literal["join", "filter", "aggregate", "subquery", "sort_limit"]] = Field(default_factory=lambda: ["join"], min_length=1)
    strategy: Literal["SMOKE", "STANDARD", "FULL", "AI_EXPLORATORY"] = "STANDARD"
    data_scale: Literal["SMALL", "MEDIUM", "LARGE"] = "SMALL"
    risk_focus: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def one_feature_per_job(self):
        if len(self.features) != 1:
            raise ValueError("JOB_FEATURE_SCOPE_MUST_BE_SINGLE")
        if len(set(self.risk_focus)) != len(self.risk_focus):
            raise ValueError("JOB_RISK_FOCUS_DUPLICATE")
        return self


class SemanticAction(StrictModel):
    action: ActionName
    # Generic case-id shape; the strict per-feature prefix is enforced by the
    # application/db-worker layers against the plugin registry.
    case_id: str | None = Field(default=None, pattern=r"^QUERY\.[A-Z0-9_]+\.[A-Z0-9]+$")
    reason: str = Field(min_length=1, max_length=4000)

    @model_validator(mode="after")
    def candidate_arguments(self):
        specific = self.action.startswith("candidate.") and self.action != "candidate.generate"
        if specific != (self.case_id is not None):
            raise ValueError("ACTION_ARGUMENTS_INVALID")
        return self


class TestPlan(StrictModel):
    goal: str = Field(min_length=1, max_length=4000)
    actions: list[SemanticAction] = Field(default_factory=list)


class ActionResult(StrictModel):
    action: ActionName
    status: ActionStatus
    case_id: str | None = None
    outputs: dict[str, Any] = Field(default_factory=dict)
    evidence_refs: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    next_allowed_actions: list[ActionName] = Field(default_factory=list)


class FailureAnalysis(StrictModel):
    category: Literal["TEST_ASSERTION", "DATABASE_ERROR", "RUNTIME_ENVIRONMENT", "EVIDENCE_STALE", "COVERAGE_GAP", "UNKNOWN"]
    failure_summary: str = Field(min_length=1, max_length=4000)
    likely_area: str = Field(min_length=1, max_length=1000)
    recommended_action: str = Field(min_length=1, max_length=2000)
    confidence: float = Field(ge=0, le=1)


class TechnicalReview(StrictModel):
    review_type: Literal["ai_technical"] = "ai_technical"
    decision: Literal["PASS", "CONCERNS", "FAIL"]
    findings: list[str] = Field(default_factory=list)
    recommendation: Literal["READY_FOR_HUMAN_REVIEW", "NEEDS_HUMAN_CHECK", "INVESTIGATE"]


class JobAbandonment(StrictModel):
    """Immutable record of an operator's explicit decision to stop a job."""
    operator: str = Field(min_length=1, max_length=200)
    reason: str = Field(min_length=1, max_length=2000)
    abandoned_at: str
    previous_state: Literal["PLANNED", "RUNNING", "WAITING_APPROVAL", "BLOCKED", "FAILED", "COMPLETED"]


class StrategyCompletionEvidence(StrictModel):
    """Versioned, self-checking snapshot of a Job's strategy completion facts."""
    schema_version: Literal["1", "2"] = "2"
    candidate_scope_ids: list[str]
    generated_cases_valid: bool
    regression_pass: bool
    no_blocking_failure: bool
    budget_or_no_gap: bool
    smoke_complete: bool
    regression_result_identity: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    coverage_snapshot: dict[str, Any] = Field(default_factory=dict)
    budget: dict[str, Any] = Field(default_factory=dict)
    completion_reason: Literal["BUDGET_EXHAUSTED", "NO_COVERAGE_GAP", "INCOMPLETE", "LEGACY_FROZEN"]
    completed_at: str = Field(min_length=1)
    completion_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="before")
    @classmethod
    def normalize_legacy_snapshot(cls, value):
        if isinstance(value, dict) and "completion_hash" not in value:
            value = dict(value)
            value.setdefault("regression_result_identity", None)
            value.setdefault("coverage_snapshot", {})
            value.setdefault("budget", {})
            value.setdefault("completion_reason", "LEGACY_FROZEN")
            value.setdefault("completed_at", "legacy-checkpoint")
            value["completion_hash"] = xgmj1_sha256(value)
        return value

    @model_validator(mode="after")
    def validate_frozen_identity(self):
        if len(self.candidate_scope_ids) != len(set(self.candidate_scope_ids)):
            raise ValueError("STRATEGY_COMPLETION_SCOPE_DUPLICATE")
        if self.completion_hash != xgmj1_sha256(self.model_dump(mode="json", exclude={"completion_hash"})):
            raise ValueError("STRATEGY_COMPLETION_HASH_MISMATCH")
        return self


class TestJob(StrictModel):
    job_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    intent: TestIntent
    plan: TestPlan
    state: Literal["PLANNED", "RUNNING", "WAITING_APPROVAL", "BLOCKED", "FAILED", "COMPLETED"] = "PLANNED"
    current_action: SemanticAction | None = None
    action_results: list[ActionResult] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    failure_analysis: FailureAnalysis | None = None
    explanation: str = ""
    revision: int = 0
    completed_requests: dict[str, str] = Field(default_factory=dict)
    preflight_required: bool = True
    # Candidate IDs selected for this job by generation. Existing deterministic
    # candidates may be adopted explicitly; other files in the shared root are excluded.
    candidate_scope_ids: list[str] = Field(default_factory=list)
    # Immutable snapshot attached to acceptance.inspect and retained after promotion.
    strategy_completion: StrategyCompletionEvidence | None = None
    control_plane_layer_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    git_commit: str | None = Field(default=None, pattern=r"^[0-9a-f]{40,64}$")
    abandonment: JobAbandonment | None = None


class ActionRequest(StrictModel):
    request_id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,80}$")
    expected_revision: int = Field(ge=1)
    action: SemanticAction
    technical_review: TechnicalReview | None = None
    review_context_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def review_arguments(self):
        is_review = self.action.action == "candidate.technical_review"
        if is_review != (self.technical_review is not None) or is_review != (self.review_context_id is not None):
            raise ValueError("TECHNICAL_REVIEW_ARGUMENTS_INVALID")
        return self


class JobEvent(StrictModel):
    sequence: int = Field(ge=1)
    event: Literal["CREATED", "STARTED", "ACTION_STARTED", "ACTION_FINISHED", "PAUSED", "RESUMED", "FINISHED", "RECOVERED", "ABANDONED"]
    timestamp: str
    checkpoint: TestJob


# Repair contracts are deliberately reserved, not executable in this MVP.
RESERVED_ACTIONS = ("repair.propose", "repair.validate")
