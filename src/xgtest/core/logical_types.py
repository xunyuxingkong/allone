"""Single source of truth for DB-API declared type to XG logical type mapping."""

from __future__ import annotations

from typing import Any


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
