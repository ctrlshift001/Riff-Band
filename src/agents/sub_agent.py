from __future__ import annotations

from typing import Any, List, Optional

from pydantic import Field
import re
from base.agent.base_agent import BaseAgent
from base.engine.logs import LogLevel, logger
from base.engine.utils import parse_llm_action_response, parse_llm_output
from agents.memory import Memory
from core.interfaces import Action, TaskContext



class ResearchSubAgent(BaseAgent):
    """Generic sub-agent for delegated research and report-writing work."""

    name: str = Field(default="ResearchSubAgent")
    description: str = Field(default="Delegated sub-agent for focused research tasks")
    task_instruction: str = Field(default="")
    context: str = Field(default="")
    original_question: str = Field(default="")
    allowed_tools: Optional[List[str]] = Field(default=None)
    current_env_instruction: str = Field(default="")
    current_action_space: str = Field(default="")
    memory: Memory = Field(default=None)
    prompt_builder: Any = Field(default=None) 
    task_label: str = Field(default="")

    class Config:
        arbitrary_types_allowed = True


    def reset(self, task_context: TaskContext) -> None:
        if self.memory is None:
            self.memory = Memory(llm=self.llm, max_memory=10)
        else:
            self.memory.clear()

        self.current_action_space = task_context.action_space

        if not self.original_question:
            self.original_question = task_context.instruction

        # Tool filtering (if allowed_tools specified)
        label = f"[{self.task_label}]" if self.task_label else "[task_unknown]"
        if self.allowed_tools:
            self.current_action_space = self._filter_action_space(
                task_context.action_space, 
                self.allowed_tools
            )
            logger.info(
                f"[ResearchSubAgent] {label} = {self.task_instruction} "
                f"Filtered to tools: {self.allowed_tools}"
            )
        else:
            self.current_action_space = task_context.action_space

    def _normalize_tool_name(self, name: str) -> str:
        normalized = name.lower().replace("_", "")
        if normalized.endswith("action"):
            normalized = normalized[:-6]
        return normalized
    
    def _tool_matches(self, tool_name: str, allowed_tools: List[str]) -> bool:
        if tool_name in allowed_tools:
            return True

        normalized_tool = self._normalize_tool_name(tool_name)
        for allowed in allowed_tools:
            if self._normalize_tool_name(allowed) == normalized_tool:
                return True
        return False

    # 过滤LLM返回的action space，保留allowed_tools中允许的工具
    def _filter_action_space(self, action_space: str, allowed_tools: List[str]) -> str:
        if not allowed_tools:
            return action_space

        blocks = re.split(r"\n(?=### )", action_space)
        filtered_blocks = []

        for block in blocks:
            if block.startswith("Available actions"):
                filtered_blocks.append(block.rstrip())
                continue

            match = re.match(r"### (\w+)", block)
            if match:
                tool_name = match.group(1)
                if self._tool_matches(tool_name, allowed_tools):
                    filtered_blocks.append(block.rstrip())

        return "\n\n".join(filtered_blocks)        

    def _get_memory(self) -> str:
        return self.memory.as_text() if self.memory else "None"

    def _build_fast_partial_finish(self) -> Action:
        return {
            "action": "finish",
            "params": {
                "status": "partial",
                "message": "Stopped early because no local sources were found and web search is unavailable.",
                "completed": [],
                "issues": [
                    "No local sources available.",
                    "Web search is disabled because SERPER_API_KEY is missing.",
                ],
                "result": "Please add local source files under sources_dir or configure SERPER_API_KEY.",
            },
            "memory": "Execution stopped early due to unavailable data sources.",
        }

    def _build_no_access_finish(self, error: str) -> Action:
        return {
            "action": "finish",
            "params": {
                "status": "partial",
                "message": "Stopped early because local sources are empty and web search access failed.",
                "completed": [],
                "issues": [
                    "No local sources available.",
                    f"Web search error: {error}",
                ],
                "result": "Please add local sources or fix SERPER authorization before rerun.",
            },
            "memory": "Execution stopped due to empty local sources and web search authorization failure.",
        }
    

    async def step(
        self,
        observation: Any,
        history: Any,
        current_step: int = 1,
        max_steps: int = 20,
    ) -> tuple[Action, str, str]:
        if self.prompt_builder is None:
            raise ValueError("ResearchSubAgent requires a prompt_builder")

        if isinstance(observation, dict) and current_step == 1:
            source_count = int(observation.get("source_count", 0))
            search_enabled = bool(observation.get("search_enabled", False))
            if source_count == 0 and not search_enabled:
                action = self._build_fast_partial_finish()
                raw_response = "Auto-finish: empty local sources and web search disabled."
                label = f"[{self.task_label}]" if self.task_label else "[task_unknown]"
                logger.agent_action(f"[ResearchSubAgent] {label}Action: {action}")
                return action, raw_response, "No prompt sent due to fast-finish guard."

        if isinstance(observation, dict):
            is_web_fail = (
                observation.get("action") == "web_search"
                and observation.get("success") is False
                and isinstance(observation.get("error"), str)
            )
            if is_web_fail:
                error_text = str(observation.get("error", "web_search failed"))
                unauthorized = ("403" in error_text) or ("Unauthorized" in error_text)
                first_obs = history[0].observation if history else {}
                source_count = int(first_obs.get("source_count", 0)) if isinstance(first_obs, dict) else 0
                if source_count == 0 and unauthorized:
                    action = self._build_no_access_finish(error_text)
                    raw_response = "Auto-finish: empty local sources and web search unauthorized."
                    label = f"[{self.task_label}]" if self.task_label else "[task_unknown]"
                    logger.agent_action(f"[ResearchSubAgent] {label}Action: {action}")
                    return action, raw_response, "No prompt sent due to web-access guard."

        prompt = self.prompt_builder.build_prompt(
            task_instruction=self.task_instruction,
            context=self.context,
            original_question=self.original_question,
            action_space=self.current_action_space,
            observation=observation,
            memory=self._get_memory(),
            current_step=current_step,
            max_steps=max_steps,
        )
        #print("当前subagent提示词:", prompt
        label = f"[{self.task_label}]" if self.task_label else "[task_unknown]"
        logger.log_to_file(LogLevel.INFO, f"[ResearchSubAgent] {label}Prompt:\n{prompt}\n")

        response = await self.llm(prompt)
        # print("当前subagent原始响应:", response)

        # Parse response
        memory_content = parse_llm_output(response, "memory")
        thinking = memory_content.get("memory") if isinstance(memory_content, dict) else None
        action = parse_llm_action_response(response)

        # 终端打印agent_action
        logger.agent_action(f"[ResearchSubAgent] {label}Action: {action}")

        # 记忆存储
        if self.memory:
            previous_obs = history[-1].info.get("last_action_result") if history else observation
            await self.memory.add_memory(
                obs=previous_obs,
                action=action,
                thinking=thinking,
                raw_response=response,
            )

        return action, response, prompt

    async def run(self, request: Optional[str] = None) -> str:
        return request or ""
