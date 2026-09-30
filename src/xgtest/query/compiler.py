"""Compile legacy query assets into a governance-free worker contract."""

from xgtest.core.canonical import xgmj1_sha256
from xgtest.core.models import QueryCaseInput, QueryStep, StrictModel


class ExecutableMetadata(StrictModel):
    id: str
    timeout: str


class QueryExecutable(StrictModel):
    schema_version: str = "1"
    metadata: ExecutableMetadata
    steps: tuple[QueryStep, ...]

    @property
    def execution_hash(self) -> str:
        return xgmj1_sha256(self.model_dump(mode="json"))


def compile_query_asset(asset: QueryCaseInput) -> QueryExecutable:
    return QueryExecutable(
        metadata=ExecutableMetadata(id=asset.metadata.id, timeout=asset.metadata.timeout),
        steps=asset.steps,
    )
