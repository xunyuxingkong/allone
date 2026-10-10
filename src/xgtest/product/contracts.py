"""User-facing Test Mission contract: why a test exists, what it covers, what it excludes."""
import re
from typing import ClassVar, Literal

from pydantic import Field, field_validator

from xgtest.core.model_base import StrictModel

# Product-level mission state, deliberately separate from internal Core states.
MissionState = Literal["DRAFT", "READY", "RUNNING", "WAITING_APPROVAL", "BLOCKED", "COMPLETED"]
MissionStrategy = Literal["SMOKE", "STANDARD", "FULL", "AI_EXPLORATORY"]
MissionDataScale = Literal["SMALL", "MEDIUM", "LARGE"]

# Only features the deterministic Core can actually model and measure coverage for today.
# Kept narrow on purpose: a mission must never claim coverage the Core cannot deliver.
SUPPORTED_FEATURES = ("join", "filter", "aggregate", "subquery")

# Rough planning ranges per intensity (cases), mirroring the product roadmap.
STRATEGY_CASE_RANGE: dict[str, tuple[int, int]] = {
    "SMOKE": (30, 50),
    "STANDARD": (150, 300),
    "FULL": (500, 2000),
    "AI_EXPLORATORY": (150, 300),
}

_IDENTIFIER = re.compile(r"^[a-z][a-z0-9_-]*$")


def _identifiers(values, code: str) -> list[str]:
    for value in values:
        if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
            raise ValueError(code)
    return list(values)


class TestMission(StrictModel):
    __test__: ClassVar[bool] = False  # keep pytest from collecting this model as a test class

    mission_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    name: str = Field(min_length=1, max_length=200)
    purpose: str = Field(min_length=1, max_length=2000)
    module: Literal["query"] = "query"
    features: list[str] = Field(min_length=1)
    strategy: MissionStrategy = "STANDARD"
    data_scale: MissionDataScale = "SMALL"
    risk_focus: list[str] = Field(default_factory=list)
    acceptance_goal: str = Field(default="本期定义范围内语义正确", min_length=1, max_length=1000)
    excluded_scope: list[str] = Field(default_factory=list)
    created_by: str = Field(default="user", min_length=1, max_length=200)
    state: MissionState = "DRAFT"
    job_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{32}$")

    @field_validator("features")
    @classmethod
    def features_are_supported(cls, values: list[str]) -> list[str]:
        identifiers = _identifiers(values, "MISSION_FEATURE_INVALID")
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("MISSION_FEATURE_DUPLICATE")
        unsupported = [value for value in identifiers if value not in SUPPORTED_FEATURES]
        if unsupported:
            raise ValueError(f"MISSION_FEATURE_UNAVAILABLE:{','.join(sorted(unsupported))}")
        return identifiers

    @field_validator("risk_focus")
    @classmethod
    def risk_focus_is_identifiers(cls, values: list[str]) -> list[str]:
        identifiers = _identifiers(values, "MISSION_RISK_FOCUS_INVALID")
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("MISSION_RISK_FOCUS_DUPLICATE")
        return identifiers


def strategy_estimate(strategy: MissionStrategy) -> dict:
    """Planning estimate shown before a job is created (a range, never a promise)."""
    low, high = STRATEGY_CASE_RANGE[strategy]
    return {"strategy": strategy, "case_min": low, "case_max": high,
            "sql_min": low, "sql_max": high * 2, "unit": "cases"}
