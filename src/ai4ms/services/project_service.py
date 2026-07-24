from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from ai4ms.assets import DataAssetService
from ai4ms.db.store import ProjectStore, RevisionConflictError
from ai4ms.delivery import DeliveryExportError, DeliveryExportService
from ai4ms.literature.service import LiteratureSearchService
from ai4ms.orchestration import AOrchestraStageService
from ai4ms.runners import AnalysisJobService, AnalysisRunnerService
from ai4ms.services.models import (
    STAGE_DEFINITIONS,
    STAGES_BY_KEY,
    ApprovalDecision,
    AnalysisRerunRequest,
    AnalysisRunRequest,
    CreateProjectRequest,
    DraftRequest,
    LiteratureSearchRequest,
    StageDecisionRequest,
    StageStatus,
    StageUpdateRequest,
    StageWorkspaceUpdateRequest,
    UpdateProjectRequest,
)
from ai4ms.services.stage_generation import (
    StageContentValidationError,
    StageGenerationService,
)


class ProjectNotFoundError(LookupError):
    pass


class StageNotFoundError(LookupError):
    pass


class StageLockedError(RuntimeError):
    pass


class StageRevisionConflictError(RuntimeError):
    pass


STAGE_TEMPLATES: dict[str, dict[str, Any]] = {
    "problem": {"initial_idea": "", "research_object": "", "problem_boundary": "", "objective": "", "questions": [], "candidate_gaps": [], "counter_searches": [], "unknowns": []},
    "literature": {"topic_summary": "", "query_blocks": [], "databases": [], "languages": [], "inclusion_criteria": [], "exclusion_criteria": [], "screening_questions": [], "counter_searches": [], "sources": [], "papers": [], "search_runs": [], "research_streams": [], "syntheses": [], "gap_candidates": [], "recommended_next_steps": [], "unknowns": [], "coverage_limits": []},
    "theory": {"theoretical_lenses": [], "constructs": [], "mechanisms": [], "research_questions": [], "competing_explanations": [], "falsifiable_propositions": [], "contribution_boundary": "", "unknowns": []},
    "design": {"research_question": "", "unit_of_analysis": "", "design_lane": "", "estimand_or_objective": "", "method_options": [], "primary_method_id": "", "assumptions": [], "falsification": [], "threats_to_validity": [], "stopping_conditions": [], "unknowns": []},
    "data": {"data_sources": [], "variables": [], "sample_definition": "", "time_coverage": "", "join_keys": [], "pii_class": "unknown", "privacy_risks": [], "ethics_checks": [], "quality_checks": [], "blocking_issues": [], "unknowns": []},
    "identification": {"design_lane": "", "estimand_or_objective": "", "analysis_sample": "", "unit_of_analysis": "", "variable_roles": [], "model_specifications": [], "diagnostics": [], "analysis_steps": [], "missing_data_plan": "", "multiplicity_plan": "", "robustness_plan": [], "stopping_conditions": [], "execution_engine": "unknown", "code_language": "", "stata_do_file": "", "seed": None, "expected_outputs": [], "reproducibility_requirements": [], "unknowns": []},
    "analysis": {"execution_engine": "unknown", "readiness_summary": "", "expected_outputs": [], "preflight_checks": [], "result_review_checks": [], "runner_status": "not_checked", "approved_analysis_plan_revision": 0, "approved_analysis_plan_hash": "", "do_file": "", "runs": [], "results": [], "blocking_issues": [], "unknowns": []},
    "robustness": {"robustness_matrix": [], "failed_checks": [], "interpretation_limits": [], "next_runs": [], "reproducibility_report": "", "unknowns": []},
    "evidence": {"claims": [], "mechanisms": [], "heterogeneity": [], "limitations": [], "interpretation": "", "unknowns": []},
    "delivery": {"title": "", "executive_summary": "", "conclusions": [], "policy_implications": [], "outline": [], "reference_paper_ids": [], "approved_claims": [], "references": [], "limitations": [], "reproducibility_notes": [], "disclosure": "", "release_notes": "", "unknowns": [], "exports": [], "visual_report_path": "", "research_package_path": ""},
}


