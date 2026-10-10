"""Test Product Layer: mission contract, mission<->job composition, and job_logic identity."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from xgtest.ai.controller import JobController
from xgtest.product.contracts import TestMission, strategy_estimate
from xgtest.product.mission_service import MissionService


@pytest.fixture
def service(tmp_path):
    return MissionService(tmp_path, JobController(tmp_path))


DEFINITION = {"name": "Query 语义正确性标准测试", "purpose": "验证 Query 模块核心语义正确性",
    "features": ["join"], "strategy": "STANDARD", "data_scale": "SMALL",
    "risk_focus": ["null", "duplicate"], "excluded_scope": ["performance", "concurrency"]}


def test_mission_contract_validates_and_estimates():
    mission = TestMission.model_validate({**DEFINITION, "mission_id": "0" * 32, "state": "READY"})
    assert mission.state == "READY" and mission.module == "query" and mission.features == ["join"]
    # Filter is now a modelled feature and is accepted.
    assert TestMission.model_validate({**DEFINITION, "mission_id": "0" * 32, "features": ["filter"]}).features == ["filter"]
    assert strategy_estimate("STANDARD") == {"strategy": "STANDARD", "case_min": 150, "case_max": 300,
        "sql_min": 150, "sql_max": 600, "unit": "cases"}
    # A feature the Core cannot model yet is still rejected; the fail-closed rule stays live.
    with pytest.raises(ValueError, match="MISSION_FEATURE_UNAVAILABLE"):
        TestMission.model_validate({**DEFINITION, "mission_id": "0" * 32, "features": ["window"]})
    with pytest.raises(ValueError, match="MISSION_FEATURE_DUPLICATE"):
        TestMission.model_validate({**DEFINITION, "mission_id": "0" * 32, "features": ["join", "join"]})


def test_mission_create_start_links_a_job_and_maps_state(service):
    created = service.create(DEFINITION)
    mission_id = created["mission"]["mission_id"]
    assert created["state"] == "READY" and created["mission"]["job_id"] is None
    assert created["tested_scope"] == ["join"] and created["untested_scope"] == ["performance", "concurrency"]
    started = service.start(mission_id)
    assert started["state"] == "RUNNING"
    job_id = started["mission"]["job_id"]
    assert job_id is not None
    # The mission links to a real durable job; the product layer adds no new truth.
    assert service.controller.store.load(job_id).intent.intent == "query.full_test"
    assert [item["mission_id"] for item in service.store.list()] == [mission_id]


def test_ai_summary_presents_only_recorded_ai_output(service):
    created = service.create(DEFINITION)
    mission_id = created["mission"]["mission_id"]
    # Before a job exists there is no AI output, and the view says so rather than inventing one.
    empty = service.ai_summary(mission_id)
    assert empty["available"] is False and empty["note"]
    started = service.start(mission_id)
    job_id = started["mission"]["job_id"]
    # With a job but no AI artifacts recorded yet, the counts are honestly zero.
    summary = service.view(mission_id)["ai_summary"]
    assert summary["available"] is True and summary["job_id"] == job_id
    assert summary["advisory_only"] is True and summary["does_not_change_core"] is True
    assert summary["generated_candidate_count"] == 0 and summary["technical_review_count"] == 0
    assert summary["summary"] is None and summary["failure_analysis"] is None


def test_ai_summary_reflects_recorded_explanation_and_failure(service):
    from xgtest.ai.models import ActionResult, FailureAnalysis
    mission_id = service.create(DEFINITION)["mission"]["mission_id"]
    job_id = service.start(mission_id)["mission"]["job_id"]
    # A failure analysis is only recorded after a real blocked/failed result (Core invariant).
    controller = service.controller
    job = controller.store.load(job_id)
    blocked = ActionResult(action="project.preflight", status="BLOCKED", blockers=["DATABASE_NETWORK_UNREACHABLE"])
    with controller.store.lock(job_id):
        controller.store.save(job.model_copy(update={"state": "BLOCKED", "action_results": [blocked]}), "ACTION_FINISHED")
    controller.annotate(job_id, controller.store.load(job_id).revision, "本轮只做了环境预检，数据库不可达。",
        {"category": "RUNTIME_ENVIRONMENT", "failure_summary": "数据库端口连接超时",
         "likely_area": "目标数据库主机不可达", "recommended_action": "确认端口连通后 resume", "confidence": 0.9})
    summary = service.ai_summary(mission_id)
    assert summary["summary"] == "本轮只做了环境预检，数据库不可达。"
    assert summary["failure_analysis"]["category"] == "RUNTIME_ENVIRONMENT"
    assert summary["failure_analysis"]["confidence"] == 0.9
    # Presentation is a copy of the recorded artifact; it does not alter the job.
    stored = controller.store.load(job_id)
    assert stored.failure_analysis == FailureAnalysis.model_validate(summary["failure_analysis"])


def test_filter_mission_starts_a_job_scoped_to_filter(service):
    created = service.create({**DEFINITION, "features": ["filter"]})
    mission_id = created["mission"]["mission_id"]
    assert created["tested_scope"] == ["filter"]
    started = service.start(mission_id)
    job_id = started["mission"]["job_id"]
    job = service.controller.store.load(job_id)
    # The intent stays query.full_test, but the feature selects the job scope.
    assert job.intent.intent == "query.full_test" and job.intent.features == ["filter"]
    assert service.controller.services(job_id)[0].ctx.scope.feature == "filter"
    # The JOIN default is untouched: a default job still scopes to join.
    join_job = service.controller.create("default", {"intent": "query.status"})["job_id"]
    assert service.controller.services(join_job)[0].ctx.scope.feature == "join"


def test_aggregate_mission_starts_a_job_scoped_to_aggregate(service):
    created = service.create({**DEFINITION, "features": ["aggregate"]})
    mission_id = created["mission"]["mission_id"]
    assert created["tested_scope"] == ["aggregate"]
    job_id = service.start(mission_id)["mission"]["job_id"]
    assert service.controller.store.load(job_id).intent.features == ["aggregate"]
    assert service.controller.services(job_id)[0].ctx.scope.feature == "aggregate"


def test_subquery_mission_starts_a_job_scoped_to_subquery(service):
    created = service.create({**DEFINITION, "features": ["subquery"]})
    mission_id = created["mission"]["mission_id"]
    assert created["tested_scope"] == ["subquery"]
    job_id = service.start(mission_id)["mission"]["job_id"]
    assert service.controller.store.load(job_id).intent.features == ["subquery"]
    assert service.controller.services(job_id)[0].ctx.scope.feature == "subquery"


def test_mission_start_requires_ready(service):
    mission_id = service.create(DEFINITION)["mission"]["mission_id"]
    service.start(mission_id)
    with pytest.raises(ValueError, match="MISSION_NOT_READY"):
        service.start(mission_id)


def test_mission_cannot_bypass_single_mutable_job_policy(service):
    service.start(service.create(DEFINITION)["mission"]["mission_id"])
    second = service.create({**DEFINITION, "name": "第二个任务"})["mission"]["mission_id"]
    # A second full_test is refused by the same durable-job policy, not by the product layer.
    with pytest.raises(ValueError, match="MUTABLE_JOB_ALREADY_EXISTS"):
        service.start(second)


def test_missions_web_api_create_list_get_start(tmp_path):
    from fastapi.testclient import TestClient
    from xgtest.web.app import create_app
    client = TestClient(create_app(SimpleNamespace(project_root=tmp_path)))
    created = client.post("/api/missions", json=DEFINITION)
    assert created.status_code == 200, created.text
    mission_id = created.json()["mission"]["mission_id"]
    assert client.get("/api/missions").json()["items"][0]["mission_id"] == mission_id
    assert client.get(f"/api/missions/{mission_id}").json()["state"] == "READY"
    assert client.post(f"/api/missions/{mission_id}/start").json()["state"] == "RUNNING"
    assert client.get("/api/missions/invalid").status_code == 400
    assert client.post("/api/missions", json={**DEFINITION, "features": ["window"]}).status_code == 400


def test_scope_matrix_separates_requirement_case_and_execution_counts():
    from xgtest.web.service import QueryReadService
    matrix = QueryReadService.from_environment().scope_matrix("pairwise")
    totals = matrix["totals"]
    # Same Core numbers as coverage(): the product view must not recompute them.
    coverage = QueryReadService.from_environment().coverage("pairwise")
    assert totals["requirements"] == coverage["required"]
    assert totals["covered"] == coverage["active_covered"]
    assert totals["missing"] == coverage["active_missing"]
    # Requirement, case and execution counts are distinct scales and must not be conflated.
    assert totals["cases"] < totals["requirements"]
    assert totals["executions"] >= totals["cases"]
    assert set(matrix["count_semantics"]) == {"requirements", "cases", "executions"}
    assert matrix["rows"] and all(row["status"] in {"covered", "partial", "missing"} for row in matrix["rows"])
    # Row coverage never exceeds its requirements, and a fully covered row is marked covered.
    assert all(0 <= row["covered"] <= row["required"] for row in matrix["rows"])
    # Tested / untested scope partitions the modelled space: a value is in exactly one side.
    tested_keys = {(item["dimension"], item["value"]) for item in matrix["tested_scope"]}
    untested_keys = {(item["dimension"], item["value"]) for item in matrix["untested_scope"]}
    assert not (tested_keys & untested_keys)
    assert tested_keys | untested_keys == {(row["dimension"], row["value"]) for row in matrix["rows"]}
    assert all(item["label"] for item in (*matrix["tested_scope"], *matrix["untested_scope"]))
    # The verdict keeps "defined scope" and "module" separate so PASS is never misread.
    assert set(matrix["scope_verdict"]) == {"defined_scope", "module"}
    assert matrix["scope_verdict"]["module"] == "模块全量：未完整（MODULE_FULL_INCOMPLETE）"
    with pytest.raises(ValueError, match="COVERAGE_STRATEGY_UNSUPPORTED"):
        QueryReadService.from_environment().scope_matrix("nope")


def test_scope_matrix_is_exposed_over_http():
    from fastapi.testclient import TestClient
    from xgtest.web.app import create_app
    client = TestClient(create_app())
    response = client.get("/api/scope-matrix?strategy=pairwise")
    assert response.status_code == 200
    body = response.json()
    assert set(body["totals"]) == {"requirements", "covered", "missing", "cases", "executions"}
    assert body["strategy"] == "pairwise"
    assert client.get("/api/scope-matrix?strategy=nope").status_code == 400


def test_case_origin_explains_why_and_where_a_case_came_from():
    from xgtest.web.service import QueryReadService
    service = QueryReadService.from_environment()
    items = service.list_candidates()["items"]
    if not items:
        pytest.skip("no candidates in the active workspace")
    # The list leads with the semantic path and a source label, not a bare id.
    assert all(item["path_summary"] and item["source_label"] in {"AI 生成", "人工定义"} for item in items)
    detail = service.get_candidate(items[0]["case_id"])
    origin = detail["origin"]
    assert origin["reason"] and origin["source"]
    assert origin["path"] and all(step["label"] and step["dimension"] for step in origin["path"])
    # A template-generated case must expose its provenance and be labelled as AI generated.
    if origin["source_detail"]:
        assert origin["source"] == "AI 生成"
        assert {"generator", "template_id", "strategy"} <= set(origin["source_detail"])


def test_job_logic_identity_is_narrower_than_ui_and_covers_workflow():
    from xgtest.core.contract_set import build_contract_descriptor
    with __import__("tempfile").TemporaryDirectory() as temporary:
        root = Path(temporary)
        for relative, content in {
            "webui/src/views/JobDetailView.vue": "display = 1\n",
            "src/xgtest/web/app.py": "route = 1\n",
            "src/xgtest/product/contracts.py": "mission = 1\n",
            "src/xgtest/generator/package.py": "gate = 1\n",
            "src/xgtest/ai/controller.py": "loop = 1\n",
        }.items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        baseline = build_contract_descriptor(root)
        (root / "webui/src/views/JobDetailView.vue").write_text("display = 2\n")
        (root / "src/xgtest/web/app.py").write_text("route = 2\n")
        after_ui = build_contract_descriptor(root)
        # Display-only changes must not touch job logic, but do move the broad control plane.
        assert after_ui["layers"]["mission_logic"]["id"] == baseline["layers"]["mission_logic"]["id"]
        assert after_ui["layers"]["control_plane"]["id"] != baseline["layers"]["control_plane"]["id"]
        (root / "src/xgtest/product/contracts.py").write_text("mission = 2\n")
        (root / "src/xgtest/generator/package.py").write_text("gate = 2\n")
        after_logic = build_contract_descriptor(root)
        # Workflow changes (product layer and governance) must move job logic.
        assert after_logic["layers"]["mission_logic"]["id"] != baseline["layers"]["mission_logic"]["id"]
