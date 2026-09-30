"""Compile coordinator assets into the execution-only worker contract."""
from __future__ import annotations

from typing import TYPE_CHECKING
from xgtest.core.execution_models import QueryExecutable, ExecutableMetadata

if TYPE_CHECKING:
    from xgtest.core.control_models import QueryCaseInput


def compile_query_asset(asset: QueryCaseInput) -> QueryExecutable:
    return QueryExecutable(
        metadata=ExecutableMetadata(id=asset.metadata.id, timeout=asset.metadata.timeout),
        steps=asset.steps,
    )
