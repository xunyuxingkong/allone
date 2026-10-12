"""Compose missions with Core state. This layer arranges values; Core still decides them."""
import uuid
import json
from pathlib import Path

from xgtest.product.contracts import TestMission, strategy_estimate
from xgtest.product.store import MissionStore

# Product mission state is a pure projection of the durable Job state; no new truth is created.
# A PLANNED job already means the mission was started and is waiting for the agent to act.
_JOB_TO_MISSION_STATE = {
    "PLANNED": "RUNNING",
    "RUNNING": "RUNNING",
    "WAITING_APPROVAL": "WAITING_APPROVAL",
    "BLOCKED": "BLOCKED",
    "FAILED": "BLOCKED",  # includes operator-abandoned jobs
    "COMPLETED": "COMPLETED",
}


class MissionService:
    def __init__(self, root, controller):
        self.root = Path(root).resolve()
        self.controller = controller
        self.store = MissionStore(self.root / "artifacts/missions")

    def _mission_id(self) -> str:
        return uuid.uuid4().hex

    def create(self, definition: dict) -> dict:
        features = definition.get("features")
        if not isinstance(features, list) or not features:
            raise ValueError("MISSION_FEATURES_REQUIRED")
        # A definition that passes contract validation is complete, so it starts READY.
        candidate = TestMission.model_validate({**definition, "mission_id": self._mission_id(), "state": "READY"})
        with self.store.lock(candidate.mission_id):
            self.store.save(candidate)
        return self.view(candidate.mission_id)

    def start(self, mission_id: str) -> dict:
        mission = self.store.load(mission_id)
        if mission.state != "READY":
            raise ValueError("MISSION_NOT_READY")
        # Reuse query.full_test; the mission's feature selects the job's scope.
        goal = f"{mission.name}｜{mission.purpose}"
        job = self.controller.create(goal, {"intent": "query.full_test", "features": list(mission.features),
            "strategy": mission.strategy, "data_scale": mission.data_scale, "risk_focus": mission.risk_focus})
        with self.store.lock(mission_id):
            current = self.store.load(mission_id)
            self.store.save(current.model_copy(update={"job_id": job["job_id"], "state": "RUNNING"}))
        return self.view(mission_id)

    def _job_state(self, mission: TestMission) -> str:
        if mission.job_id is None:
            return mission.state
        try:
            return _JOB_TO_MISSION_STATE[self.controller.status(mission.job_id)["state"]]
        except (ValueError, OSError):
            return "BLOCKED"

    def _job(self, mission: TestMission):
        if mission.job_id is None:
            return None
        try:
            return self.controller.store.load(mission.job_id)
        except (ValueError, OSError):
            return None

    def ai_summary(self, mission_id: str) -> dict:
        """Present what the external AI actually produced for this mission's job.

        Advisory only: this layer never invents findings, statuses or coverage. Every
        item below is copied from a recorded AI artifact or Core result.
        """
        mission = self.store.load(mission_id)
        job = self._job(mission)
        if job is None:
            return {"mission_id": mission_id, "job_id": mission.job_id, "available": False,
                    "note": "尚未启动测试任务，AI 尚无产出。"}
        generated = [result for result in job.action_results if result.action == "candidate.generate"]
        reviews = [result for result in job.action_results if result.action == "candidate.technical_review"]
        review_decisions = [result.outputs.get("ai_technical_review", {}).get("decision")
                            for result in reviews if isinstance(result.outputs.get("ai_technical_review"), dict)]
        explanations = [{"reason": result.outputs.get("reason")} for result in job.action_results
                        if result.action.startswith("candidate.") and result.outputs.get("reason")]
        return {
            "mission_id": mission_id, "job_id": job.job_id, "available": True,
            "advisory_only": True,
            "summary": job.explanation or None,
            "failure_analysis": job.failure_analysis.model_dump(mode="json") if job.failure_analysis else None,
            "generated_candidate_count": len(generated),
            "technical_review_count": len(reviews),
            "technical_review_decisions": {"PASS": review_decisions.count("PASS"),
                                           "CONCERNS": review_decisions.count("CONCERNS"),
                                           "FAIL": review_decisions.count("FAIL")},
            "reused_evidence": explanations,
            "does_not_change_core": True,
        }

    def exploration(self, mission_id: str) -> dict:
        """Assemble an AI-exploration briefing for the mission's job.

        Read-only: it reads Core coverage and the job's recorded results and
        classifies the remaining gaps by risk. It never generates, promotes or
        decides anything; the external agent chooses the next action.
        """
        from xgtest.product.exploration import brief
        mission = self.store.load(mission_id)
        job = self._job(mission)
        # Coverage and candidate data come from Core through the job's own services,
        # so the briefing reflects the feature the mission actually scopes to.
        coverage: dict = {"required": 0, "active_covered": 0, "active_missing": 0, "missing_requirements": []}
        failures: list[dict] = []
        rounds = 0
        if job is not None:
            _, module, _, _ = self.controller.services(job.job_id)
            coverage = module.inspect_coverage().outputs
            rounds = sum(1 for result in job.action_results if result.action == "candidate.generate")
            for result in job.action_results:
                if result.action == "module.regression":
                    failures.extend(result.outputs.get("failures", []) or [])
        return brief(coverage, failures, rounds)

    def view(self, mission_id: str) -> dict:
        mission = self.store.load(mission_id)
        state = self._job_state(mission)
        job = self._job(mission)
        executed = bool(job and any(
            result.status in {"PASS", "FAIL"} and result.action in {
                "module.regression", "candidate.trial", "candidate.mutation"
            }
            for result in job.action_results
        ))
        covered = bool(job and any(
            result.action == "feature.coverage" and result.status == "PASS"
            and result.outputs.get("active_missing") == 0 for result in job.action_results
        ))
        generation = self.controller.generation_progress(job) if job is not None else {
            "budget": 30 if mission.strategy == "SMOKE" else None,
            "generated_total": 0,
            "remaining_budget": 30 if mission.strategy == "SMOKE" else None,
            "stalled": False,
        }
        smoke_completion = self.smoke_completion("STANDARD", None, None, None, generation)
        if job is not None and mission.strategy == "SMOKE":
            _, module, candidates, _ = self.controller.services(job.job_id)
            smoke_completion = self.smoke_completion(mission.strategy, job, module, candidates, generation)
        approval_review = self._approval_review(job, mission)
        return {
            "mission": mission.model_dump(mode="json"),
            "state": state,
            "requested_scope": list(mission.features),
            "executed_scope": list(mission.features) if executed else [],
            "covered_scope": list(mission.features) if covered else [],
            "excluded_scope": list(mission.excluded_scope),
            "unmodelled_scope": [],
            "execution_policy": {
                "strategy": mission.strategy,
                "coverage_strategy": "all_values" if mission.strategy == "FULL" else "pairwise",
                "candidate_budget": 30 if mission.strategy == "SMOKE" else None,
                "data_scale": mission.data_scale,
                "risk_focus": list(mission.risk_focus),
                "data_scale_applied": False,
                "risk_focus_applied": False,
            },
            "generation_progress": {
                **generation,
                "coverage_target": "SMOKE_BUDGET_OR_NO_GAP" if mission.strategy == "SMOKE" else "DEFINED_SCOPE_COVERAGE",
                "pairwise_complete": bool(job and any(
                    result.action == "feature.coverage" and result.status == "PASS"
                    and result.outputs.get("active_missing") == 0 for result in job.action_results
                )),
                **smoke_completion,
            },
            "approval_review": approval_review,
            "estimate": strategy_estimate(mission.strategy, mission.features[0]),
            "ai_summary": self.ai_summary(mission_id),
            "completeness_note": "MODULE_FULL_INCOMPLETE",
        }

    @staticmethod
    def smoke_completion(strategy, job, module, candidates, generation) -> dict:
        result = {"smoke_complete": False, "regression_pass": False,
                  "generated_cases_valid": False, "no_blocking_failure": False}
        if strategy != "SMOKE" or job is None:
            return result
        generated_ids = {
            case_id for action in job.action_results if action.action == "candidate.generate"
            for case_id in action.outputs.get("candidate_ids", []) if isinstance(case_id, str)
        }
        readiness = {item["case_id"]: item for item in candidates.readiness()}
        generated_cases_valid = (
            generated_ids <= readiness.keys()
            and all(readiness[case_id]["static_valid"] and readiness[case_id]["mutation_valid"]
                    and readiness[case_id]["trial_verified"] and readiness[case_id]["technical_review_accepted"]
                    for case_id in generated_ids)
        )
        regression = next((item for item in reversed(job.action_results) if item.action == "module.regression"), None)
        regression_pass = bool(regression and module.regression_valid(regression))
        no_blocking_failure = job.state not in {"BLOCKED", "FAILED"} and not any(
            item.status in {"FAIL", "BLOCKED"} for item in job.action_results
        )
        coverage = module.inspect_coverage().outputs
        budget_or_no_gap = generation["remaining_budget"] == 0 or coverage.get("provisional_missing") == 0
        return {
            "smoke_complete": regression_pass and budget_or_no_gap and generated_cases_valid and no_blocking_failure,
            "regression_pass": regression_pass,
            "generated_cases_valid": generated_cases_valid,
            "no_blocking_failure": no_blocking_failure,
        }

    def _approval_review(self, job, mission: TestMission) -> dict:
        if job is None:
            return {"status": "NOT_READY", "reason": "测试任务尚未启动。"}
        directory = self.controller.store.directory(job.job_id) / "acceptance"
        manifest_path = directory / "package-manifest.json"
        plan_path = directory / "promotion-plan.json"
        manifest = plan = {}
        try:
            if manifest_path.is_file():
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if plan_path.is_file():
                plan = json.loads(plan_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"status": "INVALID", "reason": "审批包文件无法读取，请重新检查验收包。"}
        latest_preflight = next((result for result in reversed(job.action_results) if result.action == "acceptance.preflight"), None)
        package_result = next((result for result in reversed(job.action_results) if result.action == "acceptance.inspect"), None)
        regression = next((result for result in reversed(job.action_results) if result.action == "module.regression"), None)
        readiness = latest_preflight.outputs.get("readiness") if latest_preflight else None
        status = (
            "APPROVED" if latest_preflight and latest_preflight.status == "PASS"
            else "INVALID" if package_result and package_result.status == "BLOCKED"
            else "WAITING_APPROVAL" if package_result or job.state == "WAITING_APPROVAL"
            else "NOT_READY"
        )
        package = package_result.outputs if package_result else {}
        coverage_summary = {}
        coverage_path = directory / "coverage-summary.json"
        if coverage_path.is_file():
            try:
                coverage_summary = json.loads(coverage_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                return {"status": "INVALID", "reason": "覆盖摘要无法读取，请重新冻结审批包。"}
        trial_index = mutation_index = {}
        for name, target in (("trial-run-index.json", "trial"), ("mutation-validation-index.json", "mutation")):
            path = directory / name
            if path.is_file():
                try:
                    value = json.loads(path.read_text(encoding="utf-8"))
                    if target == "trial":
                        trial_index = value
                    else:
                        mutation_index = value
                except (OSError, json.JSONDecodeError):
                    return {"status": "INVALID", "reason": f"{name} 无法读取，请重新冻结审批包。"}
        profile_target = {}
        profile_path = self.controller.profile
        if profile_path.is_file():
            try:
                profile = json.loads(profile_path.read_text(encoding="utf-8"))
                profile_target = profile.get("identity", {}).get("target", {})
            except (OSError, json.JSONDecodeError):
                profile_target = {}
        trial_items = trial_index.get("candidates", []) if isinstance(trial_index, dict) else []
        mutation_items = mutation_index.get("candidates", []) if isinstance(mutation_index, dict) else []
        review_decisions = [
            result.outputs.get("ai_technical_review", {}).get("decision")
            for result in job.action_results
            if result.action == "candidate.technical_review"
            and isinstance(result.outputs.get("ai_technical_review"), dict)
        ]
        return {
            "status": status,
            "reason": "审批绑定当前冻结清单与 Promotion Plan；签名必须由本地 Operator 完成。" if status == "WAITING_APPROVAL" else None,
            "readiness": readiness or package.get("readiness"),
            "manifest_id": manifest.get("manifest_id") or package.get("manifest_id"),
            "plan_hash": plan.get("plan_hash"),
            "manifest_ref": manifest_path.relative_to(self.root).as_posix() if manifest_path.is_file() else None,
            "plan_ref": plan_path.relative_to(self.root).as_posix() if plan_path.is_file() else None,
            "candidate_count": len(manifest.get("members", [])) if isinstance(manifest.get("members"), list) else package.get("expected_count"),
            "runtime_profile_id": manifest.get("runtime_profile_id"),
            "database_version": profile_target.get("database_version"),
            "database_build_time": profile_target.get("db_build"),
            "contract_bindings": manifest.get("contract_bindings", {}),
            "coverage": {
                "active_covered": coverage_summary.get("active_covered"),
                "active_missing": coverage_summary.get("active_missing"),
                "provisional_missing": coverage_summary.get("provisional_missing_if_promoted"),
            },
            "ci_disposition": manifest.get("ci_disposition"),
            "technical_review_count": sum(1 for result in job.action_results if result.action == "candidate.technical_review"),
            "technical_reviews": [
                {
                    "case_id": result.case_id,
                    "decision": result.outputs.get("ai_technical_review", {}).get("decision"),
                    "recommendation": result.outputs.get("ai_technical_review", {}).get("recommendation"),
                    "findings": result.outputs.get("ai_technical_review", {}).get("findings", []),
                }
                for result in job.action_results
                if result.action == "candidate.technical_review"
                and isinstance(result.outputs.get("ai_technical_review"), dict)
            ],
            "evidence": {
                "regression_status": regression.status if regression else "NOT_RUN",
                "regression_failures": len(regression.outputs.get("failures", []) or []) if regression else 0,
                "trial_status": "PASS" if trial_items and all(item.get("status") == "PASS" for item in trial_items) else "INCOMPLETE",
                "trial_double_run_pass_count": trial_index.get("double_run_pass_count", 0) if isinstance(trial_index, dict) else 0,
                "mutation_killed_count": sum(1 for item in mutation_items if item.get("status") == "KILLED") if isinstance(mutation_items, list) else 0,
                "technical_review_decisions": {name: review_decisions.count(name) for name in ("PASS", "CONCERNS", "FAIL")},
                "blockers": list(dict.fromkeys([*job.blockers, *(package_result.blockers if package_result else [])])),
            },
            "untested_scope": list(mission.features) if not any(
                result.action == "feature.coverage" and result.status == "PASS"
                and result.outputs.get("active_missing") == 0 for result in job.action_results
            ) else [],
        }
