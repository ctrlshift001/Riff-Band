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


class _FakeAnalysisRunner:
    def status(self) -> dict:
        return {
            "available": True,
            "engine": "stata",
            "mode": "batch",
            "executable_name": "fake-stata",
            "version": "19",
            "edition": "MP",
            "license_mode": "user_byol",
            "license_confirmed": True,
            "max_concurrency": 1,
            "reason": "",
        }

    def preflight(self, project: dict, project_dir, request) -> dict:
        return {
            "status": "ready",
            "reason_code": "ready",
            "analysis_plan_revision": next(stage for stage in project["stages"] if stage["key"] == "identification")["revision"],
            "input_artifact_path": request.input_artifact_path,
            "checks": {"gate_passed": True},
            "issues": [],
        }

    async def submit(self, project: dict, project_dir, request) -> dict:
        return {
            "run_id": "run_api_test",
            "status": "succeeded",
            "reason_code": "completed",
            "requested_by": request.requested_by,
            "analysis_plan_revision": next(stage for stage in project["stages"] if stage["key"] == "identification")["revision"],
            "analysis_plan_hash": "plan_hash",
            "do_file_sha256": "a" * 64,
            "runner_profile": self.status(),
            "preflight": self.preflight(project, project_dir, request),
            "exit_code": 0,
            "output_artifacts": [{"path": "artifacts/runs/run_api_test/results.csv", "sha256": "b" * 64}],
            "manifest_path": "artifacts/runs/run_api_test/manifest.json",
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


def _valid_evidence_content() -> dict:
    return {
        "claims": [
            {
                "claim_id": "C1",
                "claim_text": "现有论文元数据支持 AI 采用与创新关系的候选文献综合判断。",
                "claim_type": "literature_synthesis",
                "status": "supported",
                "confidence": "medium",
                "scope": {"population_or_system": "企业", "time": "论文覆盖期", "geography": "论文覆盖地区", "boundary_conditions": ["仅为文献综合"]},
                "evidence": [{"evidence_id": "EV1", "evidence_type": "paper", "artifact_id": "paper_a", "locator": "title and metadata", "direction": "supports", "strength": "moderate"}],
                "assumptions": [],
                "counterevidence": [],
                "uncertainty_note": "尚无本地模型结果，不能作因果判断。",
                "robustness_check_ids": [],
                "mechanism_ids": [],
            }
        ],
        "mechanisms": [],
        "heterogeneity": [],
        "limitations": ["当前仅有论文元数据证据。"],
        "interpretation": "结论只覆盖文献综合，不包含本地因果估计。",
        "unknowns": ["本地估计结果"],
    }


def _valid_delivery_content() -> dict:
    return {
        "title": "AI 采用与企业创新研究报告",
        "executive_summary": "现有论文元数据支持候选关系判断，但尚无本地模型结果，因此不能形成因果结论。",
        "conclusions": [{"conclusion_id": "CON1", "statement": "当前只能形成 AI 采用与创新关系的有限文献综合结论。", "claim_ids": ["C1"], "evidence_ids": ["EV1"], "status": "supported", "scope_note": "限于现有论文覆盖范围。"}],
        "policy_implications": [{"implication_id": "POL1", "statement": "企业可继续评估 AI 采用，但应先验证数据和实际效果。", "audience": "企业管理者", "claim_ids": ["C1"], "conditions": ["完成本地数据验证"], "risk_note": "不能把文献关系直接解释为因果收益。"}],
        "outline": [
            {"section_id": "SEC1", "title": "研究问题", "purpose": "说明问题和范围。", "claim_ids": [], "evidence_ids": []},
            {"section_id": "SEC2", "title": "证据", "purpose": "展示可追溯文献证据。", "claim_ids": ["C1"], "evidence_ids": ["EV1"]},
            {"section_id": "SEC3", "title": "结论", "purpose": "给出有限结论和披露。", "claim_ids": ["C1"], "evidence_ids": ["EV1"]},
        ],
        "approved_claims": ["C1"],
        "reference_paper_ids": ["paper_a"],
        "references": [{"paper_id": "paper_a", "title": "Paper A", "authors": ["Li"]}],
        "limitations": ["没有本地模型结果。"],
        "reproducibility_notes": ["结论保留 claim_id 和 evidence_id。"],
        "disclosure": "报告为 AI 辅助草稿，最终内容由研究者审批。",
        "release_notes": "首次交付。",
        "unknowns": ["本地估计结果"],
        "exports": [],
        "visual_report_path": "",
        "research_package_path": "",
    }


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
    formulas = client.get("/api/v1/knowledge/formulas?q=双重差分&method_id=M06&limit=4").json()["items"]

    assert len(methods) == 4
    assert all(item["method_id"].startswith("M") for item in methods)
    assert len(sources) == 5
    assert all(item["source_id"].startswith("D") for item in sources)
    assert len(formulas) == 4
    assert all("formula_id" in item for item in formulas)


def test_analysis_runner_api_preflight_and_run_revision(tmp_path):
    client = TestClient(create_app(tmp_path, analysis_runner=_FakeAnalysisRunner()))
    project = _create_project(client)
    project_id = project["project_id"]

    locked = client.post(
        f"/api/v1/projects/{project_id}/stages/analysis/preflight",
        json={"input_artifact_path": "input.dta"},
    )
    assert locked.status_code == 409

    for index, stage_key in enumerate(("problem", "literature", "theory", "design", "data", "identification")):
        if index:
            drafted = client.post(
                f"/api/v1/projects/{project_id}/stages/{stage_key}/draft",
                json={"generation_mode": "template"},
            )
            assert drafted.status_code == 200
        project = _approve(client, project_id, stage_key)

    runner = client.get("/api/v1/runners/stata")
    assert runner.status_code == 200
    assert runner.json()["available"] is True

    preflight = client.post(
        f"/api/v1/projects/{project_id}/stages/analysis/preflight",
        json={"input_artifact_path": "input.dta"},
    )
    assert preflight.status_code == 200
    assert preflight.json()["status"] == "ready"

    submitted = client.post(
        f"/api/v1/projects/{project_id}/stages/analysis/runs",
        json={"input_artifact_path": "input.dta"},
    )
    assert submitted.status_code == 200
    stage = submitted.json()["stages"][6]
    assert stage["revision"] == 1
    assert stage["content"]["runs"][0]["run_id"] == "run_api_test"
    assert stage["content"]["results"][0]["status"] == "succeeded"


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

    for index, stage_key in enumerate(stage_keys[:8]):
        if index > 0:
            drafted = client.post(
                f"/api/v1/projects/{project_id}/stages/{stage_key}/draft",
                json={"instruction": f"Create {stage_key} structure"},
            )
            assert drafted.status_code == 200
            assert drafted.json()["stages"][index]["revision"] == 1
        if stage_key == "literature":
            current = client.get(f"/api/v1/projects/{project_id}/stages/literature").json()["content"]
            current["papers"] = [{"paper_id": "paper_a", "title": "Paper A", "authors": ["Li"], "year": 2025}]
            saved = client.put(
                f"/api/v1/projects/{project_id}/stages/literature",
                json={"content": current, "change_reason": "Add traceable paper"},
            )
            assert saved.status_code == 200
        project = _approve(client, project_id, stage_key)

    evidence = client.put(
        f"/api/v1/projects/{project_id}/stages/evidence",
        json={"content": _valid_evidence_content(), "change_reason": "Build Claim-Evidence graph"},
    )
    assert evidence.status_code == 200
    project = _approve(client, project_id, "evidence")

    delivery = client.put(
        f"/api/v1/projects/{project_id}/stages/delivery",
        json={"content": _valid_delivery_content(), "change_reason": "Prepare delivery"},
    )
    assert delivery.status_code == 200
    exported = client.post(f"/api/v1/projects/{project_id}/stages/delivery/export")
    assert exported.status_code == 200
    export_record = exported.json()["stages"][9]["content"]["exports"][-1]
    report = client.get(f"/api/v1/projects/{project_id}/exports/{export_record['export_id']}/report")
    package = client.get(f"/api/v1/projects/{project_id}/exports/{export_record['export_id']}/package")
    assert report.status_code == 200
    assert "Claim-Evidence" in report.text
    assert report.headers["content-disposition"].startswith("inline")
    assert package.status_code == 200
    assert package.headers["content-type"] == "application/zip"
    project = _approve(client, project_id, "delivery")

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
