from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


ResearchDepth = Literal["quick", "standard", "deep"]
ResearchOutputFormat = Literal["markdown", "latex", "json"]
ResearchStatus = Literal["done", "partial", "blocked"]
ResearchTrigger = Literal["cli", "mcp", "internal"]


class ResearchRequest(BaseModel):
    """Stable request schema shared by CLI commands and future MCP tools."""

    topic: str = Field(description="Research topic or question.")
    depth: ResearchDepth = Field(default="standard")
    output_format: ResearchOutputFormat = Field(default="markdown")
    sources: list[str] = Field(default_factory=list)
    constraints: str = Field(default="")
    trigger: ResearchTrigger = Field(default="internal")
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("topic")
    @classmethod
    def topic_must_not_be_empty(cls, value: str) -> str:
        value = str(value or "").strip()
        if not value:
            raise ValueError("research topic must not be empty")
        return value


class ResearchArtifact(BaseModel):
    """A file or structured object produced by research mode."""

    type: str = Field(default="report")
    path: str = Field(default="")
    description: str = Field(default="")


class ResearchResult(BaseModel):
    """Stable result schema returned by research mode and future MCP tools."""

    status: ResearchStatus = Field(default="partial")
    summary: str = Field(default="")
    report_path: str = Field(default="")
    artifacts: list[ResearchArtifact] = Field(default_factory=list)
    open_issues: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
