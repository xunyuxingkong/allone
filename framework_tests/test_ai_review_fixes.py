"""Regression checks for the four control-plane findings in review 6311887."""
import json
from types import SimpleNamespace
import pytest

from framework_tests.test_ai_jobs import controller, create, act
from xgtest.application.services import CandidateService, context_hash, worker_launch
from xgtest.application.worker_results import safe_worker_error, failure_projection


@pytest.fixture
def review_service(controller, monkeypatch):
    job_id = create(controller)
    act(controller, job_id, "project.preflight")
    act(controller, job_id, "module.regression")
    case_id = "QUERY.JOIN.203908E1"
    context = {"candidate": {"sql": "SELECT 1"}, "rows": [[1]], "duration": 0.5}
    ctx = SimpleNamespace(job_dir=controller.store.directory(job_id),
        reader=SimpleNamespace(get_candidate=lambda _: {"trial_evidence_status": "verified"}),
        relative=lambda path: path.relative_to(controller.root).as_posix())
    service = CandidateService(ctx, None)
    monkeypatch.setattr(service, "mutation_valid", lambda _: True)
    monkeypatch.setattr(service, "review_context", lambda _: context)
    candidate = controller.services(job_id)[2]
    candidate.technical_review = service.technical_review
    def readiness():
        state = service.review_state(case_id)
        return [{"case_id": case_id, "static_valid": True, "mutation_valid": True, "trial_verified": True,
            "technical_review_valid": state["valid"], "technical_review_accepted": state["accepted"]}]
    candidate.readiness = readiness
    return job_id, case_id, context, service


def submit_review(controller, data, decision, recommendation):
    job_id, case_id, context, service = data
    return controller.execute(job_id, {"request_id": decision + "_" + recommendation,
        "expected_revision": controller.store.load(job_id).revision,
        "action": {"action": "candidate.technical_review", "case_id": case_id, "reason": "Inspect actual review decision"},
        "review_context_id": context_hash(context), "technical_review": {"decision": decision, "findings": ["Fixture finding"], "recommendation": recommendation}})


def test_failed_technical_review_blocks_acceptance(controller, review_service):
    job_id, case_id, context, service = review_service
    result = submit_review(controller, review_service, "FAIL", "INVESTIGATE")
    assert result["state"] == "BLOCKED"
    assert result["blockers"] == ["AI_TECHNICAL_REVIEW_FAILED"]
    assert service.review_state(case_id) == {"valid": True, "accepted": False, "decision": "FAIL", "blocker": "AI_TECHNICAL_REVIEW_FAILED"}
    for action in ("acceptance.inspect", "acceptance.preflight", "acceptance.promote"):
        with pytest.raises(ValueError, match="ACTION_NOT_ELIGIBLE"): act(controller, job_id, action)
    saved = json.loads((service.ctx.job_dir / "technical-reviews" / f"{case_id}.json").read_text())
    assert saved["review"]["decision"] == "FAIL"


@pytest.mark.parametrize("decision", ["CONCERNS", "PASS"])
def test_concerns_review_requires_human_check(controller, review_service, decision):
    result = submit_review(controller, review_service, decision, "NEEDS_HUMAN_CHECK")
    assert result["state"] == "BLOCKED"
    assert result["blockers"] == ["AI_TECHNICAL_REVIEW_NEEDS_HUMAN_CHECK"]
    assert not review_service[3].review_state(review_service[1])["accepted"]
    assert not any(item["action"].startswith("acceptance.") for item in controller.status(review_service[0])["eligible_actions"])


def test_reassessment_can_pass_but_cannot_become_human_approval(controller, review_service):
    submit_review(controller, review_service, "FAIL", "INVESTIGATE")
    result = submit_review(controller, review_service, "PASS", "READY_FOR_HUMAN_REVIEW")
    assert result["state"] == "RUNNING"
    assert review_service[3].review_state(review_service[1])["accepted"]
    gate = act(controller, review_service[0], "acceptance.inspect")
    assert gate["state"] == "WAITING_APPROVAL"


def test_stale_accepted_review_cannot_open_acceptance(controller, review_service):
    submit_review(controller, review_service, "PASS", "READY_FOR_HUMAN_REVIEW")
    review_service[2]["rows"] = [[2]]
    state = review_service[3].review_state(review_service[1])
    assert not state["valid"] and not state["accepted"]
    with pytest.raises(ValueError, match="ACTION_NOT_ELIGIBLE"): act(controller, review_service[0], "acceptance.inspect")


