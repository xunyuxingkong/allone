"""Minimal Xugu connection integration for the SQL MVP probe path."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any, Iterator

from xgtest.core.logical_types import map_declared_logical_type


_ENVIRONMENT_KEYS = {
    "host": "XGTEST_DB_HOST",
    "port": "XGTEST_DB_PORT",
    "database": "XGTEST_DB_NAME",
    "user": "XGTEST_DB_USER",
    "password": "XGTEST_DB_PASSWORD",
}


@dataclass(frozen=True)
class XuguConnectionConfig:
    host: str
    port: str
    database: str
    user: str
    password: str

    @classmethod
    def from_environment(cls, environ: dict[str, str] | None = None) -> "XuguConnectionConfig":
        source = os.environ if environ is None else environ
        values: dict[str, str] = {}
        missing: list[str] = []
        for field, environment_key in _ENVIRONMENT_KEYS.items():
            value = source.get(environment_key)
            if not value:
                missing.append(environment_key)
            else:
                values[field] = value
        if missing:
            raise ValueError(f"missing database configuration: {', '.join(missing)}")
        return cls(**values)


@dataclass(frozen=True)
class XuguQueryResult:
    columns: tuple[str, ...]
    column_types: tuple[str | None, ...]
    rows: tuple[tuple[Any, ...], ...]
    logical_types: tuple[str | None, ...] = ()


def map_driver_type(declared_type: Any) -> str | None:
    """Map a DB-API type name to the framework logical type vocabulary."""
    return map_declared_logical_type(declared_type)


def extract_error(error: Exception) -> dict[str, str | None]:
    """Return stable error attributes without exposing connection details."""
    message = re.sub(
        r"(?i)\b(password|passwd|pwd|token|secret|authorization|api[_-]?key|access[_-]?token)\s*(?:=|:)\s*(?:bearer\s+)?(?:'[^']*'|\"[^\"]*\"|[^,;\s]+)",
        r"\1=<redacted>",
        str(error),
    )
    message = re.sub(r"(?i)(://[^:/\s]+:)[^@/\s]+@", r"\1<redacted>@", message)
    code = next((str(getattr(error, name)) for name in ("code", "errno") if getattr(error, name, None) is not None), None)
    if code is None:
        matched = re.search(r"\[([A-Z]\d+)\b", message)
        code = matched.group(1) if matched else None
    sqlstate = getattr(error, "sqlstate", None)
    return {"code": code, "sqlstate": str(sqlstate) if sqlstate is not None else None, "message": message}


def connect(config: XuguConnectionConfig) -> Any:
    """Open one project-scoped Xugu connection without logging secret values."""
    try:
        import xgcondb
    except ImportError as error:
        raise RuntimeError("Xugu Python driver xgcondb is unavailable in this environment") from error
    return xgcondb.Connect(
        host=config.host,
        port=config.port,
        database=config.database,
        user=config.user,
        password=config.password,
    )


def smoke_probe(config: XuguConnectionConfig) -> tuple[Any, ...]:
    """Verify Driver connection, cursor creation and a side-effect-free query."""
    connection = connect(config)
    cursor: Any | None = None
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT 1")
        row = cursor.fetchone()
        if row != (1,):
            raise RuntimeError(f"unexpected Xugu smoke result: {row!r}")
        return row
    finally:
        if cursor is not None:
            cursor.close()
        connection.close()


class XuguSession:
    """Small DB-API facade used by the single-process SQL MVP runner."""

    def __init__(self, config: XuguConnectionConfig) -> None:
        self.config = config
        self.connection: Any | None = None

    def open(self) -> "XuguSession":
        self.connection = connect(self.config)
        return self

    def execute(self, sql: str, parameters: tuple[Any, ...] = ()) -> int:
        cursor = self._connection().cursor()
        try:
            cursor.execute(sql, parameters)
            return int(getattr(cursor, "rowcount", -1))
        finally:
            cursor.close()

    def query(self, sql: str, parameters: tuple[Any, ...] = ()) -> XuguQueryResult:
        cursor = self._connection().cursor()
        try:
            cursor.execute(sql, parameters)
            description = cursor.description or ()
            column_types = tuple(str(item[1]) if len(item) > 1 and item[1] is not None else None for item in description)
            fetchmany = getattr(cursor, "fetchmany", None)
            rows: list[tuple[Any, ...]] = []
            if callable(fetchmany):
                while True:
                    batch = fetchmany(1000)
                    if not batch:
                        break
                    rows.extend(tuple(row) for row in batch)
            else:
                rows.extend(tuple(row) for row in cursor.fetchall())
            return XuguQueryResult(
                columns=tuple(str(item[0]) for item in description),
                column_types=column_types,
                rows=tuple(rows),
                logical_types=tuple(map_driver_type(item) for item in column_types),
            )
        finally:
            cursor.close()

    def iter_query_rows(self, sql: str, parameters: tuple[Any, ...] = (), batch_size: int = 1000) -> Iterator[tuple[Any, ...]]:
        """Yield query rows in bounded batches for large-result callers."""
        if batch_size < 1:
            raise ValueError("batch_size must be positive")
        cursor = self._connection().cursor()
        try:
            cursor.execute(sql, parameters)
            fetchmany = getattr(cursor, "fetchmany", None)
            if callable(fetchmany):
                while True:
                    batch = fetchmany(batch_size)
                    if not batch:
                        return
                    yield from (tuple(row) for row in batch)
            else:
                yield from (tuple(row) for row in cursor.fetchall())
        finally:
            cursor.close()

    def begin(self) -> None:
        connection = self._connection()
        connection.autocommit(False)
        connection.begin()

    def commit(self) -> None:
        self._connection().commit()

    def rollback(self) -> None:
        self._connection().rollback()

    def rollback_transaction(self) -> None:
        """Rollback the current transaction boundary.

        This deliberately names the operation precisely: a rollback does not
        prove that session parameters, temporary objects, cursors, or locks
        have been reset.
        """
        self.rollback()

    def cancel(self) -> None:
        cancel = getattr(self._connection(), "cancel", None)
        if cancel is None:
            raise NotImplementedError("xgcondb connection does not expose cancel()")
        cancel()

    def reset(self) -> None:
        """Reset the complete session after adapter reset semantics are proven."""
        raise NotImplementedError("full Xugu session reset is not verified; use rollback_transaction()")

    def close(self) -> None:
        if self.connection is not None:
            self.connection.close()
            self.connection = None

    def _connection(self) -> Any:
        if self.connection is None:
            raise RuntimeError("XuguSession is not open")
        return self.connection
