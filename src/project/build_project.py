from __future__ import annotations

import asyncio
import importlib.util
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Tuple

from agents.main_agent import MainAgent
from agents.sub_agent import SubAgent
from base.engine.async_llm import LLMsConfig, create_llm_instance
from base.engine.logs import logger
from core.message import (
    ErrorMessage,
    OrchestratorDecision,
    OrchestratorThinking,
    PhaseTransition,
    ShellMessage,
    StatusUpdate,
    SubAgentCreated,
    TaskCancelled,
    TaskComplete,
    WorkerCompleted,
    WorkerSpawned,
    WorkerWaitEnd,
    WorkerWaitStart,
)
from core.runner import AgentRunner
from environments.environment import TaskExecutionEnvironment
from modes.router import ModeDecision, ModeRouter
from orchestration_tools.complete_task import CompleteTaskTool
from orchestration_tools.delegate import (
    CloseWorkerSessionTool,
    ContinueTaskTool,
    DelegateTaskTool,
    DelegateTasksTool,
    InspectWorkerSessionTool,
    ListWorkerSessionsTool,
    WaitWorkerSessionsTool,
    agent_label,
)
from project.prompts import GenericMainPromptBuilder, GenericSubPromptBuilder
from project.tools import (
    ListSourcesTool,
    ReadScratchpadTool,
    ReadSourceTool,
    ReadSourcesTool,
    RecordFindingTool,
    SearchSourcesTool,
    VerifyArtifactsTool,
    WebSearchTool,
    WriteReportSectionTool,
    WriteScratchpadNoteTool,
)


@dataclass(frozen=True)
class RuntimeProfile:
    name: str = "generic"
    report_filename: str = "task_report.md"
    required_sections: List[str] = field(
        default_factory=lambda: [
            "Executive Summary",
            "Key Findings",
            "Actionable Recommendations",
        ]
    )
    min_findings: int = 5
    task_goal: str = "完成用户任务并交付可验证结果。"
    workflow_hints: List[str] = field(default_factory=list)
    completion_requirements: List[str] = field(default_factory=list)
    subtask_toolkits: Dict[str, List[str]] = field(default_factory=dict)
    default_worker_tools: List[str] = field(default_factory=list)
    parallel_forbidden_tools: List[str] = field(default_factory=list)


def _normalize_sub_models(main_model: str, sub_models: List[Any]) -> List[str]:
    normalized: List[str] = []
    for item in sub_models or []:
        if isinstance(item, dict):
            name = str(item.get("name") or item.get("model") or "").strip()
        else:
            name = str(item).strip()
        if name and name not in normalized:
            normalized.append(name)
    main = str(main_model or "").strip()
    if main and main not in normalized:
        normalized.insert(0, main)
    return normalized


def _default_subtask_toolkits() -> Dict[str, List[str]]:
    return {
        "policy_research": [
            "search_sources",
            "read_sources",
            "read_source",
            "web_search",
            "record_finding",
            "write_scratchpad_note",
        ],
        "company_research": [
            "search_sources",
            "read_sources",
            "read_source",
            "web_search",
            "record_finding",
            "write_scratchpad_note",
        ],
        "supply_chain": [
            "search_sources",
            "read_sources",
            "read_source",
            "web_search",
            "record_finding",
            "write_scratchpad_note",
        ],
        "financial_metrics": [
            "search_sources",
            "read_sources",
            "read_source",
            "web_search",
            "record_finding",
            "write_scratchpad_note",
        ],
        "news_signals": [
            "web_search",
            "record_finding",
            "write_scratchpad_note",
        ],
        "report_drafting": [
            "read_scratchpad",
            "search_sources",
            "read_sources",
            "read_source",
            "write_report_section",
            "write_scratchpad_note",
        ],
        "verification": [
            "read_scratchpad",
            "verify_artifacts",
            "write_scratchpad_note",
        ],
        "general_research": [
            "search_sources",
            "read_sources",
            "read_source",
            "web_search",
            "record_finding",
            "write_scratchpad_note",
        ],
    }


def _default_worker_tools() -> List[str]:
    return [
        "list_sources",
        "search_sources",
        "read_source",
        "read_sources",
        "web_search",
        "record_finding",
        "write_scratchpad_note",
        "read_scratchpad",
        "write_report_section",
        "verify_artifacts",
    ]


def _default_parallel_forbidden_tools() -> List[str]:
    return ["write_report_section"]


def _default_model_routing(sub_models: List[str]) -> Dict[str, str]:
    """Backward-compatible default profile-to-model routing used by tests/config callers."""
    if not sub_models:
        model = ""
        return {
            "policy_research": model,
            "company_research": model,
            "supply_chain": model,
            "financial_metrics": model,
            "news_signals": model,
            "report_drafting": model,
            "verification": model,
            "general_research": model,
        }

    primary = sub_models[0]
    secondary = sub_models[1] if len(sub_models) > 1 else primary
    return {
        "policy_research": primary,
        "company_research": secondary,
        "supply_chain": primary,
        "financial_metrics": primary,
        "news_signals": secondary,
        "report_drafting": secondary,
        "verification": secondary,
        "general_research": secondary,
    }


def _generic_profile(sub_models: List[str]) -> RuntimeProfile:
    return RuntimeProfile(
        workflow_hints=[
            "委派前先理解用户目标、约束和期望产物。",
            "只有当探索、执行或验证需要并行性或隔离性时，才启动 SubAgent。",
            "最终完成前，由 MainAgent 综合 SubAgent 结果。",
            "最终答案或产物必须对照用户请求完成验证。",
        ],
        completion_requirements=[
            "返回简洁的完成总结。",
            "如有重要产物或证据，需要列出。",
            "如果任务为 partial 或 blocked，需要说明剩余问题。",
        ],
        subtask_toolkits=_default_subtask_toolkits(),
        default_worker_tools=_default_worker_tools(),
        parallel_forbidden_tools=_default_parallel_forbidden_tools(),
    )


