"""External-agent boundaries and durable job lifecycle; no live DB required."""
from pathlib import Path
from types import SimpleNamespace
import json
import pytest
from xgtest.ai.controller import JobController
from xgtest.ai.models import ActionRequest, ActionResult, TestIntent as Intent
from xgtest.ai.store import JobStore


@pytest.fixture
def controller(tmp_path, monkeypatch):
    controller = JobController(tmp_path)
    project = SimpleNamespace(inspect=lambda: {"ready": True, "blockers": []},
        preflight=lambda: ActionResult(action="project.preflight", status="PASS"))
    module = SimpleNamespace(inspect=lambda: {"module_completion": "MODULE_FULL_INCOMPLETE"},
        inspect_coverage=lambda: ActionResult(action="feature.coverage", status="PASS", outputs={"provisional_missing": 0}),
        regression_valid=lambda result: result.status == "PASS",
        run_regression=lambda: ActionResult(action="module.regression", status="PASS"))
    candidates = SimpleNamespace(readiness=lambda *_: [], generate=lambda **kwargs: ActionResult(action="candidate.generate", status="PASS", outputs={"limit": kwargs.get("limit")}))
    acceptance = SimpleNamespace(manifest_path=tmp_path / "missing.json",
        inspect=lambda: ActionResult(action="acceptance.inspect", status="WAITING_APPROVAL", blockers=["HUMAN_REVIEW_REQUIRED"]),
        preflight=lambda: ActionResult(action="acceptance.preflight", status="WAITING_APPROVAL"),
        promote=lambda: ActionResult(action="acceptance.promote", status="WAITING_APPROVAL"))
    monkeypatch.setattr(controller, "services", lambda job_id: (project, module, candidates, acceptance))
    return controller


def create(controller, intent="query.full_test"):
    return controller.create("Verify query", {"intent": intent})["job_id"]


def act(controller, job_id, action, request_id=None):
    return controller.execute(job_id, {"expected_revision": controller.store.load(job_id).revision,
        "request_id": request_id or action.replace(".", "_"), "action": {"action": action, "reason": "Test selection"}})


def test_status_completion(controller):
    job_id = create(controller, "query.status")
    for action in ("project.inspect", "module.inspect", "feature.coverage"): result = act(controller, job_id, action)
    assert result["state"] == "COMPLETED"
    assert controller.status(job_id)["eligible_actions"] == []


@pytest.mark.parametrize("action", ["shell.execute", "repair.propose", "repair.validate", "approval.sign"])
def test_untrusted_actions_rejected(action):
    with pytest.raises(ValueError):
        ActionRequest.model_validate({"request_id": "x", "expected_revision": 1, "action": {"action": action, "reason": "invalid"}})


def test_extra_arguments_rejected():
    with pytest.raises(ValueError):
        Intent.model_validate({"intent": "query.full_test", "shell": "echo unsafe"})


def test_prerequisites(controller):
    job_id = create(controller)
    with pytest.raises(ValueError, match="ACTION_NOT_ELIGIBLE"): act(controller, job_id, "acceptance.promote")
    with pytest.raises(ValueError, match="ACTION_NOT_ELIGIBLE"): act(controller, job_id, "module.regression")
    assert controller.store.load(job_id).revision == 1


def test_revision_conflict(controller):
    job_id = create(controller)
    act(controller, job_id, "project.inspect")
    with pytest.raises(ValueError, match="JOB_REVISION_CONFLICT"):
        controller.execute(job_id, {"request_id": "new", "expected_revision": 1,
            "action": {"action": "project.inspect", "reason": "stale"}})


def test_idempotency(controller):
    job_id = create(controller)
    first = act(controller, job_id, "project.inspect", "same")
    second = act(controller, job_id, "project.inspect", "same")
    assert second == first
    with pytest.raises(ValueError, match="REQUEST_ID_REUSED"): act(controller, job_id, "module.inspect", "same")


def test_human_gate(controller):
    job_id = create(controller)
    for action in ("project.preflight", "module.regression", "acceptance.inspect"): result = act(controller, job_id, action)
    assert result["state"] == "WAITING_APPROVAL"
    with pytest.raises(ValueError, match="ACTION_NOT_ELIGIBLE"): act(controller, job_id, "acceptance.promote")
    resumed = controller.resume(job_id, result["revision"])
    assert resumed["state"] == "PLANNED"
    assert resumed["preflight_required"] is True
    assert any(r["action"] == "project.preflight" for r in resumed["action_results"])
    assert any(r["action"] == "module.regression" for r in resumed["action_results"])


def test_annotations_cannot_change_truth(controller):
    job_id = create(controller)
    result = controller.annotate(job_id, 1, "Agent opinion only")
    assert result["state"] == "PLANNED" and result["action_results"] == []
    with pytest.raises(ValueError, match="NO_FAILURE_TO_ANALYZE"):
        controller.annotate(job_id, result["revision"], "analysis", {"category": "UNKNOWN", "failure_summary": "x",
            "likely_area": "x", "recommended_action": "x", "confidence": 0.5})


