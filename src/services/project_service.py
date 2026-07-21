from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from db.store import ProjectStore
from literature.service import LiteratureSearchService
from services.models import (
    STAGE_DEFINITIONS,
    STAGES_BY_KEY,
    ApprovalDecision,
    CreateProjectRequest,
    DraftRequest,
    LiteratureSearchRequest,
    StageDecisionRequest,
    StageStatus,
    StageUpdateRequest,
)
from services.stage_generation import StageGenerationService


class ProjectNotFoundError(LookupError):
    pass


class StageNotFoundError(LookupError):
    pass


class StageLockedError(RuntimeError):
    pass


STAGE_TEMPLATES: dict[str, dict[str, Any]] = {
    "problem": {"initial_idea": "", "research_object": "", "problem_boundary": "", "objective": "", "questions": [], "candidate_gaps": [], "counter_searches": [], "unknowns": []},
    "literature": {"topic_summary": "", "query_blocks": [], "databases": [], "languages": [], "inclusion_criteria": [], "exclusion_criteria": [], "screening_questions": [], "counter_searches": [], "sources": [], "papers": [], "search_runs": [], "research_streams": [], "syntheses": [], "gap_candidates": [], "recommended_next_steps": [], "unknowns": [], "coverage_limits": []},
    "theory": {"theoretical_lenses": [], "constructs": [], "mechanisms": [], "research_questions": [], "competing_explanations": [], "falsifiable_propositions": [], "contribution_boundary": "", "unknowns": []},
    "design": {"research_question": "", "unit_of_analysis": "", "design_lane": "", "estimand_or_objective": "", "method_options": [], "primary_method_id": "", "assumptions": [], "falsification": [], "threats_to_validity": [], "stopping_conditions": [], "unknowns": []},
    "data": {"data_sources": [], "variables": [], "sample_definition": "", "time_coverage": "", "join_keys": [], "pii_class": "unknown", "privacy_risks": [], "ethics_checks": [], "quality_checks": [], "blocking_issues": [], "unknowns": []},
    "identification": {"estimand": "", "analysis_steps": [], "variable_table": [], "model_specifications": [], "diagnostics": [], "code_plan": [], "assumptions": []},
    "analysis": {"runner_status": "not_checked", "approved_code_revision": "", "do_file": "", "runs": [], "results": [], "reproducibility": {}, "blocking_issues": []},
    "robustness": {"robustness_matrix": [], "alternative_measures": [], "alternative_samples": [], "placebo_tests": [], "failed_checks": [], "reproducibility_report": ""},
    "evidence": {"claims": [], "mechanisms": [], "heterogeneity": [], "evidence_links": [], "counter_evidence": [], "limitations": [], "interpretation": ""},
    "delivery": {"conclusions": [], "policy_implications": [], "outline": [], "approved_claims": [], "references": [], "visual_report_path": "", "research_package_path": "", "release_notes": ""},
}


class ProjectService:
    def __init__(
        self,
        store: ProjectStore,
        data_dir: str | Path,
        stage_generation: StageGenerationService | None = None,
        literature_search: LiteratureSearchService | None = None,
    ):
        self.store = store
        self.data_dir = Path(data_dir)
        self.projects_dir = self.data_dir / "projects"
        self.stage_generation = stage_generation or StageGenerationService()
        self.literature_search = literature_search or LiteratureSearchService(self.projects_dir)
        self.projects_dir.mkdir(parents=True, exist_ok=True)
        self.store.initialize()

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

    def get_stage(self, project_id: str, stage_key: str) -> dict[str, Any]:
        self._require_stage(stage_key)
        try:
            return self.store.get_stage(project_id, stage_key)
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

    def decide_stage(self, project_id: str, stage_key: str, request: StageDecisionRequest) -> dict[str, Any]:
        self._require_stage(stage_key)
        project = self.get_project(project_id)
        self._ensure_unlocked(project, stage_key)
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

    @staticmethod
    def _enrich(project: dict[str, Any]) -> dict[str, Any]:
        stages = project.get("stages", [])
        approved = sum(1 for stage in stages if stage["status"] == StageStatus.APPROVED.value)
        result = dict(project)
        result["progress"] = {"approved": approved, "total": len(STAGE_DEFINITIONS)}
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
