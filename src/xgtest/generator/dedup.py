"""Duplicate classification without silently deleting purposeful cases."""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any, Iterable

from xgtest.core.canonical import xgmj1_sha256
from xgtest.design.signature import coverage_signature
from xgtest.design.model import TestModel


def normalize_sql(sql: str) -> str:
    return re.sub(r"\s+", " ", sql).strip().rstrip(";").casefold()


def classify_duplicates(cases: Iterable[Any], model: TestModel) -> tuple[dict[str, Any], ...]:
    items = tuple(cases)
    groups: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    semantic_by_id: dict[str, str] = {}
    id_conflicts: set[str] = set()
    for case in items:
        semantic = xgmj1_sha256([
            {"sql": step.sql, "expected": step.expected.model_dump(mode="json"), "comparison": step.comparison.model_dump(mode="json")}
            for step in case.steps
        ])
        groups["case_content"][semantic].append(case.metadata.id)
        if case.metadata.id in semantic_by_id and semantic_by_id[case.metadata.id] != semantic:
            id_conflicts.add(case.metadata.id)
        semantic_by_id[case.metadata.id] = semantic
        for step in case.steps:
            groups["normalized_sql"][normalize_sql(step.sql)].append(case.metadata.id)
        for claim in case.coverage:
            if claim.model_id == model.model_id and claim.model_version == model.model_version:
                try:
                    groups["coverage_signature"][coverage_signature(model, claim.assignment)].append(case.metadata.id)
                except ValueError:
                    continue
        if case.generation is not None:
            groups["template_parameters"][xgmj1_sha256({
                "template": case.generation.template_id,
                "version": case.generation.template_version,
                "assignment": case.coverage[0].assignment if case.coverage else {},
            })].append(case.metadata.id)
    conflicts = []
    duplicate_case_ids: set[str] = set()
    for kind, values in groups.items():
        for signature, case_ids in sorted(values.items()):
            unique_ids = sorted(set(case_ids))
            if len(unique_ids) > 1 or (kind == "case_content" and len(case_ids) > 1):
                classification = (
                    "EXACT_DUPLICATE" if kind == "case_content"
                    else "POSSIBLE_SQL_DUPLICATE" if kind == "normalized_sql"
                    else "COVERAGE_DUPLICATE" if kind == "coverage_signature"
                    else "PARAMETER_DUPLICATE"
                )
                conflicts.append({"classification": classification, "case_ids": unique_ids, "signature": signature})
                duplicate_case_ids.update(unique_ids)
    for case_id in sorted(id_conflicts):
        conflicts.append({"classification": "CASE_ID_CONTENT_CONFLICT", "case_ids": [case_id], "signature": case_id})
        duplicate_case_ids.add(case_id)
    for case in items:
        case_id = case.metadata.id
        if case_id not in duplicate_case_ids:
            conflicts.append({
                "classification": "UNIQUE",
                "case_ids": [case_id],
                "signature": semantic_by_id[case_id],
            })
    return tuple(conflicts)
