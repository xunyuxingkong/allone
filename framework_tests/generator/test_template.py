from pathlib import Path

import yaml

from xgtest.design.model import load_test_model
from xgtest.generator.candidate import case_payload, generate_candidates
from xgtest.generator.template import TEMPLATE_ID, TEMPLATE_VERSION
from xgtest.core.models import QueryCaseInput
from xgtest.query.loader import load_query_case, load_query_directory


ROOT = Path(__file__).resolve().parents[2]


def test_same_assignment_renders_identical_case_payload() -> None:
    model = load_test_model(ROOT / "models" / "query" / "join.yaml")
    assignment = {"join_type": "left", "predicate": "equality", "datatype": "int", "null_side": "right", "interaction": "none"}
    first = case_payload(model, assignment, "pairwise")
    second = case_payload(model, assignment, "pairwise")
    assert first == second
    assert first["metadata"]["status"] == "generated"
    assert first["steps"][0]["expected"] == {"rows": [[2, None, None]]}


def test_template_descriptor_matches_implementation_identity() -> None:
    descriptor = yaml.safe_load((ROOT / "generators" / "query" / "templates" / "join.yaml").read_text(encoding="utf-8"))
    assert descriptor["template_id"] == TEMPLATE_ID
    assert descriptor["template_version"] == TEMPLATE_VERSION


def test_generated_case_round_trips_through_query_runner_payload(tmp_path: Path) -> None:
    model = load_test_model(ROOT / "models" / "query" / "join.yaml")
    active = load_query_directory(ROOT / "cases" / "query")
    candidate = generate_candidates(model, "pairwise", active, tmp_path, limit=1)[0]
    case = load_query_case(candidate)
    worker_payload = QueryCaseInput.model_validate_json(case.model_dump_json())
    assert worker_payload.generation == case.generation
    assert worker_payload.coverage == case.coverage
