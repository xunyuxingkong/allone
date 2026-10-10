"""Versioned deterministic WHERE/Filter SQL template.

Every assignment renders a plain ``SELECT ... FROM (<union of rows>) d WHERE ...``
with ``rowsort`` comparison. Expected rows are produced by the same pure
evaluator used to build the WHERE fragment, so SQL and expectation cannot drift.

The fixture is deliberately wider than one row: for each predicate it carries at
least one row the predicate keeps and one it drops, so a mutation that widens or
narrows the predicate always changes the observable row set. ``null_handling``
controls whether the NULL row is present, which makes three-valued logic visible.
"""

from __future__ import annotations

from typing import Any

from xgtest.design.constraint import validate_assignment
from xgtest.design.model import TestModel


TEMPLATE_ID = "query.filter.default"
TEMPLATE_VERSION = "1"

# Ranks are the fixture's key values; rank 2 is the comparison boundary. Rank 4
# exists only so arithmetic/conversion predicates have a row beyond the bound.
_RANKS = (1, 2, 3, 4)
_NULL_LABEL = "rn"


def _value(datatype: str, rank: int) -> Any:
    if datatype == "int":
        return rank
    if datatype == "varchar":
        return "abcd"[rank - 1]
    if datatype == "date":
        return f"2020-01-{rank:02d}"
    raise ValueError(f"FILTER_TEMPLATE_DATATYPE_UNSUPPORTED: {datatype}")


def _literal(datatype: str, rank: int) -> str:
    value = _value(datatype, rank)
    if datatype == "int":
        return f"CAST({value} AS INTEGER)"
    if datatype == "date":
        return f"DATE '{value}'"
    return f"'{value}'"


def _relation(datatype: str, ranks: tuple[int, ...], *, with_null: bool) -> str:
    selects = [f"SELECT {_literal(datatype, rank)} AS k, '{_label(rank)}' AS label" for rank in ranks]
    if with_null:
        selects.append(f"SELECT NULL AS k, '{_NULL_LABEL}' AS label")
    return "(" + " UNION ALL ".join(selects) + ")"


def _fixture(null_handling: str) -> tuple[tuple[int, ...], bool]:
    return _RANKS, null_handling != "none"


def _label(rank: int) -> str:
    # Rank 4 is the deliberate LIKE non-match; the rest match 'r%'.
    return f"x{rank}" if rank == 4 else f"r{rank}"


def _matches(predicate: str, operator: str, datatype: str, rank: int | None) -> bool:
    """Evaluate the predicate for one fixture row (rank None = the NULL row).

    Mirrors SQL three-valued logic: a comparison against NULL is UNKNOWN, and an
    UNKNOWN row is not returned; only IS NULL keeps it.
    """
    if rank is None:
        return predicate == "is_null"
    value = _value(datatype, rank)
    one, two, three = _value(datatype, 1), _value(datatype, 2), _value(datatype, 3)
    if predicate == "boolean_combination":
        # A non-trivial base so AND/OR/NOT each keep and drop rows.
        return value <= two
    if predicate == "comparison":
        return {
            "equals": value == two,
            "not_equals": value != two,
            "less_than": value < two,
            "less_equal": value <= two,
            "greater_than": value > two,
            "greater_equal": value >= two,
        }[operator]
    if predicate == "between":
        return one <= value <= two
    if predicate == "in_list":
        return value in {one, three}
    if predicate == "like":
        return _label(rank).startswith("r")
    if predicate == "is_null":
        return False
    if predicate == "arithmetic":
        return value + _value(datatype, 1) >= _value(datatype, 3)
    if predicate == "conversion":
        return str(value) == str(two)
    raise ValueError(f"FILTER_TEMPLATE_PREDICATE_UNSUPPORTED: {predicate}")


def _fragment(datatype: str, predicate: str, operator: str) -> str:
    """The base WHERE fragment for (predicate, operator); a fixed table, not string building."""
    one, two, three = _literal(datatype, 1), _literal(datatype, 2), _literal(datatype, 3)
    if predicate == "comparison":
        return {
            "equals": f"d.k = {two}",
            "not_equals": f"d.k <> {two}",
            "less_than": f"d.k < {two}",
            "less_equal": f"d.k <= {two}",
            "greater_than": f"d.k > {two}",
            "greater_equal": f"d.k >= {two}",
        }[operator]
    if predicate == "between":
        return f"d.k BETWEEN {one} AND {two}"
    if predicate == "in_list":
        return f"d.k IN ({one}, {three})"
    if predicate == "like":
        return "d.label LIKE 'r%'"
    if predicate == "is_null":
        return "d.k IS NULL"
    if predicate == "arithmetic":
        return f"(d.k + {one}) >= {three}"
    if predicate == "conversion":
        return f"CAST(d.k AS VARCHAR) = '{_value(datatype, 2)}'"
    if predicate == "boolean_combination":
        # A non-trivial base predicate; `interaction` (constrained to non-none)
        # then shapes the observable row set through AND/OR/NOT.
        return f"d.k <= {two}"
    raise ValueError(f"FILTER_TEMPLATE_PREDICATE_UNSUPPORTED: {predicate}")


def _combined(fragment: str, interaction: str) -> str:
    if interaction == "none":
        return fragment
    if interaction == "and":
        return f"({fragment}) AND d.label <> 'r3'"
    if interaction == "or":
        return f"({fragment}) OR d.k IS NULL"
    if interaction == "not":
        return f"NOT ({fragment})"
    raise ValueError(f"FILTER_TEMPLATE_INTERACTION_UNSUPPORTED: {interaction}")


def _kept(predicate: str, operator: str, datatype: str, interaction: str, rank: int | None) -> bool:
    """Evaluate the combined WHERE clause over one fixture row."""
    base = _matches(predicate, operator, datatype, rank)
    if interaction == "none":
        return base
    if interaction == "and":
        return base and rank != 3
    if interaction == "or":
        return base or rank is None
    if interaction == "not":
        return not base
    raise ValueError(f"FILTER_TEMPLATE_INTERACTION_UNSUPPORTED: {interaction}")


def render_filter(model: TestModel, assignment: dict[str, str]) -> dict[str, Any]:
    validate_assignment(model, assignment)
    predicate = assignment["predicate"]
    operator = assignment["operator"]
    null_handling = assignment["null_handling"]
    datatype = assignment["datatype"]
    interaction = assignment["interaction"]

    ranks, with_null = _fixture(null_handling)
    relation = _relation(datatype, ranks, with_null=with_null)
    where = _combined(_fragment(datatype, predicate, operator), interaction)
    sql = f"SELECT d.k AS k, d.label AS label FROM {relation} d WHERE {where}"

    rows: list[list[Any]] = []
    for rank in ranks:
        if _kept(predicate, operator, datatype, interaction, rank):
            rows.append([_value(datatype, rank), _label(rank)])
    if with_null and _kept(predicate, operator, datatype, interaction, None):
        rows.append([None, _NULL_LABEL])
    return {"sql": sql, "expected": {"rows": rows}, "comparison": {"mode": "rowsort"}}
