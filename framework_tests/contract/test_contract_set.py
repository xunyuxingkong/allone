import json
from pathlib import Path

from xgtest.core.contract_set import _content_hashes, build_contract_descriptor


ROOT = Path(__file__).resolve().parents[2]


def test_contract_descriptor_has_stable_sorted_content_identity() -> None:
    first = build_contract_descriptor(ROOT)
    assert first == build_contract_descriptor(ROOT)
    assert len(first["contract_set_id"]) == 64
    assert "registry/features.yaml" in first["sources"]
    assert "src/xgtest/core/models.py" in first["sources"]
    assert "src/xgtest/runtime/profile.py" in first["sources"]
    assert "src/xgtest/runtime/comparator.py" in first["sources"]
    assert "src/xgtest/adapter/xugu.py" in first["sources"]
    assert "schemas/UnifiedCase.schema.json" in first["generated"]
    assert all("\\" not in path for path in (*first["sources"], *first["generated"]))


def test_contract_source_hash_is_independent_of_platform_line_endings(tmp_path: Path) -> None:
    source = tmp_path / "contract.py"
    source.write_bytes(b"first\nsecond\n")
    unix_hash = _content_hashes(tmp_path, (), ("contract.py",))
    source.write_bytes(b"first\r\nsecond\r\n")
    assert _content_hashes(tmp_path, (), ("contract.py",)) == unix_hash


def test_committed_candidate_matches_current_contract() -> None:
    expected = json.loads((ROOT / "docs/g0a/contract-descriptor-candidate.json").read_text(encoding="utf-8"))
    assert build_contract_descriptor(ROOT) == expected


def test_query_semantics_files_are_part_of_contract_identity(tmp_path: Path) -> None:
    query = tmp_path / "src/xgtest/query"
    query.mkdir(parents=True)
    source = query / "runner.py"
    source.write_text("value = 1\n", encoding="utf-8")
    before = _content_hashes(tmp_path, ("src/xgtest/query",), ())
    source.write_text("value = 2\n", encoding="utf-8")
    after = _content_hashes(tmp_path, ("src/xgtest/query",), ())
    assert before != after
