import pytest
from pydantic import ValidationError

from xgtest.core.models import EffectiveMetadata
from xgtest.generated.registry_enums import CaseAssetStatus, FeatureKey, IsolationScope, Level


def test_effective_metadata_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        EffectiveMetadata(
            metadata_version="1.1",
            id="QUERY.JOIN.000001",
            title="join",
            module="query",
            feature=FeatureKey.JOIN,
            level=Level.P0,
            status=CaseAssetStatus.DRAFT,
            timeout="30s",
            isolation=IsolationScope.WORKER_SCHEMA,
            unexpected=True,
        )


def test_effective_metadata_rejects_implicit_bool() -> None:
    with pytest.raises(ValidationError):
        EffectiveMetadata(
            metadata_version="1.1",
            id="QUERY.JOIN.000001",
            title="join",
            module="query",
            feature=FeatureKey.JOIN,
            level=Level.P0,
            status=CaseAssetStatus.DRAFT,
            timeout="30s",
            isolation=IsolationScope.WORKER_SCHEMA,
            destructive="false",
        )
