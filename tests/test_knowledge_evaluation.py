import asyncio
import json
import time

import pytest
from fastapi.testclient import TestClient

from ai4ms.api.app import create_app
from ai4ms.inference.gateway import InferenceResponse
from ai4ms.knowledge import (
    KnowledgeEvaluationOutputError,
    KnowledgeEvaluationService,
)
from ai4ms.services.models import KnowledgeEvaluationRequest


class _FakeGateway:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    async def generate(
        self, system_prompt: str, user_prompt: str
    ) -> InferenceResponse:
        self.calls.append((system_prompt, user_prompt))
        prompt = json.loads(user_prompt)
        kind = prompt["candidate_kind"]
        assessments = [
            {
                "candidate_id": candidate_id,
                "score": 84 if kind == "methods" else 79,
                "rationale": (
                    "与当前研究问题和候选设计较匹配。"
                    if kind == "methods"
                    else "可表达候选模型，但尚未冻结变量口径。"
                ),
                "missing_information": ["固定效应层级" if kind == "methods" else "变量定义"],
            }
            for candidate_id in prompt["required_candidate_ids"]
        ]
        return InferenceResponse(
            text=json.dumps(
                {
                    "methods": assessments if kind == "methods" else [],
                    "formulas": assessments if kind == "formulas" else [],
                    "summary": "分数为当前输入下的相对适配评估。",
                },
                ensure_ascii=False,
            ),
            model="fake-model",
            usage={"total_tokens": 123},
        )


def _project() -> dict:
    return {
        "project_id": "prj_eval",
        "title": "AI 采用与企业创新",
        "initial_idea": "AI 采用如何影响企业创新？",
        "stages": [
            {
                "key": "problem",
                "revision": 1,
                "content": {"questions": ["AI 采用如何影响企业创新？"]},
            },
            {
                "key": "literature",
                "revision": 0,
                "content": {"papers": []},
            },
            {"key": "theory", "revision": 0, "content": {}},
            {"key": "design", "revision": 0, "content": {}},
            {"key": "data", "revision": 0, "content": {}},
        ],
    }


def test_knowledge_scores_are_model_generated_persisted_and_invalidated(tmp_path):
    gateway = _FakeGateway()
    service = KnowledgeEvaluationService(
        tmp_path, gateway_factory=lambda: gateway
    )
    project = _project()
    request = KnowledgeEvaluationRequest(
        methods=[
            {
                "candidate_id": "M01",
                "name": "面板固定效应",
                "description": "控制不可观测时间不变异质性。",
                "assumptions": ["严格外生性"],
            }
        ],
        formulas=[
            {
                "candidate_id": "F01",
                "name": "双向固定效应式",
                "description": "企业和时间固定效应模型。",
                "assumptions": ["误差结构可处理"],
            }
        ],
    )

    evaluated = asyncio.run(service.evaluate(project, request))

    assert evaluated["status"] == "current"
    assert evaluated["model"] == "fake-model"
    assert evaluated["methods"][0]["score"] == 84
    assert evaluated["formulas"][0]["score"] == 79
    assert gateway.calls
    assert "不是成功概率" in gateway.calls[0][0]
    assert service.load(project)["status"] == "current"

    project["stages"][0]["revision"] = 2
    assert service.load(project)["status"] == "stale"


class _MissingCandidateGateway:
    async def generate(
        self, _system_prompt: str, _user_prompt: str
    ) -> InferenceResponse:
        return InferenceResponse(
            text=json.dumps(
                {"methods": [], "formulas": [], "summary": "漏项响应"},
                ensure_ascii=False,
            ),
            model="incomplete-model",
            usage={},
        )


class _ConcurrentGateway(_FakeGateway):
    def __init__(self) -> None:
        super().__init__()
        self.active = 0
        self.max_active = 0

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> InferenceResponse:
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        try:
            await asyncio.sleep(0.02)
            return await super().generate(system_prompt, user_prompt)
        finally:
            self.active -= 1


def test_knowledge_evaluation_rejects_silent_candidate_omissions(tmp_path):
    service = KnowledgeEvaluationService(
        tmp_path,
        gateway_factory=_MissingCandidateGateway,
    )
    request = KnowledgeEvaluationRequest(
        methods=[
            {
                "candidate_id": "M01",
                "name": "面板固定效应",
                "description": "控制不可观测时间不变异质性。",
                "assumptions": ["严格外生性"],
            }
        ],
    )

    with pytest.raises(KnowledgeEvaluationOutputError, match="M01"):
        asyncio.run(service.evaluate(_project(), request))


def test_standard_library_evaluation_uses_one_batch_per_candidate_kind(
    tmp_path,
    monkeypatch,
):
    monkeypatch.delenv("AI4MS_KNOWLEDGE_EVAL_BATCH_SIZE", raising=False)
    gateway = _ConcurrentGateway()
    service = KnowledgeEvaluationService(
        tmp_path,
        gateway_factory=lambda: gateway,
    )
    request = KnowledgeEvaluationRequest(
        methods=[
            {
                "candidate_id": f"M{index:02d}",
                "name": f"候选方法 {index}",
                "description": "用于验证标准方法库的完整评估。",
                "assumptions": [],
            }
            for index in range(1, 17)
        ],
        formulas=[
            {
                "candidate_id": f"F{index:02d}",
                "name": f"候选公式 {index}",
                "description": "用于验证标准公式库的完整评估。",
                "assumptions": [],
            }
            for index in range(1, 13)
        ],
    )

    evaluated = asyncio.run(service.evaluate(_project(), request))

    assert len(evaluated["methods"]) == 16
    assert len(evaluated["formulas"]) == 12
    assert evaluated["usage"]["batch_calls"] == 2
    assert len(gateway.calls) == 2
    assert gateway.max_active == 2


def test_knowledge_evaluation_background_job_can_be_polled(tmp_path):
    evaluator = KnowledgeEvaluationService(
        tmp_path / "projects",
        gateway_factory=_FakeGateway,
    )
    with TestClient(
        create_app(data_dir=tmp_path, knowledge_evaluation=evaluator)
    ) as client:
        project = client.post(
            "/api/v1/projects",
            json={
                "title": "AI 采用与企业创新",
                "initial_idea": "AI 采用如何影响企业创新？",
            },
        ).json()
        response = client.post(
            f"/api/v1/projects/{project['project_id']}/knowledge/evaluation/jobs",
            json={
                "methods": [
                    {
                        "candidate_id": "M01",
                        "name": "面板固定效应",
                        "description": "控制不可观测时间不变异质性。",
                        "assumptions": ["严格外生性"],
                    }
                ],
                "formulas": [
                    {
                        "candidate_id": "F01",
                        "name": "双向固定效应式",
                        "description": "企业和时间固定效应模型。",
                        "assumptions": [],
                    }
                ],
            },
        )
        assert response.status_code == 202
        job = response.json()

        for _ in range(50):
            job = client.get(
                f"/api/v1/projects/{project['project_id']}/knowledge/evaluation/jobs/{job['job_id']}"
            ).json()
            if job["status"] not in {"queued", "running"}:
                break
            time.sleep(0.02)

        assert job["status"] == "succeeded"
        assert len(job["result"]["methods"]) == 1
        assert len(job["result"]["formulas"]) == 1
        assert (
            tmp_path
            / "projects"
            / project["project_id"]
            / "artifacts"
            / "knowledge"
            / "jobs"
            / f"{job['job_id']}.json"
        ).exists()
