"""Read-only projections over Query History, Cases and Runtime metadata."""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path
from typing import Any

from xgtest.core.contract_set import build_contract_descriptor
from xgtest.query.history import QueryRunHistory
from xgtest.query.loader import load_query_directory_with_sources
from xgtest.runtime.profile import load_profile


class QueryReadService:
    def __init__(
        self,
        runs_dir: Path,
        cases_dir: Path,
        *,
        profile_path: Path | None = None,
        project_root: Path | None = None,
    ) -> None:
        self.history = QueryRunHistory(runs_dir)
        self.cases_dir = Path(cases_dir).resolve()
        self.profile_path = profile_path
        self.project_root = (project_root or Path(__file__).resolve().parents[3]).resolve()

    @classmethod
    def from_environment(cls) -> "QueryReadService":
        root = Path(__file__).resolve().parents[3]
        runs = Path(os.environ.get("XGTEST_RUNS_DIR", root / "artifacts" / "runs"))
        cases = Path(os.environ.get("XGTEST_CASES_DIR", root / "cases" / "query"))
        profile = os.environ.get("XGTEST_RUNTIME_PROFILE")
        return cls(runs, cases, profile_path=Path(profile) if profile else None, project_root=root)

    def list_runs(
        self,
        *,
        status: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> dict[str, Any]:
        items = self.history.list_runs(status=status, date_from=date_from, date_to=date_to, offset=offset, limit=limit)
        return {"items": items, "offset": offset, "limit": limit, "next_offset": offset + len(items) if len(items) == limit else None}

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        return self.history.get_run(run_id)

    def list_cases(
        self,
        run_id: str,
        *,
        status: str | None = None,
        feature: str | None = None,
        case_id: str | None = None,
        failure_type: str | None = None,
        sort_by: str | None = None,
        sort_dir: str = "asc",
        offset: int = 0,
        limit: int = 100,
    ) -> dict[str, Any] | None:
        run = self.get_run(run_id)
        if run is None:
            return None
        cases = list(run["cases"])
        if status:
            cases = [item for item in cases if item["status"] == status]
        if feature:
            cases = [item for item in cases if item.get("feature") == feature]
        if case_id:
            cases = [item for item in cases if case_id.lower() in item["case_id"].lower()]
        if failure_type:
            cases = [item for item in cases if item.get("failure_type") == failure_type]
        if sort_by:
            if sort_by != "duration_ms":
                raise ValueError("QUERY_CASE_SORT_UNSUPPORTED")
            if sort_dir not in ("asc", "desc"):
                raise ValueError("QUERY_CASE_SORT_DIR_INVALID")
            reverse = sort_dir == "desc"
            cases.sort(key=lambda item: (item.get("duration_ms") is None, item.get("duration_ms") or 0), reverse=reverse)
        return {"items": cases[offset:offset + limit], "total": len(cases), "offset": offset, "limit": limit}

    def get_case(self, run_id: str, case_id: str) -> dict[str, Any] | None:
        run = self.history.get_run(run_id)
        report = next((case for case in run["cases"] if case["case_id"] == case_id), None) if run else None
        if report is None:
            return None
        definition: dict[str, Any] | None = None
        source_available = False
        source_file = report.get("source_file")
        if source_file and report.get("case_source_hash"):
            try:
                candidate = (self.cases_dir / source_file).resolve()
                candidate.relative_to(self.cases_dir)
                assets = load_query_directory_with_sources(self.cases_dir)
                for asset in assets:
                    if asset.source.relative_path == source_file and asset.source.source_hash == report["case_source_hash"]:
                        definition = asset.case.model_dump(mode="json")
                        source_available = True
                        break
            except (OSError, ValueError):
                source_available = False
        return {
            "report": report,
            "git_commit": run.get("git_commit"),
            "source_available": source_available,
            "case_definition": definition,
        }

    def runtime_profile(self) -> dict[str, Any] | None:
        if self.profile_path is None or not self.profile_path.is_file():
            return None
        profile = load_profile(self.profile_path)
        identity = profile["identity"]
        capabilities = identity.get("capabilities", {})
        target = identity.get("target", {})
        driver = identity.get("driver", {})
        return {
            "sql_runtime_profile_id": profile["sql_runtime_profile_id"],
            "evidence_sha256": profile["evidence_sha256"],
            "contract_set_id": identity.get("contract_set_id"),
            "target": target,
            "driver": {key: driver[key] for key in ("module", "version", "build", "python_version") if key in driver},
            "capabilities": capabilities,
        }

    def contract(self) -> dict[str, Any]:
        descriptor = build_contract_descriptor(self.project_root)
        return {
            "contract_version": descriptor["contract_version"],
            "contract_set_id": descriptor["contract_set_id"],
            "descriptor_version": descriptor["descriptor_version"],
        }

    def type_support(self) -> dict[str, Any]:
        profile = self.runtime_profile()
        if profile is None:
            return {"available": False, "items": []}
        mappings = profile.get("capabilities", {}).get("type_mapping", {})
        items = [
            {"driver_type": name, **mapping}
            for name, mapping in sorted(mappings.items())
            if isinstance(mapping, dict)
        ]
        return {"available": True, "items": items}