def test_replay_partial_event_and_stale_checkpoint(controller):
    job_id = create(controller)
    result = act(controller, job_id, "project.inspect")
    directory = controller.store.directory(job_id)
    (directory / "state.json").write_text("invalid")
    with (directory / "events.jsonl").open("ab") as stream: stream.write(b'{"unfinished":')
    assert controller.store.load(job_id).revision == result["revision"]
    act(controller, job_id, "module.inspect")
    for line in (directory / "events.jsonl").read_text().splitlines(): json.loads(line)


def test_locks_and_path_boundaries(controller):
    with controller.store.execution_lock():
        with pytest.raises(ValueError, match="JOB_BUSY"):
            with controller.store.execution_lock(): pass
    with pytest.raises(ValueError, match="JOB_ID_INVALID"): controller.store.load("../outside")


def test_interrupted_action_requires_resume(controller):
    from xgtest.ai.models import SemanticAction
    job_id = create(controller)
    job = controller.store.load(job_id)
    with controller.store.lock(job_id):
        job = controller.store.save(job.model_copy(update={"state": "RUNNING", "current_action": SemanticAction(action="module.regression", reason="interrupted")}), "ACTION_STARTED")
    assert controller.status(job_id)["eligible_actions"] == []
    controller.resume(job_id, job.revision)
    assert controller.store.load(job_id).current_action is None


def test_technical_review_requires_bound_context():
    with pytest.raises(ValueError, match="TECHNICAL_REVIEW_ARGUMENTS_INVALID"):
        ActionRequest.model_validate({"request_id": "review", "expected_revision": 1,
            "action": {"action": "candidate.technical_review", "case_id": "QUERY.JOIN.GEN001", "reason": "review"}})


def test_read_only_jobs_api(controller):
    from fastapi.testclient import TestClient
    from xgtest.web.app import create_app
    job_id = create(controller)
    client = TestClient(create_app(SimpleNamespace(project_root=controller.root)))
    assert client.get("/api/jobs").json()["items"][0]["job_id"] == job_id
    assert client.get(f"/api/jobs/{job_id}").json()["state"] == "PLANNED"
    assert client.post(f"/api/jobs/{job_id}", json={"state": "COMPLETED"}).status_code == 405
    assert client.get("/api/jobs/invalid").status_code == 400
    assert client.get("/api/jobs/" + "0" * 32).status_code == 404


def test_failure_does_not_disappear_on_inspection(controller, monkeypatch):
    project = controller.services("unused")[0]
    monkeypatch.setattr(project, "preflight", lambda: ActionResult(action="project.preflight", status="BLOCKED", blockers=["DATABASE_NETWORK_UNREACHABLE"]))
    job_id = create(controller)
    act(controller, job_id, "project.preflight")
    result = act(controller, job_id, "project.inspect")
    assert result["state"] == "BLOCKED"
    assert result["blockers"] == ["DATABASE_NETWORK_UNREACHABLE"]


def test_runtime_drift_invalidates_preflight(controller, monkeypatch):
    job_id = create(controller)
    act(controller, job_id, "project.preflight")
    project = controller.services(job_id)[0]
    monkeypatch.setattr(project, "inspect", lambda: {"ready": True, "blockers": [], "runtime_profile_id": "new"})
    assert {"action": "project.preflight", "case_id": None} in controller.status(job_id)["eligible_actions"]
    with pytest.raises(ValueError, match="ACTION_NOT_ELIGIBLE"): act(controller, job_id, "module.regression")


def test_promotion_resume_and_post_regression(controller, monkeypatch):
    from xgtest.ai.models import SemanticAction
    job_id = create(controller)
    project, module, candidates, acceptance = controller.services(job_id)
    act(controller, job_id, "project.preflight")
    act(controller, job_id, "module.regression")
    job = controller.store.load(job_id)
    with controller.store.lock(job_id):
        job = controller.store.save(job.model_copy(update={"current_action": SemanticAction(action="acceptance.promote", reason="synthetic crash"), "state": "RUNNING"}), "ACTION_STARTED")
    calls = []
    def promote():
        calls.append("core recovery")
        return ActionResult(action="acceptance.promote", status="PASS", outputs={"fixture": "synthetic"})
    monkeypatch.setattr(acceptance, "promote", promote)
    acceptance.post_verify = lambda regression: ActionResult(action="acceptance.post_verify", status="PASS", outputs={"formal_final": "HOLD"})
    controller.resume(job_id, job.revision)
    assert calls == ["core recovery"]
    assert {"action": "module.regression", "case_id": None} in controller.status(job_id)["eligible_actions"]
    with pytest.raises(ValueError, match="ACTION_NOT_ELIGIBLE"): act(controller, job_id, "acceptance.post_verify")
    act(controller, job_id, "module.regression", "post_regression")
    result = act(controller, job_id, "acceptance.post_verify")
    assert result["state"] == "COMPLETED"
    assert result["action_results"][-1]["outputs"]["formal_final"] == "HOLD"


def test_context_hash_accepts_runtime_floats():
    from xgtest.application.services import context_hash
    assert context_hash({"duration": 0.5}) == context_hash({"duration": 0.50})
    assert context_hash({"duration": 0.5}) != context_hash({"duration": 0.6})