def test_control_plane_change_blocks_resume_and_action(controller):
    from xgtest.core.contract_set import build_contract_descriptor
    source = controller.root / "src/xgtest/ai/controller.py"
    source.parent.mkdir(parents=True)
    source.write_text("original logic")
    job_id = create(controller)
    execution_id = build_contract_descriptor(controller.root)["contract_set_id"]
    source.write_text("changed logic")
    assert build_contract_descriptor(controller.root)["contract_set_id"] == execution_id
    with pytest.raises(ValueError, match="JOB_CONTROL_PLANE_CHANGED"):
        controller.resume(job_id, controller.store.load(job_id).revision)
    stored = controller.store.load(job_id)
    assert stored.state == "BLOCKED"
    assert stored.blockers == ["JOB_CONTROL_PLANE_CHANGED"]
    assert stored.control_plane_layer_id != build_contract_descriptor(controller.root)["layers"]["control_plane"]["id"]
    with pytest.raises(ValueError, match="JOB_CONTROL_PLANE_CHANGED"): act(controller, job_id, "project.inspect")
    assert controller.status(job_id)["eligible_actions"] == []
    assert controller.store.load(job_id).action_results == []


def test_missing_legacy_identity_is_not_silently_adopted(controller):
    job_id = create(controller)
    job = controller.store.load(job_id)
    with controller.store.lock(job_id):
        controller.store.save(job.model_copy(update={"control_plane_layer_id": None}), "PAUSED")
    with pytest.raises(ValueError, match="JOB_CONTROL_PLANE_IDENTITY_MISSING"):
        controller.resume(job_id, controller.store.load(job_id).revision)


@pytest.mark.parametrize("state", ["PLANNED", "RUNNING", "WAITING_APPROVAL", "BLOCKED"])
def test_second_mutating_job_is_rejected(controller, state):
    job_id = create(controller)
    job = controller.store.load(job_id)
    with controller.store.lock(job_id): controller.store.save(job.model_copy(update={"state": state}), "PAUSED")
    with pytest.raises(ValueError, match="MUTABLE_JOB_ALREADY_EXISTS"):
        create(controller, "query.join.verify")
    create(controller, "query.status")
    assert len(controller.store.list()) == 2


def test_failed_job_cannot_resume_over_another_mutable_job(controller):
    first = create(controller)
    job = controller.store.load(first)
    with controller.store.lock(first): controller.store.save(job.model_copy(update={"state": "FAILED"}), "PAUSED")
    second = create(controller)
    with pytest.raises(ValueError, match="MUTABLE_JOB_ALREADY_EXISTS"):
        controller.resume(first, controller.store.load(first).revision)
    with pytest.raises(ValueError, match="MUTABLE_JOB_ALREADY_EXISTS"): act(controller, first, "project.inspect")
    assert controller.store.load(second).state == "PLANNED"


def test_simultaneous_creations_cannot_create_two_mutable_jobs(controller):
    from concurrent.futures import ThreadPoolExecutor
    def attempt():
        try: return create(controller)
        except ValueError as error: return str(error)
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(lambda _: attempt(), range(2)))
    assert len(controller.store.list()) == 1
    assert any(value in {"JOB_BUSY", "MUTABLE_JOB_ALREADY_EXISTS"} for value in outcomes)


def test_password_not_in_worker_command():
    environment = {"XGTEST_DB_HOST": "192.0.2.1", "XGTEST_DB_PASSWORD": "sensitive-value",
        "XGTEST_DB_USER": "test-user", "WSLENV": "CUSTOM/p:XGTEST_DB_PASSWORD/w:PYTHONPATH/p"}
    command, child_env = worker_launch("artifacts/jobs/test/request.json", "wsl", environment, True)
    assert "sensitive-value" not in " ".join(command)
    assert "test-user" not in " ".join(command)
    assert not any("XGTEST_DB_" in argument for argument in command)
    assert child_env["XGTEST_DB_PASSWORD"] == "sensitive-value"
    assert "XGTEST_DB_PASSWORD/u" in child_env["WSLENV"]
    assert "CUSTOM/p" in child_env["WSLENV"]
    assert "XGTEST_DB_PASSWORD/w" not in child_env["WSLENV"]
    assert environment["WSLENV"] == "CUSTOM/p:XGTEST_DB_PASSWORD/w:PYTHONPATH/p"


