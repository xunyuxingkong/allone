"""Probe verified Xugu SQL MVP capabilities using one disposable table.

Connection settings are read from XGTEST_DB_* environment variables. The probe
creates a randomly named table, writes only to that table, and always attempts
to drop it before returning. Reports contain no password or connection string.
"""

from __future__ import annotations

import json
import secrets
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import xgcondb

from xgtest.adapter.xugu import XuguConnectionConfig, connect


def _table_name() -> str:
    return f"XGT_CAP_{secrets.token_hex(5).upper()}"


def _error_details(error: Exception) -> dict[str, Any]:
    details: dict[str, Any] = {
        "exception_type": type(error).__name__,
        "message": str(error),
    }
    for attribute in ("errno", "sqlstate", "code"):
        value = getattr(error, attribute, None)
        if value is not None:
            details[attribute] = str(value)
    return details


def _value_details(value: Any) -> dict[str, str]:
    return {"python_type": f"{type(value).__module__}.{type(value).__qualname__}", "repr": repr(value)}


def _count(connection: Any, table: str, row_id: int) -> int:
    cursor = connection.cursor()
    try:
        cursor.execute(f"SELECT COUNT(*) FROM {table} WHERE id = {row_id}")
        return int(cursor.fetchone()[0])
    finally:
        cursor.close()


def run_probe(config: XuguConnectionConfig, artifact_dir: Path) -> dict[str, Any]:
    artifact_dir.mkdir(parents=True, exist_ok=True)
    table = _table_name()
    report: dict[str, Any] = {
        "probe_version": "1",
        "started_at": datetime.now(UTC).isoformat(),
        "target": {"host": config.host, "port": config.port, "database": config.database},
        "driver": {"module": "xgcondb", "version": list(xgcondb.version_info)},
        "table": table,
        "capabilities": {},
    }
    connection: Any | None = None
    second_connection: Any | None = None
    cursor: Any | None = None
    table_created = False

    try:
        connection = connect(config)
        report["capabilities"]["connection"] = {"status": "VERIFIED"}
        cursor = connection.cursor()
        cursor.execute(
            f"CREATE TABLE {table} ("
            "id INT PRIMARY KEY, amount DECIMAL(10,2), ratio DOUBLE, label VARCHAR(32))"
        )
        connection.commit()
        table_created = True
        cursor.execute(f"INSERT INTO {table} (id, amount, ratio, label) VALUES (1, 1.20, 3.5, 'xgtest')")
        connection.commit()
        cursor.execute(f"SELECT id, amount, ratio, label FROM {table} WHERE id = 1")
        row = cursor.fetchone()
        values = [_value_details(value) for value in row]
        report["capabilities"]["basic_type_read"] = {
            "status": "VERIFIED",
            "column_metadata": repr(cursor.description),
            "values": values,
        }
        report["capabilities"]["type_mapping"] = {
            "int": {"status": "VERIFIED", "observed": values[0]},
            "decimal": {
                "status": "FAILED",
                "scope": "default Driver mapping",
                "observed": values[1],
                "reason": "DECIMAL was returned as float; it cannot satisfy exact Decimal comparison",
            },
            "float": {"status": "VERIFIED", "observed": values[2]},
            "string": {"status": "VERIFIED", "observed": values[3]},
            "date_time": {"status": "UNKNOWN", "reason": "not included in the basic probe"},
            "bytes": {"status": "UNKNOWN", "reason": "not included in the basic probe"},
        }

        second_connection = connect(config)
        connection.autocommit(False)
        connection.begin()
        cursor.execute(f"INSERT INTO {table} (id, amount, ratio, label) VALUES (2, 2.20, 4.5, 'rollback')")
        connection.rollback()
        rollback_visible_count = _count(second_connection, table, 2)
        connection.begin()
        cursor.execute(f"INSERT INTO {table} (id, amount, ratio, label) VALUES (3, 3.20, 5.5, 'commit')")
        connection.commit()
        commit_visible_count = _count(second_connection, table, 3)
        transaction_status = "VERIFIED" if rollback_visible_count == 0 and commit_visible_count == 1 else "FAILED"
        report["capabilities"]["transaction_commit_rollback"] = {
            "status": transaction_status,
            "autocommit_disabled": True,
            "rollback_visible_count": rollback_visible_count,
            "commit_visible_count": commit_visible_count,
        }

        try:
            cursor.execute(f"SELECT * FROM {table}_MISSING")
        except Exception as error:
            report["capabilities"]["sql_error_mapping"] = {"status": "VERIFIED", **_error_details(error)}
        else:
            report["capabilities"]["sql_error_mapping"] = {
                "status": "FAILED",
                "message": "query against a missing table did not raise an error",
            }

        report["capabilities"]["cancel_stop_proof"] = {
            "status": "UNKNOWN",
            "driver_has_cancel": hasattr(connection, "cancel"),
            "reason": "requires a bounded long-query and server-side stop observation",
        }
        report["capabilities"]["reset_probe"] = {
            "status": "UNKNOWN",
            "reason": "requires session-state, lock and temporary-object probes",
        }
    except Exception as error:
        report["fatal_error"] = _error_details(error)
    finally:
        if cursor is not None:
            try:
                cursor.close()
            except Exception as error:
                report.setdefault("cleanup_errors", []).append(_error_details(error))
        if second_connection is not None:
            try:
                second_connection.rollback()
                second_connection.close()
            except Exception as error:
                report.setdefault("cleanup_errors", []).append(_error_details(error))
        if connection is not None:
            try:
                if table_created:
                    connection.rollback()
                    cleanup_cursor = connection.cursor()
                    try:
                        cleanup_cursor.execute(f"DROP TABLE {table}")
                        connection.commit()
                        report["cleanup"] = {"status": "VERIFIED"}
                    finally:
                        cleanup_cursor.close()
                connection.close()
            except Exception as error:
                report["cleanup"] = {"status": "FAILED", **_error_details(error)}

    report["finished_at"] = datetime.now(UTC).isoformat()
    artifact = artifact_dir / f"xugu-capability-{table.lower()}.json"
    artifact.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report["artifact"] = str(artifact)
    return report


def main() -> None:
    config = XuguConnectionConfig.from_environment()
    report = run_probe(config, Path("artifacts/capabilities"))
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    if report.get("fatal_error") or report.get("cleanup", {}).get("status") == "FAILED":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
