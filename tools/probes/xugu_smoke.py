"""Run a side-effect-free Xugu Driver connectivity probe.

Pass connection settings through XGTEST_DB_HOST, XGTEST_DB_PORT,
XGTEST_DB_NAME, XGTEST_DB_USER and XGTEST_DB_PASSWORD. This script never
prints the configured user, password or connection string.
"""

from __future__ import annotations

import json

from xgtest.adapter.xugu import XuguConnectionConfig, smoke_probe


def main() -> None:
    config = XuguConnectionConfig.from_environment()
    row = smoke_probe(config)
    print(json.dumps({"probe": "xugu_connect_select_1", "status": "VERIFIED", "row": row}))


if __name__ == "__main__":
    main()

\n