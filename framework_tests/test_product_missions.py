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
    assert strategy_estimate("STANDARD") == {"strategy": "STANDARD", "case_min": 150, "case_max": 300,
        "sql_min": 150, "sql_max": 600, "unit": "cases"}
    # The Core cannot model these yet; a mission must not claim coverage it cannot deliver.
    with pytest.raises(ValueError, match="MISSION_FEATURE_UNAVAILABLE"):
        TestMission.model_validate({**DEFINITION, "mission_id": "0" * 32, "features": ["filter"]})
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
    assert client.post("/api/missions", json={**DEFINITION, "features": ["filter"]}).status_code == 400


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
