import json
from pathlib import Path

from xgtest.core.contract_set import _content_hashes, build_contract_descriptor, validate_contract_descriptor


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


def test_layer_invalidation_does_not_treat_cli_or_tests_as_runtime(tmp_path: Path) -> None:
    for relative, content in {
        "src/xgtest/query/runner.py": "execute = 1\n",
        "src/xgtest/runtime/comparator.py": "compare = 1\n",
        "src/xgtest/cli.py": "display = 1\n",
        "framework_tests/example.py": "assert True\n",
        "src/xgtest/generator/package.py": "gate = 1\n",
    }.items():
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    baseline = build_contract_descriptor(tmp_path)
    validate_contract_descriptor(baseline)
    (tmp_path / "src/xgtest/cli.py").write_text("display = 2\n")
    (tmp_path / "framework_tests/example.py").write_text("assert False\n")
    (tmp_path / "src/xgtest/generator/package.py").write_text("gate = 2\n")
    changed = build_contract_descriptor(tmp_path)
    assert baseline["contract_set_id"] == changed["contract_set_id"]
    for layer in ("control_plane", "suite", "governance"):
        assert baseline["layers"][layer]["id"] != changed["layers"][layer]["id"]
    (tmp_path / "src/xgtest/runtime/comparator.py").write_text("compare = 2\n")
    assert build_contract_descriptor(tmp_path)["contract_set_id"] != baseline["contract_set_id"]


def test_historical_v1_descriptor_is_validated_without_relabeling():
    raw = (ROOT / "docs/g0a/contract-descriptor-v12-legacy.json").read_text(encoding="utf-8")
    validate_contract_descriptor(json.loads(raw))
