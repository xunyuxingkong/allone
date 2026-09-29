"""Review evidence authoring after human/Git review has happened."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from xgtest.core.canonical import xgmj1_sha256
from xgtest.query.loader import load_query_case
from xgtest.generator.template import semantic_hash
from xgtest.design.constraint import validate_assignment
from xgtest.design.model import TestModel
from xgtest.design.signature import candidate_signature
from xgtest.generator.template import TEMPLATE_ID, TEMPLATE_VERSION


def current_review_input_hash(case: Any, semantic: str) -> str:
    return xgmj1_sha256({
        "case_id": case.metadata.id,
        "semantic_hash": semantic,
        "trial_run_hash": case.validation_evidence.trial_run_hash,
        "trial_artifact_sha256": case.validation_evidence.trial_artifact_sha256,
        "coverage": [claim.model_dump(mode="json") for claim in case.coverage],
    })


def record_review(
    path: Path,
    *,
    model: TestModel,
    reviewer: str,
    review_reference: str,
    coverage_reference: str,
) -> dict[str, str]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    case = load_query_case(path)
    if case.metadata.status.value != "review":
        raise ValueError("CANDIDATE_STATUS_INVALID: review evidence expects review status")
    if case.oracle is None or case.validation_evidence is None or case.validation_evidence.trial_run_hash is None or case.validation_evidence.trial_artifact_sha256 is None:
        raise ValueError("CANDIDATE_TRIAL_EVIDENCE_REQUIRED")
    if len(case.coverage) != 1 or case.coverage[0].model_id != model.model_id or case.coverage[0].model_version != model.model_version:
        raise ValueError("CANDIDATE_COVERAGE_MODEL_MISMATCH")
    validate_assignment(model, case.coverage[0].assignment)
    if case.metadata.id != f"QUERY.JOIN.{candidate_signature(model, case.coverage[0].assignment, TEMPLATE_ID, TEMPLATE_VERSION)[:8].upper()}":
        raise ValueError("CANDIDATE_ID_MISMATCH")
    semantic = semantic_hash(payload)
    if case.validation_evidence.semantic_hash != semantic:
        raise ValueError("CANDIDATE_SEMANTIC_HASH_STALE")
    expected_static_hash = xgmj1_sha256({
        "case_id": case.metadata.id,
        "semantic_hash": semantic,
        "assignment": case.coverage[0].assignment,
    })
    if case.validation_evidence.static_validation_hash != expected_static_hash:
        raise ValueError("CANDIDATE_STATIC_EVIDENCE_STALE")
    review_input_hash = current_review_input_hash(case, semantic)
    payload["review_evidence"] = {
        "review_input_hash": review_input_hash,
        "semantic_hash": semantic,
        "trial_artifact_sha256": case.validation_evidence.trial_artifact_sha256,
        "reviewer": reviewer,
        "review_reference": review_reference,
    }
    payload["coverage_review"] = {
        "review_input_hash": review_input_hash,
        "evidence_ref": coverage_reference,
    }
    payload["validation_evidence"]["review_hash"] = review_input_hash
    path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return {"case_id": case.metadata.id, "review_input_hash": review_input_hash}
