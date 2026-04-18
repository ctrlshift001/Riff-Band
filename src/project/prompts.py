from __future__ import annotations

import json
from typing import Any, Dict, List

from core.utils import format_tools_description


class GBAMainPromptBuilder:
    """调度智能体的提示词构造器"""

    @staticmethod
    def build_prompt(
        instruction: str,
        meta: Dict[str, Any],
        prior_context: str,
        attempt_index: int,
        max_attempts: int,
        sub_models: List[str],
        subtask_history: str = "",
        tools: List[Any] | None = None,
    ) -> str:
        model_routing = meta.get("model_routing", {})
        subtask_toolkits = meta.get("subtask_toolkits", {})
        required_sections = meta.get("required_sections", [])
        min_findings = int(meta.get("min_findings", 5))
        report_path = meta.get("report_path", "workspace/output/gba_industry_report.md")
        findings_path = meta.get("findings_path", "workspace/output/findings.jsonl")
        max_parallel = int(meta.get("max_parallel_subtasks", 3))

        return f"""
你是粤港澳大湾区产业分析项目的**主调度智能体**。

目标：
1. 将项目拆解为聚焦的子任务。
2. 根据任务依赖关系，选择**单任务委派**或**并行委派**。
3. 只有通过质量检查后，才能确认最终完成。

委派规则：
- 当子任务依赖前置结果或需要撰写报告时，使用 `delegate_task`。
- 仅对可独立运行的子任务，使用 `delegate_tasks` 并行执行。
- 并行模式下，工具**禁止**包含 `write_report_section`。
- 默认最大并发数为 {max_parallel}，除非另行设置。

执行进度：
- 第 {attempt_index}/{max_attempts} 次尝试
- 剩余尝试次数：{max_attempts - attempt_index}

项目简报：
{instruction}

历史上下文：
{prior_context or "无"}

子任务历史：
{subtask_history or "尚未分配子任务"}

可用子智能体工具：
{format_tools_description(tools or [])}

模型分配规则：
{json.dumps(model_routing, ensure_ascii=False, indent=2)}

子任务工具包：
{json.dumps(subtask_toolkits, ensure_ascii=False, indent=2)}

只返回JSON格式，严格使用以下其中一种动作格式。

单任务委派：
{{
  "action": "delegate_task",
  "reasoning": "说明为何需要执行该子任务",
  "params": {{
    "task_instruction": "聚焦的子任务",
    "context": "相关上下文",
    "model": "{sub_models} 中的一个",
    "tools": ["search_sources", "read_sources", "record_finding"]
  }}
}}

并行任务委派：
{{
  "action": "delegate_tasks",
  "reasoning": "说明这些任务为何可独立并行执行",
  "params": {{
    "max_concurrency": {max_parallel},
    "tasks": [
      {{
        "task_instruction": "独立任务1",
        "context": "任务1上下文",
        "model": "{sub_models} 中的一个",
        "tools": ["search_sources", "read_sources", "record_finding"]
      }},
      {{
        "task_instruction": "独立任务2",
        "context": "任务2上下文",
        "model": "{sub_models} 中的一个",
        "tools": ["search_sources", "read_source", "web_search", "record_finding"]
      }}
    ]
  }}
}}

任务完成：
{{
  "action": "complete_task",
  "reasoning": "说明报告为何已就绪可交付",
  "params": {{
    "executive_summary": "简短执行摘要",
    "report_path": "{report_path}",
    "findings_path": "{findings_path}",
    "required_sections": {json.dumps(required_sections, ensure_ascii=False)},
    "min_findings": {min_findings},
    "confidence": "high|medium|low"
  }}
}}
""".strip()


class GBASubPromptBuilder:
    """子任务执行智能体的提示词构造器"""

    @staticmethod
    def build_prompt(
        task_instruction: str,
        context: str,
        original_question: str,
        action_space: str,
        observation: Any,
        memory: str,
        current_step: int,
        max_steps: int,
    ) -> str:
        remaining_steps = max_steps - current_step
        return f"""
你是粤港澳大湾区产业分析的**专业执行子智能体**。

已分配任务：
{task_instruction}

原始项目需求：
{original_question}

上下文：
{context or "无"}

可用操作：
{action_space}

当前观察结果：
{observation}

记忆信息：
{memory}

规则：
- 仅在分配的任务范围内工作。
- 优先分析本地资料，资料不足时再使用联网搜索。
- 如果数据不充分，以 partial 状态结束并说明缺口。
- 剩余步骤：{remaining_steps}

只返回JSON格式。

工具调用格式：
{{"action": "工具名称", "params": {{...}}, "memory": "本步骤确认的信息"}}

结束任务格式：
{{
  "action": "finish",
  "params": {{
    "status": "done|partial|blocked",
    "message": "已完成内容",
    "completed": ["具体产出"],
    "issues": ["剩余缺口"],
    "result": "可选简短结果"
  }},
  "memory": "下一个智能体需要知道的信息"
}}
""".strip()