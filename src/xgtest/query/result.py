"""Serialization boundary for Query Run reports."""

from __future__ import annotations

import json
from pathlib import Path

from xgtest.core.models import QueryRunReport


def write_query_report(report: QueryRunReport, output: Path) -> dict[str, object]:
    payload = report.model_dump(mode="json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload
