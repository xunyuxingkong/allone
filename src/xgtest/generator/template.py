"""Versioned deterministic JOIN SQL template."""

from __future__ import annotations

from typing import Any

from xgtest.core.canonical import xgmj1_sha256
from xgtest.design.constraint import validate_assignment
from xgtest.design.model import TestModel


TEMPLATE_ID = "query.join.default"
TEMPLATE_VERSION = "4"

# Ordered values let every supported datatype express matching and unmatched rows.
_MATCH = {"none": (2, 2), "equality": (2, 2), "inequality": (2, 3), "less_equal": (2, 3)}
_UNMATCHED = {"equality": (2, 3), "inequality": (2, 2), "less_equal": (3, 2)}
_EXTRA_RIGHT = {"equality": 1, "inequality": 2, "less_equal": 1}
_EXTRA_LEFT = {"equality": 1, "inequality": 3, "less_equal": 4}


def _value(datatype: str, rank: int) -> Any:
    if datatype == "int":
        return rank
    if datatype == "varchar":
        return "abcdef"[rank - 1]
    if datatype == "date":
        return f"2020-01-{rank:02d}"
    raise ValueError(f"JOIN_TEMPLATE_DATATYPE_UNSUPPORTED: {datatype}")


def _literal(datatype: str, rank: int) -> str:
    value = _value(datatype, rank)
    if datatype == "int":
        return f"CAST({value} AS INTEGER)"
    if datatype == "date":
        return f"DATE '{value}'"
    return f"'{value}'"


def _relation(datatype: str, ranks: list[int], *, right: bool) -> str:
    selects = [
        f"SELECT {_literal(datatype, rank)} AS k" + (", 'right-row' AS label" if right else "")
        for rank in ranks
    ]
    return "(" + " UNION ALL ".join(selects) + ")"


def _matches(predicate: str, left: int, right: int) -> bool:
    if predicate == "none":
        return True
    if predicate == "equality":
        return left == right
    if predicate == "inequality":
        return left != right
    return left <= right


def _source_rows(join_type: str, predicate: str, null_side: str) -> tuple[list[int], list[int]]:
    if predicate == "less_equal":
        # Include a < b, a = b and a > b in the fixture. For outer-join
        # assignments, keep the requested NULL-extension side observable.
        if null_side == "both":
            return [2, 3, 5], [3, 4, 1]
        if null_side == "left":
            return [2, 3, 4], [3, 4, 1]
        if null_side == "right":
            return [1, 2, 5], [2, 4]
        return [1, 2, 4], [2, 4, 5]
    if null_side == "none":
        left, right = _MATCH[predicate]
        return [left], [right]
    if null_side == "both" or join_type in {"left", "right"}:
        left, right = _UNMATCHED[predicate]
        return [left], [right]
    left, right = _MATCH[predicate]
    if null_side == "left":
        return [left], [right, _EXTRA_RIGHT[predicate]]
    return [left, _EXTRA_LEFT[predicate]], [right]


def _expected_rows(datatype: str, join_type: str, predicate: str, left: list[int], right: list[int]) -> list[list[Any]]:
    matched = [(i, j) for i, a in enumerate(left) for j, b in enumerate(right) if _matches(predicate, a, b)]
    rows: list[list[Any]] = [[_value(datatype, left[i]), _value(datatype, right[j]), "right-row"] for i, j in matched]
    if join_type in {"left", "full"}:
        rows.extend([_value(datatype, a), None, None] for i, a in enumerate(left) if not any(pair[0] == i for pair in matched))
    if join_type in {"right", "full"}:
        rows.extend([None, _value(datatype, b), "right-row"] for j, b in enumerate(right) if not any(pair[1] == j for pair in matched))
    return rows


def render_join(model: TestModel, assignment: dict[str, str]) -> dict[str, Any]:
    validate_assignment(model, assignment)
    join_type = assignment["join_type"]
    predicate = assignment["predicate"]
    datatype = assignment["datatype"]
    null_side = assignment["null_side"]
    interaction = assignment["interaction"]
    left, right = _source_rows(join_type, predicate, null_side)
    left_relation = _relation(datatype, left, right=False)
    right_relation = _relation(datatype, right, right=True)
    on_clause = {
        "equality": "a.k = b.k",
        "inequality": "a.k <> b.k",
        "less_equal": "a.k <= b.k",
    }.get(predicate)
    join_sql = {"inner": "JOIN", "left": "LEFT JOIN", "right": "RIGHT JOIN", "full": "FULL OUTER JOIN", "cross": "CROSS JOIN"}[join_type]
    base_sql = f"SELECT a.k AS left_key, b.k AS right_key, b.label FROM {left_relation} a {join_sql} {right_relation} b"
    if on_clause is not None:
        base_sql += f" ON {on_clause}"

    if interaction == "none":
        sql = base_sql
    elif interaction == "group_by":
        sql = (
            "SELECT q.left_key, q.right_key, q.label FROM "
            f"({base_sql} UNION ALL {base_sql}) q "
            "GROUP BY q.left_key, q.right_key, q.label"
        )
    else:
        noise = f"SELECT {_literal(datatype, 2)} AS left_key, {_literal(datatype, 2)} AS right_key, 'drop-row' AS label"
        source = f"({base_sql} UNION ALL {noise}) q"
        if interaction == "where":
            condition = "q.label = 'right-row' OR q.label IS NULL"
        else:
            condition = (
                "EXISTS (SELECT 1 FROM (SELECT 1 AS marker) probe "
                "WHERE probe.marker = 1 AND (q.label = 'right-row' OR q.label IS NULL))"
            )
        sql = f"SELECT q.left_key, q.right_key, q.label FROM {source} WHERE {condition}"

    rows = _expected_rows(datatype, join_type, predicate, left, right)
    return {"sql": sql, "expected": {"rows": rows}, "comparison": {"mode": "rowsort"}}


def semantic_hash(case_payload: dict[str, Any]) -> str:
    step_projection = [
        {"sql": step["sql"], "expected": step["expected"], "comparison": step["comparison"]}
        for step in case_payload["steps"]
    ]
    return xgmj1_sha256(step_projection)
