from __future__ import annotations

import asyncio
import json

import pytest

from inference.gateway import InferenceResponse
from inference.structured import extract_json_object
from prompts.catalog import PromptCatalog
from services.stage_generation import (
    StageGenerationNotSupportedError,
    StageGenerationService,
)


def _problem_payload() -> dict:
    return {
        "initial_idea": "A model must not replace this authoritative field",
        "research_object": "使用生成式 AI 的企业",
        "problem_boundary": "考察企业采用生成式 AI 与创新结果之间的关系，不预设因果成立",
        "objective": "explain",
        "units": ["企业"],
        "geography": ["中国"],
        "time_window": "待研究者确认",
        "concepts": [
            {
                "label": "生成式 AI 采用",
                "terms": ["generative AI adoption", "生成式人工智能采用"],
                "exclude_terms": ["仅讨论算法性能"],
            }
        ],
        "questions": ["生成式 AI 采用与企业创新结果之间存在什么关系？"],
        "candidate_gaps": [
            {
                "gap_type": "context",
                "statement": "不同企业情境下的关系可能不同",
                "why_only_candidate": "尚未执行系统检索，不能确认是否构成研究空白",
                "counter_search": "generative AI adoption firm innovation heterogeneity",
            }
        ],
        "counter_searches": ["生成式 AI 企业创新 相邻术语 已有研究"],
        "unknowns": ["采用指标口径", "可获得数据范围"],
    }


def _project() -> dict:
    return {
        "project_id": "prj_test",
        "title": "生成式 AI 与企业创新",
        "initial_idea": "生成式 AI 是否影响企业创新？",
        "stages": [
            {"key": "problem", "revision": 1, "content": {"initial_idea": "生成式 AI 是否影响企业创新？"}},
            {"key": "literature", "revision": 0, "content": {}},
        ],
    }


class _FakeGateway:
    def __init__(self, responses: list[InferenceResponse]):
        self.responses = list(responses)
        self.calls: list[tuple[str, str]] = []

    async def generate(self, system_prompt: str, user_prompt: str) -> InferenceResponse:
        self.calls.append((system_prompt, user_prompt))
        return self.responses.pop(0)


def test_extract_json_object_accepts_fenced_output():
    assert extract_json_object('```json\n{"value": 1}\n```') == {"value": 1}


def test_problem_generation_is_validated_and_preserves_initial_idea():
    response = InferenceResponse(
        text=json.dumps(_problem_payload(), ensure_ascii=False),
        model="test-model",
        usage={"input_tokens": 10, "output_tokens": 20, "total_tokens": 30, "call_count": 1},
    )
    gateway = _FakeGateway([response])
    service = StageGenerationService(gateway_factory=lambda: gateway)

    content = asyncio.run(service.generate(_project(), "problem", "不要预设因果"))

    assert content["initial_idea"] == "生成式 AI 是否影响企业创新？"
    assert content["generation"]["prompt_id"] == "ai4ms.stage.problem"
    assert content["generation"]["model"] == "test-model"
    assert content["generation"]["attempts"] == 1
    assert len(gateway.calls) == 1


def test_invalid_model_json_gets_one_repair_attempt():
    repaired = InferenceResponse(
        text=json.dumps(_problem_payload(), ensure_ascii=False),
        model="test-model",
        usage={"total_tokens": 40, "call_count": 1},
    )
    gateway = _FakeGateway(
        [
            InferenceResponse(text="{}", model="test-model", usage={"total_tokens": 5, "call_count": 1}),
            repaired,
        ]
    )
    service = StageGenerationService(gateway_factory=lambda: gateway)

    content = asyncio.run(service.generate(_project(), "problem"))

    assert content["generation"]["attempts"] == 2
    assert content["generation"]["usage"]["total_tokens"] == 45
    assert "未通过结构或引用约束" in gateway.calls[1][1]


