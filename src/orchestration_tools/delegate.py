from __future__ import annotations

import asyncio
import copy
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
from uuid import uuid4

from pydantic import Field

from base.agent.base_action import BaseAction
from base.engine.async_llm import LLMsConfig, create_llm_instance
from base.engine.logs import LogLevel, logger
from core.interfaces import Action, Observation, TaskContext
from core.runner import AgentRunner


def _normalize_tool_name(name: str) -> str:
    normalized = name.lower().strip().replace("_", "")
    if normalized.endswith("action"):
        normalized = normalized[:-6]
    return normalized


def _normalize_context(context: Any) -> str:
    if context is None:
        return ""
    if isinstance(context, str):
        return context
    if isinstance(context, (dict, list)):
        try:
            return json.dumps(context, ensure_ascii=False, indent=2)
        except TypeError:
            return str(context)
    return str(context)


def _format_trace(trace) -> str:
    if not trace:
        return "No steps executed."
    lines = []
    for idx, step in enumerate(trace, 1):
        lines.append(f"Step {idx}: {step.action}")
        lines.append(f"  Observation: {step.observation}")
    return "\n".join(lines)


def _filter_action_space(action_space: str, allowed_tools: Set[str]) -> str:
    if not allowed_tools:
        return action_space

    blocks = re.split(r"\n(?=### )", action_space)
    filtered_blocks: List[str] = []
    for block in blocks:
        if block.startswith("Available actions"):
            filtered_blocks.append(block.rstrip())
            continue
        match = re.match(r"### (\w+)", block)
        if not match:
            continue
        block_tool = match.group(1)
        if _normalize_tool_name(block_tool) in allowed_tools or block_tool == "finish":
            filtered_blocks.append(block.rstrip())

    return "\n\n".join(filtered_blocks)


@dataclass
class ScopedEnvironment:
    """Execution wrapper that enforces tool-level permissions for one delegated run."""

    base_env: Any
    allowed_tools: Set[str]
    max_steps: int
    _local_steps: int = 0

    def get_task_context(self) -> TaskContext:
        base_ctx = self.base_env.get_task_context()
        filtered_action_space = _filter_action_space(base_ctx.action_space, self.allowed_tools)
        meta = dict(base_ctx.meta_data or {})
        meta["allowed_tools"] = sorted(self.allowed_tools)
        return TaskContext(
            task_id=base_ctx.task_id,
            instruction=base_ctx.instruction,
            action_space=filtered_action_space,
            max_steps=base_ctx.max_steps,
            meta_data=meta,
        )

    async def reset(self, seed: int | None = None) -> Observation:
        self._local_steps = 0
        try:
            obs = await self.base_env.reset(seed=seed)
        except TypeError:
            obs = await self.base_env.reset()
        if isinstance(obs, dict):
            obs = dict(obs)
            obs["allowed_tools"] = sorted(self.allowed_tools)
        return obs

    async def step(self, action: Action) -> Tuple[Observation, float, bool, Dict[str, Any]]:
        self._local_steps += 1
        action_name = str(action.get("action", ""))
        normalized = _normalize_tool_name(action_name)
        if action_name != "finish" and normalized not in self.allowed_tools:
            done = self._local_steps >= self.max_steps
            obs: Observation = {
                "action": action_name,
                "success": False,
                "error": (
                    f"Tool '{action_name}' 在当前分配的任务中不被允许 "
                    f"Allowed tools: {sorted(self.allowed_tools)} and finish."
                ),
                "current_step": self._local_steps,
                "max_steps": self.max_steps,
            }
            info: Dict[str, Any] = {"error": "forbidden_tool"}
            return obs, 0.0, done, info
        return await self.base_env.step(action)


