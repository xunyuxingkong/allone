from pathlib import Path

from xgtest.core.contract_set import _content_hashes, build_contract_descriptor


ROOT = Path(__file__).resolve().parents[2]


def test_contract_descriptor_has_stable_sorted_content_identity() -> None:
    first = build_contract_descriptor(ROOT)
    assert first == build_contract_descriptor(ROOT)
    assert len(first["contract_set_id"]) == 64
    assert "registry/features.yaml" in first["sources"]
    assert "src/xgtest/core/models.py" in first["sources"]
    assert "schemas/UnifiedCase.schema.json" in first["generated"]
    assert all("\\" not in path for path in (*first["sources"], *first["generated"]))


def test_contract_source_hash_is_independent_of_platform_line_endings(tmp_path: Path) -> None:
    source = tmp_path / "contract.py"
    source.write_bytes(b"first\nsecond\n")
    unix_hash = _content_hashes(tmp_path, (), ("contract.py",))
    source.write_bytes(b"first\r\nsecond\r\n")
    assert _content_hashes(tmp_path, (), ("contract.py",)) == unix_hash
