"""XGR1 reversible JSON representation of database observations.

Ordinary JSON scalars retain their values. Typed cells carry an explicit tag;
legacy ISO strings remain readable without pretending to recover Python types.
"""

import base64
import math
from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation
from typing import Any


def encode_cell(value: Any) -> Any:
    if value is None or type(value) in {str, int, bool}:
        return value
    if type(value) is float:
        if math.isfinite(value):
            return value
        return {"$xgr1": "float", "value": "nan" if math.isnan(value) else "inf" if value > 0 else "-inf"}
    if isinstance(value, (bytes, bytearray, memoryview)):
        return {"$xgr1": "bytes", "value": base64.b64encode(bytes(value)).decode("ascii")}
    if isinstance(value, Decimal):
        return {"$xgr1": "decimal", "value": str(value)}
    for kind, cell_type in (("datetime", datetime), ("date", date), ("time", time)):
        if isinstance(value, cell_type):
            return {"$xgr1": kind, "value": value.isoformat()}
    raise ValueError(f"ROW_CODEC_TYPE_UNSUPPORTED:{type(value).__name__}")


def decode_cell(value: Any) -> Any:
    if value is None or type(value) in {str, int, bool}:
        return value
    if type(value) is float and math.isfinite(value):
        return value
    if not isinstance(value, dict) or set(value) != {"$xgr1", "value"} or not isinstance(value["value"], str):
        raise ValueError("ROW_CODEC_CELL_INVALID")
    kind, raw = value["$xgr1"], value["value"]
    if kind == "bytes":
        result = base64.b64decode(raw, validate=True)
        if base64.b64encode(result).decode("ascii") != raw:
            raise ValueError("ROW_CODEC_BASE64_NONCANONICAL")
        return result
    if kind == "decimal":
        try:
            return Decimal(raw)
        except InvalidOperation as error:
            raise ValueError("ROW_CODEC_DECIMAL_INVALID") from error
    if kind == "datetime":
        return datetime.fromisoformat(raw)
    if kind == "date":
        return date.fromisoformat(raw)
    if kind == "time":
        return time.fromisoformat(raw)
    if kind == "float" and raw in {"nan", "inf", "-inf"}:
        return float(raw)
    raise ValueError("ROW_CODEC_TAG_INVALID")


def encode_rows(rows: Any) -> list[list[Any]]:
    return [[encode_cell(value) for value in row] for row in rows]


def decode_rows(rows: Any) -> tuple[tuple[Any, ...], ...]:
    if not isinstance(rows, (list, tuple)) or any(not isinstance(row, (list, tuple)) for row in rows):
        raise ValueError("ROW_CODEC_ROWS_INVALID")
    return tuple(tuple(decode_cell(value) for value in row) for row in rows)
