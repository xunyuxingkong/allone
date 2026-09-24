from pathlib import Path

import pytest

from xgtest.core.models import ExpectedError, ExpectedHash, ExpectedRows
from xgtest.query.loader import load_query_case, validate_query_directory


VALID = """
metadata:
  id: QUERY.BASIC.0001
  title: one constant
  feature: query
steps:
  - id: q1
    kind: query
    sql: SELECT 1
    comparison:
      mode: exact
    expected:
      rows:
        - [1]
"""


def write_case(tmp_path: Path, content: str = VALID, name: str = "case.yaml") -> Path:
    path = tmp_path / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def test_loader_returns_typed_query_case(tmp_path: Path) -> None:
    case = load_query_case(write_case(tmp_path))
    assert case.metadata.id == "QUERY.BASIC.0001"
    assert case.steps[0].kind == "query"
    assert isinstance(case.steps[0].expected, ExpectedRows)


@pytest.mark.parametrize("replacement", [
    "    kind: statement",
    "    sql: ''",
    "    expected:\n      affected_rows: 1",
    "    expected:\n      rows: []\n      sha256: " + "a" * 64,
    "    expected:\n      rows: []\n      code: E5021",
])
def test_loader_rejects_non_query_or_invalid_expected(tmp_path: Path, replacement: str) -> None:
    content = VALID.replace("    kind: query\n    sql: SELECT 1\n    comparison:\n      mode: exact\n    expected:\n      rows:\n        - [1]", replacement)
    with pytest.raises(ValueError):
        load_query_case(write_case(tmp_path, content))


def test_loader_supports_sha256_and_expected_error_variants(tmp_path: Path) -> None:
    digest = "a" * 64
    sha_case = VALID.replace("mode: exact", "mode: sha256").replace("rows:\n        - [1]", f"sha256: {digest}")
    error_case = VALID.replace("mode: exact", "mode: expected_error").replace("rows:\n        - [1]", "code: E5021")
    assert isinstance(load_query_case(write_case(tmp_path, sha_case)).steps[0].expected, ExpectedHash)
    assert isinstance(load_query_case(write_case(tmp_path, error_case)).steps[0].expected, ExpectedError)


def test_loader_rejects_duplicate_step_ids_and_yaml_keys(tmp_path: Path) -> None:
    duplicate_id = VALID.replace("steps:\n", "steps:\n  - id: q1\n    kind: query\n    sql: SELECT 2\n    comparison: {mode: exact}\n    expected: {rows: [[2]]}\n")
    with pytest.raises(ValueError, match="QUERY_STEP_ID_DUPLICATED"):
        load_query_case(write_case(tmp_path, duplicate_id))
    duplicate_key = VALID.replace("  id: QUERY.BASIC.0001", "  id: QUERY.BASIC.0001\n  id: QUERY.BASIC.0002")
    with pytest.raises(ValueError, match="DUPLICATE_KEY"):
        load_query_case(write_case(tmp_path, duplicate_key))


def test_directory_validation_counts_cases_and_duplicate_case_ids(tmp_path: Path) -> None:
    write_case(tmp_path, VALID, "a.yaml")
    write_case(tmp_path, VALID, "nested/b.yaml")
    result = validate_query_directory(tmp_path)
    assert result["status"] == "FAIL"
    assert result["cases"] == 1
    assert result["invalid"] == 1
    assert "QUERY_CASE_ID_DUPLICATED" in result["errors"][0]
