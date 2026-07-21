from __future__ import annotations

import sqlite3

from fastapi.testclient import TestClient

from ai4ms.api.app import create_app


class _FakeStageGeneration:
    async def generate(self, project: dict, stage_key: str, instruction: str = "") -> dict:
        return {
            "initial_idea": project["initial_idea"],
            "research_object": "platform firms",
            "generation": {
                "mode": "model",
                "prompt_id": f"test.{stage_key}",
                "prompt_version": "test",
                "model": "fake-model",
                "instruction": instruction,
            },
        }


class _FakeLiteratureSearch:
    async def search(self, project_id: str, stage_content: dict, request) -> dict:
        assert project_id
        assert stage_content["query_blocks"]
        return {
            "search_id": "search_api_test",
            "searched_at": "2026-07-21T00:00:00+00:00",
            "status": "complete",
            "queries": ["AI adoption"],
            "backends": list(request.backends),
            "counts": {"identified": 2, "deduplicated": 1},
            "papers": [{"paper_id": "paper_a", "title": "Paper A"}],
            "source_runs": [{"backend": "openalex", "success": True, "record_count": 1}],
            "snapshot_path": "artifacts/literature/search_api_test.json",
        }


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
    assert [stage["position"] for stage in stages] == list(range(1, 11))
    assert [stage["code"] for stage in stages] == [f"S{index}" for index in range(10)]
    assert stages[-1]["artifact_type"] == "ResearchPackage"
    profile = client.get("/api/v1/meta/domain-profile").json()
    assert profile["key"] == "management_science"
    assert profile["name"] == "管理科学"
    inference = client.get("/api/v1/meta/inference")
    assert inference.status_code == 200
    assert set(inference.json()) == {"configured", "model", "reason"}
    assert "api_key" not in inference.text.lower()
    assert client.get("/openapi.json").json()["info"]["title"] == "AI4MS 科研工作台 API"

    page = client.get("/")
    assert page.status_code == 200
    assert "AI4MS 科研工作台" in page.text
    assert client.get("/assets/app.js").status_code == 200


def test_project_stage_gate_and_revision_flow(tmp_path):
    client = TestClient(create_app(tmp_path))
    project = _create_project(client)
    project_id = project["project_id"]

    assert project["current_stage"] == "problem"
    assert project["stages"][0]["revision"] == 1
    assert project["stages"][1]["status"] == "not_started"
    assert project["stages"][0]["content_hash"]

    locked = client.post(
        f"/api/v1/projects/{project_id}/stages/literature/draft",
        json={"instruction": ""},
    )
    assert locked.status_code == 409
    assert locked.json()["error"]["code"] == "stage_locked"

    project = _approve(client, project_id, "problem")
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


def test_model_draft_is_saved_as_an_agent_revision(tmp_path):
    client = TestClient(create_app(tmp_path, stage_generation=_FakeStageGeneration()))
    project = _create_project(client)

    response = client.post(
        f"/api/v1/projects/{project['project_id']}/stages/problem/draft",
        json={"instruction": "clarify the unit", "generation_mode": "model"},
    )

    assert response.status_code == 200
    stage = response.json()["stages"][0]
    assert stage["revision"] == 2
    assert stage["author_type"] == "agent"
    assert stage["content"]["generation"]["model"] == "fake-model"
    assert stage["content"]["generation"]["instruction"] == "clarify the unit"


def test_literature_search_endpoint_saves_papers_and_run_metadata(tmp_path):
    client = TestClient(create_app(tmp_path, literature_search=_FakeLiteratureSearch()))
    project = _create_project(client)
    project_id = project["project_id"]
    _approve(client, project_id, "problem")
    client.put(
        f"/api/v1/projects/{project_id}/stages/literature",
        json={
            "content": {"query_blocks": [{"query_en": "AI adoption"}]},
            "change_reason": "search plan",
        },
    )

    response = client.post(
        f"/api/v1/projects/{project_id}/stages/literature/search",
        json={"backends": ["openalex"]},
    )

    assert response.status_code == 200
    stage = response.json()["stages"][1]
    assert stage["author_type"] == "agent"
    assert stage["content"]["papers"][0]["paper_id"] == "paper_a"
    assert stage["content"]["search_runs"][0]["snapshot_path"].endswith("search_api_test.json")


