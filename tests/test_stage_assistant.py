import asyncio
import json

import pytest
from fastapi.testclient import TestClient

from ai4ms.api.app import create_app
from ai4ms.inference.gateway import InferenceResponse
from ai4ms.services.models import (
    StageSuggestionDecisionRequest,
    StageSuggestionGenerateRequest,
    StageToolInvokeRequest,
)
from ai4ms.services.stage_assistant import (
    StageAssistantError,
    StageAssistantService,
)


class _SuggestionGateway:
    async def generate(
        self,
        _system_prompt: str,
        user_prompt: str,
    ) -> InferenceResponse:
        prompt = json.loads(user_prompt)
        assert prompt["project_context"]["current_stage"]["content"]
        return InferenceResponse(
            text=json.dumps(
                {
                    "summary": "当前课题需补强边界、反向证据和人工决定记录。",
                    "suggestions": [
                        {
                            "title": "明确企业样本边界",
                            "reason": "当前草稿没有说明企业规模与地区范围。",
                            "before": "研究对象：企业",
                            "after": "待研究者确认企业规模、地区和观察期。",
                            "target": "scope",
                            "tool_id": "project.asset.read",
                        },
                        {
                            "title": "补充反向检索",
                            "reason": "当前原创性判断缺少可推翻它的检索路径。",
                            "before": "反向检索：空",
                            "after": "加入可能否定候选空白的关键词组合。",
                            "target": "evidence_note",
                            "tool_id": "not.registered",
                        },
                        {
                            "title": "记录是否接受数据约束",
                            "reason": "下一阶段需要知道研究者接受了哪些可行性限制。",
                            "before": "人工决定：空",
                            "after": "待研究者填写接受或拒绝约束的理由。",
                            "target": "decision",
                            "tool_id": "",
                        },
                    ],
                },
                ensure_ascii=False,
            ),
            model="fake-suggestion-model",
            usage={"total_tokens": 321},
        )


def _project() -> dict:
    return {
        "project_id": "prj_assistant",
        "title": "AI 采用与企业创新",
        "initial_idea": "AI 采用如何影响企业创新？",
        "current_stage": "problem",
        "approvals": [],
        "data_assets": [],
        "stages": [
            {
                "key": "problem",
                "position": 0,
                "revision": 2,
                "content_hash": "problem-hash-2",
                "status": "needs_review",
                "content": {
                    "research_object": "企业",
                    "questions": ["AI 采用如何影响企业创新？"],
                },
                "readiness": {"percent": 67},
            },
            {
                "key": "literature",
                "position": 1,
                "revision": 0,
                "content_hash": None,
                "status": "not_started",
                "content": {"papers": [], "search_runs": []},
                "readiness": {"percent": 0},
            },
            {
                "key": "design",
                "position": 3,
                "revision": 1,
                "content_hash": "design-hash-1",
                "status": "needs_review",
                "content": {"primary_method_id": ""},
                "readiness": {"percent": 42},
            },
        ],
    }


def test_suggestions_are_generated_persisted_decided_and_invalidated(tmp_path):
    project = _project()
    service = StageAssistantService(
        tmp_path,
        gateway_factory=_SuggestionGateway,
    )

    generated = asyncio.run(
        service.generate_suggestions(
            project,
            "problem",
            StageSuggestionGenerateRequest(),
        )
    )

    assert generated["status"] == "current"
    assert generated["stage_revision"] == 2
    assert len(generated["suggestions"]) == 3
    assert generated["suggestions"][1]["tool_id"] == ""
    suggestion_id = generated["suggestions"][0]["suggestion_id"]

    decided = service.decide_suggestion(
        project,
        "problem",
        suggestion_id,
        StageSuggestionDecisionRequest(state="accepted", note="纳入草稿"),
    )
    assert decided["suggestions"][0]["state"] == "accepted"
    assert service.load_suggestions(project, "problem")["suggestions"][0]["decision_note"] == "纳入草稿"

    project["stages"][0]["revision"] = 3
    project["stages"][0]["content_hash"] = "problem-hash-3"
    assert service.load_suggestions(project, "problem")["status"] == "stale"
    with pytest.raises(StageAssistantError, match="最新阶段 revision"):
        service.decide_suggestion(
            project,
            "problem",
            suggestion_id,
            StageSuggestionDecisionRequest(state="rejected"),
        )

    project = _project()
    design_suggestions = asyncio.run(
        service.generate_suggestions(
            project,
            "design",
            StageSuggestionGenerateRequest(),
        )
    )
    assert design_suggestions["status"] == "current"
    project["stages"][0]["revision"] = 3
    project["stages"][0]["content_hash"] = "problem-hash-3"
    assert service.load_suggestions(project, "design")["status"] == "stale"


