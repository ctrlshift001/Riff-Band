from __future__ import annotations

import os
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Tuple

from agents.main_agent import MainAgent
from agents.sub_agent import SubAgent
from base.engine.async_llm import LLMsConfig, create_llm_instance
from base.engine.logs import logger
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
    model_routing: Dict[str, str] = field(default_factory=dict)


def _normalize_sub_models(main_model: str, sub_models: List[str]) -> List[str]:
    normalized = [str(item).strip() for item in (sub_models or []) if str(item).strip()]
    if main_model not in normalized:
        normalized.insert(0, main_model)
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
        model_routing=_default_model_routing(sub_models),
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
        model_routing=_default_model_routing(sub_models),
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
    model_routing: Dict[str, str] | None = None,
) -> RuntimeProfile:
    normalized_name = (profile_name or "generic").strip() or "generic"
    base = _gba_profile(sub_models) if normalized_name == "gba_industry_analysis" else _generic_profile(sub_models)

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
            model_routing=dict(base.model_routing),
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
        model_routing=dict(model_routing or base.model_routing),
    )


@dataclass
class AgentProject:
    main_agent: MainAgent
    max_attempts: int
    final_wait_seconds: int = 180

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
            finish = {
                "status": item.get("status", ""),
                "message": item.get("message", ""),
                "completed": item.get("completed", []),
                "issues": item.get("issues", []),
                "result": item.get("result", ""),
                "session_id": item.get("session_id", ""),
                "profile": item.get("profile", ""),
                "trace_summary": str(item.get("trace_summary", "") or "")[:2000],
            }
            entries.append(finish)
        findings_preview = []
        findings_path = Path(str(self.main_agent.meta.get("findings_path", "") or ""))
        if findings_path.is_file():
            for line in findings_path.read_text(encoding="utf-8").splitlines()[:30]:
                line = line.strip()
                if not line:
                    continue
                try:
                    findings_preview.append(json.loads(line))
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
        self.main_agent._update_context("wait_worker_sessions", params, result)
        action = {
            "action": "wait_worker_sessions",
            "params": params,
            "result": result,
            "forced_final_wait": True,
        }
        attempts.append({"action": action, "raw_response": "forced final wait for running SubAgent sessions"})
        return result

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
        self.main_agent._update_context("wait_worker_sessions", wait_params, wait_result)
        wait_action = {
            "action": "wait_worker_sessions",
            "params": wait_params,
            "result": wait_result,
            "forced_synthesis_wait": True,
        }
        attempts.append({"action": wait_action, "raw_response": "forced synthesis wait"})
        return wait_result

    async def run(self):
        attempts = []
        final_result = None
        for _ in range(self.max_attempts):
            action, raw_response = await self.main_agent.step(None, [])
            attempts.append({"action": action, "raw_response": raw_response})

            if action["action"] != "complete_task":
                continue

            result = action.get("result", {})
            if result.get("done") and result.get("quality_gate_passed"):
                final_result = result
                break

        if final_result is None:
            final_wait_result = await self._collect_remaining_sessions(attempts)
            summary = final_wait_result.get("summary", {}) if isinstance(final_wait_result, dict) else {}
            has_collected = int(summary.get("completed", 0) or 0) > 0
            still_running = int(summary.get("still_running", 0) or 0)
            if has_collected or still_running == 0:
                await self._run_synthesis_if_needed(attempts)
                previous_max = self.main_agent.max_attempts
                self.main_agent.max_attempts = max(previous_max, self.main_agent.attempt + 1)
                try:
                    action, raw_response = await self.main_agent.step(None, [], forced_final_decision=True)
                finally:
                    self.main_agent.max_attempts = previous_max
                action["forced_final_decision"] = True
                attempts.append({"action": action, "raw_response": raw_response})
                if action["action"] == "complete_task":
                    result = action.get("result", {})
                    if result.get("done") and result.get("quality_gate_passed"):
                        final_result = result
        return {"attempts": attempts, "final_result": final_result}


@dataclass
class SingleAgentProject:
    sub_agent: SubAgent
    env: TaskExecutionEnvironment

    async def run(self):
        runner = AgentRunner()
        result = await runner.run(self.sub_agent, self.env)
        finish_result = {}
        if result.trace:
            finish_result = (
                result.trace[-1].info.get("finish_result", {})
                if result.trace[-1].info.get("finished")
                else {}
            )

        meta = self.env.meta_data or {}
        report_path = str(meta.get("report_path", str(self.env.output_dir / "task_report.md")))
        findings_path = str(meta.get("findings_path", str(self.env.output_dir / "findings.jsonl")))
        complete = await CompleteTaskTool()(
            executive_summary=str(finish_result.get("message", "") or "single-agent execution finished"),
            confidence="medium",
            status="done" if finish_result.get("status") == "done" else "partial",
            report_path=report_path,
            artifacts=[{"type": "report", "path": report_path, "description": "single-agent report output"}],
            verification=["single-agent run completed; report quality gate evaluated"],
            open_issues=list(finish_result.get("issues", []) or []),
            findings_path=findings_path,
            required_sections=list(meta.get("required_sections", []) or []),
            min_findings=int(meta.get("min_findings", 0) or 0),
        )
        return {
            "attempts": [
                {
                    "action": {"action": "single_agent_run", "result": finish_result},
                    "raw_response": result.trace[-1].raw_response if result.trace else "",
                }
            ],
            "final_result": complete,
        }

# 创建runtime，确定产物路径、工具实例、环境变量等，并注入到工具中以实现状态共享
def _build_runtime_components(
    sub_models: List[str],
    brief_text: str,
    sources_dir: Path,
    output_dir: Path,
    max_subagent_steps: int,
    profile: RuntimeProfile,
    subagent_process_timeout_seconds: int = 180,
) -> Tuple[TaskExecutionEnvironment, List[object]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / profile.report_filename
    findings_path = output_dir / "findings.jsonl"
    scratchpad_path = output_dir / "scratchpad" / "shared.md"
    search_enabled = bool(os.getenv("SERPER_API_KEY"))

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
            "model_routing": dict(profile.model_routing),
            "brief_injection_mode": "direct_prompt_context",
            "max_parallel_subtasks": 3,
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
    subagent_process_timeout_seconds: int = 180,
    profile_name: str = "generic",
    report_filename: str = "task_report.md",
    required_sections: List[str] | None = None,
    min_findings: int = 5,
) -> AgentProject:
    # 1.标准化模型列表，确保主模型在首位
    sub_models = _normalize_sub_models(main_model, sub_models)
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
        subagent_process_timeout_seconds=subagent_process_timeout_seconds,
        profile_name="gba_industry_analysis",
    )