def test_knowledge_registry_endpoints_expose_compact_candidates(tmp_path):
    client = TestClient(create_app(tmp_path))

    methods = client.get("/api/v1/knowledge/methods?goal=causal&limit=4").json()["items"]
    sources = client.get("/api/v1/knowledge/data-sources?q=企业专利&limit=5").json()["items"]

    assert len(methods) == 4
    assert all(item["method_id"].startswith("M") for item in methods)
    assert len(sources) == 5
    assert all(item["source_id"].startswith("D") for item in sources)


def test_upstream_change_invalidates_downstream_and_persists(tmp_path):
    client = TestClient(create_app(tmp_path))
    project = _create_project(client)
    project_id = project["project_id"]
    project = _approve(client, project_id, "problem")

    drafted = client.post(
        f"/api/v1/projects/{project_id}/stages/literature/draft",
        json={"instruction": ""},
    )
    assert drafted.status_code == 200
    project = _approve(client, project_id, "literature")
    assert project["stages"][1]["status"] == "approved"
    assert project["stages"][2]["status"] == "in_progress"

    changed = client.put(
        f"/api/v1/projects/{project_id}/stages/problem",
        json={
            "content": {"research_object": "platform firms", "questions": ["What changes?"]},
            "change_reason": "Narrowed research object",
            "author_type": "human",
        },
    )
    assert changed.status_code == 200
    project = changed.json()
    assert project["current_stage"] == "problem"
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


def test_complete_s0_to_s9_flow(tmp_path):
    client = TestClient(create_app(tmp_path))
    project = _create_project(client)
    project_id = project["project_id"]
    stage_keys = [stage["key"] for stage in project["stages"]]

    for index, stage_key in enumerate(stage_keys):
        if index > 0:
            drafted = client.post(
                f"/api/v1/projects/{project_id}/stages/{stage_key}/draft",
                json={"instruction": f"Create {stage_key} structure"},
            )
            assert drafted.status_code == 200
            assert drafted.json()["stages"][index]["revision"] == 1
        project = _approve(client, project_id, stage_key)

    assert project["status"] == "completed"
    assert project["current_stage"] == "delivery"
    assert project["progress"] == {"approved": 10, "total": 10}
    assert all(stage["status"] == "approved" for stage in project["stages"])


def test_legacy_nine_stage_database_is_migrated_without_losing_revisions(tmp_path):
    client = TestClient(create_app(tmp_path))
    project = _create_project(client)
    project_id = project["project_id"]
    db_path = tmp_path / "ai4ms.db"

    with sqlite3.connect(db_path) as conn:
        renames = (
            ("analysis", "run"),
            ("identification", "analysis"),
            ("theory", "topic"),
            ("problem", "idea"),
        )
        for new_key, old_key in renames:
            conn.execute(
                "UPDATE stage_revisions SET stage_key = ? WHERE project_id = ? AND stage_key = ?",
                (old_key, project_id, new_key),
            )
            conn.execute(
                "UPDATE approval_events SET stage_key = ? WHERE project_id = ? AND stage_key = ?",
                (old_key, project_id, new_key),
            )
            conn.execute(
                "UPDATE stage_states SET stage_key = ? WHERE project_id = ? AND stage_key = ?",
                (old_key, project_id, new_key),
            )
        conn.execute(
            "DELETE FROM stage_states WHERE project_id = ? AND stage_key = 'robustness'",
            (project_id,),
        )
        conn.execute(
            "UPDATE projects SET current_stage = 'idea' WHERE project_id = ?",
            (project_id,),
        )

    migrated = TestClient(create_app(tmp_path)).get(f"/api/v1/projects/{project_id}")
    assert migrated.status_code == 200
    payload = migrated.json()
    assert payload["current_stage"] == "problem"
    assert [stage["key"] for stage in payload["stages"]] == [
        "problem",
        "literature",
        "theory",
        "design",
        "data",
        "identification",
        "analysis",
        "robustness",
        "evidence",
        "delivery",
    ]
    assert payload["stages"][0]["revision"] == 1
    assert payload["stages"][0]["content"]["initial_idea"]
    assert payload["stages"][7]["revision"] == 0
