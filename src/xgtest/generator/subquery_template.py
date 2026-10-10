"""Versioned deterministic Subquery SQL template.

Renders a read-only ``SELECT`` exercising one subquery predicate form over a
fixed outer relation and an inner subquery whose result shape is chosen by
``subquery_result``. ``rowsort`` comparison; expected rows come from a pure
evaluator so SQL and expectation cannot drift.

The outer relation carries three distinct keys so every predicate form keeps a
*partial* subset — some rows in, some out — which keeps each result set non-empty
and non-full, and therefore mutation-viable.
"""

from __future__ import annotations

from typing import Any

from xgtest.design.constraint import validate_assignment
from xgtest.design.model import TestModel


TEMPLATE_ID = "query.subquery.default"
TEMPLATE_VERSION = "1"

# Outer rows (label, key-rank): key 1 matches the inner match value, keys 2 and 3
# are decoys, so a predicate that keys on "matches the subquery" is discriminating.
_OUTER = (("o1", 1), ("o2", 2), ("o3", 3))
_MATCH_RANK = 1
_DECOY_RANK = 3


def _key(datatype: str, rank: int) -> Any:
    """The comparable key for a row rank (0=non-matching probe, 1=match, 2/3 decoys)."""
    if datatype == "int":
        return rank
    if datatype == "varchar":
        return {0: "z", 1: "a", 2: "b", 3: "c", 4: "z"}[rank]
    if datatype == "date":
        return f"2020-01-{rank:02d}"
    raise ValueError(f"SUBQUERY_TEMPLATE_DATATYPE_UNSUPPORTED: {datatype}")


def _literal(datatype: str, rank: int) -> str:
    value = _key(datatype, rank)
    if datatype == "int":
        return f"CAST({value} AS INTEGER)"
    if datatype == "date":
        return f"DATE '{value}'"
    return f"'{value}'"


def _outer_relation(datatype: str) -> str:
    selects = [f"SELECT '{label}' AS label, {_literal(datatype, rank)} AS k" for label, rank in _OUTER]
    return "(" + " UNION ALL ".join(selects) + ")"


def _inner_relation(datatype: str, result: str) -> str:
    """Uncorrelated inner relation for the requested result shape."""
    if result == "matching":
        return f"(SELECT {_literal(datatype, _MATCH_RANK)} AS k)"
    if result == "non_matching":
        # A single row that no outer key equals (rank 4 is not an outer key).
        return f"(SELECT {_literal(datatype, 4)} AS k)"
    if result == "with_null":
        return f"(SELECT {_literal(datatype, _MATCH_RANK)} AS k UNION ALL SELECT NULL AS k)"
    if result == "empty":
        return f"(SELECT {_literal(datatype, _MATCH_RANK)} AS k FROM (SELECT 1) one WHERE 1 = 0)"
    raise ValueError(f"SUBQUERY_TEMPLATE_RESULT_UNSUPPORTED: {result}")


def _correlated_inner(datatype: str, result: str) -> str:
    """A correlated inner relation that references the outer alias o.k.

    It yields a row only when the outer key satisfies a fixed join condition, so
    per-row predicates discriminate: 'matching' probes the outer key directly;
    the other shapes select on a constant that no outer key equals.
    """
    target = _literal(datatype, _MATCH_RANK)
    if result == "matching":
        return f"(SELECT {target} AS k WHERE o.k = {target})"
    if result == "with_null":
        # A NULL-producing probe: EXISTS sees a row, IN/ANY see NULL (UNKNOWN).
        return f"(SELECT NULL AS k WHERE o.k = {_literal(datatype, _DECOY_RANK)})"
    # non_matching / empty: a probe that is false for every outer row.
    return f"(SELECT {_literal(datatype, 4)} AS k WHERE o.k = {_literal(datatype, 4)})"


def _matches(predicate: str, result: str, rank: int, *, correlated: bool) -> bool:
    """Evaluate one outer key (by rank) against the subquery for the given shape."""
    is_match = rank == _MATCH_RANK
    is_decoy = rank == _DECOY_RANK
    if predicate in {"exists", "not_exists"}:
        # The correlated probe yields a row only for the matching outer key (and,
        # for with_null, only for the decoy key).
        present = (result == "matching" and is_match) or (result == "with_null" and is_decoy)
        return present if predicate == "exists" else not present
    if predicate == "any":
        # `k = ANY (probe)`: true for the matching key under 'matching'; NULL under
        # with_null drops non-probe rows.
        if result == "with_null":
            return is_decoy
        return is_match
    if predicate == "all":
        # `k = ALL (probe)`: true only where the probe matches the row (uncorrelated
        # 'matching' keeps the match row; correlated keeps rows its probe agrees with).
        if result == "with_null":
            return is_decoy
        return is_match
    if predicate == "scalar":
        # `k = (scalar)`: only the matching key, and never for an empty subquery.
        if result == "empty":
            return False
        return is_match
    # IN / NOT IN compare the outer key against the returned set.
    if result == "with_null":
        # A NULL in the set makes NOT IN UNKNOWN for every row; IN keeps the match.
        return is_match if predicate == "in" else False
    if result in {"empty", "non_matching"}:
        return predicate == "not_in"
    return is_match if predicate == "in" else not is_match


def is_mutation_observable(model: TestModel, assignment: dict[str, str]) -> bool:
    """Whether this assignment's result set is partial, hence mutation-killable.

    A predicate mutation can only be detected when the result is neither empty nor
    the whole outer relation: an all-or-nothing result (e.g. IN over a disjoint
    set) looks identical under the mutated predicate. Non-observable cases remain
    valid tests; they simply do not carry a mutation.
    """
    rows = render_subquery(model, assignment)["expected"]["rows"]
    return 0 < len(rows) < len(_OUTER)


def render_subquery(model: TestModel, assignment: dict[str, str]) -> dict[str, Any]:
    validate_assignment(model, assignment)
    predicate = assignment["predicate"]
    correlated = assignment["correlation"] == "correlated"
    result = assignment["subquery_result"]
    datatype = assignment["datatype"]

    outer = _outer_relation(datatype)
    inner = _correlated_inner(datatype, result) if correlated else _inner_relation(datatype, result)

    if predicate in {"in", "not_in"}:
        op = "IN" if predicate == "in" else "NOT IN"
        sql = f"SELECT o.label AS label FROM {outer} o WHERE o.k {op} {inner}"
    elif predicate in {"exists", "not_exists"}:
        kw = "EXISTS" if predicate == "exists" else "NOT EXISTS"
        sql = f"SELECT o.label AS label FROM {outer} o WHERE {kw} {inner}"
    elif predicate == "scalar":
        sql = f"SELECT o.label AS label FROM {outer} o WHERE o.k = {inner}"
    else:
        op = "ANY" if predicate == "any" else "ALL"
        sql = f"SELECT o.label AS label FROM {outer} o WHERE o.k = {op} {inner}"

    rows = [[label] for label, rank in _OUTER if _matches(predicate, result, rank, correlated=correlated)]
    return {"sql": sql, "expected": {"rows": rows}, "comparison": {"mode": "rowsort"}}