class _DelegateBase(BaseAction):
    env: Any = Field(default=None, exclude=True)
    models: List[str] = Field(default_factory=list)
    subagent_factory: Optional[Callable[..., Any]] = Field(default=None, exclude=True)
    runner: AgentRunner = Field(default_factory=AgentRunner, exclude=True)

    class Config:
        arbitrary_types_allowed = True

    def _resolve_allowed_tools(self, requested_tools: Optional[List[str]]) -> Optional[List[str]]:
        if not requested_tools:
            return None
        env_tools = getattr(self.env, "tools", {})
        env_names = list(env_tools.keys()) if isinstance(env_tools, dict) else []
        env_normalized = {_normalize_tool_name(item): item for item in env_names}
        resolved: List[str] = []
        for raw in requested_tools:
            canonical = env_normalized.get(_normalize_tool_name(str(raw)))
            if canonical:
                resolved.append(canonical)
        deduped = sorted(set(resolved))
        return deduped or None


    # deepcopy为每个并行子任务创建一个环境副本，确保输出文件路径隔离，并返回副本环境和对应的findings文件路径
    def _create_isolated_env(self, task_index: int, run_id: str) -> Tuple[Any, Path]:
        try:
            env_clone = copy.deepcopy(self.env)
        except Exception as exc:
            raise RuntimeError(f"Failed to clone environment for parallel task {task_index}: {exc}") from exc

        base_output = Path(getattr(self.env, "output_dir", Path("workspace/output")))
        task_output_dir = base_output / "parallel_runs" / run_id / f"task_{task_index}"
        task_output_dir.mkdir(parents=True, exist_ok=True)

        if hasattr(env_clone, "output_dir"):
            env_clone.output_dir = task_output_dir

        if hasattr(env_clone, "meta_data") and isinstance(env_clone.meta_data, dict):
            env_clone.meta_data = dict(env_clone.meta_data)
            env_clone.meta_data["output_dir"] = str(task_output_dir)
            env_clone.meta_data["report_path"] = str(task_output_dir / "gba_industry_report.md")
            env_clone.meta_data["findings_path"] = str(task_output_dir / "findings.jsonl")

        tools_map = getattr(env_clone, "tools", {})
        if isinstance(tools_map, dict):
            for tool in tools_map.values():
                if hasattr(tool, "report_path"):
                    tool.report_path = task_output_dir / "gba_industry_report.md"
                if hasattr(tool, "findings_path"):
                    tool.findings_path = task_output_dir / "findings.jsonl"

        return env_clone, (task_output_dir / "findings.jsonl")

    def _merge_findings_files(self, isolated_findings: List[Path]) -> Dict[str, Any]:
        base_findings = Path(
            getattr(self.env, "meta_data", {}).get(
                "findings_path",
                str(Path(getattr(self.env, "output_dir", Path("workspace/output"))) / "findings.jsonl"),
            )
        )
        base_findings.parent.mkdir(parents=True, exist_ok=True)

        existing_keys: Set[str] = set()
        merged_count = 0
        if base_findings.exists():
            for line in base_findings.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                key = str(row.get("dedup_key", "")).strip()
                if key:
                    existing_keys.add(key)

        with base_findings.open("a", encoding="utf-8") as out:
            for file in isolated_findings:
                if not file.exists():
                    continue
                for line in file.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        row = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    key = str(row.get("dedup_key", "")).strip()
                    if key and key in existing_keys:
                        continue
                    if key:
                        existing_keys.add(key)
                    out.write(json.dumps(row, ensure_ascii=False) + "\n")
                    merged_count += 1

        return {"merged_findings": merged_count, "target_findings_path": str(base_findings)}

    async def _run_single(
        self,
        task_instruction: str,
        model: str,
        context: Any = "",
        tools: Optional[List[str]] = None,
        env_override: Any = None,
        task_index: Optional[int] = None,
    ) -> Dict[str, Any]:
        if model not in self.models:
            return {"error": f"Invalid model: {model}", "steps_taken": 0, "done": False}
        if self.subagent_factory is None:
            raise ValueError("subagent_factory is required")

        run_env = env_override or self.env
        normalized_context = _normalize_context(context)
        allowed_tools = self._resolve_allowed_tools(tools)
        label = f"task_{task_index}" if task_index is not None else "task_single"
        logger.log_to_file(
            LogLevel.INFO,
            (
                f"[Delegate] Start {label} | model={model} | tools={allowed_tools or []} | "
                f"task_instruction={task_instruction}"
            ),
        )

        llm = create_llm_instance(LLMsConfig.default().get(model))
        sub_agent = self.subagent_factory(
            llm=llm,
            task_instruction=task_instruction,
            context=normalized_context,
            original_question=run_env.get_task_context().instruction,
            allowed_tools=allowed_tools,
            task_label=label,
        )

        scoped_env = run_env
        if allowed_tools:
            scoped_env = ScopedEnvironment(
                base_env=run_env,
                allowed_tools={_normalize_tool_name(item) for item in allowed_tools},
                max_steps=int(getattr(run_env, "max_steps", 12)),
            )

        result = await self.runner.run(sub_agent, scoped_env)
        finish_result = {}
        if result.trace:
            last_info = result.trace[-1].info
            finish_result = last_info.get("finish_result", {}) if last_info.get("finished") else {}
        logger.log_to_file(
            LogLevel.INFO,
            (
                f"[Delegate] Done {label} | steps={result.steps} | done={result.done} | "
                f"status={finish_result.get('status', '')}"
            ),
        )

        return {
            "model": model,
            "steps_taken": result.steps,
            "done": result.done,
            "cost": result.cost,
            "allowed_tools": allowed_tools or [],
            "finish_result": finish_result,
            "trace_summary": _format_trace(result.trace),
        }


