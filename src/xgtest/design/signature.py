"""Stable model/assignment coverage signatures."""

from xgtest.core.canonical import xgmj1_sha256

from .constraint import validate_assignment
from .model import TestModel


def coverage_signature(model: TestModel, assignment: dict[str, str]) -> str:
    validate_assignment(model, assignment)
    identity = {
        "format": "XGMJ1",
        "model_id": model.model_id,
        "model_version": model.model_version,
        "assignment": dict(assignment),
    }
    return xgmj1_sha256(identity)


def model_signature(model: TestModel) -> str:
    return xgmj1_sha256(model.model_dump(mode="json", by_alias=True))


def candidate_signature(model: TestModel, assignment: dict[str, str], template_id: str, template_version: str) -> str:
    validate_assignment(model, assignment)
    return xgmj1_sha256({
        "format": "XGMJ1",
        "model_id": model.model_id,
        "model_version": model.model_version,
        "template_id": template_id,
        "template_version": template_version,
        "assignment": dict(assignment),
    })

