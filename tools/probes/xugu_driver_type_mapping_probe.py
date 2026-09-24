"""Capture real xgcondb column metadata for the G0A type-mapping review.

Each candidate uses a disposable table in the authorized database. Only
project-scoped artifacts are written; connection secrets are never emitted.
"""

from __future__ import annotations

import argparse
import json
import secrets
from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path
from typing import Any

import xgcondb

from xgtest.adapter.xugu import XuguConnectionConfig, connect, extract_error, map_driver_type
from xgtest.core.canonical import CanonicalCell, xgc1_encode


PROBE_VERSION = "1"
CANDIDATES = (
    ("int", "INT", "1"),
    ("integer", "INTEGER", "2"),
    ("bigint", "BIGINT", "9000000000"),
    ("smallint", "SMALLINT", "3"),
    ("numeric", "NUMERIC(10,2)", "1.25"),
    ("decimal", "DECIMAL(10,2)", "2.50"),
    ("number", "NUMBER(10,2)", "3.75"),
    ("float", "FLOAT", "1.5"),
    ("double", "DOUBLE", "2.5"),
    ("char", "CHAR(8)", "'abc'"),
    ("varchar", "VARCHAR(32)", "'hello'"),
    ("text", "TEXT", "'text'"),
    ("date", "DATE", "'2026-09-17'"),
    ("time", "TIME", "'12:34:56'"),
    ("datetime", "DATETIME", "'2026-09-17 12:34:56'"),
    ("timestamp", "TIMESTAMP", "'2026-09-17 12:34:56'"),
    ("timestamp_tz", "TIMESTAMP WITH TIME ZONE", "'2026-09-17 12:34:56+08:00'"),
    ("binary", "BINARY(8)", "'abc'"),
    ("varbinary", "VARBINARY(8)", "'abc'"),
    ("raw", "RAW(8)", "'abc'"),
    ("blob", "BLOB", "'abc'"),
    ("boolean", "BOOLEAN", "1"),
)


def _canonical_status(value: Any, logical_type: str | None) -> str:
    if logical_type is None:
        return "UNKNOWN"
    if value is None:
        return "UNKNOWN"
    if logical_type in {"date", "time", "timestamp", "timestamp_tz"} and isinstance(value, (date, time, datetime)):
        value = value.isoformat()
    if logical_type == "bytes" and isinstance(value, (bytearray, memoryview)):
        value = bytes(value)
    if logical_type == "decimal" and not isinstance(value, Decimal):
        return "FAILED"
    try:
        xgc1_encode(
            {"mode": "exact", "column_count": 1, "logical_types": [logical_type], "comparison_profile": "probe-v1"},
            [(CanonicalCell(logical_type, value),)],
        )
    except (TypeError, ValueError):
        return "FAILED"
    return "VERIFIED"


def _probe_one(config: XuguConnectionConfig, name: str, sql_type: str, literal: str) -> dict[str, Any]:
    table = f"XGT_MAP_{secrets.token_hex(5).upper()}"
    result: dict[str, Any] = {"name": name, "sql_declared_type": sql_type}
    connection: Any | None = None
    cursor: Any | None = None
    created = False
    try:
        connection = connect(config)
        cursor = connection.cursor()
        cursor.execute(f"CREATE TABLE {table} (id INT PRIMARY KEY, value {sql_type})")
        connection.commit()
        created = True
        cursor.execute(f"INSERT INTO {table} (id, value) VALUES (1, {literal})")
        connection.commit()
        cursor.execute(f"SELECT value FROM {table} WHERE id = 1")
        description = cursor.description
        value = cursor.fetchone()[0]
        raw_type = description[0][1]
        logical_type = map_driver_type(raw_type)
        result.update({
            "status": "READ",
            "description_type_python_class": f"{type(raw_type).__module__}.{type(raw_type).__qualname__}",
            "description_type_repr": repr(raw_type),
            "normalized_driver_type": str(raw_type),
            "framework_logical_type": logical_type,
            "value_python_class": f"{type(value).__module__}.{type(value).__qualname__}",
            "value_repr": repr(value),
            "canonical_compatibility": _canonical_status(value, logical_type),
        })
    except Exception as error:
        details = extract_error(error)
        result.update({"status": "FAILED", "error_code": details["code"], "error_type": type(error).__name__})
    finally:
        if cursor is not None:
            try:
                cursor.close()
            except Exception:
                result["cursor_close"] = "FAILED"
        if connection is not None:
            try:
                connection.rollback()
                if created:
                    cleanup = connection.cursor()
                    try:
                        cleanup.execute(f"DROP TABLE {table}")
                        connection.commit()
                    finally:
                        cleanup.close()
                result["cleanup"] = "PASS"
            except Exception:
                result["cleanup"] = "FAILED"
            finally:
                connection.close()
    return result


def _probe_read_only(config: XuguConnectionConfig, name: str, sql_type: str, literal: str) -> dict[str, Any]:
    """Capture expression metadata without DDL when a target is read-only."""
    result: dict[str, Any] = {"name": name, "sql_declared_type": sql_type}
    connection: Any | None = None
    cursor: Any | None = None
    try:
        connection = connect(config)
        cursor = connection.cursor()
        cursor.execute(f"SELECT CAST({literal} AS {sql_type}) AS value")
        raw_type = cursor.description[0][1]
        value = cursor.fetchone()[0]
        logical_type = map_driver_type(raw_type)
        result.update({
            "status": "READ_ONLY_EXPRESSION",
            "description_type_python_class": f"{type(raw_type).__module__}.{type(raw_type).__qualname__}",
            "description_type_repr": repr(raw_type),
            "normalized_driver_type": str(raw_type),
            "framework_logical_type": logical_type,
            "value_python_class": f"{type(value).__module__}.{type(value).__qualname__}",
            "value_repr": repr(value),
            "canonical_compatibility": _canonical_status(value, logical_type),
        })
    except Exception as error:
        details = extract_error(error)
        result.update({"status": "FAILED", "error_code": details["code"], "error_type": type(error).__name__})
    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None:
            connection.close()
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--read-only", action="store_true", help="probe SELECT CAST expressions without creating tables")
    args = parser.parse_args()
    config = XuguConnectionConfig.from_environment()
    suffix = "_read_only_v1.json" if args.read_only else "_v1.json"
    output = Path(f"artifacts/capabilities/xugu_driver_type_mapping{suffix}")
    output.parent.mkdir(parents=True, exist_ok=True)
    report = {
        "probe_version": PROBE_VERSION,
        "driver_module": "xgcondb",
        "driver_version": list(xgcondb.version_info),
        "probe_mode": "read_only_expression" if args.read_only else "table_round_trip",
        "results": [
            (_probe_read_only if args.read_only else _probe_one)(config, *candidate)
            for candidate in CANDIDATES
        ],
    }
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "artifact": str(output),
        "read": sum(item["status"] in {"READ", "READ_ONLY_EXPRESSION"} for item in report["results"]),
        "unknown_mapping": sum(item.get("status") in {"READ", "READ_ONLY_EXPRESSION"} and item["framework_logical_type"] is None for item in report["results"]),
        "cleanup_failed": [item["name"] for item in report["results"] if item.get("cleanup") == "FAILED"],
    }
    print(json.dumps(summary, sort_keys=True))
    if summary["cleanup_failed"] or summary["read"] == 0:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
