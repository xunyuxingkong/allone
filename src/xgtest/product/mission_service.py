"""Compose missions with Core state. This layer arranges values; Core still decides them."""
import uuid
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
            "estimate": strategy_estimate(mission.strategy, mission.features[0]),
            "ai_summary": self.ai_summary(mission_id),
            "completeness_note": "MODULE_FULL_INCOMPLETE",
        }