def test_complete_existing_active_coverage_without_empty_promotion(controller, monkeypatch):
    job_id = create(controller)
    module = controller.services(job_id)[1]
    monkeypatch.setattr(module, "inspect_coverage", lambda: ActionResult(action="feature.coverage", status="PASS", outputs={"active_missing": 0, "provisional_missing": 0}))
    act(controller, job_id, "project.preflight")
    after_regression = act(controller, job_id, "module.regression")
    assert after_regression["state"] == "RUNNING"
    result = act(controller, job_id, "feature.coverage")
    assert result["state"] == "COMPLETED"
    assert result["action_results"][-1]["action"] == "feature.coverage"
    assert not any(r["action"].startswith("acceptance.") for r in result["action_results"])


def test_smoke_generation_budget_is_cumulative():
    from xgtest.ai.models import ActionResult, TestIntent, TestJob, TestPlan
    job = TestJob(
        job_id="a" * 32,
        intent=TestIntent(intent="query.full_test", strategy="SMOKE"),
        plan=TestPlan(goal="smoke"),
        action_results=[
            ActionResult(action="candidate.generate", status="PASS", outputs={"candidate_ids": [f"QUERY.JOIN.GEN{i:03d}" for i in range(20)]}),
            ActionResult(action="candidate.generate", status="PASS", outputs={"candidate_ids": [f"QUERY.JOIN.GEN{i:03d}" for i in range(20, 25)]}),
        ],
    )
    progress = JobController.generation_progress(job)
    assert progress["budget"] == 30
    assert progress["generated_total"] == 25
    assert progress["remaining_budget"] == 5


def test_abandon_releases_mutable_slot_and_preserves_history(controller):
    job_id = create(controller)
    act(controller, job_id, "project.inspect")
    revision = controller.store.load(job_id).revision
    result = controller.abandon(job_id, revision, "legacy job before control-plane identity", operator="operator-1")
    assert result["state"] == "FAILED"
    assert result["current_action"] is None
    assert "JOB_ABANDONED_BY_OPERATOR" in result["blockers"]
    assert result["abandonment"] == {"operator": "operator-1", "reason": "legacy job before control-plane identity",
        "abandoned_at": result["abandonment"]["abandoned_at"], "previous_state": "RUNNING"}
    # History and evidence are preserved; the job is never deleted nor faked COMPLETED.
    assert [item["action"] for item in result["action_results"]] == ["project.inspect"]
    assert controller.store.load(job_id).abandonment is not None
    directory = controller.store.directory(job_id)
    assert "ABANDONED" in {json.loads(line)["event"] for line in (directory / "events.jsonl").read_text().splitlines()}
    assert json.loads((directory / "final-report.json").read_text())["abandonment"]["reason"] == "legacy job before control-plane identity"
    # The single mutable slot is now free for a fresh real run.
    assert create(controller) != job_id


def test_abandoned_job_is_terminal(controller):
    job_id = create(controller)
    controller.abandon(job_id, controller.store.load(job_id).revision, "stop after inspection")
    # status() reports the stored FAILED terminal state, not an identity overlay, and offers no actions.
    status = controller.status(job_id)
    assert status["state"] == "FAILED" and status["eligible_actions"] == []
    assert status["abandonment"] is not None
    with pytest.raises(ValueError, match="JOB_ABANDONED"): act(controller, job_id, "project.inspect")
    with pytest.raises(ValueError, match="JOB_ABANDONED"): controller.resume(job_id, controller.store.load(job_id).revision)
    with pytest.raises(ValueError, match="JOB_ALREADY_ABANDONED"):
        controller.abandon(job_id, controller.store.load(job_id).revision, "again")


def test_abandon_requires_operator_reason_and_current_revision(controller):
    job_id = create(controller)
    with pytest.raises(ValueError, match="JOB_REVISION_CONFLICT"): controller.abandon(job_id, 999, "stale")
    with pytest.raises(ValueError, match="ABANDON_REASON_INVALID"):
        controller.abandon(job_id, controller.store.load(job_id).revision, "")
    assert controller.store.load(job_id).abandonment is None


def test_legacy_identity_missing_job_can_be_abandoned_after_blocking_new_runs(controller):
    legacy = create(controller)
    job = controller.store.load(legacy)
    with controller.store.lock(legacy):
        controller.store.save(job.model_copy(update={"control_plane_layer_id": None}), "PAUSED")
    # The blocked legacy job monopolises the mutable slot, exactly like the real pre-identity job.
    assert controller.status(legacy)["state"] == "BLOCKED"
    with pytest.raises(ValueError, match="MUTABLE_JOB_ALREADY_EXISTS"): create(controller)
    # Abandon does not require a valid identity, so the operator can retire it and reopen the slot.
    result = controller.abandon(legacy, controller.store.load(legacy).revision, "legacy job before control-plane identity")
    assert result["state"] == "FAILED" and result["abandonment"]["previous_state"] == "PLANNED"
    assert create(controller) != legacy