def test_model_generation_rejects_unimplemented_stage_before_calling_gateway():
    gateway = _FakeGateway([])
    service = StageGenerationService(gateway_factory=lambda: gateway)

    with pytest.raises(StageGenerationNotSupportedError):
        asyncio.run(service.generate(_project(), "identification"))

    assert gateway.calls == []


def test_literature_prompt_contract_has_no_paper_or_approval_fields():
    prompt = PromptCatalog.get("literature")
    assert prompt is not None
    properties = prompt.contract.model_json_schema()["properties"]
    assert "papers" not in properties
    assert "sources" not in properties
    assert "approval" not in properties


def test_prompt_catalog_supports_s0_through_s4():
    assert PromptCatalog.supported_stage_keys() == (
        "problem",
        "literature",
        "theory",
        "design",
        "data",
    )


def _s1_s4_project() -> dict:
    project = _project()
    project["stages"] = [
        {
            "key": "problem",
            "revision": 2,
            "content": {
                "objective": "causal",
                "questions": ["AI 采用如何影响企业创新？"],
            },
        },
        {
            "key": "literature",
            "revision": 2,
            "content": {
                "papers": [
                    {
                        "paper_id": "paper_a",
                        "title": "AI adoption and innovation",
                        "authors": ["Li Ming"],
                        "year": 2024,
                        "abstract": "A study of enterprise AI adoption and innovation.",
                    }
                ],
                "syntheses": [
                    {
                        "statement": "现有证据提示二者相关，但识别仍有限。",
                        "supporting_paper_ids": ["paper_a"],
                    }
                ],
                "coverage_limits": ["当前仅有一篇论文"],
            },
        },
        {"key": "theory", "revision": 0, "content": {}},
        {"key": "design", "revision": 0, "content": {}},
        {"key": "data", "revision": 0, "content": {}},
    ]
    return project


def _theory_payload() -> dict:
    return {
        "theoretical_lenses": [
            {
                "name": "组织信息处理理论",
                "relevance": "用于解释信息处理能力与创新活动之间的关系。",
                "limits": ["不能单独确认因果方向"],
                "supporting_paper_ids": ["paper_a"],
            }
        ],
        "constructs": [
            {"name": "AI 采用", "definition": "企业部署并使用 AI 的程度。", "role": "antecedent", "measurement_unknowns": ["口径待定"]},
            {"name": "企业创新", "definition": "企业产生创新成果的表现。", "role": "outcome", "measurement_unknowns": ["指标待定"]},
        ],
        "mechanisms": [
            {
                "name": "信息处理机制",
                "chain": ["AI 采用提高信息处理能力", "信息处理能力支持创新"],
                "boundary_conditions": ["组织吸收能力"],
                "supporting_paper_ids": ["paper_a"],
                "evidence_status": "limited",
            }
        ],
        "research_questions": ["AI 采用如何通过信息处理能力影响企业创新？"],
        "competing_explanations": [{"explanation": "创新能力强的企业更早采用 AI。", "distinguishing_observation": "采用前创新趋势能够区分反向因果。"}],
        "falsifiable_propositions": [{"proposition_id": "H1", "statement": "AI 采用与企业创新正相关。", "falsification": "在可比样本中未观察到该关系。"}],
        "contribution_boundary": "只提出待检验机制，不把相关性写成因果事实。",
        "unknowns": ["构念测量方式"],
    }


def test_theory_generation_accepts_only_existing_paper_ids():
    gateway = _FakeGateway([InferenceResponse(text=json.dumps(_theory_payload(), ensure_ascii=False), model="test", usage={})])
    content = asyncio.run(StageGenerationService(lambda: gateway).generate(_s1_s4_project(), "theory"))

    assert content["generation"]["prompt_id"] == "ai4ms.stage.theory"
    assert content["mechanisms"][0]["supporting_paper_ids"] == ["paper_a"]


