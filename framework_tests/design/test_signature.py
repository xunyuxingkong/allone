from pathlib import Path

from xgtest.design.signature import candidate_signature, coverage_signature
from xgtest.design.model import load_test_model


ROOT = Path(__file__).resolve().parents[2]


def test_coverage_signature_is_key_order_independent_and_model_versioned() -> None:
    model = load_test_model(ROOT / "models" / "query" / "join.yaml")
    assignment = {"join_type": "inner", "predicate": "equality", "datatype": "int", "null_side": "none", "interaction": "none"}
    reordered = dict(reversed(tuple(assignment.items())))
    assert coverage_signature(model, assignment) == coverage_signature(model, reordered)
    next_version = model.model_copy(update={"model_version": "3"})
    assert coverage_signature(model, assignment) != coverage_signature(next_version, assignment)
    assert candidate_signature(model, assignment, "template-a", "1") != candidate_signature(model, assignment, "template-b", "1")
