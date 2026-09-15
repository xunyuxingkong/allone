"""Deterministic SQL MVP result comparison helpers."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from xgtest.adapter.xugu import extract_error


def _json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")


def rows_sha256(rows: list[tuple[Any, ...]]) -> str:
    return hashlib.sha256(_json_bytes([list(row) for row in rows])).hexdigest()


def compare_rows(actual: list[tuple[Any, ...]], expected: Any, mode: str = "exact") -> bool:
    if not isinstance(expected, dict):
        return False
    if "sha256" in expected:
        return rows_sha256(actual) == expected["sha256"]
    expected_rows = expected.get("rows")
    if not isinstance(expected_rows, list):
        return False
    normalized = [tuple(row) for row in expected_rows]
    return sorted(actual) == sorted(normalized) if mode == "rowsort" else actual == normalized


def compare_affected_rows(actual: int, expected: Any) -> bool:
    return isinstance(expected, dict) and actual == expected.get("affected_rows")


def compare_error(error: Exception, expected: Any) -> bool:
    if not isinstance(expected, dict):
        return False
    details = extract_error(error)
    message, code, sqlstate = details["message"], details["code"], details["sqlstate"]
    if expected.get("code") is not None and str(expected["code"]) != code:
        return False
    if expected.get("sqlstate") is not None and str(expected["sqlstate"]) != str(sqlstate):
        return False
    pattern = expected.get("message_pattern")
    return pattern is None or (isinstance(pattern, str) and re.search(pattern, message) is not None)
