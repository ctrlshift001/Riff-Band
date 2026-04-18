from __future__ import annotations

import asyncio
import inspect
from datetime import datetime
from typing import List, Optional

from base.engine.logs import LogLevel, logger
from core.interfaces import AgentEnvironment, RunResult, StepRecord


class AgentRunner:
    """Generic agent-environment loop."""

    step_timeout: Optional[float] = 600.0

    # sub_agent和
    async def run(self, agent, env: AgentEnvironment) -> RunResult:
        start_time = datetime.now().isoformat()
        info = env.get_task_context()
        agent.reset(info)

        reset_result = env.reset()
        obs = await reset_result if inspect.isawaitable(reset_result) else reset_result

        history: List[StepRecord] = []
        total_reward = 0.0

        for idx in range(info.max_steps):
            logger.log_to_file(LogLevel.INFO, f"[AgentRunner] Observation: {obs}")
            try:
                if self.step_timeout:
                    step_result = await asyncio.wait_for(
                        agent.step(observation=obs, history=history, current_step=idx + 1, max_steps=info.max_steps),
                        timeout=self.step_timeout,
                    )
                else:
                    step_result = await agent.step(
                        observation=obs,
                        history=history, 
                        current_step=idx + 1,
                        max_steps=info.max_steps,
                    )
            except asyncio.TimeoutError:
                history.append(
                    StepRecord(
                        observation=obs,
                        action={"action": "timeout", "params": {}},
                        reward=0.0,
                        raw_response="step timeout",
                        done=True,
                        info={"error": "step_timeout"},
                    )
                )
                break

            if len(step_result) == 3:
                action, raw_response, raw_input = step_result
            elif len(step_result) == 2:
                action, raw_response = step_result
                raw_input = None
            else:
                raise ValueError(f"Unsupported step return shape: {len(step_result)}")

            obs_next, reward, done, step_info = await env.step(action)
            history.append(
                StepRecord(
                    observation=obs,
                    action=action,
                    reward=reward,
                    raw_response=raw_response,
                    done=done,
                    info=step_info,
                    raw_input=raw_input,
                )
            )
            total_reward += reward
            obs = obs_next

            if done:
                break

        end_time = datetime.now().isoformat()
        usage = agent.llm.get_usage_summary() if getattr(agent, "llm", None) else {}
        return RunResult(
            model=usage.get("model", ""),
            total_reward=total_reward,
            steps=len(history),
            done=history[-1].done if history else False,
            trace=history,
            cost=usage.get("total_cost", 0.0),
            input_tokens=usage.get("total_input_tokens", 0),
            output_tokens=usage.get("total_output_tokens", 0),
            start_time=start_time,
            end_time=end_time,
        )
