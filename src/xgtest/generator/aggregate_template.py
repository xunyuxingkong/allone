"""Versioned deterministic Aggregate SQL template.

Renders ``SELECT <agg> FROM (<derived rows>) q [GROUP BY g] [HAVING ...]`` with
``rowsort`` comparison. Expected rows come from a pure evaluator over the fixture
rows, so SQL and expectation cannot drift.

The fixture is built from ``cardinality`` and ``null_handling`` so empty sets,
single values, duplicates, multiple groups and NULL/ALL-NULL inputs are all
observable. An aggregate over an empty or all-NULL input yields SQL NULL.
"""

from __future__ import annotations

from typing import Any

from xgtest.design.constraint import validate_assignment
from xgtest.design.model import TestModel


TEMPLATE_ID = "query.aggregate.default"
TEMPLATE_VERSION = "1"

# Group values per datatype, one per group key index.
_BASE = {"int": (10, 20, 30), "varchar": ("aa", "bb", "cc"), "date": ("2020-01-01", "2020-01-02", "2020-01-03")}
# Function -> the datatypes it accepts (matches the model constraints).
_NUMERIC_ONLY = {"sum", "avg"}


def _value(datatype: str, index: int) -> Any:
    try:
        return _BASE[datatype][index]
    except (KeyError, IndexError) as error:
        raise ValueError(f"AGGREGATE_TEMPLATE_DATATYPE_UNSUPPORTED: {datatype}") from error


def _literal(datatype: str, index: int) -> str:
    value = _value(datatype, index)
    if datatype == "int":
        return f"CAST({value} AS INTEGER)"
    if datatype == "date":
        return f"DATE '{value}'"
    return f"'{value}'"


def _spec(cardinality: str, null_handling: str) -> list[tuple[int | None, int | None]]:
    """Fixture rows as (group_key_index, value_index); None value = SQL NULL.

    ``empty`` yields no rows at all. ``grouping`` is applied later, so this only
    shapes the input relation.
    """
    if cardinality == "empty":
        return []
    groups = {"single": (0,), "duplicates": (0, 0, 1), "multiple_groups": (0, 1, 2)}[cardinality]
    rows: list[tuple[int | None, int | None]] = [(index, index) for index in groups]
    if null_handling == "with_nulls":
        rows.append((groups[0], None))
    elif null_handling == "all_null":
        rows = [(index, None) for index in groups]
    return rows


def _aggregate(function: str, values: list[Any]) -> Any:
    """Aggregate over the row values (which may contain None for NULL)."""
    if function == "count_star":
        return len(values)
    non_null = [value for value in values if value is not None]
    if function == "count":
        return len(non_null)
    if not non_null:
        return None
    if function == "sum":
        return sum(non_null)
    if function == "avg":
        total = sum(non_null)
        return total // len(non_null) if total % len(non_null) == 0 else round(total / len(non_null), 4)
    if function == "min":
        return min(non_null)
    if function == "max":
        return max(non_null)
    raise ValueError(f"AGGREGATE_TEMPLATE_FUNCTION_UNSUPPORTED: {function}")


def _relation(datatype: str, rows: list[tuple[int | None, int | None]], grouped: bool) -> str:
    selects = []
    for group, index in rows:
        key = f"CAST({group} AS INTEGER)"
        value = "NULL" if index is None else _literal(datatype, index)
        selects.append(f"SELECT {key} AS g, {value} AS v" + ("" if grouped else " FROM (SELECT 1) one"))
    if not selects:
        # Empty input: a genuine zero-row relation (the WHERE FALSE guard drops the seed).
        return "(SELECT CAST(0 AS INTEGER) AS g, CAST(0 AS INTEGER) AS v FROM (SELECT 1) one WHERE 1 = 0)"
    return "(" + " UNION ALL ".join(selects) + ")"


def is_mutation_observable(assignment: dict[str, str]) -> bool:
    """Whether this assignment's result set is non-empty and thus mutation-killable.

    An empty input with grouping returns no groups (no rows to mutate); all other
    shapes return at least one row.
    """
    return not (assignment.get("cardinality") == "empty" and assignment.get("grouping") != "none")


def render_aggregate(model: TestModel, assignment: dict[str, str]) -> dict[str, Any]:
    validate_assignment(model, assignment)
    function = assignment["function"]
    grouping = assignment["grouping"]
    null_handling = assignment["null_handling"]
    cardinality = assignment["cardinality"]
    datatype = assignment["datatype"]
    if function in _NUMERIC_ONLY and datatype == "varchar":
        raise ValueError(f"AGGREGATE_TEMPLATE_FUNCTION_DATATYPE: {function}/{datatype}")

    rows = _spec(cardinality, null_handling)
    grouped = grouping != "none"
    relation = _relation(datatype, rows, grouped)
    projection = "COUNT(*)" if function == "count_star" else f"{function.upper()}(q.v)"

    if not grouped:
        # Ungrouped aggregate: one row, even over an empty input (SQL returns one row).
        sql = f"SELECT {projection} AS agg FROM {relation} q"
        return {"sql": sql, "expected": {"rows": [[_aggregate(function, [index for _, index in rows])]]},
                "comparison": {"mode": "rowsort"}}

    by_group: dict[int, list[Any]] = {}
    for group, index in rows:
        by_group.setdefault(group, []).append(None if index is None else _value(datatype, index))
    sql = f"SELECT q.g AS g, {projection} AS agg FROM {relation} q GROUP BY q.g"
    expected = [[group, _aggregate(function, by_group[group])] for group in sorted(by_group)]
    if grouping == "group_by_having":
        sql += " HAVING COUNT(*) > 1"
        expected = [row for group, row in ((group, [group, _aggregate(function, by_group[group])]) for group in sorted(by_group))
                    if len(by_group[group]) > 1]
    return {"sql": sql, "expected": {"rows": expected}, "comparison": {"mode": "rowsort"}}
