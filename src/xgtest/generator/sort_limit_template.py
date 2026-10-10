"""Versioned deterministic Sort / Limit SQL template.

Renders ``SELECT ... FROM (<rows>) q [WHERE ...] [ORDER BY ...] [LIMIT/OFFSET]``
with **exact** comparison, because a sort/limit case is only meaningful when the
row order and the limited rows are asserted. (The other features use rowsort,
which would ignore ORDER BY entirely.)

The fixture carries unsorted values with a NULL row so every dimension is
observable: direction changes the permutation, null_ordering places the NULL,
multi-column sort breaks ties by a second key, and limit/offset cut the row set.
"""

from __future__ import annotations

from typing import Any

from xgtest.design.constraint import validate_assignment
from xgtest.design.model import TestModel


TEMPLATE_ID = "query.sort_limit.default"
TEMPLATE_VERSION = "1"

# Unsorted fixture: (label, key, tiebreak). The NULL key exercises null_ordering.
_ROWS = (("r3", 3, 2), ("r1", 1, 4), ("r2", 2, 1), ("rn", None, 0))


def _rows_for(composition: str) -> list[tuple[str, int | None, int]]:
    rows = list(_ROWS)
    if composition == "with_filter":
        # A WHERE that drops the largest key, so sort+filter is observable.
        rows = [row for row in rows if row[1] is None or row[1] < 3]
    return rows


def _sorted(rows: list[tuple[str, int | None, int]], direction: str, null_ordering: str, multi: bool) -> list[tuple[str, int | None, int]]:
    """Order the rows the way the rendered ORDER BY will.

    The ORDER BY is emitted at the SQL level; this mirrors it in Python. NULLs are
    placed first or last per null_ordering regardless of direction; the key
    comparison reverses for DESC, and a second key breaks ties for multi-column.
    """
    if direction == "none":
        return rows
    sign = 1 if direction == "asc" else -1

    def sort_key(row: tuple[str, int | None, int]):
        _, key, tiebreak = row
        null_rank = 0 if null_ordering == "nulls_first" else 1
        primary = sign * (key if key is not None else 0)
        secondary = sign * tiebreak if multi else 0
        return (null_rank, primary, secondary)

    return sorted(rows, key=sort_key)


def render_sort_limit(model: TestModel, assignment: dict[str, str]) -> dict[str, Any]:
    validate_assignment(model, assignment)
    direction = assignment["order_direction"]
    null_ordering = assignment["null_ordering"]
    sort_columns = assignment["sort_columns"]
    limit_kind = assignment["limit_kind"]
    composition = assignment["composition"]

    rows = _rows_for(composition)
    relation = "(" + " UNION ALL ".join(
        f"SELECT '{label}' AS label, " + ("NULL" if key is None else f"CAST({key} AS INTEGER)") + f" AS k, CAST({tiebreak} AS INTEGER) AS t"
        for label, key, tiebreak in rows
    ) + ") q"

    sql = "SELECT q.label AS label, q.k AS k FROM " + relation
    if composition == "with_filter":
        sql += " WHERE q.k IS NULL OR q.k < 3"
    elif composition == "with_join":
        # A self-join on the key keeps the sort observable; the tie row is excluded.
        sql = ("SELECT q.label AS label, q.k AS k FROM " + relation +
               " JOIN (SELECT 1 AS probe) p ON (q.k IS NULL OR q.k >= 1)")

    ordered = _sorted(rows, direction, null_ordering, sort_columns == "multi")
    if direction != "none":
        order_terms = "q.k " + "ASC" if direction == "asc" else "q.k DESC"
        if null_ordering == "nulls_first":
            order_terms += " NULLS FIRST"
        elif null_ordering == "nulls_last":
            order_terms += " NULLS LAST"
        if sort_columns == "multi":
            order_terms += ", q.t " + ("ASC" if direction == "asc" else "DESC")
        sql += f" ORDER BY {order_terms}"

    if limit_kind == "limit_only":
        sql += " LIMIT 2"
        ordered = ordered[:2]
    elif limit_kind == "limit_offset":
        sql += " LIMIT 2 OFFSET 1"
        ordered = ordered[1:3]

    expected = [[label, key] for label, key, _ in ordered]
    return {"sql": sql, "expected": {"rows": expected}, "comparison": {"mode": "exact"}}
