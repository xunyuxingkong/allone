import sys
from types import SimpleNamespace

import pytest

from xgtest.adapter.xugu import XuguConnectionConfig, XuguSession, extract_error, map_driver_type, smoke_probe


def test_config_requires_every_secret_reference() -> None:
    with pytest.raises(ValueError, match="XGTEST_DB_PASSWORD"):
        XuguConnectionConfig.from_environment(
            {
                "XGTEST_DB_HOST": "127.0.0.1",
                "XGTEST_DB_PORT": "1907",
                "XGTEST_DB_NAME": "SYSTEM",
                "XGTEST_DB_USER": "user",
            }
        )


def test_smoke_probe_closes_cursor_and_connection(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    class Cursor:
        def execute(self, sql: str) -> None:
            calls.append(sql)

        def fetchone(self) -> tuple[int]:
            return (1,)

        def close(self) -> None:
            calls.append("cursor.close")

    class Connection:
        def cursor(self) -> Cursor:
            return Cursor()

        def close(self) -> None:
            calls.append("connection.close")

    monkeypatch.setitem(sys.modules, "xgcondb", SimpleNamespace(Connect=lambda **_: Connection()))
    config = XuguConnectionConfig("host", "1907", "SYSTEM", "user", "password")
    assert smoke_probe(config) == (1,)
    assert calls == ["SELECT 1", "cursor.close", "connection.close"]


def test_extract_error_reads_code_from_xugu_message() -> None:
    assert extract_error(RuntimeError("[E5021 L1 C1] missing table"))["code"] == "E5021"


def test_extract_error_redacts_connection_secrets() -> None:
    details = extract_error(RuntimeError(
        "password=top-secret token=token-value Authorization: Bearer bearer-value "
        "url=xugu://user:top-secret@db:1907"
    ))
    assert all(secret not in details["message"] for secret in ("top-secret", "token-value", "bearer-value"))
    assert "<redacted>" in details["message"]


def test_driver_type_mapping_is_explicit() -> None:
    assert map_driver_type("NUMERIC") == "decimal"
    assert map_driver_type("TIMESTAMP WITH TIME ZONE") == "timestamp_tz"
    assert map_driver_type("VARCHAR") == "string"
    assert map_driver_type("BOOLEAN") == "bool"
    assert map_driver_type("VARBINARY(32)") == "bytes"
    assert map_driver_type("notimestamp") is None
    assert map_driver_type("driver.unknown") is None


def test_query_uses_bounded_fetchmany_and_exposes_logical_types(monkeypatch: pytest.MonkeyPatch) -> None:
    class Cursor:
        description = (("ID", "INTEGER"), ("NAME", "VARCHAR"))

        def __init__(self) -> None:
            self.batches = [[(1, "one")], [(2, "two")], []]

        def execute(self, sql, parameters=()):
            pass

        def fetchmany(self, size):
            assert size == 1000
            return self.batches.pop(0)

        def close(self):
            pass

    class Connection:
        def cursor(self):
            return Cursor()

        def close(self):
            pass

    monkeypatch.setitem(sys.modules, "xgcondb", SimpleNamespace(Connect=lambda **_: Connection()))
    session = XuguSession(XuguConnectionConfig("host", "1907", "SYSTEM", "user", "password")).open()
    result = session.query("SELECT 1")
    assert result.rows == ((1, "one"), (2, "two"))
    assert result.logical_types == ("int", "string")
    session.close()
