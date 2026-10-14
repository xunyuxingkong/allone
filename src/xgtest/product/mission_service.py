"""Compose missions with Core state. This layer arranges values; Core still decides them."""
import uuid
import json
from pathlib import Path

from xgtest.product.contracts import MissionChildJob, TestMission, strategy_estimate
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

    @staticmethod
    def _job_refs(mission: TestMission) -> list[MissionChildJob]:
        if mission.child_jobs:
            return list(mission.child_jobs)
        # Backward compatibility for Missions persisted before child-job orchestration.
        if mission.job_id:
            return [MissionChildJob(feature=mission.features[0], job_id=mission.job_id, attempt=1)]
        return []

    @classmethod
    def _latest_refs(cls, mission: TestMission) -> dict[str, MissionChildJob]:
        latest: dict[str, MissionChildJob] = {}
        for item in cls._job_refs(mission):
            if item.feature not in latest or item.attempt > latest[item.feature].attempt:
                latest[item.feature] = item
        return latest

    def _create_feature_job(self, mission: TestMission, feature: str) -> dict:
        goal = f"{mission.name}｜{mission.purpose}｜{feature}"
        return self.controller.create(goal, {
            "intent": "query.full_test", "mission_id": mission.mission_id,
            "features": [feature], "strategy": mission.strategy,
            "data_scale": mission.data_scale, "risk_focus": mission.risk_focus,
        }, mission_child=True)

    def create(self, definition: dict) -> dict:
        features = definition.get("features")
        if not isinstance(features, list) or not features:
            raise ValueError("MISSION_FEATURES_REQUIRED")
        # A definition that passes contract validation is complete, so it starts READY.
        candidate = TestMission.model_validate({**definition, "mission_id": self._mission_id(), "state": "READY"})
        with self.store.lock(candidate.mission_id):
            self.store.save(candidate)
        return self.view(candidate.mission_id)

    def list(self) -> list[dict]:
        items = []
        for item in self.store.list():
            mission_id = item.get("mission_id")
            if not mission_id:
                items.append(item)
                continue
            try:
                mission = self.store.load(mission_id)
                latest = self._latest_refs(mission)
                children = []
                for feature in mission.features:
                    ref = latest.get(feature)
                    if ref is None:
                        children.append({"feature": feature, "job_id": None, "state": "NOT_STARTED"})
                        continue
                    try:
                        state = self.controller.status(ref.job_id)["state"]
                    except (ValueError, OSError):
                        state = "BLOCKED"
                    children.append({"feature": feature, "job_id": ref.job_id,
                                     "attempt": ref.attempt, "state": state})
                item["state"] = self._job_state(mission)
                item["feature_jobs"] = children
                item["feature_job_count"] = len(self._job_refs(mission))
            except (OSError, ValueError):
                item["state"] = "BLOCKED"
                item["error"] = "MISSION_STATE_INVALID"
            items.append(item)
        return items

    def start(self, mission_id: str) -> dict:
        with self.store.lock(mission_id):
            mission = self.store.load(mission_id)
            if mission.state not in {"READY", "RUNNING", "BLOCKED"}:
                raise ValueError("MISSION_NOT_READY")
            created_features = {item.feature for item in self._job_refs(mission)}
            if mission.state != "READY" and set(mission.features) <= created_features:
                raise ValueError("MISSION_NOT_READY")
            for feature in mission.features:
                if feature in created_features:
                    continue
                job = self._create_feature_job(mission, feature)
                refs = self._job_refs(mission)
                attempt = 1 + sum(item.feature == feature for item in refs)
                ref = MissionChildJob(feature=feature, job_id=job["job_id"], attempt=attempt)
                mission = mission.model_copy(update={
                    "job_id": mission.job_id or job["job_id"],
                    "child_jobs": [*refs, ref], "state": "RUNNING",
                })
                self.store.save(mission)
                created_features.add(feature)
        return self.view(mission_id)

    def retry_feature(self, mission_id: str, feature: str) -> dict:
        with self.store.lock(mission_id):
            mission = self.store.load(mission_id)
            if feature not in mission.features:
                raise ValueError("MISSION_FEATURE_NOT_SELECTED")
            latest = self._latest_refs(mission).get(feature)
            if latest is None:
                raise ValueError("MISSION_FEATURE_JOB_NOT_STARTED")
            previous = self.controller.store.load(latest.job_id)
            if previous.state not in {"BLOCKED", "FAILED"}:
                raise ValueError("MISSION_FEATURE_RETRY_REQUIRES_FAILED_JOB")
            job = self._create_feature_job(mission, feature)
            refs = self._job_refs(mission)
            attempt = 1 + sum(item.feature == feature for item in refs)
            self.store.save(mission.model_copy(update={
                "job_id": mission.job_id or job["job_id"],
                "child_jobs": [*refs, MissionChildJob(feature=feature, job_id=job["job_id"], attempt=attempt)],
                "state": "RUNNING",
            }))
        return self.view(mission_id)

    def _job_state(self, mission: TestMission) -> str:
        latest = self._latest_refs(mission)
        jobs = []
        for ref in latest.values():
            try:
                jobs.append(self.controller.status(ref.job_id)["state"])
            except (ValueError, OSError):
                jobs.append("BLOCKED")
        if not jobs:
            return mission.state
        # A partially created parent mission is still in progress even if its
        # already-created child jobs have finished.
        if set(latest) != set(mission.features):
            return "RUNNING"
        states = [_JOB_TO_MISSION_STATE.get(item, "BLOCKED") for item in jobs]
        if "RUNNING" in states:
            return "RUNNING"
        if "BLOCKED" in states:
            return "BLOCKED"
        if "WAITING_APPROVAL" in states:
            return "WAITING_APPROVAL"
        return "COMPLETED" if all(item == "COMPLETED" for item in states) else "READY"

    def _job(self, mission: TestMission):
        refs = self._latest_refs(mission)
        if not refs:
            return None
        try:
            return self.controller.store.load(refs[mission.features[0]].job_id if mission.features[0] in refs else next(iter(refs.values())).job_id)
        except (ValueError, OSError):
            return None

    def ai_summary(self, mission_id: str) -> dict:
        """Present what the external AI actually produced for this mission's job.

        Advisory only: this layer never invents findings, statuses or coverage. Every
        item below is copied from a recorded AI artifact or Core result.
        """
        mission = self.store.load(mission_id)
        refs = self._latest_refs(mission)
        jobs = []
        for feature, ref in refs.items():
            try:
                jobs.append((feature, self.controller.store.load(ref.job_id)))
            except (ValueError, OSError):
                continue
        if not jobs:
            return {"mission_id": mission_id, "job_id": mission.job_id, "available": False,
                    "note": "尚未启动测试任务，AI 尚无产出。"}
        generated = [result for _, job in jobs for result in job.action_results if result.action == "candidate.generate"]
        reviews = [result for _, job in jobs for result in job.action_results if result.action == "candidate.technical_review"]
        review_decisions = [result.outputs.get("ai_technical_review", {}).get("decision")
                            for result in reviews if isinstance(result.outputs.get("ai_technical_review"), dict)]
        explanations = [{"feature": feature, "reason": result.outputs.get("reason")}
                        for feature, job in jobs for result in job.action_results
                        if result.action.startswith("candidate.") and result.outputs.get("reason")]
        failures = [{"feature": feature, **job.failure_analysis.model_dump(mode="json")}
                    for feature, job in jobs if job.failure_analysis]
        summaries = [f"{feature}: {job.explanation}" for feature, job in jobs if job.explanation]
        return {
            "mission_id": mission_id, "job_id": mission.job_id, "available": True,
            "advisory_only": True,
            "summary": "\n".join(summaries) or None,
            "failure_analysis": failures[0] if failures else None,
            "feature_failure_analyses": failures,
            "generated_candidate_count": sum(len(set(
                case_id for result in job.action_results if result.action == "candidate.generate"
                for case_id in result.outputs.get("candidate_ids", []) if isinstance(case_id, str)
            )) for _, job in jobs),
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
        latest = self._latest_refs(mission)
        feature_briefs = []
        for feature in mission.features:
            ref = latest.get(feature)
            if ref is None:
                continue
            try:
                job = self.controller.store.load(ref.job_id)
                _, module, _, _ = self.controller.services(job.job_id)
                coverage = module.inspect_coverage().outputs
                failures = [failure for result in job.action_results if result.action == "module.regression"
                            for failure in result.outputs.get("failures", []) or []]
                rounds = sum(1 for result in job.action_results if result.action == "candidate.generate")
                feature_briefs.append({"feature": feature, **brief(coverage, failures, rounds)})
            except (OSError, ValueError):
                feature_briefs.append({"feature": feature, "status": "UNAVAILABLE"})
        if len(mission.features) == 1:
            return ({key: value for key, value in feature_briefs[0].items() if key != "feature"}
                    if feature_briefs else {"features": []})
        return {"mission_id": mission_id, "features": feature_briefs}

    def _feature_job_views(self, mission: TestMission) -> list[dict]:
        latest = self._latest_refs(mission)
        views = []
        for ref in self._job_refs(mission):
            is_latest = latest.get(ref.feature) == ref
            try:
                job = self.controller.store.load(ref.job_id)
                state = self.controller.status(ref.job_id)["state"]
            except (ValueError, OSError):
                views.append({"feature": ref.feature, "attempt": ref.attempt, "job_id": ref.job_id,
                              "state": "BLOCKED", "mission_state": "BLOCKED", "is_latest": is_latest,
                              "candidate_count": 0, "generated_candidate_count": 0,
                              "case_count": None, "sql_count": None, "failure_count": None,
                              "coverage": None, "approval_status": "INVALID", "ai_findings_count": 0,
                              "blockers": ["JOB_STATE_UNAVAILABLE"]})
                continue
            regression = self.controller.last(job, "module.regression")
            coverage_result = self.controller.last(job, "feature.coverage")
            generation = self.controller.generation_progress(job)
            review = self._approval_review(job, mission)
            findings = sum(len(result.outputs.get("ai_technical_review", {}).get("findings", []))
                           for result in job.action_results if result.action == "candidate.technical_review")
            views.append({
                "feature": ref.feature, "attempt": ref.attempt, "job_id": ref.job_id,
                "state": state, "mission_state": _JOB_TO_MISSION_STATE.get(state, "BLOCKED"),
                "is_latest": is_latest, "candidate_count": len(job.candidate_scope_ids),
                "generated_candidate_count": generation["generated_total"],
                "case_count": regression.outputs.get("case_count") if regression else None,
                "sql_count": regression.outputs.get("sql_count") if regression else None,
                "failure_count": len(regression.outputs.get("failures", []) or []) if regression else None,
                "coverage": ({**coverage_result.outputs, "status": coverage_result.status} if coverage_result else None),
                "approval_status": review.get("status", "NOT_READY"),
                "ai_findings_count": findings, "blockers": list(dict.fromkeys([*job.blockers, *(
                    regression.blockers if regression else [])])),
            })
        return views

    def view(self, mission_id: str) -> dict:
        mission = self.store.load(mission_id)
        state = self._job_state(mission)
        refs = self._latest_refs(mission)
        jobs = []
        for feature, ref in refs.items():
            try:
                jobs.append((feature, self.controller.store.load(ref.job_id)))
            except (ValueError, OSError):
                continue
        job = jobs[0][1] if jobs else None
        child_views = self._feature_job_views(mission)
        latest_views = [item for item in child_views if item["is_latest"]]
        executed = [feature for feature, child in jobs if any(
            result.status in {"PASS", "FAIL", "BLOCKED"} and result.action in {
                "module.regression", "candidate.trial", "candidate.mutation"
            } for result in child.action_results
        )]
        covered = [item["feature"] for item in latest_views if item.get("coverage")
                   and item["coverage"].get("status") == "PASS" and item["coverage"].get("active_missing") == 0]
        progress = [self.controller.generation_progress(child) for _, child in jobs]
        budget_values = [item["budget"] for item in progress]
        remaining_values = [item["remaining_budget"] for item in progress]
        missing_job_count = max(0, len(mission.features) - len(jobs))
        generation = {
            "budget": (sum(item for item in budget_values if item is not None) + 30 * missing_job_count
                       if mission.strategy == "SMOKE" and all(item is not None for item in budget_values) else None),
            "generated_total": sum(item["generated_total"] for item in progress),
            "remaining_budget": (sum(item for item in remaining_values if item is not None) + 30 * missing_job_count
                                 if mission.strategy == "SMOKE" and all(item is not None for item in remaining_values) else None),
            "stalled": any(item["stalled"] for item in progress),
        }
        smoke_completions = []
        if mission.strategy == "SMOKE":
            for _, child in jobs:
                _, module, candidates, _ = self.controller.services(child.job_id)
                child_progress = self.controller.generation_progress(child)
                smoke_completions.append(self.smoke_completion(mission.strategy, child, module, candidates, child_progress))
        smoke_completion = {
            "smoke_complete": len(smoke_completions) == len(mission.features) and all(item["smoke_complete"] for item in smoke_completions),
            "regression_pass": len(smoke_completions) == len(mission.features) and all(item["regression_pass"] for item in smoke_completions),
            "generated_cases_valid": len(smoke_completions) == len(mission.features) and all(item["generated_cases_valid"] for item in smoke_completions),
            "no_blocking_failure": len(smoke_completions) == len(mission.features) and all(item["no_blocking_failure"] for item in smoke_completions),
            "strategy_completion_frozen": len(smoke_completions) == len(mission.features) and all(item.get("strategy_completion_frozen") for item in smoke_completions),
        }
        approval_review = self._approval_review(job, mission)
        latest_by_feature = {item["feature"]: item for item in latest_views}
        approval_by_feature = {
            feature: latest_by_feature.get(feature, {}).get("approval_status", "NOT_READY")
            for feature in mission.features
        }
        approval_values = list(approval_by_feature.values())
        if "INVALID" in approval_values:
            aggregate_approval = "INVALID"
        elif "APPROVED_STALE" in approval_values:
            aggregate_approval = "APPROVED_STALE"
        elif approval_values and all(item == "APPROVED_CURRENT" for item in approval_values):
            aggregate_approval = "APPROVED_CURRENT"
        elif any(item == "WAITING_APPROVAL" for item in approval_values):
            aggregate_approval = "WAITING_APPROVAL"
        else:
            aggregate_approval = "NOT_READY"
        aggregate_reason = {
            "INVALID": "至少一个 Feature 的审批材料无效或任务证据不可读取。",
            "APPROVED_STALE": "至少一个 Feature 的历史审批已过期或当前输入发生变化。",
            "APPROVED_CURRENT": "所有已请求 Feature 的当前审批均已通过只读复核。",
            "WAITING_APPROVAL": "至少一个 Feature 已进入人工审批门禁。",
            "NOT_READY": "仍有 Feature 尚未完成审批准备。",
        }[aggregate_approval]
        approval_evidence = approval_review.get("evidence", {})
        aggregate_blockers = list(dict.fromkeys([
            *approval_evidence.get("blockers", []),
            *(blocker for item in latest_views for blocker in item.get("blockers", [])),
        ]))
        approval_review = {**approval_review, "status": aggregate_approval,
                           "reason": aggregate_reason if len(mission.features) > 1 else approval_review.get("reason"),
                           "evidence": {**approval_evidence, "blockers": aggregate_blockers},
                           "feature_reviews": approval_by_feature,
                           "untested_scope": [feature for feature in mission.features if feature not in covered]}
        estimate_parts = [strategy_estimate(mission.strategy, feature) for feature in mission.features]
        estimate = {"strategy": mission.strategy,
                    "case_min": sum(item["case_min"] for item in estimate_parts),
                    "case_max": sum(item["case_max"] for item in estimate_parts),
                    "sql_min": sum(item["sql_min"] for item in estimate_parts),
                    "sql_max": sum(item["sql_max"] for item in estimate_parts), "unit": "cases"}
        known = lambda key: [item[key] for item in latest_views if isinstance(item.get(key), int)]
        feature_summary = {
            "requested_features": len(mission.features), "started_features": len(refs),
            "completed_features": sum(item.get("mission_state") == "COMPLETED" for item in latest_views),
            "blocked_features": sum(item.get("mission_state") == "BLOCKED" for item in latest_views),
            "case_count": sum(known("case_count")), "sql_count": sum(known("sql_count")),
            "failure_count": sum(known("failure_count")), "candidate_count": sum(item["candidate_count"] for item in latest_views),
            "ai_findings_count": sum(item["ai_findings_count"] for item in latest_views),
        }
        return {
            "mission": mission.model_dump(mode="json"),
            "state": state,
            "requested_scope": list(mission.features),
            "executed_scope": executed,
            "covered_scope": covered,
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
                "pairwise_complete": len(covered) == len(mission.features),
                **smoke_completion,
            },
            "approval_review": approval_review,
            "estimate": estimate,
            "feature_jobs": child_views,
            "feature_summary": feature_summary,
            "ai_summary": self.ai_summary(mission_id),
            "completeness_note": "MODULE_FULL_INCOMPLETE",
        }

    @staticmethod
    def smoke_completion(strategy, job, module, candidates, generation) -> dict:
        result = {"smoke_complete": False, "regression_pass": False,
                  "generated_cases_valid": False, "no_blocking_failure": False}
        if strategy != "SMOKE" or job is None:
            return result
        frozen = getattr(job, "strategy_completion", None)
        if hasattr(frozen, "model_dump"):
            frozen = frozen.model_dump(mode="json")
        if isinstance(frozen, dict) and frozen.get("schema_version") in {"1", "2"}:
            regression = next((item for item in reversed(job.action_results) if item.action == "module.regression"), None)
            regression_pass = bool(regression and module.regression_valid(regression))
            no_blocking_failure = job.state not in {"BLOCKED", "FAILED"}
            return {
                "smoke_complete": bool(frozen.get("smoke_complete")) and regression_pass and no_blocking_failure,
                "regression_pass": regression_pass,
                "generated_cases_valid": bool(frozen.get("generated_cases_valid")),
                "no_blocking_failure": no_blocking_failure,
                "strategy_completion_frozen": True,
            }
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
        latest_results = {}
        for item in job.action_results:
            latest_results[(item.action, item.case_id)] = item.status
        no_blocking_failure = job.state not in {"BLOCKED", "FAILED"} and not any(
            status in {"FAIL", "BLOCKED"} for status in latest_results.values()
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
        historical_approval = bool(latest_preflight and latest_preflight.status == "PASS")
        current_preflight = None
        current_approval_valid = False
        if manifest_path.is_file() and plan_path.is_file():
            try:
                acceptance = self.controller.services(job.job_id)[3]
                promotion = next((result for result in reversed(job.action_results) if result.action == "acceptance.promote"), None)
                if promotion and promotion.status == "PASS":
                    from xgtest.generator.approval_operator import verify_operator_approval
                    ctx = acceptance.ctx
                    if ctx.approval_path and ctx.allowed_signers_path:
                        current_approval_valid = verify_operator_approval(
                            ctx.approval_path, ctx.allowed_signers_path, manifest_path=manifest_path,
                            plan_path=plan_path, revoked_path=ctx.revoked_path,
                        ).get("status") == "APPROVED"
                else:
                    current_preflight = acceptance.preflight()
                    current_approval_valid = current_preflight.status == "PASS"
            except (OSError, ValueError, KeyError):
                current_preflight = None
        if current_approval_valid:
            status = "APPROVED_CURRENT"
        elif historical_approval:
            status = "APPROVED_STALE"
        elif package_result and package_result.status == "BLOCKED":
            status = "INVALID"
        elif package_result or job.state == "WAITING_APPROVAL":
            status = "WAITING_APPROVAL"
        else:
            status = "NOT_READY"
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
            "reason": (
                "当前签名、冻结清单、Promotion Plan、Signer 和撤销状态均已通过只读复核。"
                if status == "APPROVED_CURRENT" else
                "历史预检曾通过，但当前审批或输入已变化；需要重新核验并签署。"
                if status == "APPROVED_STALE" else
                "审批绑定当前冻结清单与 Promotion Plan；签名必须由本地 Operator 完成。"
                if status == "WAITING_APPROVAL" else None
            ),
            "readiness": (current_preflight.outputs.get("readiness") if current_preflight else None) or readiness or package.get("readiness"),
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
            "untested_scope": list(job.intent.features) if not any(
                result.action == "feature.coverage" and result.status == "PASS"
                and result.outputs.get("active_missing") == 0 for result in job.action_results
            ) else [],
        }
