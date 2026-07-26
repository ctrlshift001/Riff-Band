from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from ai4ms.inference.gateway import (
    InferenceGateway,
    OpenAICompatibleGateway,
)
from ai4ms.inference.structured import StructuredOutputError, validate_structured_output
from ai4ms.reporting import build_ai_report_envelope
from ai4ms.services.models import KnowledgeCandidateInput, KnowledgeEvaluationRequest


class CandidateAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_id: str
    score: int = Field(ge=0, le=100)
    rationale: str = Field(min_length=1, max_length=1000)
    missing_information: list[str] = Field(default_factory=list, max_length=8)


class KnowledgeAssessmentContract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    methods: list[CandidateAssessment]
    formulas: list[CandidateAssessment]
    summary: str = Field(default="", max_length=2000)


class KnowledgeEvaluationOutputError(RuntimeError):
    pass


class KnowledgeEvaluationService:
    def __init__(
        self,
        projects_dir: str | Path,
        gateway_factory: Callable[[], InferenceGateway] | None = None,
    ) -> None:
        self.projects_dir = Path(projects_dir)
        self.gateway_factory = gateway_factory or OpenAICompatibleGateway

    def load(self, project: dict[str, Any]) -> dict[str, Any]:
        path = self._artifact_path(str(project["project_id"]))
        if not path.exists():
            return self._empty(project, "not_evaluated")
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return self._empty(project, "invalid")
        if not isinstance(payload, dict):
            return self._empty(project, "invalid")
        payload["status"] = (
            "current"
            if payload.get("context_hash") == self.context_hash(project)
            else "stale"
        )
        return payload

    async def evaluate(
        self,
        project: dict[str, Any],
        request: KnowledgeEvaluationRequest,
    ) -> dict[str, Any]:
        context = self._project_context(project)
        system_prompt = (
            "你是管理科学研究方法审核者。请比较候选方法和公式与当前课题的适配性。"
            "分数是基于当前输入的相对适配判断，不是成功概率或统计显著性。"
            "不得补造数据、识别条件或已满足的假设。缺少信息必须写入 missing_information。"
            "只输出符合给定 JSON 结构的对象。"
        )
        user_prompt = json.dumps(
            {
                "task": "分别评估所有候选方法和公式，返回 0-100 整数分数、简短理由和缺失信息。",
                "project_context": context,
                "methods": [item.model_dump() for item in request.methods],
                "formulas": [item.model_dump() for item in request.formulas],
                "output_schema": KnowledgeAssessmentContract.model_json_schema(),
            },
            ensure_ascii=False,
        )
        response = await self.gateway_factory().generate(system_prompt, user_prompt)
        try:
            assessed = validate_structured_output(
                response.text, KnowledgeAssessmentContract
            )
        except StructuredOutputError as exc:
            raise KnowledgeEvaluationOutputError(str(exc)) from exc

        methods = self._validated_assessments(assessed.methods, request.methods)
        formulas = self._validated_assessments(assessed.formulas, request.formulas)
        payload = {
            "evaluation_id": f"eval_{uuid4().hex[:12]}",
            "project_id": project["project_id"],
            "status": "current",
            "context_hash": self.context_hash(project),
            "model": response.model,
            "evaluated_at": datetime.now(UTC).isoformat(),
            "summary": assessed.summary,
            "methods": methods,
            "formulas": formulas,
            "usage": response.usage,
        }
        payload["ai_report"] = build_ai_report_envelope(
            project_id=str(project["project_id"]),
            stage_key="design",
            content={
                "executive_summary": assessed.summary
                or "方法与公式候选适配性评估，等待研究者审核。",
                "method_ids": [
                    item["candidate_id"] for item in methods
                ],
                "formula_ids": [
                    item["candidate_id"] for item in formulas
                ],
                "reasoning_trace": {
                    "problem_framing": "比较候选方法与公式对当前管理科学课题的相对适配性。",
                    "logic_chain": [],
                    "assumptions": [],
                    "alternatives": [
                        "保留低分候选作为敏感性或替代设计，需人工判断。"
                    ],
                    "uncertainties": sorted(
                        {
                            missing
                            for item in [*methods, *formulas]
                            for missing in item.get("missing_information", [])
                        }
                    ),
                    "human_decisions": [
                        "研究者决定主方法、备选方法、公式和失败退出规则。"
                    ],
                    "next_verifications": [
                        "逐项核验方法假设、数据可得性和公式符号定义。"
                    ],
                },
            },
            prompt_id="ai4ms.knowledge.evaluation",
            prompt_version="1.0.0",
            model=response.model,
            generated_at=payload["evaluated_at"],
            evidence_library=_evidence_library(project),
        )
        path = self._artifact_path(str(project["project_id"]))
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        temporary.replace(path)
        return payload

    @staticmethod
    def _validated_assessments(
        assessments: list[CandidateAssessment],
        candidates: list[KnowledgeCandidateInput],
    ) -> list[dict[str, Any]]:
        allowed = {item.candidate_id for item in candidates}
        seen: set[str] = set()
        result: list[dict[str, Any]] = []
        for assessment in assessments:
            if assessment.candidate_id not in allowed or assessment.candidate_id in seen:
                continue
            seen.add(assessment.candidate_id)
            result.append(assessment.model_dump())
        return result

    @staticmethod
    def context_hash(project: dict[str, Any]) -> str:
        context = KnowledgeEvaluationService._project_context(project)
        encoded = json.dumps(
            context, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    @staticmethod
    def _project_context(project: dict[str, Any]) -> dict[str, Any]:
        stage_keys = {"problem", "literature", "theory", "design", "data"}
        return {
            "title": project.get("title", ""),
            "initial_idea": project.get("initial_idea", ""),
            "stages": [
                {
                    "key": stage.get("key"),
                    "revision": stage.get("revision", 0),
                    "content": stage.get("content", {}),
                }
                for stage in project.get("stages", [])
                if stage.get("key") in stage_keys
            ],
        }

    def _artifact_path(self, project_id: str) -> Path:
        return (
            self.projects_dir
            / project_id
            / "artifacts"
            / "knowledge"
            / "evaluation.json"
        )

    @staticmethod
    def _empty(
        project: dict[str, Any],
        status: Literal["not_evaluated", "invalid"],
    ) -> dict[str, Any]:
        return {
            "evaluation_id": "",
            "project_id": project["project_id"],
            "status": status,
            "context_hash": KnowledgeEvaluationService.context_hash(project),
            "model": "",
            "evaluated_at": "",
            "summary": "",
            "methods": [],
            "formulas": [],
            "usage": {},
            "ai_report": None,
        }


def _evidence_library(project: dict[str, Any]) -> list[dict[str, Any]]:
    literature = next(
        (
            stage
            for stage in project.get("stages", [])
            if stage.get("key") == "literature"
        ),
        {},
    )
    content = literature.get("content", {})
    if not isinstance(content, dict):
        return []
    return [
        item
        for item in content.get("evidence_library", [])
        if isinstance(item, dict)
    ]
