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
        # Resolve the mission to an internal Job intent. Adding a feature needs a matching intent.
        intent = "query.full_test"
        goal = f"{mission.name}｜{mission.purpose}"
        job = self.controller.create(goal, {"intent": intent})
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

    def view(self, mission_id: str) -> dict:
        mission = self.store.load(mission_id)
        state = self._job_state(mission)
        return {
            "mission": mission.model_dump(mode="json"),
            "state": state,
            "tested_scope": list(mission.features),
            "untested_scope": list(mission.excluded_scope),
            "estimate": strategy_estimate(mission.strategy),
            "completeness_note": "MODULE_FULL_INCOMPLETE",
        }
