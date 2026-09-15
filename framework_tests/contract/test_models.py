import pytest
from pydantic import ValidationError

from xgtest.core.models import EffectiveMetadata


def test_effective_metadata_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        EffectiveMetadata(
            id="QUERY.JOIN.000001",
            title="join",
            module="query",
            feature="join",
            level="P0",
            status="draft",
            timeout="30s",
            isolation="worker_schema",
            unexpected=True,
        )


def test_effective_metadata_rejects_implicit_bool() -> None:
    with pytest.raises(ValidationError):
        EffectiveMetadata(
            id="QUERY.JOIN.000001",
            title="join",
            module="query",
            feature="join",
            level="P0",
            status="draft",
            timeout="30s",
            isolation="worker_schema",
            destructive="false",
        )

\n