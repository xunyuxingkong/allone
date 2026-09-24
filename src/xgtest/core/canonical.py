"""Version 1 canonical encoders used by Golden Vectors."""

from __future__ import annotations

import hashlib
import math
import re
import struct
from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any, Iterable, Mapping


def _decimal_text(value: Decimal) -> str:
    if not value.is_finite():
        raise ValueError("XGMJ1 rejects non-finite decimal values")
    if value.is_zero():
        return "0"
    text = format(value.normalize(), "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def _string(value: str) -> str:
    encoded: list[str] = ['"']
    for char in value:
        codepoint = ord(char)
        if 0xD800 <= codepoint <= 0xDFFF:
            raise ValueError("XGMJ1 rejects isolated surrogate code points")
        if char == '"':
            encoded.append('\\"')
        elif char == "\\":
            encoded.append("\\\\")
        elif codepoint <= 0x1F:
            encoded.append(f"\\u{codepoint:04x}")
        else:
            encoded.append(char)
    encoded.append('"')
    return "".join(encoded)


def xgmj1_text(value: Any) -> str:
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, str):
        return _string(value)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, Decimal):
        return _decimal_text(value)
    if isinstance(value, float):
        raise TypeError("XGMJ1 requires Decimal instead of float")
    if isinstance(value, Mapping):
        if not all(isinstance(key, str) for key in value):
            raise TypeError("XGMJ1 object keys must be strings")
        return "{" + ",".join(
            f"{_string(key)}:{xgmj1_text(value[key])}" for key in sorted(value)
        ) + "}"
    if isinstance(value, (tuple, list)):
        return "[" + ",".join(xgmj1_text(item) for item in value) + "]"
    raise TypeError(f"XGMJ1 cannot encode {type(value).__name__}")


def xgmj1_bytes(value: Any) -> bytes:
    return xgmj1_text(value).encode("utf-8")


def xgmj1_sha256(value: Any) -> str:
    return hashlib.sha256(xgmj1_bytes(value)).hexdigest()


@dataclass(frozen=True)
class CanonicalCell:
    logical_type: str
    value: Any


_TYPE_TAGS = {
    "null": 0,
    "bool": 1,
    "int": 2,
    "decimal": 3,
    "float": 4,
    "string": 5,
    "date": 6,
    "time": 7,
    "timestamp": 8,
    "timestamp_tz": 9,
    "bytes": 10,
}

_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TIME = re.compile(r"^\d{2}:\d{2}:\d{2}(?:\.\d+)?$")
_TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?$")
_TIMESTAMP_TZ = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$")


def _cell_payload(cell: CanonicalCell) -> bytes:
    logical_type, value = cell.logical_type, cell.value
    if logical_type == "null":
        if value is not None:
            raise ValueError("null cell must have None value")
        return b""
    if logical_type == "bool":
        if type(value) is not bool:
            raise TypeError("bool cell requires bool")
        return b"\x01" if value else b"\x00"
    if logical_type == "int":
        if type(value) is not int:
            raise TypeError("int cell requires int")
        return str(value).encode("ascii")
    if logical_type == "decimal":
        if not isinstance(value, Decimal):
            raise TypeError("decimal cell requires Decimal")
        return _decimal_text(value).encode("ascii")
    if logical_type == "float":
        if type(value) is not float:
            raise TypeError("float cell requires float")
        if math.isnan(value):
            return bytes.fromhex("7ff8000000000000")
        return struct.pack(">d", 0.0 if value == 0.0 else value)
    if logical_type == "string":
        if not isinstance(value, str):
            raise TypeError("string cell requires str")
        return value.encode("utf-8")
    if logical_type in {"date", "time", "timestamp", "timestamp_tz"}:
        if not isinstance(value, str):
            raise TypeError(f"{logical_type} cell requires str")
        expression = {"date": _DATE, "time": _TIME, "timestamp": _TIMESTAMP, "timestamp_tz": _TIMESTAMP_TZ}[logical_type]
        if not expression.fullmatch(value):
            raise ValueError(f"{logical_type} cell is not in canonical format")
        try:
            if logical_type == "date":
                date.fromisoformat(value)
            elif logical_type == "time":
                time.fromisoformat(value)
            elif logical_type == "timestamp":
                parsed = datetime.fromisoformat(value)
                if parsed.tzinfo is not None:
                    raise ValueError("timestamp must be timezone-naive")
            else:
                datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as error:
            raise ValueError(f"{logical_type} cell has invalid temporal value") from error
        return value.encode("ascii")
    if logical_type == "bytes":
        if not isinstance(value, bytes):
            raise TypeError("bytes cell requires bytes")
        return value
    raise ValueError(f"unknown logical type {logical_type}")


def xgc1_encode(header: Mapping[str, Any], rows: Iterable[Iterable[CanonicalCell]]) -> bytes:
    return b"".join(xgc1_iter_encode(header, rows))


def xgc1_iter_encode(header: Mapping[str, Any], rows: Iterable[Iterable[CanonicalCell]]) -> Iterable[bytes]:
    """Yield the exact XGC1 byte stream incrementally for bounded-memory hashing."""
    required = {"mode", "column_count", "logical_types", "comparison_profile"}
    if set(header) != required:
        raise ValueError("XGC1 header must contain exactly the required fields")
    column_count = header["column_count"]
    logical_types = header["logical_types"]
    if type(column_count) is not int or column_count < 0:
        raise ValueError("XGC1 column_count must be a non-negative int")
    if not isinstance(logical_types, list) or len(logical_types) != column_count:
        raise ValueError("XGC1 logical_types must match column_count")
    header_bytes = xgmj1_bytes(header)
    yield b"XGC1" + struct.pack(">Q", len(header_bytes)) + header_bytes
    for row in rows:
        cells = tuple(row)
        if len(cells) != column_count:
            raise ValueError("XGC1 row length must match column_count")
        frame = bytearray(struct.pack(">Q", len(cells)))
        for index, cell in enumerate(cells):
            # ``null`` is a value tag and may occur in a nullable column whose
            # declared logical type is known from another row.  All non-null
            # values still have to match the column declaration exactly.
            if cell.logical_type != logical_types[index] and cell.logical_type != "null":
                raise ValueError("XGC1 cell logical type must match header")
            payload = _cell_payload(cell)
            frame.extend(bytes([_TYPE_TAGS[cell.logical_type]]))
            frame.extend(struct.pack(">Q", len(payload)))
            frame.extend(payload)
        yield struct.pack(">Q", len(frame)) + frame