def _gba_profile(sub_models: List[str]) -> RuntimeProfile:
    return RuntimeProfile(
        name="gba_industry_analysis",
        report_filename="gba_industry_report.md",
        required_sections=[
            "执行摘要",
            "政策驱动与约束",
            "城市与产业比较",
            "投资机会与风险",
        ],
        min_findings=5,
        task_goal="生成一份结构化的粤港澳大湾区产业分析报告，并给出可行动结论。",
        workflow_hints=[
            "先收集证据；优先记录带来源链接或明确证据的发现。",
            "政策、城市比较、机会和风险等独立研究线索应优先并行委派。",
            "写入可复用的 scratchpad 笔记，便于综合阶段复用中间结论。",
            "收集到足够发现后再撰写报告章节。",
            "完成前检查报告章节、来源覆盖和 findings 数量。",
        ],
        completion_requirements=[
            "在 report_path 生成 markdown 报告。",
            "包含所有必需报告章节。",
            "在 findings.jsonl 中保留足够的有来源发现。",
            "报告或 findings 中应包含明确来源链接或证据。",
        ],
        subtask_toolkits=_default_subtask_toolkits(),
        default_worker_tools=_default_worker_tools(),
        parallel_forbidden_tools=_default_parallel_forbidden_tools(),
    )


def _resolve_profile(
    sub_models: List[str],
    profile_name: str | None = None,
    report_filename: str | None = None,
    required_sections: List[str] | None = None,
    min_findings: int | None = None,
    task_goal: str | None = None,
    workflow_hints: List[str] | None = None,
    completion_requirements: List[str] | None = None,
    subtask_toolkits: Dict[str, List[str]] | None = None,
    default_worker_tools: List[str] | None = None,
    parallel_forbidden_tools: List[str] | None = None,
) -> RuntimeProfile:
    normalized_name = (profile_name or "generic").strip() or "generic"
    base = (
        _gba_profile(sub_models)
        if normalized_name == "gba_industry_analysis"
        else _generic_profile(sub_models)
    )

    if normalized_name != base.name:
        base = RuntimeProfile(
            name=normalized_name,
            report_filename=base.report_filename,
            required_sections=list(base.required_sections),
            min_findings=base.min_findings,
            task_goal=base.task_goal,
            workflow_hints=list(base.workflow_hints),
            completion_requirements=list(base.completion_requirements),
            subtask_toolkits=dict(base.subtask_toolkits),
            default_worker_tools=list(base.default_worker_tools),
            parallel_forbidden_tools=list(base.parallel_forbidden_tools),
        )

    return RuntimeProfile(
        name=base.name,
        report_filename=report_filename or base.report_filename,
        required_sections=list(required_sections or base.required_sections),
        min_findings=base.min_findings if min_findings is None else min_findings,
        task_goal=task_goal or base.task_goal,
        workflow_hints=list(workflow_hints or base.workflow_hints),
        completion_requirements=list(completion_requirements or base.completion_requirements),
        subtask_toolkits=dict(subtask_toolkits or base.subtask_toolkits),
        default_worker_tools=list(default_worker_tools or base.default_worker_tools),
        parallel_forbidden_tools=list(parallel_forbidden_tools or base.parallel_forbidden_tools),
    )


def _infer_required_sections_from_brief(brief_text: str) -> List[str]:
    text = str(brief_text or "")
    candidates = [
        "执行摘要",
        "城市比较",
        "政策驱动",
        "政策驱动与约束",
        "城市与产业比较",
        "投资机会与风险",
        "关键发现",
        "行动建议",
        "Executive Summary",
        "City Comparison",
        "Policy Drivers and Constraints",
        "Key Findings",
        "Actionable Recommendations",
    ]
    found: List[str] = []
    for title in candidates:
        if title in text and title not in found:
            found.append(title)
    return found