def test_registered_tools_execute_or_require_confirmation_and_are_audited(tmp_path):
    project = _project()
    service = StageAssistantService(tmp_path)

    read_run = asyncio.run(
        service.invoke_tool(
            project,
            "problem",
            StageToolInvokeRequest(tool_id="project.asset.read"),
            [],
        )
    )
    assert read_run["status"] == "completed"
    assert read_run["result"]["title"] == project["title"]

    write_run = asyncio.run(
        service.invoke_tool(
            project,
            "problem",
            StageToolInvokeRequest(tool_id="revision.patch"),
            [],
        )
    )
    assert write_run["status"] == "confirmation_required"

    audit_path = (
        tmp_path
        / project["project_id"]
        / "artifacts"
        / "tool-runs"
        / "problem"
        / f"{read_run['tool_run_id']}.json"
    )
    assert audit_path.exists()

    with pytest.raises(StageAssistantError, match="不是 problem 阶段注册工具"):
        asyncio.run(
            service.invoke_tool(
                project,
                "problem",
                StageToolInvokeRequest(tool_id="runner.submit"),
                [],
            )
        )


def test_stage_assistant_routes_expose_real_suggestions_and_tools(tmp_path):
    assistant = StageAssistantService(
        tmp_path / "projects",
        gateway_factory=_SuggestionGateway,
    )
    with TestClient(
        create_app(data_dir=tmp_path, stage_assistant=assistant)
    ) as client:
        created = client.post(
            "/api/v1/projects",
            json={
                "title": "AI 采用与企业创新",
                "initial_idea": "AI 采用如何影响企业创新？",
            },
        ).json()
        project_id = created["project_id"]
        saved = client.put(
            f"/api/v1/projects/{project_id}/stages/problem",
            json={
                "content": {
                    "initial_idea": "AI 采用如何影响企业创新？",
                    "research_object": "企业",
                    "unit_of_analysis": "企业年度",
                    "management_problem": "如何配置 AI 投资",
                    "scientific_question": "AI 采用如何影响企业创新？",
                    "research_lanes": ["causal"],
                    "candidate_gaps": ["边界条件尚待检索"],
                    "reverse_searches": ["AI adoption no innovation effect"],
                    "scope": {
                        "population": "企业",
                        "time": "待确认",
                        "geography": "待确认",
                        "stakeholders": ["管理者"],
                    },
                    "human_decisions": ["确认样本边界"],
                    "unknowns": ["可用数据"],
                },
                "change_reason": "保存课题草稿",
            },
        )
        assert saved.status_code == 200

        suggestions = client.post(
            f"/api/v1/projects/{project_id}/stages/problem/suggestions",
            json={"instruction": ""},
        )
        assert suggestions.status_code == 200
        assert len(suggestions.json()["suggestions"]) == 3

        tool_run = client.post(
            f"/api/v1/projects/{project_id}/stages/problem/tools/invoke",
            json={"tool_id": "project.asset.read", "query": ""},
        )
        assert tool_run.status_code == 200
        assert tool_run.json()["status"] == "completed"
