from pathlib import Path

from xgtest.core.contract_set import build_contract_descriptor


ROOT = Path(__file__).resolve().parents[2]


def test_contract_descriptor_has_stable_sorted_content_identity() -> None:
    first = build_contract_descriptor(ROOT)
    assert first == build_contract_descriptor(ROOT)
    assert len(first["contract_set_id"]) == 64
    assert "registry/features.yaml" in first["sources"]
    assert "src/xgtest/core/models.py" in first["sources"]
    assert "schemas/UnifiedCase.schema.json" in first["generated"]
    assert all("\\" not in path for path in (*first["sources"], *first["generated"]))
