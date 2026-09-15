import sys
from types import SimpleNamespace

import pytest

from xgtest.adapter.xugu import XuguConnectionConfig, smoke_probe


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
