"""Coverage-gap driven deterministic JOIN candidate generation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from xgtest.core.canonical import xgmj1_sha256
from xgtest.design.coverage import assignment_requirements, coverage_gap, valid_assignments
from xgtest.design.model import TestModel
from xgtest.design.signature import candidate_signature, coverage_signature, model_signature
from xgtest.generator.template import TEMPLATE_ID, TEMPLATE_VERSION, render_join, semantic_hash
from xgtest.query.loader import load_query_case


GENERATOR_ID = "query_template_generator"
GENERATOR_VERSION = "4"


def case_payload(model: TestModel, assignment: dict[str, str], strategy: str) -> dict[str, Any]:
    rendered = render_join(model, assignment)
    signature = coverage_signature(model, assignment)
    input_hash = xgmj1_sha256({
        "model_hash": model_signature(model),
        "template_id": TEMPLATE_ID,
        "template_version": TEMPLATE_VERSION,
        "strategy": strategy,
        "assignment": assignment,
    })
    return {
        "metadata": {
            "id": f"QUERY.JOIN.{candidate_signature(model, assignment, TEMPLATE_ID, TEMPLATE_VERSION)[:8].upper()}",
            "title": f"Generated JOIN {signature[:8]}",
            "module": "query",
            "feature": model.feature,
            "subfeature": model.subfeature,
            "level": "P1",
            "status": "generated",
            "timeout": "30s",
            "isolation": "session",
            "tags": ["join", "generated"],
        },
        "coverage": [{
            "claim_id": f"join_{signature[:12]}",
            "model_id": model.model_id,
            "model_version": model.model_version,
            "assignment": dict(assignment),
            "assertion_refs": ["q1"],
        }],
        "generation": {
            "generator": GENERATOR_ID,
            "generator_version": GENERATOR_VERSION,
            "model_id": model.model_id,
            "model_version": model.model_version,
            "template_id": TEMPLATE_ID,
            "template_version": TEMPLATE_VERSION,
            "strategy": strategy,
            "seed": None,
            "input_hash": input_hash,
        },
        "oracle": {"kind": "known_result", "reference": f"join-template-v{TEMPLATE_VERSION}"},
        "steps": [{
            "id": "q1",
            "kind": "query",
            **rendered,
        }],
    }


def _select_gap_assignments(model: TestModel, strategy: str, existing_cases: tuple[Any, ...], limit: int | None) -> tuple[dict[str, str], ...]:
    claims = [claim for case in existing_cases if case.metadata.status.value == "active" for claim in case.coverage]
    gap = coverage_gap(model, claims, strategy)
    uncovered = {req.requirement_id for req in gap["missing_requirements"]}
    candidates = []
    for assignment in valid_assignments(model):
        claims_for_assignment = assignment_requirements(model, assignment, strategy)
        gain = claims_for_assignment & uncovered
        if gain:
            candidates.append((assignment, gain))
    chosen: list[dict[str, str]] = []
    while uncovered and candidates and (limit is None or len(chosen) < limit):
        best = min(
            candidates,
            key=lambda pair: (-len(pair[1] & uncovered), tuple(sorted(pair[0].items()))),
        )
        if not best[1] & uncovered:
            break
        chosen.append(best[0])
        uncovered -= best[1]
        candidates = [pair for pair in candidates if pair[0] != best[0]]
    return tuple(chosen)


def generate_candidates(
    model: TestModel,
    strategy: str,
    existing_cases: tuple[Any, ...],
    output_dir: Path,
    *,
    limit: int | None = None,
) -> tuple[Path, ...]:
    if limit is not None and limit < 1:
        raise ValueError("GENERATOR_LIMIT_INVALID")
    if model.model_id != "query.join":
        raise ValueError("GENERATOR_FEATURE_UNSUPPORTED: only query.join is implemented")
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for assignment in _select_gap_assignments(model, strategy, existing_cases, limit):
        payload = case_payload(model, assignment, strategy)
        path = output_dir / f"{payload['metadata']['id']}.yaml"
        if path.exists():
            existing = load_query_case(path)
            existing_payload = yaml.safe_load(path.read_text(encoding="utf-8"))
            if (
                existing.metadata.id != payload["metadata"]["id"]
                or existing.generation is None
                or existing.generation.input_hash != payload["generation"]["input_hash"]
                or semantic_hash(existing_payload) != semantic_hash(payload)
            ):
                raise ValueError(f"CANDIDATE_ID_CONTENT_CONFLICT: {path}")
            written.append(path)
            continue
        path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True), encoding="utf-8")
        written.append(path)
    return tuple(written)


def static_validate_candidate(path: Path, model: TestModel) -> dict[str, Any]:
    case = load_query_case(path)
    current_status = case.metadata.status.value
    if current_status not in {"generated", "draft", "review"}:
        raise ValueError("CANDIDATE_STATUS_INVALID: static validation expects generated status")
    if case.generation is None or case.oracle is None:
        raise ValueError("CANDIDATE_PROVENANCE_REQUIRED")
    if case.generation.strategy not in {"all_values", "pairwise"}:
        raise ValueError("CANDIDATE_STRATEGY_NOT_IMPLEMENTED")
    if (
        case.generation.generator != GENERATOR_ID
        or case.generation.generator_version != GENERATOR_VERSION
        or case.generation.template_id != TEMPLATE_ID
        or case.generation.template_version != TEMPLATE_VERSION
    ):
        raise ValueError("CANDIDATE_PROVENANCE_MISMATCH")
    if case.oracle.kind != "known_result" or case.oracle.reference != f"join-template-v{TEMPLATE_VERSION}":
        raise ValueError("CANDIDATE_ORACLE_PROVENANCE_INVALID")
    if case.generation.model_id != model.model_id or case.generation.model_version != model.model_version:
        raise ValueError("CANDIDATE_MODEL_MISMATCH")
    if len(case.coverage) != 1:
        raise ValueError("CANDIDATE_COVERAGE_REQUIRED")
    claim = case.coverage[0]
    if claim.model_id != model.model_id or claim.model_version != model.model_version:
        raise ValueError("CANDIDATE_COVERAGE_MODEL_MISMATCH")
    from xgtest.design.constraint import validate_assignment

    validate_assignment(model, claim.assignment)
    expected_id = f"QUERY.JOIN.{candidate_signature(model, claim.assignment, TEMPLATE_ID, TEMPLATE_VERSION)[:8].upper()}"
    if case.metadata.id != expected_id:
        raise ValueError("CANDIDATE_ID_MISMATCH")
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    expected_step = {"id": "q1", "kind": "query", **render_join(model, claim.assignment)}
    if payload.get("steps") != [expected_step]:
        raise ValueError("CANDIDATE_COVERAGE_SQL_EXPECTED_MISMATCH")
    expected_input_hash = xgmj1_sha256({
        "model_hash": model_signature(model),
        "template_id": TEMPLATE_ID,
        "template_version": TEMPLATE_VERSION,
        "strategy": case.generation.strategy,
        "assignment": claim.assignment,
    })
    if case.generation.input_hash != expected_input_hash:
        raise ValueError("CANDIDATE_INPUT_HASH_MISMATCH")
    semantic = semantic_hash(payload)
    static_hash = xgmj1_sha256({"case_id": case.metadata.id, "semantic_hash": semantic, "assignment": claim.assignment})
    if current_status in {"draft", "review"}:
        if (
            case.validation_evidence is None
            or case.validation_evidence.semantic_hash != semantic
            or case.validation_evidence.static_validation_hash != static_hash
        ):
            raise ValueError("CANDIDATE_STATIC_EVIDENCE_STALE")
        return {"case_id": case.metadata.id, "status": current_status, "semantic_hash": semantic, "static_validation_hash": static_hash}
    payload["metadata"]["status"] = "draft"
    payload["validation_evidence"] = {"semantic_hash": semantic, "static_validation_hash": static_hash}
    path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return {"case_id": case.metadata.id, "status": "draft", "semantic_hash": semantic, "static_validation_hash": static_hash}
