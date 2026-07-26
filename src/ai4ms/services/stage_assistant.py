from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from ai4ms.inference import OpenAICompatibleGateway
from ai4ms.inference.gateway import InferenceGateway
from ai4ms.inference.structured import StructuredOutputError, validate_structured_output
from ai4ms.knowledge import KnowledgeRegistry
from ai4ms.literature.service import LiteratureSearchService
from ai4ms.prompts import get_stage_policy
from ai4ms.runners import AnalysisRunnerService
from ai4ms.runners.stata import StataPolicyScanner
from ai4ms.services.models import (
    AnalysisRunRequest,
    LiteratureSearchRequest,
    StageSuggestionDecisionRequest,
    StageSuggestionGenerateRequest,
    StageToolInvokeRequest,
)


class SuggestedChange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=2, max_length=200)
    reason: str = Field(min_length=5, max_length=1200)
    before: str = Field(min_length=1, max_length=500)
    after: str = Field(min_length=1, max_length=1200)
    target: Literal[
        "summary",
        "objective",
        "content",
        "scope",
        "evidence_note",
        "decision",
        "risk",
        "handoff",
    ]
    tool_id: str = Field(default="", max_length=120)


class StageSuggestionContract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=5, max_length=1200)
    suggestions: list[SuggestedChange] = Field(min_length=3, max_length=3)


