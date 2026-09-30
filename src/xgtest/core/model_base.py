"""Model base; definitions owned by this layer."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator, model_validator
from xgtest.generated.registry_enums import (AttemptStatus, CaseAssetStatus, CaseExecutionStatus, FailureType, FeatureKey, IsolationScope, Level, ResourceAccessMode, StepStatus)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

