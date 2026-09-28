"""Filesystem-backed, read-only Query Run History index and reader."""

from __future__ import annotations

import json
import os
import re
import tempfile
from datetime import date
from pathlib import Path
from typing import Any

from xgtest.core.models import QueryRunReport


class QueryHistoryError(ValueError):
    """A history index or run artifact is invalid."""


class QueryRunHistory:
    def __init__(self, runs_dir: Path) -> None:
        self.runs_dir = Path(runs_dir).resolve()
        self.index_path = self.runs_dir / "index.json"

    def record(self, report: dict[str, Any]) -> None:
        """Persist an immutable run report and atomically update its index."""
        validated = QueryRunReport.model_validate_json(json.dumps(report))
        payload = validated.model_dump(mode="json")
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        run_path = self._run_path(validated.run_id)
        self._write_json_atomic(run_path, payload)

        counts = {status: 0 for status in ("PASS", "FAIL", "ERROR", "TIMEOUT", "SKIPPED")}
        for case in validated.cases:
            counts[case.status.value] = counts.get(case.status.value, 0) + 1
        entry = {
            "run_id": validated.run_id,
            "started_at": validated.started_at.isoformat(),
            "status": validated.status.value,
            "database_alias": validated.target.database_alias,
            "git_commit": validated.git_commit,
            "case_count": len(validated.cases),
            "pass": counts["PASS"],
            "pass_rate": (counts["PASS"] / len(validated.cases) * 100) if validated.cases else 0.0,
            "fail": counts["FAIL"],
            "error": counts["ERROR"],
            "timeout": counts["TIMEOUT"],
            "duration_ms": max(0.0, (validated.finished_at - validated.started_at).total_seconds() * 1000),
        }
        entries = self._read_index()
        entries = [old for old in entries if old.get("run_id") != validated.run_id]
        entries.append(entry)
        entries.sort(key=lambda item: (item.get("started_at", ""), item["run_id"]), reverse=True)
        self._write_json_atomic(self.index_path, entries)

    def list_runs(
        self,
        *,
        status: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        if offset < 0 or not 1 <= limit <= 500:
            raise ValueError("QUERY_HISTORY_PAGINATION_INVALID")
        entries = self._read_index()
        if status:
            entries = [entry for entry in entries if entry.get("status") == status]
        if date_from:
            entries = [entry for entry in entries if entry.get("started_at", "")[:10] >= date_from.isoformat()]
        if date_to:
            entries = [entry for entry in entries if entry.get("started_at", "")[:10] <= date_to.isoformat()]
        return entries[offset:offset + limit]

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        path = self._run_path(run_id)
        if not path.is_file():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            return QueryRunReport.model_validate_json(json.dumps(payload)).model_dump(mode="json")
        except (OSError, json.JSONDecodeError, ValueError) as error:
            raise QueryHistoryError(f"QUERY_HISTORY_RUN_INVALID:{run_id}") from error

    def get_case(self, run_id: str, case_id: str) -> dict[str, Any] | None:
        report = self.get_run(run_id)
        if report is None:
            return None
        return next((case for case in report["cases"] if case["case_id"] == case_id), None)

    def _run_path(self, run_id: str) -> Path:
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", run_id):
            raise ValueError("QUERY_HISTORY_RUN_ID_INVALID")
        candidate = (self.runs_dir / f"{run_id}.json").resolve()
        if candidate.parent != self.runs_dir:
            raise ValueError("QUERY_HISTORY_RUN_ID_INVALID")
        return candidate

    def _read_index(self) -> list[dict[str, Any]]:
        if not self.index_path.exists():
            return []
        try:
            payload = json.loads(self.index_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise QueryHistoryError("QUERY_HISTORY_INDEX_INVALID") from error
        if not isinstance(payload, list) or not all(isinstance(item, dict) for item in payload):
            raise QueryHistoryError("QUERY_HISTORY_INDEX_INVALID")
        for item in payload:
            item.setdefault("timeout", 0)
            if "pass_rate" not in item:
                count = item.get("case_count", 0)
                passed = item.get("pass", 0)
                item["pass_rate"] = (passed / count * 100) if isinstance(count, int) and count > 0 and isinstance(passed, int) else 0.0
        return payload

    @staticmethod
    def _write_json_atomic(path: Path, payload: Any) -> None:
        data = json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
        descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary_name, path)
        finally:
            try:
                os.unlink(temporary_name)
            except FileNotFoundError:
                pass