class StageAssistantError(RuntimeError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


class StageSuggestionOutputError(RuntimeError):
    pass


class StageAssistantService:
    """Execute registered read-only tools and persist AI draft suggestions."""

    def __init__(
        self,
        projects_dir: str | Path,
        *,
        literature_search: LiteratureSearchService | None = None,
        analysis_runner: AnalysisRunnerService | None = None,
        gateway_factory: Callable[[], InferenceGateway] | None = None,
    ) -> None:
        self.projects_dir = Path(projects_dir)
        self.literature_search = literature_search or LiteratureSearchService(
            self.projects_dir
        )
        self.analysis_runner = analysis_runner or AnalysisRunnerService()
        self.gateway_factory = gateway_factory or OpenAICompatibleGateway

    def load_suggestions(
        self,
        project: dict[str, Any],
        stage_key: str,
    ) -> dict[str, Any]:
        stage = self._stage(project, stage_key)
        path = self._suggestion_path(str(project["project_id"]), stage_key)
        if not path.exists():
            return self._empty_suggestions(project, stage, "not_generated")
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return self._empty_suggestions(project, stage, "invalid")
        if not isinstance(payload, dict) or not isinstance(
            payload.get("suggestions"), list
        ):
            return self._empty_suggestions(project, stage, "invalid")
        payload["status"] = (
            "current"
            if payload.get("context_hash") == self.context_hash(project, stage_key)
            else "stale"
        )
        return payload

    async def generate_suggestions(
        self,
        project: dict[str, Any],
        stage_key: str,
        request: StageSuggestionGenerateRequest,
    ) -> dict[str, Any]:
        stage = self._stage(project, stage_key)
        if int(stage.get("revision") or 0) <= 0:
            raise StageAssistantError(
                "stage_suggestions_require_saved_revision",
                "请先保存当前阶段草稿，再生成基于 revision 的 AI 建议。",
            )
        if stage.get("status") == "not_started":
            raise StageAssistantError(
                "stage_suggestions_stage_locked",
                "当前阶段尚未解锁，不能生成阶段建议。",
            )
        policy = get_stage_policy(stage_key)
        context = self._assistant_context(project, stage_key)
        allowed_tools = {tool.tool_id for tool in policy.tools}
        system_prompt = (
            "你是 AI4MS 管理科学科研工作台的阶段审阅助手。"
            "请只根据当前已保存的项目、阶段草稿和阶段政策提出三条具体修改建议。"
            "每条建议必须指出当前内容、建议内容、理由和应写入的草稿字段。"
            "不得声称已经检索、运行分析、验证假设或批准阶段；缺少证据时应明确写成待补充。"
            "建议应针对当前课题，禁止输出通用占位模板。"
            "tool_id 只能从输入的可调用工具中选择；不需要工具时使用空字符串。"
            "只输出符合给定 JSON Schema 的对象。"
        )
        user_prompt = json.dumps(
            {
                "task": "审阅当前保存的阶段草稿并生成三条可操作建议",
                "researcher_instruction": request.instruction,
                "project_context": context,
                "stage_policy": policy.public_dict(),
                "output_schema": StageSuggestionContract.model_json_schema(),
            },
            ensure_ascii=False,
        )
        response = await self.gateway_factory().generate(system_prompt, user_prompt)
        try:
            generated = validate_structured_output(
                response.text,
                StageSuggestionContract,
            )
        except StructuredOutputError as exc:
            raise StageSuggestionOutputError(str(exc)) from exc

        suggestions: list[dict[str, Any]] = []
        for item in generated.suggestions:
            data = item.model_dump()
            if data["tool_id"] not in allowed_tools:
                data["tool_id"] = ""
            suggestions.append(
                {
                    "suggestion_id": f"sug_{uuid4().hex[:12]}",
                    **data,
                    "state": "pending",
                    "decided_at": "",
                }
            )

        payload = {
            "suggestion_set_id": f"suggestions_{uuid4().hex[:12]}",
            "project_id": project["project_id"],
            "stage_key": stage_key,
            "stage_revision": int(stage.get("revision") or 0),
            "status": "current",
            "context_hash": self.context_hash(project, stage_key),
            "model": response.model,
            "generated_at": datetime.now(UTC).isoformat(),
            "summary": generated.summary,
            "suggestions": suggestions,
            "usage": response.usage,
        }
        self._write_json(
            self._suggestion_path(str(project["project_id"]), stage_key),
            payload,
        )
        return payload

    def decide_suggestion(
        self,
        project: dict[str, Any],
        stage_key: str,
        suggestion_id: str,
        request: StageSuggestionDecisionRequest,
    ) -> dict[str, Any]:
        payload = self.load_suggestions(project, stage_key)
        if payload["status"] != "current":
            raise StageAssistantError(
                "stale_stage_suggestions",
                "当前建议不是基于最新阶段 revision，请先重新生成建议。",
            )
        suggestion = next(
            (
                item
                for item in payload["suggestions"]
                if item.get("suggestion_id") == suggestion_id
            ),
            None,
        )
        if suggestion is None:
            raise StageAssistantError(
                "suggestion_not_found",
                f"未找到建议 {suggestion_id}",
            )
        suggestion["state"] = request.state
        suggestion["decision_note"] = request.note
        suggestion["decided_at"] = (
            "" if request.state == "pending" else datetime.now(UTC).isoformat()
        )
        self._write_json(
            self._suggestion_path(str(project["project_id"]), stage_key),
            payload,
        )
        return payload

    async def invoke_tool(
        self,
        project: dict[str, Any],
        stage_key: str,
        request: StageToolInvokeRequest,
        analysis_runs: list[dict[str, Any]],
    ) -> dict[str, Any]:
        stage = self._stage(project, stage_key)
        policy = get_stage_policy(stage_key)
        tool = next(
            (item for item in policy.tools if item.tool_id == request.tool_id),
            None,
        )
        if tool is None:
            raise StageAssistantError(
                "stage_tool_not_allowed",
                f"{request.tool_id} 不是 {stage_key} 阶段注册工具",
            )

        run_id = f"tool_{uuid4().hex[:12]}"
        started_at = datetime.now(UTC).isoformat()
        if tool.requires_human_confirmation:
            payload = {
                "tool_run_id": run_id,
                "project_id": project["project_id"],
                "stage_key": stage_key,
                "stage_revision": int(stage.get("revision") or 0),
                "tool_id": tool.tool_id,
                "risk_level": tool.risk_level,
                "status": "confirmation_required",
                "summary": (
                    f"{tool.tool_id} 涉及写入、运行或交付动作，"
                    "必须通过对应工作台由研究者明确确认，阶段智能体没有自动执行。"
                ),
                "result": {
                    "purpose": tool.purpose,
                    "allowed_actions": list(tool.allowed_actions),
                    "forbidden_actions": list(tool.forbidden_actions),
                },
                "started_at": started_at,
                "finished_at": datetime.now(UTC).isoformat(),
            }
            self._persist_tool_run(payload)
            return payload

        try:
            result, summary = await self._execute_read_only_tool(
                project,
                stage_key,
                request,
                analysis_runs,
            )
            run_status = "completed"
        except Exception as exc:
            result = {"error": f"{type(exc).__name__}: {str(exc)[:500]}"}
            summary = f"{tool.tool_id} 调用失败：{str(exc)[:300]}"
            run_status = "failed"

        payload = {
            "tool_run_id": run_id,
            "project_id": project["project_id"],
            "stage_key": stage_key,
            "stage_revision": int(stage.get("revision") or 0),
            "tool_id": tool.tool_id,
            "risk_level": tool.risk_level,
            "status": run_status,
            "summary": summary,
            "result": result,
            "started_at": started_at,
            "finished_at": datetime.now(UTC).isoformat(),
        }
        self._persist_tool_run(payload)
        return payload

    async def _execute_read_only_tool(
        self,
        project: dict[str, Any],
        stage_key: str,
        request: StageToolInvokeRequest,
        analysis_runs: list[dict[str, Any]],
    ) -> tuple[dict[str, Any], str]:
        tool_id = request.tool_id
        query = (
            request.query.strip()
            or request.instruction.strip()
            or f"{project.get('title', '')} {project.get('initial_idea', '')}".strip()
        )
        stages = {
            item["key"]: item for item in project.get("stages", [])
        }

        if tool_id == "project.asset.read":
            result = {
                "title": project.get("title", ""),
                "initial_idea": project.get("initial_idea", ""),
                "current_stage": project.get("current_stage", ""),
                "stage": self._compact(stages[stage_key]),
                "data_assets": self._compact(project.get("data_assets", [])),
                "approvals": self._compact(project.get("approvals", [])),
            }
            return result, "已读取当前项目、阶段 revision、数据资产和审批记录。"

        literature_backends = {
            "literature.openalex": ["openalex"],
            "literature.crossref": ["crossref"],
            "literature.semantic_scholar": ["semantic_scholar"],
            "literature.arxiv": ["arxiv"],
            "literature.scout": [
                "openalex",
                "crossref",
                "semantic_scholar",
                "arxiv",
            ],
        }
        if tool_id in literature_backends:
            literature = stages.get("literature", {}).get("content", {})
            search = await self.literature_search.search(
                str(project["project_id"]),
                literature,
                LiteratureSearchRequest(
                    queries=[query],
                    backends=literature_backends[tool_id],
                    limit_per_backend=6,
                    max_queries=1,
                ),
            )
            result = {
                "search_id": search["search_id"],
                "status": search["status"],
                "counts": search["counts"],
                "papers": search["papers"][:8],
                "source_runs": search["source_runs"],
                "snapshot_path": search["snapshot_path"],
            }
            return (
                result,
                f"检索完成：识别 {search['counts']['identified']} 条，"
                f"去重后 {search['counts']['deduplicated']} 篇；已保存检索快照。",
            )

        if tool_id == "literature.screen_and_dedupe":
            content = stages.get("literature", {}).get("content", {})
            papers = content.get("papers", []) if isinstance(content, dict) else []
            ids = [str(item.get("paper_id") or "") for item in papers if isinstance(item, dict)]
            result = {
                "paper_count": len(papers),
                "unique_paper_ids": len(set(item for item in ids if item)),
                "duplicate_ids": sorted(
                    {item for item in ids if item and ids.count(item) > 1}
                ),
                "search_runs": self._compact(content.get("search_runs", [])),
            }
            return result, "已对当前 S1 论文记录和检索批次执行确定性去重审计。"

        if tool_id == "evidence.graph.read":
            result = {
                "papers": self._compact(
                    stages.get("literature", {}).get("content", {}).get("papers", [])
                ),
                "theory": self._compact(stages.get("theory", {}).get("content", {})),
                "claims": self._compact(
                    stages.get("evidence", {}).get("content", {}).get("claims", [])
                ),
            }
            return result, "已读取当前论文、理论结构和主张—证据记录。"

        if tool_id == "knowledge.method.lookup":
            items = KnowledgeRegistry.method_candidates(query=query, limit=8)
            return {"items": items}, f"方法库返回 {len(items)} 个候选方法。"

        if tool_id == "knowledge.formula.lookup":
            design = stages.get("design", {}).get("content", {})
            method_ids = [
                str(design.get("primary_method_id") or "")
            ] + [
                str(item.get("method_id") or "")
                for item in design.get("method_options", [])
                if isinstance(item, dict)
            ]
            items = KnowledgeRegistry.formula_candidates(
                query=query,
                method_ids=[item for item in method_ids if item],
                limit=10,
            )
            return {"items": items}, f"公式库返回 {len(items)} 个候选公式。"

        if tool_id == "knowledge.data_source.lookup":
            items = KnowledgeRegistry.data_source_candidates(query=query, limit=10)
            return {"items": items}, f"数据源库返回 {len(items)} 个候选数据源。"

        if tool_id == "knowledge.diagnostic.lookup":
            items = KnowledgeRegistry.diagnostic_rules(
                query=request.query,
                stage="S7" if stage_key == "robustness" else "",
                limit=18,
            )
            return {"items": items}, f"诊断注册表返回 {len(items)} 条适用规则。"

        if tool_id == "design.feasibility.check":
            readiness = stages.get("design", {}).get("readiness", {})
            result = {
                "readiness": readiness,
                "design": self._compact(stages.get("design", {}).get("content", {})),
            }
            return result, (
                "研究设计完整性检查已完成；"
                f"当前完成度 {readiness.get('percent', 0)}%。"
            )

        if tool_id == "data.asset.profile":
            assets = self._compact(project.get("data_assets", []))
            return {"items": assets}, f"读取到 {len(assets)} 个项目数据资产及元信息。"

        if tool_id == "data.governance.check":
            content = stages.get("data", {}).get("content", {})
            fields = ("data_sources", "pii_class", "privacy_risks", "ethics_checks")
            missing = [
                field
                for field in fields
                if content.get(field) in (None, "", [], {})
                or (field == "pii_class" and content.get(field) == "unknown")
            ]
            result = {
                "missing_fields": missing,
                "blocking_issues": self._compact(content.get("blocking_issues", [])),
                "status": "blocked" if missing or content.get("blocking_issues") else "ready_for_review",
            }
            return result, f"数据治理检查完成，发现 {len(missing)} 个待补字段。"

        if tool_id == "stata.policy.scan":
            do_file = str(
                stages.get("identification", {})
                .get("content", {})
                .get("stata_do_file", "")
            )
            issues = [
                *StataPolicyScanner.scan(do_file),
                *StataPolicyScanner.required_structure_issues(do_file),
            ]
            return {"issues": issues}, f"Stata 静态策略扫描完成，发现 {len(issues)} 个问题。"

        if tool_id == "runner.preflight":
            assets = project.get("data_assets", [])
            asset_id = str(assets[0].get("asset_id") or "") if assets else ""
            result = self.analysis_runner.preflight(
                project,
                self.projects_dir / str(project["project_id"]),
                AnalysisRunRequest(input_asset_id=asset_id),
            )
            return result, f"Runner 预检状态：{result.get('status', 'unknown')}。"

        if tool_id in {"runner.status_logs", "runner.result.read"}:
            runs = self._compact(analysis_runs[:10])
            succeeded = sum(
                1 for item in analysis_runs if item.get("status") == "succeeded"
            )
            return {"items": runs}, f"读取到 {len(runs)} 条运行记录，其中 {succeeded} 条成功。"

        if tool_id == "evidence.artifact.verify":
            literature_ids = {
                str(item.get("paper_id") or "")
                for item in stages.get("literature", {}).get("content", {}).get("papers", [])
                if isinstance(item, dict)
            }
            run_ids = {
                str(item.get("run_id") or "") for item in analysis_runs
            }
            available = literature_ids | run_ids
            claims = stages.get("evidence", {}).get("content", {}).get("claims", [])
            missing: list[dict[str, Any]] = []
            for claim in claims:
                if not isinstance(claim, dict):
                    continue
                references = claim.get("evidence_artifact_ids", [])
                unknown = [
                    item for item in references if str(item) not in available
                ]
                if unknown:
                    missing.append(
                        {
                            "claim_id": claim.get("claim_id", ""),
                            "unknown_evidence_ids": unknown,
                        }
                    )
            return {"invalid_claims": missing}, f"证据产物核验完成，发现 {len(missing)} 条无效引用。"

        if tool_id == "citation.validate":
            paper_ids = {
                str(item.get("paper_id") or "")
                for item in stages.get("literature", {}).get("content", {}).get("papers", [])
                if isinstance(item, dict)
            }
            references = stages.get("delivery", {}).get("content", {}).get(
                "reference_paper_ids", []
            )
            missing = [item for item in references if str(item) not in paper_ids]
            return {
                "reference_count": len(references),
                "unknown_reference_ids": missing,
            }, f"引用核验完成，发现 {len(missing)} 个未知 paper_id。"

        raise StageAssistantError(
            "stage_tool_not_implemented",
            f"{tool_id} 尚未绑定可执行适配器",
        )

    @classmethod
    def context_hash(cls, project: dict[str, Any], stage_key: str) -> str:
        payload = cls._assistant_context(project, stage_key)
        return hashlib.sha256(
            json.dumps(
                payload,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()

    @classmethod
    def _assistant_context(
        cls,
        project: dict[str, Any],
        stage_key: str,
    ) -> dict[str, Any]:
        stage = cls._stage(project, stage_key)
        upstream = [
            {
                "key": item.get("key"),
                "revision": item.get("revision", 0),
                "status": item.get("status"),
                "content": cls._compact(item.get("content", {})),
            }
            for item in project.get("stages", [])
            if int(item.get("position") or 0) < int(stage.get("position") or 0)
        ]
        return {
            "title": project.get("title", ""),
            "initial_idea": project.get("initial_idea", ""),
            "current_stage": {
                "key": stage_key,
                "revision": stage.get("revision", 0),
                "status": stage.get("status"),
                "readiness": cls._compact(stage.get("readiness", {})),
                "content": cls._compact(stage.get("content", {})),
            },
            "upstream_stages": upstream[-4:],
        }

    @classmethod
    def _compact(cls, value: Any, depth: int = 0) -> Any:
        if depth >= 4:
            return "[内容层级已截断]"
        if isinstance(value, str):
            return value[:2400]
        if isinstance(value, list):
            return [cls._compact(item, depth + 1) for item in value[:12]]
        if isinstance(value, dict):
            return {
                str(key): cls._compact(item, depth + 1)
                for key, item in list(value.items())[:30]
                if key not in {"logs", "stata_do_file"}
            }
        return value

    @staticmethod
    def _stage(project: dict[str, Any], stage_key: str) -> dict[str, Any]:
        stage = next(
            (
                item
                for item in project.get("stages", [])
                if item.get("key") == stage_key
            ),
            None,
        )
        if stage is None:
            raise StageAssistantError(
                "stage_not_found",
                f"未找到阶段 {stage_key}",
            )
        return stage

    def _persist_tool_run(self, payload: dict[str, Any]) -> None:
        path = (
            self.projects_dir
            / str(payload["project_id"])
            / "artifacts"
            / "tool-runs"
            / str(payload["stage_key"])
            / f"{payload['tool_run_id']}.json"
        )
        self._write_json(path, payload)

    def _suggestion_path(self, project_id: str, stage_key: str) -> Path:
        return (
            self.projects_dir
            / project_id
            / "artifacts"
            / "suggestions"
            / f"{stage_key}.json"
        )

    @classmethod
    def _empty_suggestions(
        cls,
        project: dict[str, Any],
        stage: dict[str, Any],
        status: Literal["not_generated", "invalid"],
    ) -> dict[str, Any]:
        return {
            "suggestion_set_id": "",
            "project_id": project["project_id"],
            "stage_key": stage["key"],
            "stage_revision": int(stage.get("revision") or 0),
            "status": status,
            "context_hash": cls.context_hash(project, str(stage["key"])),
            "model": "",
            "generated_at": "",
            "summary": "",
            "suggestions": [],
            "usage": {},
        }

    @staticmethod
    def _write_json(path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(path)
