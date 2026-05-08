from __future__ import annotations

from config import AgentConfig
from research.schema import ResearchRequest, ResearchResult


async def run_research(request: ResearchRequest, config: AgentConfig) -> ResearchResult:
    """Run research mode.

    This is intentionally a stable internal service boundary. The concrete
    research state machine will be implemented behind this function so the CLI
    command and future MCP tool can share the same behavior.
    """
    return ResearchResult(
        status="partial",
        summary=(
            "Research mode interface is ready, but the dedicated research "
            "pipeline has not been implemented yet."
        ),
        open_issues=[
            "research workflow state machine is not implemented",
        ],
        metadata={
            "topic": request.topic,
            "depth": request.depth,
            "output_format": request.output_format,
            "trigger": request.trigger,
            "mode": config.mode,
            "profile_name": config.profile_name,
        },
    )