class ProjectService:
    def __init__(
        self,
        store: ProjectStore,
        data_dir: str | Path,
        stage_generation: StageGenerationService | None = None,
        literature_search: LiteratureSearchService | None = None,
        analysis_runner: AnalysisRunnerService | None = None,
        delivery_export: DeliveryExportService | None = None,
    ):
        self.store = store
        self.data_dir = Path(data_dir)
        self.projects_dir = self.data_dir / "projects"
        self.stage_generation = stage_generation or StageGenerationService(
            orchestrator=AOrchestraStageService(self.projects_dir)
        )
        self.literature_search = literature_search or LiteratureSearchService(self.projects_dir)
        self.analysis_runner = analysis_runner or AnalysisRunnerService()
        self.delivery_export = delivery_export or DeliveryExportService(self.projects_dir)
        self.data_assets = DataAssetService(self.store, self.projects_dir)
        self.projects_dir.mkdir(parents=True, exist_ok=True)
        self.store.initialize()
        self.analysis_jobs = AnalysisJobService(
            self.projects_dir,
            self.analysis_runner,
            self.get_project,
            self._record_analysis_run,
        )

    def stage_definitions(self) -> list[dict[str, Any]]:
        return [stage.model_dump() for stage in STAGE_DEFINITIONS]

    def create_project(self, request: CreateProjectRequest) -> dict[str, Any]:
        project = self.store.create_project(request.title, request.initial_idea)
        project_dir = self.projects_dir / project["project_id"]
        (project_dir / "artifacts").mkdir(parents=True, exist_ok=True)
        (project_dir / "exports").mkdir(parents=True, exist_ok=True)
        return self._enrich(project)

    def list_projects(self) -> list[dict[str, Any]]:
        return self.store.list_projects()

    def get_project(self, project_id: str) -> dict[str, Any]:
        try:
            return self._enrich(self.store.get_project(project_id))
        except KeyError as exc:
            raise ProjectNotFoundError(project_id) from exc

    async def upload_data_asset(
        self,
        project_id: str,
        filename: str,
        media_type: str,
        read,
    ) -> dict[str, Any]:
        self.get_project(project_id)
        return await self.data_assets.upload(
            project_id, filename, media_type, read
        )

    def list_data_assets(self, project_id: str) -> list[dict[str, Any]]:
        self.get_project(project_id)
        return self.store.list_data_assets(project_id)

    def get_stage(self, project_id: str, stage_key: str) -> dict[str, Any]:
        self._require_stage(stage_key)
        try:
            return self.store.get_stage(project_id, stage_key)
        except KeyError as exc:
            raise ProjectNotFoundError(project_id) from exc

    def update_project(self, project_id: str, request: UpdateProjectRequest) -> dict[str, Any]:
        try:
            return self._enrich(
                self.store.update_project(project_id, request.title, request.initial_idea)
            )
        except KeyError as exc:
            raise ProjectNotFoundError(project_id) from exc

    async def create_draft(self, project_id: str, stage_key: str, request: DraftRequest) -> dict[str, Any]:
        project = self.get_project(project_id)
        self._ensure_unlocked(project, stage_key)
        stage = next(item for item in project["stages"] if item["key"] == stage_key)
        content = deepcopy(STAGE_TEMPLATES[stage_key])
        content.update(stage.get("content") or {})
        if request.generation_mode == "model":
            generated = await self.stage_generation.generate(project, stage_key, request.instruction)
            content.update(generated)
            change_reason = f"Generated model draft for {stage_key}"
        else:
            if stage_key == "problem":
                content.setdefault("initial_idea", project["initial_idea"])
            content["draft_source"] = "structure_template"
            if request.instruction:
                content["draft_instruction"] = request.instruction
            change_reason = "Created structured stage draft"
        if stage_key == "analysis":
            plan_stage = next(item for item in project["stages"] if item["key"] == "identification")
            plan = plan_stage.get("content") or {}
            content.update(
                {
                    "execution_engine": plan.get("execution_engine", "unknown"),
                    "approved_analysis_plan_revision": plan_stage.get("revision", 0),
                    "approved_analysis_plan_hash": plan_stage.get("content_hash", ""),
                    "do_file": plan.get("stata_do_file", ""),
                    "runner_status": "available" if self.analysis_runner.status()["available"] else "unavailable",
                }
            )
        update = StageUpdateRequest(
            content=content,
            change_reason=change_reason,
            author_type="agent",
        )
        return self.update_stage(project_id, stage_key, update)

    async def search_literature(self, project_id: str, request: LiteratureSearchRequest) -> dict[str, Any]:
        project = self.get_project(project_id)
        self._ensure_unlocked(project, "literature")
        stage = next(item for item in project["stages"] if item["key"] == "literature")
        content = deepcopy(STAGE_TEMPLATES["literature"])
        content.update(stage.get("content") or {})
        search_run = await self.literature_search.search(project_id, content, request)
        content["papers"] = search_run.pop("papers")
        content["sources"] = search_run["source_runs"]
        content.setdefault("search_runs", []).append(search_run)
        update = StageUpdateRequest(
            content=content,
            change_reason=f"Executed literature search {search_run['search_id']}",
            author_type="agent",
        )
        return self.update_stage(project_id, "literature", update)

    def preflight_analysis_run(self, project_id: str, request: AnalysisRunRequest) -> dict[str, Any]:
        project = self.get_project(project_id)
        self._ensure_unlocked(project, "analysis")
        return self.analysis_runner.preflight(
            project,
            self.projects_dir / project_id,
            request,
        )

    async def submit_analysis_run(self, project_id: str, request: AnalysisRunRequest) -> dict[str, Any]:
        project = self.get_project(project_id)
        self._ensure_unlocked(project, "analysis")
        return await self.analysis_jobs.submit(project_id, request)

    def list_analysis_runs(self, project_id: str) -> list[dict[str, Any]]:
        return self.analysis_jobs.list(project_id)

    def get_analysis_run(self, project_id: str, run_id: str) -> dict[str, Any]:
        return self.analysis_jobs.get(project_id, run_id)

    def get_analysis_run_result(self, project_id: str, run_id: str) -> dict[str, Any]:
        return self.analysis_jobs.result(project_id, run_id)

    async def cancel_analysis_run(self, project_id: str, run_id: str) -> dict[str, Any]:
        return await self.analysis_jobs.cancel(project_id, run_id)

    async def rerun_analysis(
        self,
        project_id: str,
        run_id: str,
        request: AnalysisRerunRequest,
    ) -> dict[str, Any]:
        project = self.get_project(project_id)
        self._ensure_unlocked(project, "analysis")
        return await self.analysis_jobs.rerun(
            project_id,
            run_id,
            timeout_seconds=request.timeout_seconds,
        )

    def _record_analysis_run(self, project_id: str, run: dict[str, Any]) -> dict[str, Any]:
        project = self.get_project(project_id)
        stage = next(item for item in project["stages"] if item["key"] == "analysis")
        content = deepcopy(STAGE_TEMPLATES["analysis"])
        content.update(stage.get("content") or {})
        content.setdefault("runs", []).append(run)
        content["runner_status"] = (
            "available" if run.get("runner_profile", {}).get("available") else "unavailable"
        )
        content["last_preflight"] = run.get("preflight", {})
        if run.get("status") in {"succeeded", "failed"}:
            content.setdefault("results", []).append(
                {
                    "run_id": run["run_id"],
                    "status": run["status"],
                    "exit_code": run.get("exit_code"),
                    "data_signature": run.get("data_signature", ""),
                    "structured_results": run.get("structured_results", []),
                    "output_artifacts": run.get("output_artifacts", []),
                }
            )
        update = StageUpdateRequest(
            content=content,
            change_reason=f"Recorded analysis run {run['run_id']} ({run['status']}:{run['reason_code']})",
            author_type="agent",
        )
        return self.update_stage(project_id, "analysis", update)

    def export_delivery(self, project_id: str) -> dict[str, Any]:
        project = self.get_project(project_id)
        self._ensure_unlocked(project, "delivery")
        stage = next(item for item in project["stages"] if item["key"] == "delivery")
        export_record = self.delivery_export.export(project)
        content = deepcopy(STAGE_TEMPLATES["delivery"])
        content.update(stage.get("content") or {})
        content.setdefault("exports", []).append(export_record)
        content["visual_report_path"] = export_record["visual_report_path"]
        content["research_package_path"] = export_record["research_package_path"]
        content["manifest_path"] = export_record["manifest_path"]
        return self.update_stage(
            project_id,
            "delivery",
            StageUpdateRequest(
                content=content,
                change_reason=f"Generated delivery export {export_record['export_id']}",
                author_type="agent",
            ),
        )

    def delivery_artifact(self, project_id: str, export_id: str, kind: str) -> Path:
        project = self.get_project(project_id)
        return self.delivery_export.artifact_path(project, export_id, kind)

    def update_stage(self, project_id: str, stage_key: str, request: StageUpdateRequest) -> dict[str, Any]:
        project = self.get_project(project_id)
        self._ensure_unlocked(project, stage_key)
        try:
            result = self.store.update_stage(
                project_id=project_id,
                stage_key=stage_key,
                content=request.content,
                change_reason=request.change_reason,
                author_type=request.author_type,
            )
        except KeyError as exc:
            raise ProjectNotFoundError(project_id) from exc
        return self._enrich(result)

    def update_stage_workspace(
        self,
        project_id: str,
        stage_key: str,
        request: StageWorkspaceUpdateRequest,
    ) -> dict[str, Any]:
        project = self.get_project(project_id)
        self._ensure_unlocked(project, stage_key)
        stage = next(item for item in project["stages"] if item["key"] == stage_key)
        content = deepcopy(stage.get("content") or {})
        content["_workspace"] = request.workspace.model_dump()
        try:
            result = self.store.update_stage(
                project_id=project_id,
                stage_key=stage_key,
                content=content,
                change_reason=request.change_reason,
                author_type="human",
                expected_revision=request.expected_revision,
            )
        except RevisionConflictError as exc:
            raise StageRevisionConflictError(str(exc)) from exc
        except KeyError as exc:
            raise ProjectNotFoundError(project_id) from exc
        return self._enrich(result)

    def decide_stage(self, project_id: str, stage_key: str, request: StageDecisionRequest) -> dict[str, Any]:
        self._require_stage(stage_key)
        project = self.get_project(project_id)
        self._ensure_unlocked(project, stage_key)
        if request.decision is ApprovalDecision.APPROVE:
            stage = next(item for item in project["stages"] if item["key"] == stage_key)
            StageGenerationService.validate_stage_content(project, stage_key, stage.get("content", {}))
            if stage_key == "literature":
                content = stage.get("content", {})
                if not content.get("search_runs"):
                    raise StageContentValidationError("S1 批准前必须执行至少一次可追溯文献检索")
                if not content.get("papers"):
                    raise StageContentValidationError("S1 检索未形成可追溯论文记录，不能进入下一阶段")
            if stage_key == "delivery":
                exports = stage.get("content", {}).get("exports", [])
                if not exports:
                    raise StageContentValidationError("G5 批准前必须生成 HTML 报告与研究包")
                latest = exports[-1]
                fingerprint = self.delivery_export.delivery_fingerprint(stage.get("content", {}))
                if latest.get("source_content_fingerprint") != fingerprint:
                    raise StageContentValidationError("S9 内容在最近一次导出后已变化，请重新生成交付包")
                self.delivery_export.artifact_path(project, str(latest.get("export_id", "")), "report")
                self.delivery_export.artifact_path(project, str(latest.get("export_id", "")), "package")
        try:
            result = self.store.decide_stage(
                project_id=project_id,
                stage_key=stage_key,
                decision=request.decision,
                reason=request.reason,
                actor_type=request.actor_type,
            )
        except KeyError as exc:
            raise ProjectNotFoundError(project_id) from exc
        return self._enrich(result)

    def _enrich(self, project: dict[str, Any]) -> dict[str, Any]:
        stages = project.get("stages", [])
        approved = sum(1 for stage in stages if stage["status"] == StageStatus.APPROVED.value)
        result = dict(project)
        result["progress"] = {"approved": approved, "total": len(STAGE_DEFINITIONS)}
        result["data_assets"] = self.store.list_data_assets(str(project["project_id"]))
        return result

    @staticmethod
    def _require_stage(stage_key: str) -> None:
        if stage_key not in STAGES_BY_KEY:
            raise StageNotFoundError(stage_key)

    def _ensure_unlocked(self, project: dict[str, Any], stage_key: str) -> None:
        self._require_stage(stage_key)
        definition = STAGES_BY_KEY[stage_key]
        if definition.position == 1:
            return
        previous = project["stages"][definition.position - 2]
        if previous["status"] != StageStatus.APPROVED.value:
            raise StageLockedError(
                f"stage '{stage_key}' is locked until '{previous['key']}' is approved"
            )
