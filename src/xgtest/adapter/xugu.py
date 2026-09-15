"""Minimal Xugu connection integration for the SQL MVP probe path."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any


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

    def query(self, sql: str, parameters: tuple[Any, ...] = ()) -> tuple[list[str], list[tuple[Any, ...]]]:
        cursor = self._connection().cursor()
        try:
            cursor.execute(sql, parameters)
            description = cursor.description or ()
            columns = [str(item[0]) for item in description]
            return columns, [tuple(row) for row in cursor.fetchall()]
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

    def cancel(self) -> None:
        cancel = getattr(self._connection(), "cancel", None)
        if cancel is None:
            raise NotImplementedError("xgcondb connection does not expose cancel()")
        cancel()

    def reset(self) -> None:
        """Reset the transaction boundary; session parameters require a new session."""
        self.rollback()

    def close(self) -> None:
        if self.connection is not None:
            self.connection.close()
            self.connection = None

    def _connection(self) -> Any:
        if self.connection is None:
            raise RuntimeError("XuguSession is not open")
        return self.connection
