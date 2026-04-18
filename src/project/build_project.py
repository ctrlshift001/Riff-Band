from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

from agents.main_agent import MainOrchestratorAgent
from agents.sub_agent import ResearchSubAgent
from base.engine.async_llm import LLMsConfig, create_llm_instance
from environments.environment import GBAAnalysisEnvironment
from project.prompts import GBAMainPromptBuilder, GBASubPromptBuilder
from project.tools import (
    ListSourcesTool,
    SearchSourcesTool,
    ReadSourceTool,
    ReadSourcesTool,
    RecordFindingTool,
    WebSearchTool,
    WriteReportSectionTool,
)
from orchestration_tools.complete_task import CompleteTaskTool
from orchestration_tools.delegate import DelegateTaskTool, DelegateTasksTool


def _default_subtask_toolkits() -> Dict[str, List[str]]:
    return {
        "policy_research": ["search_sources", "read_sources", "read_source", "web_search", "record_finding"],
        "company_research": ["search_sources", "read_sources", "read_source", "web_search", "record_finding"],
        "supply_chain": ["search_sources", "read_sources", "read_source", "web_search", "record_finding"],
        "financial_metrics": ["search_sources", "read_sources", "read_source", "web_search", "record_finding"],
        "news_signals": ["web_search", "record_finding"],
        "report_drafting": ["search_sources", "read_sources", "read_source", "write_report_section"],
        "general_research": ["search_sources", "read_sources", "read_source", "web_search", "record_finding"],
    }


# 模型路由设置
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
        "general_research": secondary,
    }


@dataclass
class GBAAnalysisProject:
    main_agent: MainOrchestratorAgent
    max_attempts: int

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
        return {"attempts": attempts, "final_result": final_result}


def build_gba_analysis_project(
    main_model: str,
    sub_models: List[str],
    brief_text: str,
    sources_dir: Path,
    output_dir: Path,
    max_attempts: int = 6,
    max_subagent_steps: int = 10,
) -> GBAAnalysisProject:
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "gba_industry_report.md"
    findings_path = output_dir / "findings.jsonl"
    search_enabled = bool(os.getenv("SERPER_API_KEY"))

    task_tools = [
        ListSourcesTool(sources_dir=sources_dir),
        SearchSourcesTool(sources_dir=sources_dir),
        ReadSourceTool(sources_dir=sources_dir),
        ReadSourcesTool(sources_dir=sources_dir),
        WebSearchTool(),
        RecordFindingTool(findings_path=findings_path),
        WriteReportSectionTool(report_path=report_path),
    ]

    required_sections = [
        "Executive Summary",
        "Policy Drivers and Constraints",
        "City and Industry Comparison",
        "Investment Opportunities and Risks",
    ]
    min_findings = 5

    env = GBAAnalysisEnvironment(
        project_id="gba_industry_analysis",
        brief_text=brief_text,
        sources_dir=sources_dir,
        output_dir=output_dir,
        tools=task_tools,
        max_steps=max_subagent_steps,
        meta_data={
            "report_path": str(report_path),
            "findings_path": str(findings_path),
            "required_sections": required_sections,
            "min_findings": min_findings,
            "search_enabled": search_enabled,
            "subtask_toolkits": _default_subtask_toolkits(), # 模型路由规则
            "model_routing": _default_model_routing(sub_models),
            "brief_injection_mode": "direct_prompt_context",
            "max_parallel_subtasks": 3,
        },
    )

    delegate_tool = DelegateTaskTool(
        env=env,
        models=sub_models,
        subagent_factory=lambda **kwargs: ResearchSubAgent(prompt_builder=GBASubPromptBuilder, **kwargs),
    )
    delegate_tasks_tool = DelegateTasksTool(
        env=env,
        models=sub_models,
        subagent_factory=lambda **kwargs: ResearchSubAgent(prompt_builder=GBASubPromptBuilder, **kwargs),
    )
    complete_tool = CompleteTaskTool()
    main_llm = create_llm_instance(LLMsConfig.default().get(main_model))
    main_agent = MainOrchestratorAgent(
        llm=main_llm,
        sub_models=sub_models,
        tools=[delegate_tool, delegate_tasks_tool, complete_tool],
        subagent_tools=task_tools,
        prompt_builder=GBAMainPromptBuilder,
        max_attempts=max_attempts,
    )
    main_agent.reset(env.get_task_context())
    return GBAAnalysisProject(main_agent=main_agent, max_attempts=max_attempts)
