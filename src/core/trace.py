from __future__ import annotations

from typing import List

from core.interfaces import StepRecord


def format_trace(trace: List[StepRecord], max_output_len: int = 240) -> str:
    """Create a readable trace summary for delegated runs."""
    if not trace:
        return "No steps executed."

    lines = []
    for idx, step in enumerate(trace, 1):
        action_name = step.action.get("action", "unknown")
        params = step.action.get("params", {})
        observation = step.observation if isinstance(step.observation, dict) else {"value": step.observation}
        output = str(observation.get("output", observation))
        if len(output) > max_output_len:
            output = output[:max_output_len] + f"...[+{len(output) - max_output_len} chars]"
        lines.append(f"Step {idx}: {action_name} {params}")
        lines.append(f"  output: {output}")
    return "\n".join(lines)