class DelegateTaskTool(_DelegateBase):
    """Delegate one focused subtask to a sub-agent."""

    name: str = "delegate_task"
    description: str = "Delegate a focused analysis subtask to a sub-agent"
    parameters: Dict[str, Any] = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "task_instruction": {"type": "string"},
                "context": {"type": "string"},
                "model": {"type": "string"},
                "tools": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["task_instruction", "model"],
            "additionalProperties": False,
        }
    )

    async def __call__(
        self,
        task_instruction: str,
        model: str,
        context: Any = "",
        tools: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        return await self._run_single(
            task_instruction=task_instruction,
            model=model,
            context=context,
            tools=tools,
            env_override=None,
        )


class DelegateTasksTool(_DelegateBase):
    """Delegate multiple focused subtasks and run them concurrently."""

    name: str = "delegate_tasks"
    description: str = "Delegate multiple independent subtasks to sub-agents in parallel"
    parameters: Dict[str, Any] = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "tasks": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "task_instruction": {"type": "string"},
                            "context": {"type": "string"},
                            "model": {"type": "string"},
                            "tools": {"type": "array", "items": {"type": "string"}},
                        },
                        "required": ["task_instruction", "model"],
                    },
                },
                "max_concurrency": {"type": "integer", "default": 3},
            },
            "required": ["tasks"],
            "additionalProperties": False,
        }
    )

    async def __call__(self, tasks: List[Dict[str, Any]], max_concurrency: int = 3) -> Dict[str, Any]:
        if not tasks:
            return {"success": False, "message": "tasks cannot be empty", "results": []}

        # Hard rule: writing report sections is forbidden in parallel phase.
        for idx, task in enumerate(tasks):
            task_tools = [str(item) for item in (task.get("tools") or [])]
            if any(_normalize_tool_name(item) == _normalize_tool_name("write_report_section") for item in task_tools):
                return {
                    "success": False,
                    "message": f"Task[{idx}] includes forbidden tool write_report_section in parallel mode.",
                    "results": [],
                }

        limit = max(1, int(max_concurrency or 3))
        semaphore = asyncio.Semaphore(limit)
        run_id = uuid4().hex
        isolated_files: List[Path] = []
        logger.log_to_file(
            LogLevel.INFO,
            f"[DelegateTasks] run_id={run_id} max_concurrency={limit} total_tasks={len(tasks)}",
        )

        async def _run(idx: int, task: Dict[str, Any]) -> Dict[str, Any]:
            async with semaphore:
                isolated_env, isolated_findings = self._create_isolated_env(idx, run_id)
                result = await self._run_single(
                    task_instruction=str(task.get("task_instruction", "")),
                    model=str(task.get("model", "")),
                    context=task.get("context", ""),
                    tools=task.get("tools"),
                    env_override=isolated_env,
                    task_index=idx,
                )
                result["task_index"] = idx
                result["task_instruction"] = str(task.get("task_instruction", ""))
                result["isolated_findings_path"] = str(isolated_findings)
                isolated_files.append(isolated_findings)
                return result

        all_results = await asyncio.gather(*[_run(i, t) for i, t in enumerate(tasks)])
        merge_info = self._merge_findings_files(isolated_files)

        summary = {
            "total": len(all_results),
            "done_count": sum(1 for item in all_results if item.get("finish_result", {}).get("status") == "done"),
            "partial_count": sum(1 for item in all_results if item.get("finish_result", {}).get("status") == "partial"),
            "blocked_count": sum(1 for item in all_results if item.get("finish_result", {}).get("status") == "blocked"),
            "total_steps": sum(int(item.get("steps_taken", 0)) for item in all_results),
            "total_cost": sum(float(item.get("cost", 0.0)) for item in all_results),
            "max_concurrency": limit,
        }
        summary.update(merge_info)
        return {"success": True, "results": all_results, "summary": summary}