@dataclass
class AgentProject:
    main_agent: MainAgent
    max_attempts: int
    final_wait_seconds: int = 180
    model_retry_failures: Dict[str, set[str]] = field(default_factory=dict)

    def _main_report_exists(self) -> bool:
        report_path = str(self.main_agent.meta.get("report_path", "") or "").strip()
        return bool(report_path) and Path(report_path).exists()

    def _build_synthesis_instruction(self) -> str:
        required_sections = list(self.main_agent.meta.get("required_sections", []) or [])
        report_path = str(self.main_agent.meta.get("report_path", "") or "").strip()
        findings_path = str(self.main_agent.meta.get("findings_path", "") or "").strip()
        scratchpad_path = str(self.main_agent.meta.get("scratchpad_path", "") or "").strip()
        sections = "、".join(str(item) for item in required_sections) if required_sections else "按用户任务要求组织章节"
        return (
            "任务类型: write\n"
            "期望产出: 在主 report_path 生成最终 markdown 报告\n"
            f"完成标准: 报告写入 {report_path}；包含章节 {sections}；"
            "整合已收集 findings/scratchpad/session 结果；正文保留关键来源链接；完成后 finish。\n"
            "具体任务: 不要继续写 parallel_runs 中的中间报告。读取已有 findings 和 scratchpad，"
            "综合所有已完成或 partial 的 SubAgent 结果，生成面向用户的最终报告。\n"
            f"主报告路径: {report_path}\n"
            f"findings_path: {findings_path}\n"
            f"scratchpad_path: {scratchpad_path}"
        )

    def _build_synthesis_context(self) -> str:
        entries = []
        for item in self.main_agent.task_entries:
            trace_summary = str(item.get("trace_summary", "") or "")
            finish = {
                "status": item.get("status", ""),
                "message": item.get("message", ""),
                "completed": list(item.get("completed", []) or [])[:8],
                "issues": [str(issue)[:300] for issue in list(item.get("issues", []) or [])[:6]],
                "result": str(item.get("result", "") or "")[:1200],
                "session_id": item.get("session_id", ""),
                "profile": item.get("profile", ""),
                "trace_digest": trace_summary[:800],
            }
            entries.append(finish)
        findings_preview = []
        findings_path = Path(str(self.main_agent.meta.get("findings_path", "") or ""))
        if findings_path.is_file():
            for line in findings_path.read_text(encoding="utf-8").splitlines()[:12]:
                line = line.strip()
                if not line:
                    continue
                try:
                    item = json.loads(line)
                    if isinstance(item, dict):
                        findings_preview.append({
                            key: str(value)[:600]
                            for key, value in item.items()
                            if key in {"topic", "entity", "finding", "evidence", "source_url", "source_title"}
                        })
                    else:
                        findings_preview.append({"raw": str(item)[:500]})
                except json.JSONDecodeError:
                    findings_preview.append({"raw": line[:500]})
        return (
            "以下是 MainAgent 已收集的 SubAgent 结果摘要。请把它们作为中间材料综合，"
            "不要逐段机械拼接。\n\n"
            f"[session_summaries]\n{json.dumps(entries, ensure_ascii=False, indent=2)}\n\n"
            f"[merged_findings_preview]\n{json.dumps(findings_preview, ensure_ascii=False, indent=2)}"
        )

    async def _collect_remaining_sessions(self, attempts: List[Dict[str, Any]]) -> Dict[str, Any]:
        wait_tool = next((item for item in self.main_agent.tools if item.name == "wait_worker_sessions"), None)
        if wait_tool is None:
            return {}

        timeout = int(
            self.main_agent.meta.get(
                "final_wait_seconds",
                self.main_agent.meta.get("subagent_process_timeout_seconds", self.final_wait_seconds),
            )
            or self.final_wait_seconds
        )
        timeout = max(1, timeout)
        params = {"session_ids": [], "timeout_seconds": timeout}
        logger.info(f"[AgentProject] Final wait for running SubAgent sessions timeout={timeout}s")
        result = await wait_tool(**params)
        context_params = dict(params)
        context_params["_event_type"] = "final_wait"
        self.main_agent._update_context("wait_worker_sessions", context_params, result)
        action = {
            "action": "wait_worker_sessions",
            "params": params,
            "result": result,
            "forced_final_wait": True,
        }
        attempts.append({"action": action, "raw_response": "forced final wait for running SubAgent sessions"})
        return result

    def _running_session_ids(self) -> List[str]:
        wait_tool = next((item for item in self.main_agent.tools if item.name == "wait_worker_sessions"), None)
        if wait_tool is None:
            return []
        session_store = getattr(wait_tool, "session_store", {}) or {}
        return [
            str(session_id)
            for session_id, session in session_store.items()
            if session.get("state") == "running"
        ]

    def _wait_timeout_seconds(self) -> int:
        timeout = int(
            self.main_agent.meta.get(
                "final_wait_seconds",
                self.main_agent.meta.get("subagent_process_timeout_seconds", self.final_wait_seconds),
            )
            or self.final_wait_seconds
        )
        return max(1, timeout)

    @staticmethod
    def _retry_key_for_task(task_instruction: str) -> str:
        return " ".join(str(task_instruction or "").lower().split())

    @staticmethod
    def _is_model_unavailable_result(item: Dict[str, Any]) -> bool:
        finish = item.get("finish_result", {}) or {}
        status = str(finish.get("status", "") or item.get("worker_state", "")).strip().lower()
        if status not in {"blocked", "failed"}:
            return False
        text = " ".join(
            str(part)
            for part in [
                finish.get("message", ""),
                " ".join(str(issue) for issue in list(finish.get("issues", []) or [])),
                item.get("error", ""),
                json.dumps(item.get("worker_process", {}) or {}, ensure_ascii=False),
            ]
        ).lower()
        model_failure_markers = (
            "sub-agent worker failed",
            "configuration for",
            "api key",
            "apikey",
            "unauthorized",
            "authentication",
            "permission",
            "invalid model",
            "model not found",
            "rate limit",
            "timeout",
            "connection",
            "base_url",
            "openai",
            "llm",
            "401",
            "403",
            "429",
            "5xx",
        )
        return any(marker in text for marker in model_failure_markers)

    def _select_retry_model(self, failed_model: str, task_instruction: str) -> str:
        if len(self.main_agent.sub_models) <= 1:
            return ""
        key = self._retry_key_for_task(task_instruction)
        failed_models = self.model_retry_failures.setdefault(key, set())
        if failed_model:
            failed_models.add(failed_model)
        for model in self.main_agent.sub_models:
            if model not in failed_models:
                return model
        return ""

    @staticmethod
    def _merge_wait_results(primary: Dict[str, Any], extra: Dict[str, Any]) -> Dict[str, Any]:
        if not extra:
            return primary
        merged = dict(primary or {})
        merged_results = list((primary or {}).get("results", []) or [])
        merged_results.extend(list(extra.get("results", []) or []))
        primary_summary = dict((primary or {}).get("summary", {}) or {})
        extra_summary = dict(extra.get("summary", {}) or {})
        merged_summary = dict(primary_summary)
        for key in ("completed", "still_running", "merged_findings", "merged_scratchpads"):
            merged_summary[key] = int(primary_summary.get(key, 0) or 0) + int(extra_summary.get(key, 0) or 0)
        waited_for = list(primary_summary.get("waited_for", []) or [])
        waited_for.extend(list(extra_summary.get("waited_for", []) or []))
        if waited_for:
            merged_summary["waited_for"] = waited_for
        merged["results"] = merged_results
        merged["summary"] = merged_summary
        return merged

    async def _retry_model_unavailable_sessions(
        self,
        attempts: List[Dict[str, Any]],
        wait_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        results = list((wait_result or {}).get("results", []) or [])
        if not results:
            return {}
        delegate_tool = next((item for item in self.main_agent.tools if item.name == "delegate_task"), None)
        wait_tool = next((item for item in self.main_agent.tools if item.name == "wait_worker_sessions"), None)
        if delegate_tool is None or wait_tool is None:
            return {}

        retry_session_ids: List[str] = []
        for item in results:
            if not self._is_model_unavailable_result(item):
                continue
            failed_model = str(item.get("model", "") or "").strip()
            task_instruction = str(item.get("task_instruction", "") or "").strip()
            retry_model = self._select_retry_model(failed_model, task_instruction)
            if not retry_model:
                continue

            old_session_id = str(item.get("session_id", "") or "").strip()
            old_session = getattr(wait_tool, "session_store", {}).get(old_session_id, {}) or {}
            retry_params = {
                "task_instruction": task_instruction,
                "context": old_session.get("last_context", old_session.get("context", "")),
                "model": retry_model,
                "tools": list(item.get("allowed_tools") or old_session.get("tools") or []),
            }
            logger.info(
                "[AgentProject] Retry subtask with alternate sub_model "
                f"old_session={old_session_id} failed_model={failed_model} retry_model={retry_model}"
            )
            spawn_result = await delegate_tool._spawn_single(
                task_instruction=retry_params["task_instruction"],
                model=retry_params["model"],
                context=retry_params["context"],
                tools=retry_params["tools"],
                result_schema=old_session.get("result_schema"),
                env_override=old_session.get("env"),
            )
            self.main_agent._update_context("delegate_task", retry_params, spawn_result)
            attempts.append(
                {
                    "action": {
                        "action": "delegate_task",
                        "params": retry_params,
                        "result": spawn_result,
                        "model_retry": True,
                        "failed_model": failed_model,
                        "previous_session_id": old_session_id,
                    },
                    "raw_response": "model unavailable retry delegate_task",
                }
            )
            session_id = str(spawn_result.get("session_id", "") or "").strip()
            if session_id:
                retry_session_ids.append(session_id)

        if not retry_session_ids:
            return {}

        retry_wait_params = {
            "session_ids": retry_session_ids,
            "timeout_seconds": self._wait_timeout_seconds(),
            "_event_type": "auto_wait",
        }
        retry_wait_result = await wait_tool(
            session_ids=retry_session_ids,
            timeout_seconds=retry_wait_params["timeout_seconds"],
        )
        self.main_agent._update_context("wait_worker_sessions", retry_wait_params, retry_wait_result)
        attempts.append(
            {
                "action": {
                    "action": "wait_worker_sessions",
                    "params": {
                        "session_ids": retry_session_ids,
                        "timeout_seconds": retry_wait_params["timeout_seconds"],
                    },
                    "result": retry_wait_result,
                    "model_retry_wait": True,
                },
                "raw_response": "model unavailable retry wait",
            }
        )
        return retry_wait_result

    async def _wait_for_running_sessions(self, attempts: List[Dict[str, Any]]) -> Dict[str, Any]:
        running_ids = self._running_session_ids()
        if not running_ids:
            return {}
        wait_tool = next((item for item in self.main_agent.tools if item.name == "wait_worker_sessions"), None)
        if wait_tool is None:
            return {}

        timeout = self._wait_timeout_seconds()
        params = {"session_ids": running_ids, "timeout_seconds": timeout}
        logger.info(
            "[AgentProject] Auto wait for running SubAgent sessions "
            f"count={len(running_ids)} timeout={timeout}s"
        )
        result = await wait_tool(**params)
        context_params = dict(params)
        context_params["_event_type"] = "auto_wait"
        self.main_agent._update_context("wait_worker_sessions", context_params, result)
        action = {
            "action": "wait_worker_sessions",
            "params": params,
            "result": result,
            "auto_wait": True,
        }
        attempts.append({"action": action, "raw_response": "auto wait for running SubAgent sessions"})
        retry_result = await self._retry_model_unavailable_sessions(attempts, result)
        return self._merge_wait_results(result, retry_result)

    async def _run_synthesis_if_needed(self, attempts: List[Dict[str, Any]]) -> Dict[str, Any]:
        if self._main_report_exists():
            return {}
        if not self.main_agent.task_entries:
            return {}

        delegate_tool = next((item for item in self.main_agent.tools if item.name == "delegate_task"), None)
        wait_tool = next((item for item in self.main_agent.tools if item.name == "wait_worker_sessions"), None)
        if delegate_tool is None or wait_tool is None:
            return {}

        params = {
            "task_instruction": self._build_synthesis_instruction(),
            "context": self._build_synthesis_context(),
            "model": self.main_agent.sub_models[0] if self.main_agent.sub_models else "",
            "tools": [
                "read_scratchpad",
                "read_sources",
                "read_source",
                "record_finding",
                "write_report_section",
                "verify_artifacts",
            ],
        }
        params = self.main_agent._apply_delegate_defaults(params, parallel_mode=False)
        logger.info("[AgentProject] Forced synthesis: start write SubAgent for main report_path")
        spawn_result = await delegate_tool(**self.main_agent._tool_params("delegate_task", params))
        self.main_agent._update_context("delegate_task", params, spawn_result)
        spawn_action = {
            "action": "delegate_task",
            "params": params,
            "result": spawn_result,
            "forced_synthesis": True,
        }
        attempts.append({"action": spawn_action, "raw_response": "forced synthesis delegate_task"})

        session_id = str(spawn_result.get("session_id", "") or "").strip()
        timeout = int(
            self.main_agent.meta.get(
                "final_wait_seconds",
                self.main_agent.meta.get("subagent_process_timeout_seconds", self.final_wait_seconds),
            )
            or self.final_wait_seconds
        )
        wait_params = {"session_ids": [session_id] if session_id else [], "timeout_seconds": max(1, timeout)}
        wait_result = await wait_tool(**wait_params)
        context_wait_params = dict(wait_params)
        context_wait_params["_event_type"] = "forced_synthesis_wait"
        self.main_agent._update_context("wait_worker_sessions", context_wait_params, wait_result)
        wait_action = {
            "action": "wait_worker_sessions",
            "params": wait_params,
            "result": wait_result,
            "forced_synthesis_wait": True,
        }
        attempts.append({"action": wait_action, "raw_response": "forced synthesis wait"})
        return wait_result

    # ── helpers for extracting worker events from step results ──────

    @staticmethod
    def _extract_worker_events(
        action: Dict[str, Any],
    ) -> List[ShellMessage]:
        """Extract worker lifecycle messages from a MainAgent step result.
        SubAgentCreated are emitted first (four-tuple display), then WorkerSpawned.
        """
        messages: List[ShellMessage] = []
        result = action.get("result", {}) or {}
        action_name = action.get("action", "")

        if action_name == "delegate_task":
            session_id = str(result.get("session_id", "") or "")
            finish = result.get("finish_result", {}) or {}
            label = agent_label(
                str(action.get("params", {}).get("task_instruction", "")),
            )
            # Phase 1: task first
            if session_id:
                messages.append(
                    WorkerSpawned(
                        session_id=session_id,
                        label=label,
                        model=str(action.get("params", {}).get("model", "")),
                        task_instruction=str(
                            action.get("params", {}).get("task_instruction", "")
                        ),
                    )
                )
            # Phase 2: then agent four-tuple
            tools = list(result.get("allowed_tools", []) or [])
            messages.append(
                SubAgentCreated(
                    agent_id=session_id or "sub",
                    model=str(action.get("params", {}).get("model", "")),
                    tools=tools,
                    task_instruction=str(
                        action.get("params", {}).get("task_instruction", "")
                    ),
                    task_label=label,
                )
            )
            status = (
                str(finish.get("status", "") or result.get("worker_state", ""))
                .strip()
                .lower()
            )
            if status and status != "running":
                messages.append(
                    WorkerCompleted(
                        session_id=session_id,
                        label=label,
                        status=status,
                        steps_taken=int(result.get("steps_taken", 0)),
                        cost=float(result.get("cost", 0.0)),
                        message=str(finish.get("message", "") or ""),
                        issues=list(finish.get("issues", []) or []),
                    )
                )

        elif action_name == "delegate_tasks":
            # Phase 1: list all tasks first
            for idx, item in enumerate(result.get("results", []) or []):
                session_id = str(item.get("session_id", "") or "")
                label = agent_label(
                    str(item.get("task_instruction", "")),
                    idx + 1,
                )
                if session_id:
                    messages.append(
                        WorkerSpawned(
                            session_id=session_id,
                            label=label,
                            model=str(item.get("model", "")),
                            task_instruction=str(item.get("task_instruction", "")),
                        )
                    )
            # Phase 2: then show agent four-tuple assembly
            for idx, item in enumerate(result.get("results", []) or []):
                tools = list(item.get("allowed_tools", []) or [])
                label = agent_label(
                    str(item.get("task_instruction", "")),
                    idx + 1,
                )
                messages.append(
                    SubAgentCreated(
                        agent_id=f"agent_{idx + 1}",
                        model=str(item.get("model", "")),
                        tools=tools,
                        task_instruction=str(item.get("task_instruction", "")),
                        task_label=label,
                    )
                )
            # Phase 3: WorkerCompleted for already-finished tasks
            for idx, item in enumerate(result.get("results", []) or []):
                session_id = str(item.get("session_id", "") or "")
                finish = item.get("finish_result", {}) or {}
                label = agent_label(
                    str(item.get("task_instruction", "")),
                    idx + 1,
                )
                status = (
                    str(finish.get("status", "") or item.get("worker_state", ""))
                    .strip()
                    .lower()
                )
                if status and status != "running":
                    messages.append(
                        WorkerCompleted(
                            session_id=session_id,
                            label=label,
                            status=status,
                            steps_taken=int(item.get("steps_taken", 0)),
                            cost=float(item.get("cost", 0.0)),
                            message=str(finish.get("message", "") or ""),
                            issues=list(finish.get("issues", []) or []),
                        )
                    )

        elif action_name == "wait_worker_sessions":
            messages.append(
                WorkerWaitEnd(
                    completed=int(
                        result.get("summary", {}).get("completed", 0) or 0
                    ),
                    still_running=int(
                        result.get("summary", {}).get("still_running", 0) or 0
                    ),
                    results=list(result.get("results", []) or []),
                )
            )

        return messages

    # ── streaming API ─────────────────────────────────────────────

    async def stream(
        self,
        cancel_event: asyncio.Event | None = None,
    ) -> AsyncGenerator[ShellMessage, None]:
        """Run the multi-agent pipeline, yielding ShellMessages.

        If *cancel_event* is set, the loop stops at the next checkpoint
        and yields a :class:`TaskCancelled` message.
        """

        attempts: List[Dict[str, Any]] = []
        final_result = None
        last_complete_result = None
        prev_phase = ""
        accumulated_cost = 0.0
        accumulated_input_tokens = 0
        accumulated_output_tokens = 0

        for attempt_idx in range(self.max_attempts):
            if cancel_event is not None and cancel_event.is_set():
                yield TaskCancelled(
                    message="Cancelled by user.",
                    attempts=attempt_idx + 1,
                )
                break

            current_phase = self.main_agent._current_phase()
            if current_phase != prev_phase:
                yield PhaseTransition(
                    from_phase=prev_phase or "start",
                    to_phase=current_phase,
                    guidance=self.main_agent._phase_guidance(),
                )
                prev_phase = current_phase

            yield OrchestratorThinking(
                attempt=attempt_idx + 1,
                max_attempts=self.max_attempts,
            )

            action, raw_response = await self.main_agent.step(None, [])
            attempts.append({"action": action, "raw_response": raw_response})

            action_name = action.get("action", "")
            yield OrchestratorDecision(
                action=action_name,
                reasoning=action.get("reasoning", ""),
                params=action.get("params", {}),
                raw_response=raw_response or "",
            )

            for msg in self._extract_worker_events(action):
                yield msg
                if isinstance(msg, WorkerCompleted):
                    accumulated_cost += msg.cost

            if action_name in {"delegate_task", "delegate_tasks", "continue_task"}:
                running_ids = self._running_session_ids()
                if running_ids:
                    wait_timeout = self._wait_timeout_seconds()
                    yield WorkerWaitStart(
                        session_ids=running_ids,
                        timeout_seconds=wait_timeout,
                    )
                    wait_result = await self._wait_for_running_sessions(attempts)
                    wait_summary = (
                        wait_result.get("summary", {})
                        if isinstance(wait_result, dict)
                        else {}
                    )
                    wait_results = (
                        wait_result.get("results", []) or []
                        if isinstance(wait_result, dict)
                        else []
                    )
                    yield WorkerWaitEnd(
                        completed=int(wait_summary.get("completed", 0) or 0),
                        still_running=int(wait_summary.get("still_running", 0) or 0),
                        results=list(wait_results),
                    )
                    for item in wait_results:
                        finish = item.get("finish_result", {}) or {}
                        accumulated_cost += float(item.get("cost", 0.0) or 0.0)
                        accumulated_input_tokens += int(item.get("input_tokens", 0) or 0)
                        accumulated_output_tokens += int(item.get("output_tokens", 0) or 0)

            # Emit token status after each orchestration step
            llm_summary = (
                self.main_agent.llm.get_usage_summary()
                if getattr(self.main_agent, "llm", None)
                else {}
            )
            yield StatusUpdate(
                input_tokens=llm_summary.get("total_input_tokens", 0),
                output_tokens=llm_summary.get("total_output_tokens", 0),
                total_tokens=llm_summary.get("total_tokens", 0),
                phase=self.main_agent._current_phase(),
                elapsed="",
            )

            if action_name != "complete_task":
                continue

            result = action.get("result", {})
            last_complete_result = result
            if result.get("done") and result.get("quality_gate_passed"):
                final_result = result
                break

        # ── forced finalization ────────────────────────────────────
        if final_result is None and not (
            cancel_event is not None and cancel_event.is_set()
        ):
            yield WorkerWaitStart(
                session_ids=[],
                timeout_seconds=self.final_wait_seconds,
            )
            final_wait_result = await self._collect_remaining_sessions(attempts)
            summary = (
                final_wait_result.get("summary", {})
                if isinstance(final_wait_result, dict)
                else {}
            )
            yield WorkerWaitEnd(
                completed=int(summary.get("completed", 0) or 0),
                still_running=int(summary.get("still_running", 0) or 0),
                results=list(
                    (final_wait_result.get("results", []) or [])
                    if isinstance(final_wait_result, dict)
                    else []
                ),
            )

            # Always attempt forced finalization with whatever results we have
            await self._run_synthesis_if_needed(attempts)
            previous_max = self.main_agent.max_attempts
            self.main_agent.max_attempts = max(
                previous_max, self.main_agent.attempt + 1
            )
            try:
                action, raw_response = await self.main_agent.step(
                    None, [], forced_final_decision=True
                )
            finally:
                self.main_agent.max_attempts = previous_max
            action["forced_final_decision"] = True
            attempts.append({"action": action, "raw_response": raw_response})
            if action["action"] == "complete_task":
                result = action.get("result", {})
                last_complete_result = result
                if result.get("done") and result.get("quality_gate_passed"):
                    final_result = result

        # Aggregate main agent's own LLM cost
        main_usage = (
            self.main_agent.llm.get_usage_summary()
            if getattr(self.main_agent, "llm", None)
            else {}
        )
        accumulated_cost += float(main_usage.get("total_cost", 0.0) or 0.0)
        accumulated_input_tokens += int(main_usage.get("total_input_tokens", 0) or 0)
        accumulated_output_tokens += int(main_usage.get("total_output_tokens", 0) or 0)
        total_tokens = accumulated_input_tokens + accumulated_output_tokens

        display_result = final_result or last_complete_result
        passed = (
            final_result is not None
            and final_result.get("quality_gate_passed", False)
        )
        yield TaskComplete(
            success=passed,
            quality_gate_passed=passed,
            attempts=len(attempts),
            total_cost=accumulated_cost,
            cost_known=not (total_tokens > 0 and accumulated_cost == 0),
            total_tokens=total_tokens,
            input_tokens=accumulated_input_tokens,
            output_tokens=accumulated_output_tokens,
            summary=str(
                (display_result or {}).get("executive_summary", "")
            ),
            final_result=display_result,
        )

        self._run_result = {
            "attempts": attempts,
            "final_result": display_result,
        }

    async def run(self):
        """Run to completion (backward-compatible wrapper)."""
        self._run_result = None
        async for _ in self.stream():
            pass
        return self._run_result or {"attempts": [], "final_result": None}


@dataclass
class SingleAgentProject:
    sub_agent: SubAgent
    env: TaskExecutionEnvironment

    async def stream(
        self,
        cancel_event: asyncio.Event | None = None,
    ) -> AsyncGenerator[ShellMessage, None]:
        """Run single-agent mode, yielding ShellMessages."""
        runner = AgentRunner()
        async for msg in runner.stream(
            self.sub_agent, self.env, cancel_event=cancel_event
        ):
            yield msg
        result = runner._last_result
        if result is None:
            yield ErrorMessage(
                error_type="no_result",
                message="Single-agent runner produced no result.",
            )
            self._run_result = {"attempts": [], "final_result": None}
            return

        finish_result = {}
        if result.trace:
            finish_result = (
                result.trace[-1].info.get("finish_result", {})
                if result.trace[-1].info.get("finished")
                else {}
            )

        meta = self.env.meta_data or {}
        report_path = str(
            meta.get("report_path", str(self.env.output_dir / "task_report.md"))
        )
        findings_path = str(
            meta.get("findings_path", str(self.env.output_dir / "findings.jsonl"))
        )
        complete = await CompleteTaskTool()(
            executive_summary=str(
                finish_result.get("message", "")
                or "single-agent execution finished"
            ),
            confidence="medium",
            status="done" if finish_result.get("status") == "done" else "partial",
            report_path=report_path,
            artifacts=[
                {
                    "type": "report",
                    "path": report_path,
                    "description": "single-agent report output",
                }
            ],
            verification=[
                "single-agent run completed; report quality gate evaluated"
            ],
            open_issues=list(finish_result.get("issues", []) or []),
            findings_path=findings_path,
            required_sections=list(meta.get("required_sections", []) or []),
            min_findings=int(meta.get("min_findings", 0) or 0),
        )
        passed = complete.get("quality_gate_passed", False)
        yield TaskComplete(
            success=passed,
            quality_gate_passed=passed,
            attempts=1,
            total_cost=result.cost,
            cost_known=not ((result.input_tokens + result.output_tokens) > 0 and result.cost == 0),
            total_tokens=result.input_tokens + result.output_tokens,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            summary=str(complete.get("executive_summary", "")),
            final_result=complete,
        )

        self._run_result = {
            "attempts": [
                {
                    "action": {
                        "action": "single_agent_run",
                        "result": finish_result,
                    },
                    "raw_response": result.trace[-1].raw_response
                    if result.trace
                    else "",
                }
            ],
            "final_result": complete,
        }

    async def run(self):
        """Run to completion (backward-compatible wrapper)."""
        self._run_result = None
        async for _ in self.stream():
            pass
        return self._run_result or {"attempts": [], "final_result": None}

# 创建runtime，确定产物路径、工具实例、环境变量等，并注入到工具中以实现状态共享
def _build_runtime_components(
    sub_models: List[str],
    brief_text: str,
    sources_dir: Path,
    output_dir: Path,
    max_subagent_steps: int,
    profile: RuntimeProfile,
    max_parallel_subtasks: int = 3,
    subagent_process_timeout_seconds: int = 180,
) -> Tuple[TaskExecutionEnvironment, List[object]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / profile.report_filename
    findings_path = output_dir / "findings.jsonl"
    scratchpad_path = output_dir / "scratchpad" / "shared.md"
    ddg_available = bool(
        importlib.util.find_spec("ddgs")
        or importlib.util.find_spec("duckduckgo_search")
    )
    search_enabled = bool(os.getenv("SERPER_API_KEY")) or ddg_available

    task_tools = [
        ListSourcesTool(sources_dir=sources_dir),
        SearchSourcesTool(sources_dir=sources_dir),
        ReadSourceTool(sources_dir=sources_dir),
        ReadSourcesTool(sources_dir=sources_dir),
        WebSearchTool(),
        RecordFindingTool(findings_path=findings_path),
        WriteScratchpadNoteTool(scratchpad_path=scratchpad_path),
        ReadScratchpadTool(scratchpad_path=scratchpad_path),
        WriteReportSectionTool(report_path=report_path),
        VerifyArtifactsTool(
            default_report_path=report_path,
            default_findings_path=findings_path,
            default_scratchpad_path=scratchpad_path,
        ),
    ]

    env = TaskExecutionEnvironment(
        brief_text=brief_text,
        sources_dir=sources_dir,
        output_dir=output_dir,
        tools=task_tools,
        max_steps=max_subagent_steps,
        meta_data={
            "profile_name": profile.name,
            "report_path": str(report_path),
            "findings_path": str(findings_path),
            "scratchpad_path": str(scratchpad_path),
            "required_sections": list(profile.required_sections),
            "min_findings": profile.min_findings,
            "search_enabled": search_enabled,
            "subtask_toolkits": dict(profile.subtask_toolkits),
            "default_worker_tools": list(profile.default_worker_tools),
            "parallel_forbidden_tools": list(profile.parallel_forbidden_tools),
            "brief_injection_mode": "direct_prompt_context",
            "max_parallel_subtasks": max(1, int(max_parallel_subtasks or 3)),
            "subagent_process_timeout_seconds": int(subagent_process_timeout_seconds or 180),
            "task_goal": profile.task_goal,
            "workflow_hints": list(profile.workflow_hints),
            "completion_requirements": list(profile.completion_requirements),
        },
    )
    return env, task_tools


def build_agent_project(
    main_model: str,
    sub_models: List[str],
    brief_text: str,
    sources_dir: Path,
    output_dir: Path,
    max_attempts: int = 6,
    max_subagent_steps: int = 10,
    max_parallel_subtasks: int = 3,
    subagent_process_timeout_seconds: int = 180,
    profile_name: str = "generic",
    report_filename: str = "task_report.md",
    required_sections: List[str] | None = None,
    min_findings: int = 5,
) -> AgentProject:
    # 1.标准化模型列表，确保主模型在首位
    sub_models = _normalize_sub_models(main_model, sub_models)
    if required_sections is None:
        inferred_sections = _infer_required_sections_from_brief(brief_text)
        if inferred_sections:
            required_sections = inferred_sections
    #解析运行profile
    profile = _resolve_profile(
        sub_models=sub_models,
        profile_name=profile_name,
        report_filename=report_filename,
        required_sections=required_sections,
        min_findings=min_findings,
    )
    # 2.构建共享运行环境和工具
    env, task_tools = _build_runtime_components(
        sub_models=sub_models,
        brief_text=brief_text,
        sources_dir=sources_dir,
        output_dir=output_dir,
        max_subagent_steps=max_subagent_steps,
        profile=profile,
        max_parallel_subtasks=max_parallel_subtasks,
        subagent_process_timeout_seconds=subagent_process_timeout_seconds,
    )

    delegate_tool = DelegateTaskTool(
        env=env,
        models=sub_models,
        subagent_factory=lambda **kwargs: SubAgent(prompt_builder=GenericSubPromptBuilder, **kwargs),
    )
    delegate_tasks_tool = DelegateTasksTool(
        env=env,
        models=sub_models,
        subagent_factory=lambda **kwargs: SubAgent(prompt_builder=GenericSubPromptBuilder, **kwargs),
    )

    # 显式设置session_store以实现工具间的状态共享
    delegate_tasks_tool.session_store = delegate_tool.session_store
    delegate_tasks_tool.process_manager = delegate_tool.process_manager
    continue_task_tool = ContinueTaskTool(
        env=env,
        models=sub_models,
        subagent_factory=lambda **kwargs: SubAgent(prompt_builder=GenericSubPromptBuilder, **kwargs),
    )
    continue_task_tool.session_store = delegate_tool.session_store
    continue_task_tool.process_manager = delegate_tool.process_manager
    list_worker_sessions_tool = ListWorkerSessionsTool(
        env=env,
        models=sub_models,
        subagent_factory=lambda **kwargs: SubAgent(prompt_builder=GenericSubPromptBuilder, **kwargs),
    )
    list_worker_sessions_tool.session_store = delegate_tool.session_store
    list_worker_sessions_tool.process_manager = delegate_tool.process_manager
    inspect_worker_session_tool = InspectWorkerSessionTool(
        env=env,
        models=sub_models,
        subagent_factory=lambda **kwargs: SubAgent(prompt_builder=GenericSubPromptBuilder, **kwargs),
    )
    inspect_worker_session_tool.session_store = delegate_tool.session_store
    inspect_worker_session_tool.process_manager = delegate_tool.process_manager
    wait_worker_sessions_tool = WaitWorkerSessionsTool(
        env=env,
        models=sub_models,
        subagent_factory=lambda **kwargs: SubAgent(prompt_builder=GenericSubPromptBuilder, **kwargs),
    )
    wait_worker_sessions_tool.session_store = delegate_tool.session_store
    wait_worker_sessions_tool.process_manager = delegate_tool.process_manager
    close_worker_session_tool = CloseWorkerSessionTool(
        env=env,
        models=sub_models,
        subagent_factory=lambda **kwargs: SubAgent(prompt_builder=GenericSubPromptBuilder, **kwargs),
    )
    close_worker_session_tool.session_store = delegate_tool.session_store
    close_worker_session_tool.process_manager = delegate_tool.process_manager
    complete_tool = CompleteTaskTool()
    main_llm = create_llm_instance(LLMsConfig.default().get(main_model))

    main_agent = MainAgent(
        llm=main_llm,
        sub_models=sub_models,
        tools=[
            delegate_tool,
            delegate_tasks_tool,
            continue_task_tool,
            list_worker_sessions_tool,
            inspect_worker_session_tool,
            wait_worker_sessions_tool,
            close_worker_session_tool,
            complete_tool,
        ],
        subagent_tools=task_tools,
        prompt_builder=GenericMainPromptBuilder,
        max_attempts=max_attempts,
    )
    main_agent.reset(env.get_task_context())
    return AgentProject(
        main_agent=main_agent,
        max_attempts=max_attempts,
        final_wait_seconds=int(subagent_process_timeout_seconds or 180),
    )


def build_single_agent_project(
    main_model: str,
    sub_models: List[str],
    brief_text: str,
    sources_dir: Path,
    output_dir: Path,
    max_subagent_steps: int = 10,
    max_parallel_subtasks: int = 3,
    subagent_process_timeout_seconds: int = 180,
    profile_name: str = "generic",
    report_filename: str = "task_report.md",
    required_sections: List[str] | None = None,
    min_findings: int = 0,
) -> SingleAgentProject:
    sub_models = _normalize_sub_models(main_model, sub_models)
    profile = _resolve_profile(
        sub_models=sub_models,
        profile_name=profile_name,
        report_filename=report_filename,
        required_sections=required_sections,
        min_findings=min_findings,
    )
    env, _task_tools = _build_runtime_components(
        sub_models=sub_models,
        brief_text=brief_text,
        sources_dir=sources_dir,
        output_dir=output_dir,
        max_subagent_steps=max_subagent_steps,
        profile=profile,
        max_parallel_subtasks=max_parallel_subtasks,
        subagent_process_timeout_seconds=subagent_process_timeout_seconds,
    )
    sub_llm = create_llm_instance(LLMsConfig.default().get(main_model))
    sub_agent = SubAgent(
        llm=sub_llm,
        task_instruction=brief_text,
        context="",
        original_question=brief_text,
        prompt_builder=GenericSubPromptBuilder,
        task_label="single_mode",
    )
    sub_agent.reset(env.get_task_context())
    return SingleAgentProject(sub_agent=sub_agent, env=env)


async def build_project_by_mode(
    mode: str,
    main_model: str,
    sub_models: List[str],
    brief_text: str,
    sources_dir: Path,
    output_dir: Path,
    max_attempts: int = 6,
    max_subagent_steps: int = 10,
    max_parallel_subtasks: int = 3,
    subagent_process_timeout_seconds: int = 180,
    profile_name: str = "generic",
    report_filename: str = "task_report.md",
    required_sections: List[str] | None = None,
    min_findings: int = 5,
) -> Tuple[object, ModeDecision]:
    requested_mode = ModeRouter.normalize_requested_mode(mode)

    if requested_mode == "auto":
        router = ModeRouter.from_model_name(main_model)
        decision = await router.decide(brief_text)  # 路由决策
        selected_mode = decision.mode
    elif requested_mode in {"single", "multi"}:
        selected_mode = requested_mode
        decision = ModeDecision(
            mode=selected_mode,
            source="configured_override",
            reason=f"Mode explicitly forced by config: {selected_mode}",
            signals={},
        )

    if selected_mode == "single":
        project = build_single_agent_project(
            main_model=main_model,
            sub_models=sub_models,
            brief_text=brief_text,
            sources_dir=sources_dir,
            output_dir=output_dir,
            max_subagent_steps=max_subagent_steps,
            max_parallel_subtasks=max_parallel_subtasks,
            subagent_process_timeout_seconds=subagent_process_timeout_seconds,
            profile_name=profile_name,
            report_filename=report_filename,
            required_sections=required_sections,
            min_findings=0,
        )
        return project, decision

    project = build_agent_project(
        main_model=main_model,
        sub_models=sub_models,
        brief_text=brief_text,
        sources_dir=sources_dir,
        output_dir=output_dir,
        max_attempts=max_attempts,
        max_subagent_steps=max_subagent_steps,
        max_parallel_subtasks=max_parallel_subtasks,
        subagent_process_timeout_seconds=subagent_process_timeout_seconds,
        profile_name=profile_name,
        report_filename=report_filename,
        required_sections=required_sections,
        min_findings=min_findings,
    )
    return project, decision


GBAAnalysisProject = AgentProject


def build_gba_analysis_project(
    main_model: str,
    sub_models: List[str],
    brief_text: str,
    sources_dir: Path,
    output_dir: Path,
    max_attempts: int = 6,
    max_subagent_steps: int = 10,
    max_parallel_subtasks: int = 3,
    subagent_process_timeout_seconds: int = 180,
) -> AgentProject:
    return build_agent_project(
        main_model=main_model,
        sub_models=sub_models,
        brief_text=brief_text,
        sources_dir=sources_dir,
        output_dir=output_dir,
        max_attempts=max_attempts,
        max_subagent_steps=max_subagent_steps,
        max_parallel_subtasks=max_parallel_subtasks,
        subagent_process_timeout_seconds=subagent_process_timeout_seconds,
        profile_name="gba_industry_analysis",
    )
