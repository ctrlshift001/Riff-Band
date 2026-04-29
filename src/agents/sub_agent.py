from __future__ import annotations

from typing import Any, List, Optional

from pydantic import Field
import re
from base.agent.base_agent import BaseAgent
from base.engine.logs import LogLevel, logger
from base.engine.utils import parse_llm_action_response, parse_llm_output
from agents.memory import Memory
from core.interfaces import Action, TaskContext



class SubAgent(BaseAgent):
    """通用子智能体，用于执行委派的研究、验证和产物生成任务。"""

    name: str = Field(default="SubAgent")
    description: str = Field(default="执行聚焦委派任务的子智能体")
    task_instruction: str = Field(default="")
    context: str = Field(default="")
    original_question: str = Field(default="")
    allowed_tools: Optional[List[str]] = Field(default=None)
    current_env_instruction: str = Field(default="")
    current_action_space: str = Field(default="")
    memory: Memory = Field(default=None)
    preserve_memory_on_reset: bool = Field(default=False)
    prompt_builder: Any = Field(default=None) 
    task_label: str = Field(default="")

    class Config:
        arbitrary_types_allowed = True


    def reset(self, task_context: TaskContext) -> None:
        if self.memory is None:
            self.memory = Memory(llm=self.llm, max_memory=10)
        elif not self.preserve_memory_on_reset:
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
            if block.startswith("Available actions") or block.startswith("可用操作"):
                filtered_blocks.append(block.rstrip())
                continue

            match = re.match(r"### (\w+)", block)
            if match:
                tool_name = match.group(1)
                if self._tool_matches(tool_name, allowed_tools):
                    filtered_blocks.append(block.rstrip())

        return "\n\n".join(filtered_blocks)        

    def _get_memory(self) -> str:
        return self.memory.as_text() if self.memory else "无"

    def _build_fast_partial_finish(self) -> Action:
        return {
            "action": "finish",
            "params": {
                "status": "partial",
                "message": "由于没有本地资料且联网搜索不可用，已提前停止。",
                "completed": [],
                "issues": [
                    "没有可用本地资料。",
                    "缺少 SERPER_API_KEY，联网搜索未启用。",
                ],
                "result": "请在 sources_dir 下添加本地资料，或配置 SERPER_API_KEY 后重试。",
            },
            "memory": "由于数据来源不可用，执行已提前停止。",
        }

    def _build_no_access_finish(self, error: str) -> Action:
        return {
            "action": "finish",
            "params": {
                "status": "partial",
                "message": "由于本地资料为空且联网搜索访问失败，已提前停止。",
                "completed": [],
                "issues": [
                    "没有可用本地资料。",
                    f"联网搜索错误: {error}",
                ],
                "result": "请添加本地资料，或修复 Serper 授权后重试。",
            },
            "memory": "由于本地资料为空且联网搜索授权失败，执行已停止。",
        }
    

    async def step(
        self,
        observation: Any,
        history: Any,
        current_step: int = 1,
        max_steps: int = 20,
    ) -> tuple[Action, str, str]:
        if self.prompt_builder is None:
            raise ValueError("SubAgent requires a prompt_builder")

        if isinstance(observation, dict) and current_step == 1:
            source_count = int(observation.get("source_count", 0))
            search_enabled = bool(observation.get("search_enabled", False))
            if source_count == 0 and not search_enabled:
                action = self._build_fast_partial_finish()
                raw_response = "自动结束：本地资料为空且联网搜索未启用。"
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
                    raw_response = "自动结束：本地资料为空且联网搜索未授权。"
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
        
        label = f"[{self.task_label}]" if self.task_label else "[task_unknown]"
        logger.log_to_file(LogLevel.INFO, f"[ResearchSubAgent] {label}Prompt:\n{prompt}\n")

        response = await self.llm(prompt)
        

        # Parse response
        memory_content = parse_llm_output(response, "memory")
        thinking = memory_content.get("memory") if isinstance(memory_content, dict) else None
        action = parse_llm_action_response(response)

        
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

