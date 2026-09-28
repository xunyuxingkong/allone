from pathlib import Path

from xgtest.design.model import load_test_model
from xgtest.generator.dedup import classify_duplicates
from xgtest.query.loader import load_query_directory


ROOT = Path(__file__).resolve().parents[2]


def test_active_join_cases_have_distinct_coverage_signatures() -> None:
    model = load_test_model(ROOT / "models" / "query" / "join.yaml")
    cases = load_query_directory(ROOT / "cases" / "query")
    duplicates = classify_duplicates(cases, model)
    assert not [item for item in duplicates if item["classification"] == "COVERAGE_DUPLICATE"]
    assert all(item["classification"] == "UNIQUE" for item in duplicates)


def test_exact_duplicate_is_reported_for_human_review() -> None:
    model = load_test_model(ROOT / "models" / "query" / "join.yaml")
    cases = load_query_directory(ROOT / "cases" / "query")
    duplicates = classify_duplicates((*cases, cases[0]), model)
    assert any(item["classification"] == "EXACT_DUPLICATE" for item in duplicates)
