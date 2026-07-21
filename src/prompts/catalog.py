from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

from prompts.contracts import (
    DataDraft,
    DesignDraft,
    LiteraturePlanDraft,
    LiteratureSynthesisDraft,
    ProblemDraft,
    TheoryDraft,
)


COMMON_SYSTEM_PROMPT = """你是 AI4MS 管理科学科研工作台中的阶段研究助理。
你的职责是生成可供研究者审阅的结构化草稿，不是替研究者作最终决定。

必须遵守：
1. 只使用输入上下文；信息不足时写入 unknowns，不得自行补造事实、论文、数据、结论或批准状态。
2. 明确区分已有事实、研究假设、待检索项和候选空白。不得使用“首次、无人研究、完全空白”等绝对原创表述。
3. 不输出 approval、approved、human_verified 等人工决定字段。
4. 输出必须是符合给定 JSON Schema 的单个 JSON 对象，不要 Markdown、解释或代码围栏。
5. 保留用户原始科学问题的含义；可以澄清和拆分，但不能静默改变研究目标。
6. 面向多类管理科学研究，不默认课题一定是因果实证，也不默认使用某一种软件或方法。
"""


@dataclass(frozen=True)
class StagePrompt:
    prompt_id: str
    version: str
    stage_key: str
    contract: type[BaseModel]
    task_instruction: str

    def render(self, context: dict[str, Any], user_instruction: str = "") -> tuple[str, str]:
        schema = json.dumps(self.contract.model_json_schema(), ensure_ascii=False, indent=2)
        payload = json.dumps(context, ensure_ascii=False, indent=2)
        instruction = str(user_instruction or "").strip() or "无额外要求"
        user_prompt = f"""阶段任务：
{self.task_instruction}

项目上下文：
{payload}

研究者额外要求：
{instruction}

输出 JSON Schema：
{schema}
"""
        return COMMON_SYSTEM_PROMPT, user_prompt


class PromptCatalog:
    _prompts = {
        "problem": StagePrompt(
            prompt_id="ai4ms.stage.problem",
            version="1.0.0",
            stage_key="problem",
            contract=ProblemDraft,
            task_instruction="""把原始研究想法整理为 S0 问题识别草稿。识别研究对象、分析单位、时空边界、研究目标、核心概念与中英文/相邻术语。提出 1-5 个可证伪或可求解的问题。候选空白只能标记为待检索假设，并为每项给出可能推翻它的反向检索。""",
        ),
        "literature": StagePrompt(
            prompt_id="ai4ms.stage.literature-plan",
            version="1.0.0",
            stage_key="literature",
            contract=LiteraturePlanDraft,
            task_instruction="""基于已批准或当前 S0 内容生成 S1 文献检索计划，不生成论文、引文、研究流派或综合结论。检索计划必须覆盖经典基础、近年进展、相邻术语、争议/反证和候选空白反向复核；给出可直接交给 OpenAlex、Crossref、Semantic Scholar 和 arXiv 的中英文查询块、纳排标准、筛选问题和覆盖限制。""",
        ),
        "literature_synthesis": StagePrompt(
            prompt_id="ai4ms.stage.literature-synthesis",
            version="1.0.0",
            stage_key="literature",
            contract=LiteratureSynthesisDraft,
            task_instruction="""只基于上下文中已保存的论文元数据和 paper_id，形成研究流派、共识/争议/未知、候选空白及下一步。所有 supporting/opposing paper_id 必须来自输入。摘要缺失或来源覆盖有限时降低证据状态并写入 coverage_limits；不得补造论文、DOI、研究发现或绝对原创结论。""",
        ),
        "theory": StagePrompt(
            prompt_id="ai4ms.stage.theory",
            version="1.0.0",
            stage_key="theory",
            contract=TheoryDraft,
            task_instruction="""基于 S0 问题和 S1 已保存的综合与论文，生成 S2 理论构建草稿：比较理论视角、定义构念、描述机制链和边界条件、给出竞争解释及可证伪问题/命题。论文引用只能使用输入 paper_id；证据不足时使用 needs_evidence，不得把理论推断写成已有实证事实。""",
        ),
        "design": StagePrompt(
            prompt_id="ai4ms.stage.design",
            version="1.0.0",
            stage_key="design",
            contract=DesignDraft,
            task_instruction="""基于已保存的问题、文献和理论资产，并仅从输入 method_candidates 选择方法，生成 S3 主备研究设计。先判断研究泳道，再明确分析单位、estimand/求解目标、方法适配条件、关键假设、证伪检验、有效性威胁和停止条件。不得因为方法更复杂而推荐，也不得声称未知数据已经可得。""",
        ),
        "data": StagePrompt(
            prompt_id="ai4ms.stage.data",
            version="1.0.0",
            stage_key="data",
            contract=DataDraft,
            task_instruction="""基于已保存的研究设计，并仅从输入 data_source_candidates 选择候选数据源，生成 S4 数据合同和变量草稿。区分构念与操作化，列明样本、时间、连接键、缺失处理、质量检查、隐私、伦理和许可。除非输入明确证明，否则 access_status/license_status 必须是 unknown 或 pending；不可把候选数据源写成已获授权。""",
        ),
    }

    @classmethod
    def get(cls, stage_key: str, context: dict[str, Any] | None = None) -> StagePrompt | None:
        if stage_key == "literature" and (context or {}).get("current_stage_content", {}).get("papers"):
            return cls._prompts["literature_synthesis"]
        return cls._prompts.get(stage_key)

    @classmethod
    def supported_stage_keys(cls) -> tuple[str, ...]:
        return tuple(dict.fromkeys(prompt.stage_key for prompt in cls._prompts.values()))
