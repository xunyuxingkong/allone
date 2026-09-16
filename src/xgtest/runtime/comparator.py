"""Deterministic SQL MVP result comparison helpers.

Rows are encoded with the same XGC1 framing used by the contract layer.  The
runner therefore cannot accidentally create a second JSON based hash format
for values returned by the database driver.
"""

from __future__ import annotations

import hashlib
import re
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any

from xgtest.adapter.xugu import extract_error
from xgtest.core.canonical import CanonicalCell, xgc1_encode


_ERROR_FIELDS = ("code", "sqlstate", "message_pattern")
_TYPE_HINTS = {
    "timestamp with time zone": "timestamp_tz",
    "timestamp_tz": "timestamp_tz",
    "timestamptz": "timestamp_tz",
    "datetime": "timestamp",
    "timestamp": "timestamp",
    "date": "date",
    "time": "time",
    "decimal": "decimal",
    "numeric": "decimal",
    "number": "decimal",
    "double": "float",
    "float": "float",
    "real": "float",
    "bigint": "int",
    "integer": "int",
    "smallint": "int",
    "int": "int",
    "bool": "bool",
    "binary": "bytes",
    "blob": "bytes",
    "raw": "bytes",
    "bytes": "bytes",
    "varchar": "string",
    "char": "string",
    "text": "string",
    "clob": "string",
    "string": "string",
}


def is_expected_error(expected: Any) -> bool:
    """Return whether *expected* explicitly declares an error expectation.

    A normal rows/count expectation must never be treated as an error
    expectation merely because a database operation raised an exception.
    ``ExpectedError`` model dumps include these keys even when values are
    ``None``; an empty mapping does not qualify.
    """

    return isinstance(expected, dict) and any(key in expected for key in _ERROR_FIELDS)


def _declared_logical_type(declared_type: str | None) -> str | None:
    if not declared_type:
        return None
    value = " ".join(declared_type.lower().replace("<class '", "").replace("'>", "").split())
    for token in sorted(_TYPE_HINTS, key=len, reverse=True):
        if value == token or value.startswith(f"{token}(") or value.startswith(f"{token} "):
            logical_type = _TYPE_HINTS[token]
            return logical_type
    return None


def _inferred_logical_type(value: Any, declared_type: str | None = None) -> str:
    hinted = _declared_logical_type(declared_type)
    if value is None:
        return hinted or "null"
    if hinted:
        return hinted
    if type(value) is bool:
        return "bool"
    if type(value) is int:
        return "int"
    if isinstance(value, Decimal):
        return "decimal"
    if type(value) is float:
        return "float"
    if isinstance(value, datetime):
        return "timestamp_tz" if value.tzinfo is not None and value.utcoffset() is not None else "timestamp"
    if isinstance(value, date):
        return "date"
    if isinstance(value, time):
        return "time"
    if isinstance(value, (bytes, bytearray, memoryview)):
        return "bytes"
    if isinstance(value, str):
        return "string"
    raise TypeError(f"unsupported SQL result value type: {type(value).__name__}")


def _cell(value: Any, logical_type: str) -> CanonicalCell:
    if value is None:
        return CanonicalCell("null", None)
    if logical_type == "null":
        raise TypeError("non-null value cannot use null logical type")
    if logical_type == "bytes" and isinstance(value, (bytearray, memoryview)):
        value = bytes(value)
    if logical_type in {"date", "time", "timestamp", "timestamp_tz"}:
        if isinstance(value, datetime):
            value = value.isoformat()
        elif isinstance(value, (date, time)):
            value = value.isoformat()
    if logical_type == "timestamp_tz" and isinstance(value, str) and value.endswith("+00:00"):
        # Keep the offset representation stable; XGC1 accepts both this form
        # and ``Z`` and does not silently change the instant.
        pass
    return CanonicalCell(logical_type, value)


def _logical_types(rows: list[tuple[Any, ...]], column_types: list[str | None] | tuple[str | None, ...] | None, column_count: int | None) -> list[str]:
    width = column_count if column_count is not None else (len(rows[0]) if rows else 0)
    if width < 0:
        raise ValueError("column_count must be non-negative")
    declared = list(column_types or ())
    if len(declared) > width:
        raise ValueError("column_types cannot exceed column_count")
    result: list[str] = []
    for index in range(width):
        hint = declared[index] if index < len(declared) else None
        logical_type = _declared_logical_type(hint)
        if logical_type is None:
            for row in rows:
                if index < len(row) and row[index] is not None:
                    logical_type = _inferred_logical_type(row[index])
                    break
        result.append(logical_type or "null")
    return result


def _xgc1_rows(rows: list[tuple[Any, ...]], *, mode: str, column_types: list[str | None] | tuple[str | None, ...] | None = None, column_count: int | None = None) -> tuple[bytes, list[bytes]]:
    logical_types = _logical_types(rows, column_types, column_count)
    width = len(logical_types)
    canonical_rows = []
    for row in rows:
        if len(row) != width:
            raise ValueError("SQL result row width does not match column_count")
        canonical_rows.append(tuple(_cell(value, logical_types[index]) for index, value in enumerate(row)))
    header = {
        "mode": mode,
        "column_count": width,
        "logical_types": logical_types,
        "comparison_profile": "sql-mvp-v1",
    }
    stream = xgc1_encode(header, canonical_rows)
    row_frames = [xgc1_encode(header, [row]) for row in canonical_rows]
    return stream, row_frames


def rows_sha256(rows: list[tuple[Any, ...]], column_types: list[str | None] | tuple[str | None, ...] | None = None, column_count: int | None = None) -> str:
    stream, _ = _xgc1_rows(rows, mode="hash", column_types=column_types, column_count=column_count)
    return hashlib.sha256(stream).hexdigest()


def compare_rows(actual: list[tuple[Any, ...]], expected: Any, mode: str = "exact", column_types: list[str | None] | tuple[str | None, ...] | None = None, column_count: int | None = None) -> bool:
    if not isinstance(expected, dict):
        return False
    if "sha256" in expected:
        try:
            return rows_sha256(actual, column_types, column_count) == expected["sha256"]
        except (TypeError, ValueError):
            return False
    expected_rows = expected.get("rows")
    if not isinstance(expected_rows, (list, tuple)):
        return False
    normalized = [tuple(row) for row in expected_rows if isinstance(row, (list, tuple))]
    if len(normalized) != len(expected_rows):
        return False
    try:
        actual_stream, actual_frames = _xgc1_rows(actual, mode=mode, column_types=column_types, column_count=column_count)
        expected_stream, expected_frames = _xgc1_rows(normalized, mode=mode, column_types=column_types, column_count=column_count or (len(actual[0]) if actual else None))
    except (TypeError, ValueError):
        return False
    if mode == "rowsort":
        return sorted(actual_frames) == sorted(expected_frames)
    return actual_stream == expected_stream


def compare_affected_rows(actual: int, expected: Any) -> bool:
    return isinstance(expected, dict) and actual == expected.get("affected_rows")


def compare_error(error: Exception, expected: Any) -> bool:
    if not is_expected_error(expected):
        return False
    details = extract_error(error)
    message, code, sqlstate = details["message"], details["code"], details["sqlstate"]
    if expected.get("code") is not None and str(expected["code"]) != code:
        return False
    if expected.get("sqlstate") is not None and str(expected["sqlstate"]) != str(sqlstate):
        return False
    pattern = expected.get("message_pattern")
    return pattern is None or (isinstance(pattern, str) and re.search(pattern, message) is not None)