def test_design_generation_repairs_method_id_outside_registry_shortlist():
    project = _s1_s4_project()
    project["stages"][2]["content"] = _theory_payload()
    context = StageGenerationService._build_context(project, "design")
    method_ids = [item["method_id"] for item in context["method_candidates"][:2]]

    def payload(primary: str) -> dict:
        return {
            "design_lane": "empirical_causal",
            "research_question": "AI 采用如何影响企业创新？",
            "unit_of_analysis": "企业年度观测",
            "estimand_or_objective": "估计 AI 采用对企业创新结果的平均影响。",
            "method_options": [
                {"method_id": primary, "role": "primary", "rationale": "匹配因果研究目标与面板结构。", "fit_conditions": ["存在可比组"], "risks": ["残余混杂"]},
                {"method_id": method_ids[1], "role": "alternative", "rationale": "用于替代识别与结果复核。", "fit_conditions": ["数据满足方法要求"], "risks": ["估计精度不足"]},
            ],
            "primary_method_id": primary,
            "assumptions": [{"assumption_id": "A1", "category": "identification", "statement": "处理组与对照组满足方法所需可比性。", "testability": "partially_testable", "planned_check": "检验处理前趋势与协变量平衡。"}],
            "falsification": ["安慰剂时间检验"],
            "threats_to_validity": ["选择偏差"],
            "stopping_conditions": ["关键识别假设明显不成立"],
            "unknowns": ["实际可得面板长度"],
        }

    gateway = _FakeGateway(
        [
            InferenceResponse(text=json.dumps(payload("M99"), ensure_ascii=False), model="test", usage={}),
            InferenceResponse(text=json.dumps(payload(method_ids[0]), ensure_ascii=False), model="test", usage={}),
        ]
    )
    content = asyncio.run(StageGenerationService(lambda: gateway).generate(project, "design"))

    assert content["primary_method_id"] == method_ids[0]
    assert content["generation"]["attempts"] == 2
    assert "可用 ID" in gateway.calls[1][1]


def test_data_generation_uses_registry_source_ids():
    project = _s1_s4_project()
    project["stages"][2]["content"] = _theory_payload()
    project["stages"][3]["content"] = {"design_lane": "empirical_causal", "primary_method_id": "M02"}
    context = StageGenerationService._build_context(project, "data")
    source_id = context["data_source_candidates"][0]["source_id"]
    payload = {
        "data_sources": [{"source_id": source_id, "role": "candidate", "access_status": "unknown", "license_status": "unknown", "rationale": "候选数据源与企业创新变量可能相关。", "required_fields": ["企业标识", "年份"], "risks": ["授权状态未知"]}],
        "variables": [
            {"name": "AI 采用", "role": "treatment", "construct": "企业 AI 采用", "operationalization": "根据可得字段构建，口径待确认。", "unit": "企业-年", "source_ids": [source_id], "missing_data_plan": "先描述缺失机制再决定处理方式。"},
            {"name": "创新结果", "role": "outcome", "construct": "企业创新", "operationalization": "根据可得创新字段构建，口径待确认。", "unit": "企业-年", "source_ids": [source_id], "missing_data_plan": "报告缺失比例并进行敏感性分析。"},
        ],
        "sample_definition": "具有企业标识、年份及关键变量的企业年度样本。",
        "time_coverage": "取决于候选数据源实际可得年份",
        "join_keys": ["企业标识", "年份"],
        "pii_class": "unknown",
        "privacy_risks": ["字段级隐私分类尚未确认"],
        "ethics_checks": ["确认授权范围和数据最小化原则"],
        "quality_checks": ["主键唯一性", "时间覆盖", "缺失与异常值"],
        "blocking_issues": ["尚未确认访问权限"],
        "unknowns": ["许可条款"],
    }
    gateway = _FakeGateway([InferenceResponse(text=json.dumps(payload, ensure_ascii=False), model="test", usage={})])

    content = asyncio.run(StageGenerationService(lambda: gateway).generate(project, "data"))

    assert content["data_sources"][0]["source_id"] == source_id
    assert content["generation"]["prompt_id"] == "ai4ms.stage.data"
