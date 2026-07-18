from __future__ import annotations

from fastapi.testclient import TestClient

from api.app import create_app


def _create_project(client: TestClient) -> dict:
    response = client.post(
        "/api/v1/projects",
        json={
            "title": "AI adoption and firm innovation",
            "initial_idea": "How does AI adoption affect firm innovation?",
        },
    )
    assert response.status_code == 201
    return response.json()


def _approve(client: TestClient, project_id: str, stage_key: str) -> dict:
    response = client.post(
        f"/api/v1/projects/{project_id}/stages/{stage_key}/decisions",
        json={"decision": "approve", "reason": "Reviewed", "actor_type": "human"},
    )
    assert response.status_code == 200
    return response.json()


def test_health_meta_and_web_assets(tmp_path):
    client = TestClient(create_app(tmp_path))

    assert client.get("/healthz").json()["status"] == "ok"
    stages = client.get("/api/v1/meta/stages").json()["items"]
    assert [stage["position"] for stage in stages] == list(range(1, 10))
    assert stages[-1]["artifact_type"] == "ResearchPackage"
    profile = client.get("/api/v1/meta/domain-profile").json()
    assert profile["key"] == "management_science"
    assert profile["name"] == "管理科学"
    assert client.get("/openapi.json").json()["info"]["title"] == "AI4MS 科研工作台 API"

    page = client.get("/")
    assert page.status_code == 200
    assert "AI4MS 科研工作台" in page.text
    assert client.get("/assets/app.js").status_code == 200


def test_project_stage_gate_and_revision_flow(tmp_path):
    client = TestClient(create_app(tmp_path))
    project = _create_project(client)
    project_id = project["project_id"]

    assert project["current_stage"] == "idea"
    assert project["stages"][0]["revision"] == 1
    assert project["stages"][1]["status"] == "not_started"
    assert project["stages"][0]["content_hash"]

    locked = client.post(
        f"/api/v1/projects/{project_id}/stages/literature/draft",
        json={"instruction": ""},
    )
    assert locked.status_code == 409
    assert locked.json()["error"]["code"] == "stage_locked"

    project = _approve(client, project_id, "idea")
    assert project["current_stage"] == "literature"
    assert project["stages"][1]["status"] == "in_progress"

    drafted = client.post(
        f"/api/v1/projects/{project_id}/stages/literature/draft",
        json={"instruction": "Build query blocks"},
    )
    assert drafted.status_code == 200
    project = drafted.json()
    literature = project["stages"][1]
    assert literature["revision"] == 1
    assert literature["content"]["draft_source"] == "structure_template"
    assert literature["status"] == "needs_review"

    invalid_actor = client.post(
        f"/api/v1/projects/{project_id}/stages/literature/decisions",
        json={"decision": "approve", "actor_type": "agent"},
    )
    assert invalid_actor.status_code == 422


def test_upstream_change_invalidates_downstream_and_persists(tmp_path):
    client = TestClient(create_app(tmp_path))
    project = _create_project(client)
    project_id = project["project_id"]
    project = _approve(client, project_id, "idea")

    drafted = client.post(
        f"/api/v1/projects/{project_id}/stages/literature/draft",
        json={"instruction": ""},
    )
    assert drafted.status_code == 200
    project = _approve(client, project_id, "literature")
    assert project["stages"][1]["status"] == "approved"
    assert project["stages"][2]["status"] == "in_progress"

    changed = client.put(
        f"/api/v1/projects/{project_id}/stages/idea",
        json={
            "content": {"research_object": "platform firms", "questions": ["What changes?"]},
            "change_reason": "Narrowed research object",
            "author_type": "human",
        },
    )
    assert changed.status_code == 200
    project = changed.json()
    assert project["current_stage"] == "idea"
    assert project["stages"][0]["revision"] == 2
    assert project["stages"][1]["status"] == "needs_review"
    assert project["stages"][2]["status"] == "not_started"
    assert len(project["approvals"]) == 2

    restarted = TestClient(create_app(tmp_path))
    persisted = restarted.get(f"/api/v1/projects/{project_id}")
    assert persisted.status_code == 200
    assert persisted.json()["stages"][0]["content"]["research_object"] == "platform firms"


def test_validation_and_missing_resources(tmp_path):
    client = TestClient(create_app(tmp_path))

    assert client.post("/api/v1/projects", json={"title": "", "initial_idea": "x"}).status_code == 422
    missing = client.get("/api/v1/projects/prj_missing")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "project_not_found"

    project = _create_project(client)
    unknown_stage = client.get(f"/api/v1/projects/{project['project_id']}/stages/unknown")
    assert unknown_stage.status_code == 404
    assert unknown_stage.json()["error"]["code"] == "stage_not_found"
