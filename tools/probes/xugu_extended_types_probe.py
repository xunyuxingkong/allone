"""Probe Xugu DATE/TIME/BINARY parameter and result mappings.

Each candidate uses a separate disposable table. Connection settings come
from XGTEST_DB_* environment variables and are never written to the report.
"""

from __future__ import annotations

import json
import secrets
from datetime import UTC, date, datetime, time
from pathlib import Path
from typing import Any

import xgcondb

from xgtest.adapter.xugu import XuguConnectionConfig, connect


def _error(error: Exception) -> dict[str, str]:
    result = {"exception_type": type(error).__name__, "message": str(error)}
    for name in ("errno", "sqlstate", "code"):
        value = getattr(error, name, None)
        if value is not None:
            result[name] = str(value)
    return result


def _value(value: Any) -> dict[str, str]:
    return {"python_type": f"{type(value).__module__}.{type(value).__qualname__}", "repr": repr(value)}


def _candidate(name: str, sql_type: str, value: Any, parameter_type: int) -> dict[str, Any]:
    table = f"XGT_EXT_{secrets.token_hex(5).upper()}"
    result: dict[str, Any] = {"sql_type": sql_type, "table": table}
    connection: Any | None = None
    created = False
    cursor: Any | None = None
    try:
        config = XuguConnectionConfig.from_environment()
        connection = connect(config)
        cursor = connection.cursor()
        cursor.execute(f"CREATE TABLE {table} (id INT PRIMARY KEY, value {sql_type})")
        created = True
        connection.autocommit(False)
        connection.begin()
        cursor.setinputtype((xgcondb.XG_C_INTEGER, parameter_type))
        cursor.execute(f"INSERT INTO {table} (id, value) VALUES (?, ?)", (1, value))
        connection.commit()
        cursor.execute(f"SELECT value FROM {table} WHERE id = 1")
        fetched = cursor.fetchone()[0]
        result.update(
            {
                "status": "VERIFIED",
                "parameter_type": parameter_type,
                "column_metadata": repr(cursor.description),
                "input": _value(value),
                "output": _value(fetched),
            }
        )
    except Exception as error:
        result.update({"status": "FAILED", **_error(error)})
    finally:
        if cursor is not None:
            try:
                cursor.close()
            except Exception as error:
                result.setdefault("cleanup_errors", []).append(_error(error))
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
                connection.close()
                result["cleanup"] = "VERIFIED"
            except Exception as error:
                result["cleanup"] = "FAILED"
                result["cleanup_error"] = _error(error)
    return result


def main() -> None:
    output_dir = Path("artifacts/capabilities")
    output_dir.mkdir(parents=True, exist_ok=True)
    candidates = (
        ("date", "DATE", date(2026, 9, 14), xgcondb.XG_C_DATE),
        ("time", "TIME", time(12, 34, 56), xgcondb.XG_C_TIME),
        ("datetime", "DATETIME", datetime(2026, 9, 14, 12, 34, 56), xgcondb.XG_C_DATETIME),
        ("binary", "BINARY", b"\x00\x01\x02", xgcondb.XG_C_BINARY),
        ("blob", "BLOB", b"\x03\x04\x05", xgcondb.XG_C_BLOB),
    )
    report: dict[str, Any] = {
        "probe_version": "1",
        "started_at": datetime.now(UTC).isoformat(),
        "driver": {"module": "xgcondb", "version": list(xgcondb.version_info)},
        "results": {name: _candidate(name, sql_type, value, parameter_type) for name, sql_type, value, parameter_type in candidates},
    }
    report["finished_at"] = datetime.now(UTC).isoformat()
    artifact = output_dir / "xugu-extended-types.json"
    artifact.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"artifact": str(artifact), "results": report["results"]}, ensure_ascii=False, sort_keys=True))
    if any(item.get("cleanup") == "FAILED" for item in report["results"].values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()

\n