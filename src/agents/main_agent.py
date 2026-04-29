from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import Field

from base.agent.base_agent import BaseAgent
from base.engine.logs import LogLevel, logger
from core.interfaces import TaskContext
from core.utils import indent_text, parse_json_response
from orchestration_tools.taskplan import TaskPlanExecutor


class MainAgent(BaseAgent):
    """Main coordinator agent that decides delegation and completion."""

    name: str = Field(default="MainAgent")
    description: str = Field(default="Coordinates delegated tasks and decides task completion")
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
    task_plan_executor: TaskPlanExecutor = Field(default_factory=TaskPlanExecutor)
    latest_plan_task_ids: List[str] = Field(default_factory=list)

    class Config:
        arbitrary_types_allowed = True

    def reset(self, task_context: TaskContext) -> None:
        self.instruction = task_context.instruction
        self.meta = task_context.meta_data or {}
        self.attempt = 0
        self.context = ""
        self.history = []
        self.task_entries = []
        self.task_plan_executor.reset()
        self.latest_plan_task_ids = []

    def get_usage_cost(self) -> float:
        return self.llm.get_usage_summary().get("total_cost", 0.0)

    def _infer_profile(self, task_instruction: str) -> str:
        text = (task_instruction or "").lower()
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
        if any(item in text for item in ["verify", "verification", "quality gate", "qa", "validate", "check"]):
            return "verification"
        if any(item in text for item in ["report", "summary", "write section", "draft"]):
            return "report_drafting"
        return "general_research"

    def _current_phase(self) -> str:
        report_path = str(self.meta.get("report_path", "")).strip()
        report_exists = bool(report_path) and Path(report_path).exists()
        has_research = any(item.get("profile") not in {"report_drafting", "verification"} for item in self.task_entries)
        has_verification = any(item.get("profile") == "verification" for item in self.task_entries)

        if not has_research:
            return "research"
        if not report_exists:
            return "synthesis"
        if not has_verification:
            return "verification"
        return "verification"

    def _phase_guidance(self) -> str:
        phase = self._current_phase()
        if phase == "research":
            return (
                "阶段 1 / 研究：收集证据、记录 findings、写入共享 scratchpad 笔记。"
                "此阶段不要完成任务。"
            )
        if phase == "synthesis":
            return (
                "阶段 2 / 综合：把 findings 和 scratchpad 笔记整合为产物或报告章节。"
                "必须启动新的 write 类型 delegate_task 写入主 report_path；"
                "不要 continue_task 到并行 research session，避免写回 parallel_runs。"
            )
        return (
            "阶段 3 / 验证：围绕报告、findings 和 scratchpad 执行验证任务；"
            "调用 complete_task 前必须修复关键问题。"
        )

    def _format_subtask_history(self) -> str:
        if not self.task_entries:
            plan_snapshot = self.task_plan_executor.snapshot()
            return (
                "尚未委派子任务。\n\n"
                f"current_phase={self._current_phase()}\n"
                f"phase_guidance={self._phase_guidance()}\n\n"
                "task_plan_snapshot:\n"
                f"{indent_text(json.dumps(plan_snapshot, ensure_ascii=False, indent=2), '  ')}"
            )

        lines: List[str] = []
        completed_items: List[str] = []
        issues: List[str] = []
        for entry in self.task_entries:
            block = [
                (
                    f"[Attempt {entry['attempt']}] status={entry['status']} "
                    f"model={entry.get('model', 'unknown')} steps={entry.get('steps_taken', 0)}"
                ),
                f"task_instruction={entry.get('instruction', '')}",
                f"profile={entry.get('profile', 'general_research')}",
            ]
            if entry.get("session_id"):
                block.append(f"session_id={entry['session_id']} rounds={entry.get('session_rounds', 1)}")
                block.append(
                    f"subagent_reused={entry.get('worker_reused', False)} "
                    f"subagent_state={entry.get('worker_state', '')}"
                )
            if entry.get("message"):
                block.append(f"message={entry['message']}")
            if entry.get("completed"):
                block.append(f"completed={entry['completed']}")
                completed_items.extend(entry["completed"])
            if entry.get("issues"):
                block.append(f"issues={entry['issues']}")
                issues.extend(entry["issues"])
            if entry.get("result"):
                block.append(f"result={entry['result']}")
            if entry.get("trace_summary"):
                block.append("trace_summary:")
                block.append(indent_text(entry["trace_summary"], "  "))
            lines.append("\n".join(block))

        summary = [
            f"delegated_subtasks={len(self.task_entries)}",
            f"done_count={sum(1 for item in self.task_entries if item['status'] == 'done')}",
            f"current_phase={self._current_phase()}",
            f"phase_guidance={self._phase_guidance()}",
        ]
        if completed_items:
            summary.append(f"all_completed={completed_items}")
        if issues:
            summary.append(f"all_issues={issues}")
        lines.append("\n".join(summary))

        plan_snapshot = self.task_plan_executor.snapshot()
        lines.append("task_plan_snapshot:")
        lines.append(indent_text(json.dumps(plan_snapshot, ensure_ascii=False, indent=2), "  "))
        return "\n\n".join(lines)

    def _apply_delegate_defaults(self, params: Dict[str, Any], parallel_mode: bool = False) -> Dict[str, Any]:
        fixed = dict(params or {})
        instruction = str(fixed.get("task_instruction", "")).strip()
        profile = self._infer_profile(instruction)

        default_worker_tools = list(self.meta.get("default_worker_tools", []) or [])
        if not fixed.get("tools"):
            if default_worker_tools:
                fixed["tools"] = default_worker_tools
            else:
                legacy_toolkits = self.meta.get("subtask_toolkits", {}) or {}
                fixed["tools"] = list(legacy_toolkits.get(profile, []) or [])

        if parallel_mode and fixed.get("tools"):
            forbidden = set(str(item) for item in (self.meta.get("parallel_forbidden_tools", []) or []))
            fixed["tools"] = [t for t in fixed["tools"] if str(t) not in forbidden]

        routing = self.meta.get("model_routing", {}) or {}
        routed_model = routing.get(profile)
        if not fixed.get("model") and routed_model:
            fixed["model"] = routed_model

        if fixed.get("model") not in self.sub_models and self.sub_models:
            fixed["model"] = self.sub_models[0]
        if "context" not in fixed:
            fixed["context"] = ""
        fixed["worker_profile"] = profile
        return fixed

    def _apply_continue_defaults(self, params: Dict[str, Any]) -> Dict[str, Any]:
        fixed = self._apply_delegate_defaults(params, parallel_mode=False)
        fixed["session_id"] = str(fixed.get("session_id", "")).strip()
        return fixed

    def _apply_delegate_tasks_defaults(self, params: Dict[str, Any]) -> Dict[str, Any]:
        fixed = dict(params or {})
        tasks = fixed.get("tasks") or []
        fixed["tasks"] = [
            self._apply_delegate_defaults(item, parallel_mode=True)
            for item in tasks
            if isinstance(item, dict)
        ]
        if "max_concurrency" not in fixed or not fixed.get("max_concurrency"):
            fixed["max_concurrency"] = int(self.meta.get("max_parallel_subtasks", 3))
        return fixed

    def _tool_params(self, action_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Remove main-agent bookkeeping fields before calling action tools."""
        delegate_keys = {"task_instruction", "context", "model", "tools", "result_schema"}
        if action_name in {"delegate_task", "continue_task"}:
            allowed = set(delegate_keys)
            if action_name == "continue_task":
                allowed.add("session_id")
            return {k: v for k, v in dict(params or {}).items() if k in allowed}
        if action_name == "delegate_tasks":
            cleaned = dict(params or {})
            task_allowed = set(delegate_keys)
            cleaned["tasks"] = [
                {k: v for k, v in dict(item).items() if k in task_allowed}
                for item in (cleaned.get("tasks") or [])
                if isinstance(item, dict)
            ]
            return {k: v for k, v in cleaned.items() if k in {"tasks", "max_concurrency"}}
        return params

    async def step(self, observation, history, **kwargs) -> tuple[Dict[str, Any], str]:
        self.attempt += 1
        subtask_history = self._format_subtask_history()

        if self.prompt_builder is None:
            raise ValueError("MainAgent requires prompt_builder")

        prompt_meta = dict(self.meta)
        prompt_meta["current_phase"] = self._current_phase()
        prompt_meta["phase_guidance"] = self._phase_guidance()
        prompt_meta["forced_final_decision"] = bool(kwargs.get("forced_final_decision", False))
        prompt = self.prompt_builder.build_prompt(
            instruction=self.instruction,
            meta=prompt_meta,
            prior_context=self.context,
            attempt_index=self.attempt,
            max_attempts=self.max_attempts,
            sub_models=self.sub_models,
            subtask_history=subtask_history,
            tools=self.subagent_tools,
        )
        logger.log_to_file(LogLevel.INFO, f"[MainAgent] Prompt:\n{prompt}\n")
       
        response = await self.llm(prompt)
        logger.log_to_file(LogLevel.INFO, f"[MainAgent] Raw response:\n{response}\n")
        decision = parse_json_response(response)
        action_name = decision.get("action")
        params = decision.get("params", {})
        forced_final_decision = bool(kwargs.get("forced_final_decision", False))
        if forced_final_decision and action_name in {"delegate_task", "delegate_tasks", "continue_task"}:
            report_path = str(self.meta.get("report_path", "") or "")
            findings_path = str(self.meta.get("findings_path", "") or "")
            action_name = "complete_task"
            params = {
                "executive_summary": "已进入最终决策轮，基于已收集的 SubAgent 结果进行收尾。",
                "status": "partial",
                "artifacts": [
                    {"type": "report", "path": report_path, "description": "最终综合报告"}
                ],
                "verification": ["forced final decision prevented additional delegation"],
                "open_issues": ["模型在最终决策轮仍尝试继续委派，已强制转为 partial 收尾。"],
                "confidence": "medium",
                "report_path": report_path,
                "findings_path": findings_path,
                "required_sections": list(self.meta.get("required_sections", []) or []),
                "min_findings": int(self.meta.get("min_findings", 0) or 0),
            }
            decision = {
                "action": action_name,
                "reasoning": "forced_final_decision 禁止继续委派，已强制转为 complete_task。",
                "params": params,
            }

        if action_name == "delegate_task":
            params = self._apply_delegate_defaults(params, parallel_mode=False)
            task_ids = self.task_plan_executor.create_or_extend([params])  # 创建task plan
            self.latest_plan_task_ids = task_ids
            if task_ids:
                self.task_plan_executor.mark_running(task_ids[0])
        elif action_name == "continue_task":
            params = self._apply_continue_defaults(params)
            self.latest_plan_task_ids = []
        elif action_name in {"list_worker_sessions", "inspect_worker_session", "wait_worker_sessions", "close_worker_session"}:
            self.latest_plan_task_ids = []
        elif action_name == "delegate_tasks":
            params = self._apply_delegate_tasks_defaults(params)
            task_ids = self.task_plan_executor.create_or_extend(params.get("tasks") or [])
            self.latest_plan_task_ids = task_ids
            for task_id in task_ids:
                self.task_plan_executor.mark_running(task_id)
        else:
            self.latest_plan_task_ids = []

        # 调用__call__
        tool = next((item for item in self.tools if item.name == action_name), None)
        if tool is None:
            raise ValueError(f"Unknown action from MainAgent: {action_name}")

        result = await tool(**self._tool_params(action_name, params))
        self._update_context(action_name, params, result)

        logger.log_to_file(
            LogLevel.INFO,
            f"[MainAgent] Parsed decision:\n{json.dumps(decision, ensure_ascii=False, indent=2)}\n",
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
            "profile": self._infer_profile(str(base_params.get("task_instruction", ""))),
            "tools": base_params.get("tools", []),
            "steps_taken": task_result.get("steps_taken", 0),
            "message": finish_result.get("message", ""),
            "completed": finish_result.get("completed", []),
            "issues": finish_result.get("issues", []),
            "result": finish_result.get("result", ""),
            "trace_summary": task_result.get("trace_summary", ""),
            "session_id": task_result.get("session_id", ""),
            "session_rounds": task_result.get("session_rounds", 1),
            "worker_reused": task_result.get("worker_reused", False),
            "worker_state": task_result.get("worker_state", ""),
        }
        self.task_entries.append(entry)

    def _update_context(self, action: str, params: Dict[str, Any], result: Dict[str, Any]) -> None:
        summary = [f"[attempt {self.attempt}] action={action}"]

        if action == "delegate_task":
            self._append_task_entry(params, result)
            finish = result.get("finish_result", {})
            if self.latest_plan_task_ids and finish.get("status") != "running":
                self.task_plan_executor.mark_finished(self.latest_plan_task_ids[0], finish)
            summary.append(f"status={finish.get('status', 'partial')}")
            summary.append(f"tools={params.get('tools', [])}")
            if result.get("session_id"):
                summary.append(f"session_id={result.get('session_id')}")

        if action == "continue_task":
            self._append_task_entry(params, result)
            finish = result.get("finish_result", {})
            summary.append(f"status={finish.get('status', 'partial')}")
            summary.append(f"continued_session={result.get('session_id', '')}")
            summary.append(f"tools={params.get('tools', [])}")

        if action == "list_worker_sessions":
            summary.append(f"subagent_session_count={result.get('count', 0)}")

        if action == "inspect_worker_session":
            inspected = (result.get("session", {}) or {}).get("session_id", params.get("session_id", ""))
            summary.append(f"inspected_session={inspected}")

        if action == "wait_worker_sessions":
            for item in result.get("results", []) or []:
                self._append_task_entry(
                    {
                        "task_instruction": item.get("task_instruction", ""),
                        "model": item.get("model", ""),
                        "tools": item.get("allowed_tools", []),
                    },
                    item,
                )
            summary.append(f"wait_summary={result.get('summary', {})}")

        if action == "close_worker_session":
            summary.append(f"closed_session={result.get('session_id', params.get('session_id', ''))}")

        if action == "delegate_tasks":
            for idx, item in enumerate(result.get("results", []) or []):
                task_params = (params.get("tasks") or [{}])[idx] if idx < len(params.get("tasks") or []) else {}
                self._append_task_entry(task_params, item)
                if idx < len(self.latest_plan_task_ids) and item.get("finish_result", {}).get("status") != "running":
                    self.task_plan_executor.mark_finished(
                        self.latest_plan_task_ids[idx],
                        item.get("finish_result", {}),
                    )
            summary.append(f"batch_summary={result.get('summary', {})}")

        if action == "complete_task":
            summary.append(f"report_path={params.get('report_path', '')}")
            summary.append(f"confidence={params.get('confidence', '')}")
            if not result.get("quality_gate_passed", False):
                summary.append(f"quality_issues={result.get('issues', [])}")

        plan_snapshot = self.task_plan_executor.snapshot()
        summary.append(f"current_phase={self._current_phase()}")
        summary.append(f"plan_state={json.dumps(plan_snapshot, ensure_ascii=False)}")

        self.context = "\n".join(summary) + "\n\n" + self.context
        self.history.append({"attempt": self.attempt, "action": action, "result": result})

    async def run(self, request: Optional[str] = None) -> str:
        return request or ""

