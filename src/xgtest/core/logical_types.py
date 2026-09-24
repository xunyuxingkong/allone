"""Single source of truth for DB-API declared type to XG logical type mapping."""

from __future__ import annotations

from typing import Any


LOGICAL_TYPE_MAPPING_VERSION = "1"


# Longer aliases must be checked first so ``timestamp with time zone`` and
# ``timestamp`` are not shadowed by the shorter ``time`` alias.
_TYPE_ALIASES: tuple[tuple[str, str], ...] = tuple(sorted(
    {
        "timestamp with time zone": "timestamp_tz",
        "timestamp with local time zone": "timestamp_tz",
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
        "double precision": "float",
        "float": "float",
        "float4": "float",
        "float8": "float",
        "real": "float",
        "tinyint": "int",
        "bigint": "int",
        "int8": "int",
        "integer": "int",
        "int4": "int",
        "smallint": "int",
        "int2": "int",
        "int": "int",
        "boolean": "bool",
        "bool": "bool",
        "varbinary": "bytes",
        "binary": "bytes",
        "bytea": "bytes",
        "blob": "bytes",
        "raw": "bytes",
        "byte": "bytes",
        "bytes": "bytes",
        "varchar": "string",
        "nvarchar": "string",
        "character varying": "string",
        "character": "string",
        "nchar": "string",
        "char": "string",
        "text": "string",
        "clob": "string",
        "string": "string",
    }.items(),
    key=lambda item: len(item[0]),
    reverse=True,
))


def map_declared_logical_type(declared_type: Any) -> str | None:
    """Map a driver declaration using exact aliases and type parameters."""
    if declared_type is None:
        return None
    value = " ".join(str(declared_type).lower().replace("<class '", "").replace("'>", "").split())
    for alias, logical_type in _TYPE_ALIASES:
        if value == alias or value.startswith(f"{alias}(") or value.startswith(f"{alias} "):
            return logical_type
    return None


_QUERY_SUPPORTED_TYPES = {
    "int", "integer", "bigint", "smallint", "tinyint", "int2", "int4", "int8",
    "float", "float4", "float8", "real", "double", "double precision",
    "char", "character", "nchar", "varchar", "nvarchar", "character varying", "text", "string",
    "date", "time", "blob", "boolean", "bool",
}


def query_type_support(declared_type: Any) -> tuple[str | None, bool]:
    """Return the mapped type and whether current Xugu evidence permits query comparison."""
    if declared_type is None:
        return None, False
    value = " ".join(str(declared_type).lower().replace("<class '", "").replace("'>", "").split())
    base = value.split("(", 1)[0].strip()
    logical_type = map_declared_logical_type(value)
    return logical_type, base in _QUERY_SUPPORTED_TYPES and logical_type is not None


def classify_type_mapping(
    declared_type: str,
    normalized_driver_type: str | None,
    value_python_class: str | None,
    canonical_encoding: str,
    operation_status: str,
) -> dict[str, str]:
    """Separate source type fidelity from whether one Python value encodes in XGC1."""
    base = " ".join(declared_type.lower().split()).split("(", 1)[0]
    observed = " ".join((normalized_driver_type or "").lower().split())
    if operation_status not in {"READ", "READ_ONLY_EXPRESSION"}:
        fidelity = "UNKNOWN"
    elif base in {"numeric", "decimal", "number"} and value_python_class != "builtins.decimal.Decimal":
        fidelity = "LOSSY"
    elif base in {"datetime", "timestamp", "timestamp with time zone", "timestamp with local time zone"} and observed == "datetime":
        fidelity = "AMBIGUOUS"
    elif base in {"binary", "raw"} and observed == "varchar":
        fidelity = "LOSSY"
    elif base == "varbinary" and operation_status == "FAILED":
        fidelity = "UNKNOWN"
    elif normalized_driver_type is None:
        fidelity = "UNKNOWN"
    else:
        fidelity = "EXACT"

    allowed = base in _QUERY_SUPPORTED_TYPES
    supported = allowed and fidelity == "EXACT" and canonical_encoding == "VERIFIED"
    return {
        "mapping_fidelity": fidelity,
        "canonical_encoding": canonical_encoding,
        "support_status": "SUPPORTED" if supported else "UNSUPPORTED",
    }
