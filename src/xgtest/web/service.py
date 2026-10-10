"""Read-only projections over Query History, Cases and Runtime metadata."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from xgtest.core.contract_set import build_contract_descriptor
from xgtest.design.coverage import assignment_requirements, coverage_gap
from xgtest.design.model import load_test_model
from xgtest.query.history import QueryRunHistory
from xgtest.query.loader import load_query_case, load_query_directory, load_query_directory_with_sources
from xgtest.runtime.profile import load_profile
from xgtest.generator.evidence import validate_trial_artifact
from xgtest.generator.review import current_review_input_hash
from xgtest.generator.template import semantic_hash
from xgtest.generator.scope import AcceptanceScope, resolve_scope


class QueryReadService:
    def __init__(
        self,
        runs_dir: Path,
        cases_dir: Path,
        *,
        profile_path: Path | None = None,
        project_root: Path | None = None,
        candidates_dir: Path | None = None,
        trial_artifacts_dir: Path | None = None,
        scope: AcceptanceScope | None = None,
    ) -> None:
        self.scope = resolve_scope(scope=scope)
        self.history = QueryRunHistory(runs_dir)
        self.cases_dir = Path(cases_dir).resolve()
        self.profile_path = profile_path
        self.project_root = (project_root or Path(__file__).resolve().parents[3]).resolve()
        self.candidates_dir = (candidates_dir or self.scope.path(self.project_root, "candidate_root")).resolve()
        self.trial_artifacts_dir = (trial_artifacts_dir or self.project_root / "artifacts" / "trial-runs").resolve()

    @classmethod
    def from_environment(cls) -> "QueryReadService":
        root = Path(__file__).resolve().parents[3]
        runs = Path(os.environ.get("XGTEST_RUNS_DIR", root / "artifacts" / "runs"))
        scope = resolve_scope()
        cases = Path(os.environ.get("XGTEST_CASES_DIR", scope.path(root, "active_suite_root")))
        profile = os.environ.get("XGTEST_RUNTIME_PROFILE")
        candidates = Path(os.environ.get("XGTEST_CANDIDATES_DIR", scope.path(root, "candidate_root")))
        trials = Path(os.environ.get("XGTEST_TRIAL_ARTIFACTS_DIR", root / "artifacts" / "trial-runs"))
        return cls(runs, cases, profile_path=Path(profile) if profile else None, project_root=root, candidates_dir=candidates, trial_artifacts_dir=trials)

    def _feature_model(self):
        return self.scope.load_model(self.project_root)

    def _feature_scoped_assets(self, assets: list[Any]) -> list[Any]:
        """Feature assets only: mirrors AcceptanceScope.feature_claims and CandidateService.generate."""
        feature_root = self.scope.path(self.project_root, "active_root")
        legacy = {(self.project_root / name).resolve() for name in self.scope.legacy_feature_assets}
        suite_root = self.scope.path(self.project_root, "active_suite_root")
        scoped = []
        for asset in assets:
            path = (suite_root / asset.source.relative_path).resolve()
            if path.is_relative_to(feature_root) or path in legacy:
                scoped.append(asset)
        return scoped

    def _candidate_cases(self) -> list[tuple[Path, Any]]:
        if not self.candidates_dir.is_dir():
            return []
        return [(path, load_query_case(path)) for path in sorted(self.candidates_dir.glob("*.yaml"))]

    def _trial_evidence_status(self, path: Path, case: Any, contract_set_id: str, profile_id: str | None) -> str:
        evidence = case.validation_evidence
        if evidence is None or not evidence.trial_run_ref or not evidence.trial_artifact_sha256 or not evidence.trial_run_hash:
            return "missing"
        artifact_ref = Path(evidence.trial_run_ref)
        if artifact_ref.is_absolute() or ".." in artifact_ref.parts:
            return "invalid_reference"
        artifact_path = (self.trial_artifacts_dir / artifact_ref).resolve()
        if not artifact_path.is_relative_to(self.trial_artifacts_dir):
            return "invalid_reference"
        try:
            artifact_bytes = artifact_path.read_bytes()
            artifact = json.loads(artifact_bytes)
            payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, yaml.YAMLError):
            return "artifact_unavailable"
        if not isinstance(artifact, dict) or not isinstance(payload, dict):
            return "artifact_invalid"
        if hashlib.sha256(artifact_bytes).hexdigest() != evidence.trial_artifact_sha256:
            return "hash_mismatch"
        semantic = semantic_hash(payload)
        if semantic != evidence.semantic_hash or artifact.get("semantic_hash") != semantic:
            return "candidate_changed"
        if artifact.get("contract_set_id") != contract_set_id:
            return "contract_stale"
        if profile_id is None:
            return "profile_unconfigured"
        if artifact.get("runtime_profile_id") != profile_id:
            return "profile_stale"
        validation = validate_trial_artifact(
            artifact,
            case_id=case.metadata.id,
            semantic_hash=semantic,
            step_ids=tuple(step.id for step in case.steps),
            step_modes={step.id: step.comparison.mode if step.comparison else "exact" for step in case.steps},
            contract_set_id=contract_set_id,
            runtime_profile_id=profile_id,
        )
        if validation["errors"] or validation["trial_hash"] != evidence.trial_run_hash:
            return "artifact_invalid"
        return "verified"

    def _current_profile_id(self) -> str | None:
        if self.profile_path is None or not self.profile_path.is_file():
            return None
        try:
            return load_profile(self.profile_path)["sql_runtime_profile_id"]
        except (OSError, ValueError):
            return None

    def coverage(self, strategy: str = "pairwise") -> dict[str, Any]:
        if strategy not in {"pairwise", "all_values"}:
            raise ValueError("COVERAGE_STRATEGY_UNSUPPORTED")
        model = self._feature_model()
        assets = load_query_directory_with_sources(self.cases_dir)
        candidates = [case for _, case in self._candidate_cases() if case.metadata.status.value == "review"]
        active_claims = self.scope.feature_claims(self.project_root, model, assets, suite_root=self.cases_dir)
        current = coverage_gap(model, active_claims, strategy)
        provisional = coverage_gap(model, active_claims + [claim for case in candidates for claim in case.coverage], strategy)
        active_missing_ids = {item.requirement_id for item in current["missing_requirements"]}
        provisional_missing_ids = {item.requirement_id for item in provisional["missing_requirements"]}
        candidate_ids_by_requirement: dict[str, list[str]] = {}
        for case in candidates:
            for claim in case.coverage:
                if claim.model_id != model.model_id or claim.model_version != model.model_version:
                    continue
                for requirement_id in assignment_requirements(model, claim.assignment, strategy) & active_missing_ids:
                    candidate_ids_by_requirement.setdefault(requirement_id, []).append(case.metadata.id)
        matrix: dict[tuple[str, ...], dict[str, Any]] = {}
        for requirement in current["requirements"]:
            dimensions = tuple(name for name, _ in requirement.selections)
            row = matrix.setdefault(dimensions, {
                "dimensions": list(dimensions),
                "required": 0,
                "active_covered": 0,
                "provisional_covered": 0,
            })
            row["required"] += 1
            row["active_covered"] += int(requirement.requirement_id not in active_missing_ids)
            row["provisional_covered"] += int(requirement.requirement_id not in provisional_missing_ids)
        return {
            "model_id": model.model_id,
            "model_version": model.model_version,
            "strategy": strategy,
            "required": current["required"],
            "feature_coverage_root": self.scope.feature_coverage_root,
            "module_regression_root": self.scope.module_regression_root,
            "completion": {"feature": "DEFINED_SCOPE_COMPLETE" if current["missing"] == 0 else "DEFINED_SCOPE_INCOMPLETE", "module": "MODULE_FULL_INCOMPLETE"},
            "active_covered": current["covered"],
            "active_missing": current["missing"],
            "missing_requirements": [
                {
                    "requirement_id": item.requirement_id,
                    "selections": dict(item.selections),
                    "candidate_case_ids": sorted(set(candidate_ids_by_requirement.get(item.requirement_id, []))),
                }
                for item in current["missing_requirements"]
            ],
            "review_candidate_count": len(candidates),
            "provisional_covered": provisional["covered"],
            "provisional_missing": provisional["missing"],
            "matrix": [matrix[key] for key in sorted(matrix)],
            "dimensions": {name: list(dimension.values) for name, dimension in sorted(model.dimensions.items())},
            "constraints": [rule.model_dump(mode="json", by_alias=True, exclude_none=True) for rule in model.constraints],
        }

    def scope_matrix(self, strategy: str = "pairwise") -> dict[str, Any]:
        """Core-derived scope matrix: which scenarios exist, which are covered, and at what size.

        Requirement, Case and Execution counts are deliberately separate: one case can
        satisfy several requirements and run several SQL steps, so they must never be read
        as the same number.
        """
        if strategy not in {"pairwise", "all_values"}:
            raise ValueError("COVERAGE_STRATEGY_UNSUPPORTED")
        model = self._feature_model()
        assets = self._feature_scoped_assets(load_query_directory_with_sources(self.cases_dir))
        active_claims = self.scope.feature_claims(self.project_root, model, assets, suite_root=self.cases_dir)
        current = coverage_gap(model, active_claims, strategy)
        covered_ids = {item.requirement_id for item in current["requirements"]} - {item.requirement_id for item in current["missing_requirements"]}
        requirements: dict[tuple[str, str], int] = {}
        covered: dict[tuple[str, str], int] = {}
        for requirement in current["requirements"]:
            for name, value in requirement.selections:
                requirements[(name, value)] = requirements.get((name, value), 0) + 1
                if requirement.requirement_id in covered_ids:
                    covered[(name, value)] = covered.get((name, value), 0) + 1
        cases: dict[tuple[str, str], int] = {}
        executions: dict[tuple[str, str], int] = {}
        active_cases = 0
        total_executions = 0
        for asset in assets:
            case = asset.case
            if case.metadata.status.value != "active":
                continue
            active_cases += 1
            total_executions += len(case.steps)
            assignment = case.coverage[0].assignment if case.coverage else {}
            for name, value in set(assignment.items()):
                cases[(name, value)] = cases.get((name, value), 0) + 1
                executions[(name, value)] = executions.get((name, value), 0) + len(case.steps)
        rows = []
        for (name, value) in sorted(requirements):
            required, hit = requirements[(name, value)], covered.get((name, value), 0)
            rows.append({"dimension": name, "value": value, "label": self._VALUE_LABELS.get(name, {}).get(value, value),
                         "required": required, "covered": hit,
                         "cases": cases.get((name, value), 0), "executions": executions.get((name, value), 0),
                         "status": "covered" if hit == required else "partial" if hit else "missing"})
        # Tested / untested split of the modelled space, decided entirely by Core coverage.
        tested = [{"dimension": row["dimension"], "value": row["value"], "label": row["label"],
                   "covered": row["covered"], "required": row["required"]} for row in rows if row["covered"] > 0]
        untested = [{"dimension": row["dimension"], "value": row["value"], "label": row["label"],
                     "required": row["required"]} for row in rows if row["covered"] == 0]
        return {
            "feature": model.model_id, "model_version": model.model_version, "strategy": strategy,
            "rows": rows, "tested_scope": tested, "untested_scope": untested,
            "totals": {"requirements": current["required"], "covered": current["covered"],
                       "missing": current["missing"], "cases": active_cases, "executions": total_executions},
            "count_semantics": {"requirements": "覆盖义务（一个 Case 可覆盖多条）",
                                "cases": "已定义范围内的可执行用例数",
                                "executions": "这些用例包含的 SQL 步骤总数"},
            "scope_verdict": {
                "defined_scope": "当前定义范围：已覆盖" if current["missing"] == 0 else f"当前定义范围：还有 {current['missing']} 项未覆盖",
                "module": "模块全量：未完整（MODULE_FULL_INCOMPLETE）",
            },
            "module_completion": "MODULE_FULL_INCOMPLETE",
        }

    # Human-readable meaning of the model dimension values, for the semantic path view.
    _VALUE_LABELS = {
        "join_type": {"inner": "INNER JOIN", "left": "LEFT JOIN", "right": "RIGHT JOIN", "full": "FULL JOIN", "cross": "CROSS JOIN"},
        "predicate": {"none": "无连接谓词", "equality": "等值谓词", "inequality": "不等谓词", "less_equal": "≤ 谓词"},
        "datatype": {"int": "INTEGER 键", "varchar": "VARCHAR 键", "date": "DATE 键"},
        "null_side": {"none": "无 NULL 键", "left": "左表 NULL 键", "right": "右表 NULL 键", "both": "两侧 NULL 键"},
        "interaction": {"none": "无附加交互", "where": "附加 WHERE", "group_by": "附加 GROUP BY", "subquery": "附加子查询"},
    }
    _DIMENSION_ORDER = ("join_type", "predicate", "datatype", "null_side", "interaction")

    def _case_origin(self, case, assignment: dict[str, str]) -> dict[str, Any]:
        """Explain a case in user terms: its semantic path, why it exists and where it came from."""
        path = []
        for name in sorted(assignment, key=lambda item: self._DIMENSION_ORDER.index(item) if item in self._DIMENSION_ORDER else 99):
            value = assignment[name]
            path.append({"dimension": name, "value": value, "label": self._VALUE_LABELS.get(name, {}).get(value, value)})
        generation = case.generation
        source = "AI 生成" if generation is not None else "人工定义"
        if generation is None:
            reason = "人工定义的基础用例"
        else:
            strategy = generation.strategy
            reason = "AI 按 Pairwise 组合补全覆盖缺口" if strategy == "pairwise" else (
                "AI 按全取值组合补全覆盖缺口" if strategy == "all_values" else f"AI 按 {strategy} 策略生成")
        return {"path": path, "reason": reason, "source": source,
                "source_detail": None if generation is None else {
                    "generator": generation.generator, "generator_version": generation.generator_version,
                    "template_id": generation.template_id, "template_version": generation.template_version,
                    "strategy": generation.strategy, "model_id": generation.model_id, "model_version": generation.model_version}}

    def list_candidates(self, status: str | None = None) -> dict[str, Any]:
        if status is not None and status not in {"generated", "draft", "review", "active"}:
            raise ValueError("CANDIDATE_STATUS_INVALID")
        items = []
        contract_set_id = build_contract_descriptor(self.project_root)["contract_set_id"]
        profile_id = self._current_profile_id()
        for path, case in self._candidate_cases():
            if status is not None and case.metadata.status.value != status:
                continue
            trial_status = self._trial_evidence_status(path, case, contract_set_id, profile_id)
            assignment = case.coverage[0].assignment if case.coverage else {}
            items.append({
                "case_id": case.metadata.id,
                "status": case.metadata.status.value,
                "assignment": assignment,
                "model_version": case.coverage[0].model_version if case.coverage else None,
                "trial_evidence_status": trial_status,
                "trial_verified": trial_status == "verified",
                "review_recorded": case.review_evidence is not None and case.coverage_review is not None,
                # Semantic path / origin precomputed so the list can lead with meaning, not the raw id.
                "path_summary": " · ".join(item["label"] for item in self._case_origin(case, assignment)["path"]),
                "source_label": self._case_origin(case, assignment)["source"],
            })
        return {"items": items, "total": len(items)}

    def get_candidate(self, case_id: str) -> dict[str, Any] | None:
        from xgtest.generator.plugins import FEATURE_PLUGINS
        # Derive the accepted prefix set from the registry; never hardcode a length offset.
        if not FEATURE_PLUGINS.matches_case_id(case_id) or not case_id.replace(".", "").isalnum():
            raise ValueError("CANDIDATE_ID_INVALID")
        path = self.candidates_dir / f"{case_id}.yaml"
        if not path.is_file():
            return None
        case = load_query_case(path)
        if case.metadata.id != case_id:
            raise ValueError("CANDIDATE_ID_MISMATCH")
        trial_status = self._trial_evidence_status(path, case, build_contract_descriptor(self.project_root)["contract_set_id"], self._current_profile_id())
        review_status = "missing"
        if case.review_evidence is not None and case.coverage_review is not None and case.validation_evidence is not None:
            try:
                payload = yaml.safe_load(path.read_text(encoding="utf-8"))
                current_hash = current_review_input_hash(case, semantic_hash(payload))
                review_status = "binding_valid" if (
                    case.review_evidence.review_input_hash == current_hash
                    and case.coverage_review.review_input_hash == current_hash
                    and case.validation_evidence.review_hash == current_hash
                ) else "stale"
            except (OSError, ValueError, TypeError):
                review_status = "invalid"
        model = self._feature_model()
        assets = load_query_directory_with_sources(self.cases_dir)
        current = coverage_gap(model, self.scope.feature_claims(self.project_root, model, assets, suite_root=self.cases_dir), self.scope.coverage_strategy)
        candidate_requirement_ids: set[str] = set()
        for claim in case.coverage:
            if claim.model_id == model.model_id and claim.model_version == model.model_version:
                candidate_requirement_ids.update(assignment_requirements(model, claim.assignment, self.scope.coverage_strategy))
        new_requirements = [
            {"requirement_id": item.requirement_id, "selections": dict(item.selections)}
            for item in current["missing_requirements"]
            if item.requirement_id in candidate_requirement_ids
        ]
        return {
            "case_id": case.metadata.id,
            "status": case.metadata.status.value,
            "origin": self._case_origin(case, case.coverage[0].assignment if case.coverage else {}),
            "coverage": [claim.model_dump(mode="json") for claim in case.coverage],
            "generation": case.generation.model_dump(mode="json") if case.generation else None,
            "steps": [step.model_dump(mode="json") for step in case.steps],
            "validation_evidence": case.validation_evidence.model_dump(mode="json", exclude_none=True) if case.validation_evidence else None,
            "mutation_evidence": case.mutation_evidence.model_dump(mode="json", exclude_none=True) if case.mutation_evidence else None,
            "oracle": case.oracle.model_dump(mode="json", exclude_none=True) if case.oracle else None,
            "review_evidence": case.review_evidence.model_dump(mode="json", exclude_none=True) if case.review_evidence else None,
            "coverage_review": case.coverage_review.model_dump(mode="json", exclude_none=True) if case.coverage_review else None,
            "review_binding_status": review_status,
            "trial_evidence_status": trial_status,
            "review_recorded": case.review_evidence is not None and case.coverage_review is not None,
            "coverage_contribution": {"strategy": self.scope.coverage_strategy, "new_requirements": new_requirements},
        }

    def candidate_artifact(self, case_id: str, kind: str) -> bytes:
        if kind not in {"trial", "mutation"}:
            raise ValueError("CANDIDATE_ARTIFACT_KIND_INVALID")
        detail = self.get_candidate(case_id)
        if detail is None:
            raise ValueError("CANDIDATE_NOT_FOUND")
        evidence = detail["validation_evidence"] if kind == "trial" else detail["mutation_evidence"]
        if not isinstance(evidence, dict):
            raise ValueError("CANDIDATE_ARTIFACT_MISSING")
        relative = evidence.get("trial_run_ref") if kind == "trial" else evidence.get("artifact_ref")
        expected_sha = evidence.get("trial_artifact_sha256") if kind == "trial" else evidence.get("artifact_sha256")
        if not isinstance(relative, str) or not isinstance(expected_sha, str):
            raise ValueError("CANDIDATE_ARTIFACT_REFERENCE_INVALID")
        root = self.trial_artifacts_dir if kind == "trial" else self.project_root / "artifacts" / "mutations"
        ref = Path(relative)
        if ref.is_absolute() or ".." in ref.parts:
            raise ValueError("CANDIDATE_ARTIFACT_REFERENCE_INVALID")
        artifact = (root / ref).resolve()
        if not artifact.is_relative_to(root.resolve()):
            raise ValueError("CANDIDATE_ARTIFACT_REFERENCE_INVALID")
        content = artifact.read_bytes()
        if hashlib.sha256(content).hexdigest() != expected_sha:
            raise ValueError("CANDIDATE_ARTIFACT_HASH_MISMATCH")
        return content

    def candidate_trial_rows(self, case_id: str, run: str, step_id: str, offset: int, limit: int) -> dict[str, Any]:
        if run not in {"run1", "run2"}:
            raise ValueError("TRIAL_RUN_INVALID")
        artifact = json.loads(self.candidate_artifact(case_id, "trial"))
        if not isinstance(artifact, dict) or not isinstance(artifact.get(run), dict):
            raise ValueError("TRIAL_ARTIFACT_INVALID")
        for step in artifact[run].get("steps", []):
            if isinstance(step, dict) and step.get("id") == step_id:
                rows = step.get("result_rows")
                if not isinstance(rows, list):
                    raise ValueError("TRIAL_RAW_ROWS_MISSING")
                return {
                    "case_id": case_id, "run": run, "step_id": step_id,
                    "columns": step.get("columns"), "column_types": step.get("column_types"),
                    "row_count": len(rows), "offset": offset, "limit": limit,
                    "rows": rows[offset:offset + limit],
                    "result_sha256": step.get("result_sha256"),
                }
        raise ValueError("TRIAL_STEP_NOT_FOUND")

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
