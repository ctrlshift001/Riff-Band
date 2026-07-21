from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

from ai4ms.prompts.contracts import (
    AnalysisPlanDraft,
    ClaimEvidenceDraft,
    DataDraft,
    DeliveryDraft,
    DesignDraft,
    LiteraturePlanDraft,
    LiteratureSynthesisDraft,
    ProblemDraft,
    RobustnessDraft,
    RunPreparationDraft,
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
        "identification": StagePrompt(
            prompt_id="ai4ms.stage.identification",
            version="1.0.0",
            stage_key="identification",
            contract=AnalysisPlanDraft,
            task_instruction="""基于已保存的 S3 研究设计和 S4 数据合同生成 S5 分析计划。冻结 estimand/求解目标、样本、变量角色、主次模型、诊断、缺失与多重性处理、分析步骤、稳健性和停止条件。method_id 只能来自已选设计方法，formula_id 只能来自 formula_candidates。按研究泳道选择执行引擎；只有适合 Stata 的计划才生成可审阅 do-file，并固定 version、seed、只读输入和独立输出，不得包含 shell、网络、动态安装、绝对路径或父目录穿越。不得声称数据检查或模型运行已经完成。""",
        ),
        "analysis": StagePrompt(
            prompt_id="ai4ms.stage.analysis",
            version="1.0.0",
            stage_key="analysis",
            contract=RunPreparationDraft,
            task_instruction="""基于已获 G3 人工批准的 S5 分析计划生成 S6 运行准备与结果审阅清单。只描述预期产物、预检、结果审阅、阻塞项和未知，不生成或改写 do-file，不虚构 Runner、日志、退出码、统计量、表图或运行成功状态。实际代码、计划 revision 和 hash 由服务端从已批准 S5 强制绑定。""",
        ),
        "robustness": StagePrompt(
            prompt_id="ai4ms.stage.robustness",
            version="1.0.0",
            stage_key="robustness",
            contract=RobustnessDraft,
            task_instruction="""基于 S5 分析计划与 S6 不可变 Run 记录生成 S7 稳健性矩阵，覆盖替代口径、模型、样本、安慰剂、敏感性或该研究泳道适用的反证检查。specification_id 和 run_id 只能引用输入。没有结构化运行结果时，status 只能是 planned、not_run 或 blocked，不得根据预期、退出码或语言描述臆造 passed/failed；失败项及其对解释的影响必须保留。""",
        ),
        "evidence": StagePrompt(
            prompt_id="ai4ms.stage.evidence",
            version="1.0.0",
            stage_key="evidence",
            contract=ClaimEvidenceDraft,
            task_instruction="""基于 S1 论文、S6 不可变 Run 记录和 S7 稳健性矩阵生成 S8 Claim-Evidence 草稿。每条主张必须包含至少一个输入 evidence_artifacts 中的 artifact_id，并明确方向、强度、作用域、假设和不确定性。论文、run_id、method_id、机制和稳健性检查只能引用输入中的 ID。没有结构化结果的 blocked/failed Run 只能作为 reviewer_note 且只能限定主张，不得支持实证结论。稳健性失败、阻塞或不确定必须降低置信度并进入限制；不得输出审批状态。""",
        ),
        "delivery": StagePrompt(
            prompt_id="ai4ms.stage.delivery",
            version="1.0.0",
            stage_key="delivery",
            contract=DeliveryDraft,
            task_instruction="""只基于 G4 已批准的 S8 主张与证据生成 S9 写作和交付草稿。每条核心结论必须引用输入中的 claim_id 和这些主张实际包含的 evidence_id；不得使用 refuted/withdrawn 主张，不得新增数值、论文或证据。政策含义必须写清适用对象、条件和风险。reference_paper_ids 只能来自输入论文。HTML 报告、manifest、引用元数据和研究 ZIP 包由服务端确定性生成，不得编造路径或发布状态。""",
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
