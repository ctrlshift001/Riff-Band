from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StageStatus(str, Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    NEEDS_REVIEW = "needs_review"
    APPROVED = "approved"
    BLOCKED = "blocked"


class ProjectStatus(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class ApprovalDecision(str, Enum):
    APPROVE = "approve"
    REQUEST_CHANGES = "request_changes"
    REJECT = "reject"


class StageDefinition(BaseModel):
    model_config = ConfigDict(frozen=True)

    key: str
    position: int
    title: str
    short_title: str
    description: str
    artifact_type: str
    gate: str | None = None


STAGE_DEFINITIONS: tuple[StageDefinition, ...] = (
    StageDefinition(key="idea", position=1, title="说出想法", short_title="研究想法", description="澄清研究对象、目标、范围和未知项。", artifact_type="TopicBrief"),
    StageDefinition(key="literature", position=2, title="查看已有研究", short_title="已有研究", description="检索、筛选并组织论文、流派、共识与争议。", artifact_type="RelatedResearchReport"),
    StageDefinition(key="topic", position=3, title="选择值得做的课题", short_title="课题选择", description="复核候选空白并比较可行课题。", artifact_type="TopicCandidate", gate="G0"),
    StageDefinition(key="design", position=4, title="确认理论与研究设计", short_title="理论设计", description="形成机制、问题、识别或求解思路与关键假设。", artifact_type="ResearchProtocol", gate="G1"),
    StageDefinition(key="data", position=5, title="确认数据与合规", short_title="数据方法", description="确认数据、变量、方法、许可、隐私与风险。", artifact_type="DataPlan", gate="G2"),
    StageDefinition(key="analysis", position=6, title="制定分析计划和代码", short_title="分析计划", description="编辑分析步骤、模型式和 do-file revision。", artifact_type="AnalysisPlan", gate="G3"),
    StageDefinition(key="run", position=7, title="运行、稳健性与复现", short_title="运行诊断", description="管理 Runner、日志、结果、诊断和复现元数据。", artifact_type="RunArtifact"),
    StageDefinition(key="evidence", position=8, title="审核证据和结果解释", short_title="证据解释", description="连接 Claim、支持证据、反证、限制和结果。", artifact_type="ClaimEvidence", gate="G4"),
    StageDefinition(key="delivery", position=9, title="写作、发布和交付", short_title="成果交付", description="生成报告、引用、HTML 和可复现研究包。", artifact_type="ResearchPackage", gate="G5"),
)

STAGES_BY_KEY = {stage.key: stage for stage in STAGE_DEFINITIONS}


class CreateProjectRequest(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    initial_idea: str = Field(min_length=1, max_length=4000)

    @field_validator("title", "initial_idea")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()


class StageUpdateRequest(BaseModel):
    content: dict[str, Any]
    change_reason: str = Field(default="", max_length=500)
    author_type: str = Field(default="human", pattern="^(human|agent|import)$")


class StageDecisionRequest(BaseModel):
    decision: ApprovalDecision
    reason: str = Field(default="", max_length=1000)
    actor_type: str = Field(default="human", pattern="^human$")


class DraftRequest(BaseModel):
    instruction: str = Field(default="", max_length=2000)

