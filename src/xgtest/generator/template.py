"""Versioned deterministic JOIN SQL template."""

from __future__ import annotations

from typing import Any

from xgtest.core.canonical import xgmj1_sha256
from xgtest.design.constraint import validate_assignment
from xgtest.design.model import TestModel


TEMPLATE_ID = "query.join.default"
TEMPLATE_VERSION = "1"


def _typed_pair(datatype: str, predicate: str, null_side: str) -> tuple[str, str, Any, Any]:
    if datatype == "int":
        left, right = (1, 1) if null_side == "none" and predicate in {"none", "equality"} else (1, 2)
        if null_side != "none":
            left, right = ((2, 1) if predicate == "range" else (1, 1) if predicate == "inequality" else (1, 2))
        return f"{left}", f"{right}", left, right
    if datatype == "varchar":
        left, right = ("a", "a") if null_side == "none" and predicate in {"none", "equality"} else ("a", "b")
        if null_side != "none":
            left, right = (("b", "a") if predicate == "range" else ("a", "a") if predicate == "inequality" else ("a", "b"))
        return f"'{left}'", f"'{right}'", left, right
    if datatype == "date":
        left, right = ("2020-01-01", "2020-01-01") if null_side == "none" and predicate in {"none", "equality"} else ("2020-01-01", "2020-01-02")
        if null_side != "none":
            left, right = (("2020-01-02", "2020-01-01") if predicate == "range" else ("2020-01-01", "2020-01-01") if predicate == "inequality" else ("2020-01-01", "2020-01-02"))
        return f"DATE '{left}'", f"DATE '{right}'", left, right
    raise ValueError(f"JOIN_TEMPLATE_DATATYPE_UNSUPPORTED: {datatype}")


def render_join(model: TestModel, assignment: dict[str, str]) -> dict[str, Any]:
    validate_assignment(model, assignment)
    join_type = assignment["join_type"]
    predicate = assignment["predicate"]
    datatype = assignment["datatype"]
    null_side = assignment["null_side"]
    interaction = assignment["interaction"]
    left_expr, right_expr, left_value, right_value = _typed_pair(datatype, predicate, null_side)
    left_literal = f"SELECT {left_expr} AS k"
    right_literal = f"SELECT {right_expr} AS k, 'right-row' AS label"
    if predicate == "none":
        on_clause = "1 = 1"
    elif predicate == "equality":
        on_clause = "a.k = b.k"
    elif predicate == "inequality":
        on_clause = "a.k <> b.k"
    else:
        on_clause = "a.k <= b.k"
    join_sql = {
        "inner": "JOIN",
        "left": "LEFT JOIN",
        "right": "RIGHT JOIN",
        "full": "FULL OUTER JOIN",
    }.get(join_type)
    if join_type == "cross":
        from_sql = f"({left_literal}) a CROSS JOIN ({right_literal}) b"
    else:
        from_sql = f"({left_literal}) a {join_sql} ({right_literal}) b ON {on_clause}"
    sql = f"SELECT a.k AS left_key, b.k AS right_key, b.label FROM {from_sql}"
    if interaction == "where":
        sql += " WHERE a.k IS NOT NULL OR b.k IS NOT NULL"
    elif interaction == "subquery":
        sql += " WHERE EXISTS (SELECT 1 FROM (SELECT 1 AS marker) q)"
    elif interaction == "group_by":
        sql += " GROUP BY a.k, b.k, b.label"

    matched = predicate == "none" or (
        left_value == right_value if predicate == "equality"
        else left_value != right_value if predicate == "inequality"
        else left_value <= right_value
    )
    if matched:
        rows = [[left_value, right_value, "right-row"]]
    elif join_type == "inner" or join_type == "cross":
        rows = []
    elif join_type == "left":
        rows = [[left_value, None, None]]
    elif join_type == "right":
        rows = [[None, right_value, "right-row"]]
    else:
        rows = [[left_value, None, None], [None, right_value, "right-row"]]
    return {"sql": sql, "expected": {"rows": rows}, "comparison": {"mode": "rowsort"}}


def semantic_hash(case_payload: dict[str, Any]) -> str:
    step_projection = [
        {"sql": step["sql"], "expected": step["expected"], "comparison": step["comparison"]}
        for step in case_payload["steps"]
    ]
    return xgmj1_sha256(step_projection)