def test_driver_error_is_redacted_from_worker_and_job(controller, monkeypatch):
    from xgtest.application import db_worker
    job_id = create(controller)
    directory = controller.store.directory(job_id) / "executions/test"
    directory.mkdir(parents=True)
    request = directory / "request.json"
    request.write_text('{}')
    sensitive = "password=sensitive-value xugu://test-user:secret@192.0.2.1 SELECT private_column FROM private_table /private/path"
    class DriverError(Exception): pass
    def failed_execute(*args): raise DriverError(sensitive)
    monkeypatch.setattr(db_worker, "execute", failed_execute)
    monkeypatch.setattr(db_worker, "__file__", str(controller.root / "src/xgtest/application/db_worker.py"))
    monkeypatch.setattr(db_worker.sys, "argv", ["worker", request.relative_to(controller.root).as_posix()])
    db_worker.main()
    result = json.loads(request.with_suffix(".result.json").read_text())
    assert result["error_code"] == "DATABASE_EXECUTION_ERROR"
    project = controller.services(job_id)[0]
    from xgtest.ai.models import ActionResult
    project.preflight = lambda: ActionResult(action="project.preflight", status="BLOCKED", outputs=result, blockers=[result["error_code"]])
    act(controller, job_id, "project.preflight")
    for name in ("executions/test/request.result.json", "events.jsonl", "state.json", "final-report.json"):
        content = (controller.store.directory(job_id) / name).read_text()
        for secret in ("sensitive-value", "private_column", "private_table", "/private/path", "test-user"):
            assert secret not in content


def test_regression_failure_projection_preserves_reference_not_rows():
    report = {"cases": [{"case_id": "QUERY.TEST", "status": "ERROR", "failure_type": "DATABASE_ERROR",
        "error": "password=secret", "steps": [{"id": "q1", "status": "ERROR", "error": "SELECT private FROM private_table", "result_rows": [["private data"]]}]}]}
    projected = failure_projection(report, "artifacts/jobs/test/regression.json")
    assert projected == [{"case_id": "QUERY.TEST", "step_id": "q1", "status": "ERROR", "failure_type": "DATABASE_ERROR",
        "safe_error_code": "QUERY_CASE_FAILED", "artifact_ref": "artifacts/jobs/test/regression.json"}]


def test_domain_error_returns_only_known_code():
    result = safe_worker_error(ValueError("RUNTIME_PROFILE_MISMATCH: host=private password=secret"))
    assert result["error_code"] == "RUNTIME_PROFILE_MISMATCH"
    assert "private" not in json.dumps(result) and "secret" not in json.dumps(result)


def test_real_stdio_mcp_create_and_inspect_does_not_hang(tmp_path):
    pytest.importorskip("mcp", reason="optional agent extra required for stdio integration")
    import asyncio
    import sys
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    async def run():
        code = "import sys; from xgtest.ai.controller import JobController; import xgtest.ai.mcp_server as app; app.controller=JobController(sys.argv[1]); app.server.run(transport='stdio')"
        async with stdio_client(StdioServerParameters(command=sys.executable, args=["-c", code, str(tmp_path)])) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                created = await session.call_tool("create_test_job", {"goal": "Verify bounded Git reads under stdio MCP", "intent": {"intent": "query.status"}})
                assert not created.isError
                job = json.loads(created.content[0].text)
                assert job["control_plane_layer_id"] and job["git_commit"] is None
                result = await session.call_tool("execute_test_action", {"job_id": job["job_id"], "request": {
                    "request_id": "inspect", "expected_revision": 1, "action": {"action": "project.inspect", "reason": "Exercise Git metadata subprocesses"}}})
                assert not result.isError
                checkpoint = json.loads(result.content[0].text)
                assert checkpoint["action_results"][0]["action"] == "project.inspect"
                assert checkpoint["blockers"] == ["RUNTIME_PROFILE_UNAVAILABLE"]
    asyncio.run(asyncio.wait_for(run(), timeout=25))
