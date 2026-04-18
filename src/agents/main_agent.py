from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from pydantic import Field

from base.agent.base_agent import BaseAgent
from base.engine.logs import LogLevel, logger
from core.interfaces import TaskContext
from core.utils import indent_text, parse_json_response


class MainOrchestratorAgent(BaseAgent):
    """Main agent that decides whether to delegate more work or finalize the task."""

    name: str = Field(default="主Agent")
    description: str = Field(default="核心调度智能体，支持动态单任务/批量任务委派")
    sub_models: List[str] = Field(default_factory=list)
    tools: List[Any] = Field(default_factory=list)
    subagent_tools: List[Any] = Field(default_factory=list)
    prompt_builder: Any = Field(default=None)
    max_attempts: int = Field(default=6)
    instruction: str = Field(default="")
    meta: Dict[str, Any] = Field(default_factory=dict)
    attempt: int = Field(default=0)
    context: str = Field(default="")
    history: List[Dict[str, Any]] = Field(default_factory=list)
    task_entries: List[Dict[str, Any]] = Field(default_factory=list)

    class Config:
        arbitrary_types_allowed = True

    def reset(self, task_context: TaskContext) -> None:
        self.instruction = task_context.instruction
        self.meta = task_context.meta_data or {}
        self.attempt = 0
        self.context = ""
        self.history = []
        self.task_entries = []

    def get_usage_cost(self) -> float:
        return self.llm.get_usage_summary().get("total_cost", 0.0)

    def _format_subtask_history(self) -> str:
        if not self.task_entries:
            return "尚未分配子任务。"

        lines: List[str] = []
        completed_items: List[str] = []
        issues: List[str] = []
        for entry in self.task_entries:
            block = [
                f"[第 {entry['attempt']} 轮] 状态={entry['status']} 模型={entry.get('model', '未知')} 步骤数={entry.get('steps_taken', 0)}",
                f"任务指令：{entry.get('instruction', '')}",
            ]
            if entry.get("message"):
                block.append(f"执行信息：{entry['message']}")
            if entry.get("completed"):
                block.append(f"已完成：{entry['completed']}")
                completed_items.extend(entry["completed"])
            if entry.get("issues"):
                block.append(f"存在问题：{entry['issues']}")
                issues.extend(entry["issues"])
            if entry.get("result"):
                block.append(f"执行结果：{entry['result']}")
            if entry.get("trace_summary"):
                block.append("执行轨迹摘要：")
                block.append(indent_text(entry["trace_summary"], "  "))
            lines.append("\n".join(block))

        summary = [
            f"摘要：共 {len(self.task_entries)} 个子任务，"
            f"{sum(1 for item in self.task_entries if item['status'] == 'done')} 个已完成"
        ]
        if completed_items:
            summary.append(f"可复用成果：{completed_items}")
        if issues:
            summary.append(f"已知问题：{issues}")
        lines.append("\n".join(summary))
        return "\n\n".join(lines)
    
    def _infer_profile(self, task_instruction: str) -> str:
        text = task_instruction.lower()
        if any(item in text for item in ["policy", "regulation", "government"]):
            return "policy_research"
        if any(item in text for item in ["company", "competitor", "firm"]):
            return "company_research"
        if any(item in text for item in ["supply chain", "value chain", "upstream", "downstream"]):
            return "supply_chain"
        if any(item in text for item in ["finance", "financial", "valuation", "revenue"]):
            return "financial_metrics"
        if any(item in text for item in ["news", "sentiment", "public opinion"]):
            return "news_signals"
        if any(item in text for item in ["report", "summary", "write section", "draft"]):
            return "report_drafting"
        return "general_research"

    # 根据任务类型，执行sub_model分配
    def _apply_delegate_defaults(self, params: Dict[str, Any], parallel_mode: bool = False) -> Dict[str, Any]:
        fixed = dict(params or {})
        instruction = str(fixed.get("task_instruction", "")).strip()
        profile = self._infer_profile(instruction)

        toolkits = self.meta.get("subtask_toolkits", {}) or {}
        if not fixed.get("tools"):
            fixed["tools"] = list(toolkits.get(profile, toolkits.get("general_research", [])))

        # Hard rule: parallel tasks cannot write report sections.
        if parallel_mode and fixed.get("tools"):
            fixed["tools"] = [t for t in fixed["tools"] if str(t) != "write_report_section"]

        routing = self.meta.get("model_routing", {}) or {}
        routed_model = routing.get(profile)
        if not fixed.get("model") and routed_model:
            fixed["model"] = routed_model

        if fixed.get("model") not in self.sub_models and self.sub_models:
            fixed["model"] = self.sub_models[0]
        if "context" not in fixed:
            fixed["context"] = ""
        return fixed

    def _apply_delegate_tasks_defaults(self, params: Dict[str, Any]) -> Dict[str, Any]:
        fixed = dict(params or {})
        tasks = fixed.get("tasks") or []
        normalized_tasks = [self._apply_delegate_defaults(t, parallel_mode=True) for t in tasks if isinstance(t, dict)]
        fixed["tasks"] = normalized_tasks
        if "max_concurrency" not in fixed or not fixed.get("max_concurrency"):
            fixed["max_concurrency"] = int(self.meta.get("max_parallel_subtasks", 3))
        return fixed

    async def step(self, observation, history, **kwargs) -> tuple[Dict[str, Any], str]:
        self.attempt += 1
        subtask_history = self._format_subtask_history()

        if self.prompt_builder is None:
            raise ValueError("主调度智能体需要设置 prompt_builder（提示词构造器）")

        prompt = self.prompt_builder.build_prompt(
            instruction=self.instruction,
            meta=self.meta,
            prior_context=self.context,
            attempt_index=self.attempt,
            max_attempts=self.max_attempts,
            sub_models=self.sub_models,
            subtask_history=subtask_history,
            tools=self.subagent_tools,
        )
        logger.log_to_file(LogLevel.INFO, f"[MainAgent] 提示词:\n{prompt}\n")

        response = await self.llm(prompt)
        logger.log_to_file(LogLevel.INFO, f"[MainAgent] 原始返回:\n{response}\n")
        decision = parse_json_response(response)

        action_name = decision.get("action")
        params = decision.get("params", {})
        if action_name == "delegate_task":
            params = self._apply_delegate_defaults(params, parallel_mode=False)
        elif action_name == "delegate_tasks":
            params = self._apply_delegate_tasks_defaults(params)

        tool = next((item for item in self.tools if item.name == action_name), None)
        if tool is None:
            raise ValueError(f"主agent请求了未知动作: {action_name}")

        result = await tool(**params)
        self._update_context(action_name, params, result)

        logger.log_to_file(
            LogLevel.INFO,
            f"[MainAgent] 解析后决策:\n{json.dumps(decision, ensure_ascii=False, indent=2)}\n",
        )
        return {
            "action": action_name,
            "params": params,
            "result": result,
            "subtask_history": subtask_history,
        }, response

    def _append_task_entry(self, base_params: Dict[str, Any], task_result: Dict[str, Any]) -> None:
        finish_result = task_result.get("finish_result", {})
        entry = {
            "attempt": self.attempt,
            "status": finish_result.get("status", "partial"),
            "instruction": base_params.get("task_instruction", ""),
            "model": base_params.get("model", "unknown"),
            "tools": base_params.get("tools", []),
            "steps_taken": task_result.get("steps_taken", 0),
            "message": finish_result.get("message", ""),
            "completed": finish_result.get("completed", []),
            "issues": finish_result.get("issues", []),
            "result": finish_result.get("result", ""),
            "trace_summary": task_result.get("trace_summary", ""),
        }
        self.task_entries.append(entry)

    def _update_context(self, action: str, params: Dict[str, Any], result: Dict[str, Any]) -> None:
        summary = [f"[第{self.attempt}轮] 动作={action}"]

        if action == "delegate_task":
            self._append_task_entry(params, result)
            summary.append(f"状态={result.get('finish_result', {}).get('status', 'partial')}")
            summary.append(f"使用工具={params.get('tools', [])}")

        if action == "delegate_tasks":
            for idx, item in enumerate(result.get("results", []) or []):
                task_params = (params.get("tasks") or [{}])[idx] if idx < len(params.get("tasks") or []) else {}
                self._append_task_entry(task_params, item)
            batch_summary = result.get("summary", {})
            summary.append(f"批量执行摘要={batch_summary}")

        if action == "complete_task":
            summary.append(f"报告路径={params.get('report_path', '')}")
            summary.append(f"置信度={params.get('confidence', '')}")
            if not result.get("quality_gate_passed", False):
                summary.append(f"质量检查未通过={result.get('issues', [])}")

        self.context = "\n".join(summary) + "\n\n" + self.context
        self.history.append({"attempt": self.attempt, "action": action, "result": result})

    async def run(self, request: Optional[str] = None) -> str:
        return "通过运行器执行调度流程"
    