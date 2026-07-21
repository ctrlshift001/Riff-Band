from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

from ai4ms.db import ProjectStore
from ai4ms.delivery import DeliveryExportError
from ai4ms.domains import MANAGEMENT_SCIENCE_PROFILE
from ai4ms.inference import InferenceUnavailableError, inference_status
from ai4ms.knowledge import KnowledgeRegistry
from ai4ms.literature.service import LiteratureSearchInputError, LiteratureSearchService
from ai4ms.runners import AnalysisRunnerService
from ai4ms.services.models import (
    AnalysisRunRequest,
    CreateProjectRequest,
    DraftRequest,
    LiteratureSearchRequest,
    StageDecisionRequest,
    StageUpdateRequest,
)
from ai4ms.services.project_service import (
    ProjectNotFoundError,
    ProjectService,
    StageLockedError,
    StageNotFoundError,
)
from ai4ms.services.stage_generation import (
    StageContentValidationError,
    StageGenerationNotSupportedError,
    StageGenerationOutputError,
    StageGenerationService,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
WEB_ROOT = REPO_ROOT / "src" / "web" / "static"
load_dotenv(REPO_ROOT / ".env", override=False)


def _default_data_dir() -> Path:
    configured = os.environ.get("AI4MS_DATA_DIR", "").strip()
    return Path(configured) if configured else REPO_ROOT / "workspace" / "ai4ms"


def create_app(
    data_dir: str | Path | None = None,
    stage_generation: StageGenerationService | None = None,
    literature_search: LiteratureSearchService | None = None,
    analysis_runner: AnalysisRunnerService | None = None,
) -> FastAPI:
    resolved_data_dir = Path(data_dir) if data_dir is not None else _default_data_dir()
    service = ProjectService(
        ProjectStore(resolved_data_dir / "ai4ms.db"),
        resolved_data_dir,
        stage_generation=stage_generation,
        literature_search=literature_search,
        analysis_runner=analysis_runner,
    )

    app = FastAPI(
        title="AI4MS 科研工作台 API",
        version="0.3.0",
        description="面向管理科学的本地优先 AI 科研工作台。",
    )
    app.state.project_service = service

    origins = [item.strip() for item in os.environ.get("AI4MS_CORS_ORIGINS", "*").split(",") if item.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins or ["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    if WEB_ROOT.exists():
        app.mount("/assets", StaticFiles(directory=WEB_ROOT), name="assets")

    def get_service(request: Request) -> ProjectService:
        return request.app.state.project_service

    @app.exception_handler(ProjectNotFoundError)
    async def project_not_found(_request: Request, exc: ProjectNotFoundError):
        return _json_error(status.HTTP_404_NOT_FOUND, "project_not_found", str(exc))

    @app.exception_handler(StageNotFoundError)
    async def stage_not_found(_request: Request, exc: StageNotFoundError):
        return _json_error(status.HTTP_404_NOT_FOUND, "stage_not_found", str(exc))

    @app.exception_handler(StageLockedError)
    async def stage_locked(_request: Request, exc: StageLockedError):
        return _json_error(status.HTTP_409_CONFLICT, "stage_locked", str(exc))

    @app.exception_handler(StageGenerationNotSupportedError)
    async def generation_not_supported(_request: Request, exc: StageGenerationNotSupportedError):
        return _json_error(status.HTTP_409_CONFLICT, "model_generation_not_supported", str(exc))

    @app.exception_handler(InferenceUnavailableError)
    async def inference_unavailable(_request: Request, exc: InferenceUnavailableError):
        return _json_error(status.HTTP_503_SERVICE_UNAVAILABLE, "inference_unavailable", str(exc))

    @app.exception_handler(StageGenerationOutputError)
    async def invalid_model_output(_request: Request, exc: StageGenerationOutputError):
        return _json_error(status.HTTP_502_BAD_GATEWAY, "invalid_model_output", str(exc))

    @app.exception_handler(LiteratureSearchInputError)
    async def invalid_literature_search(_request: Request, exc: LiteratureSearchInputError):
        return _json_error(status.HTTP_422_UNPROCESSABLE_ENTITY, "invalid_literature_search", str(exc))

    @app.exception_handler(StageContentValidationError)
    async def invalid_stage_content(_request: Request, exc: StageContentValidationError):
        return _json_error(status.HTTP_409_CONFLICT, "invalid_stage_content", str(exc))

    @app.exception_handler(DeliveryExportError)
    async def invalid_delivery_export(_request: Request, exc: DeliveryExportError):
        return _json_error(status.HTTP_409_CONFLICT, "delivery_export_failed", str(exc))

    @app.get("/", include_in_schema=False)
    async def web_workbench():
        index = WEB_ROOT / "index.html"
        if not index.exists():
            raise HTTPException(status_code=503, detail="web workbench assets are unavailable")
        return FileResponse(index)

    @app.get("/healthz", tags=["system"])
    async def healthz():
        return {"status": "ok", "service": "ai4ms-workbench", "version": app.version}

    @app.get("/api/v1/meta/stages", tags=["meta"])
    async def stage_definitions(request: Request):
        return {"items": get_service(request).stage_definitions()}

    @app.get("/api/v1/meta/domain-profile", tags=["meta"])
    async def domain_profile():
        return MANAGEMENT_SCIENCE_PROFILE.model_dump()

    @app.get("/api/v1/meta/inference", tags=["meta"])
    async def model_inference_status():
        return inference_status()

    @app.get("/api/v1/knowledge/methods", tags=["knowledge"])
    async def method_registry(goal: str = "", q: str = "", limit: int = 10):
        return {"items": KnowledgeRegistry.method_candidates(goal, q, limit)}

    @app.get("/api/v1/knowledge/data-sources", tags=["knowledge"])
    async def data_source_registry(q: str = "", limit: int = 12):
        return {"items": KnowledgeRegistry.data_source_candidates(q, limit)}

    @app.get("/api/v1/knowledge/formulas", tags=["knowledge"])
    async def formula_registry(q: str = "", method_id: list[str] | None = None, limit: int = 12):
        return {"items": KnowledgeRegistry.formula_candidates(q, method_id or [], limit)}

    @app.get("/api/v1/runners/stata", tags=["runners"])
    async def stata_runner_status(request: Request):
        return get_service(request).analysis_runner.status()

    @app.get("/api/v1/projects", tags=["projects"])
    async def list_projects(request: Request):
        return {"items": get_service(request).list_projects()}

    @app.post("/api/v1/projects", tags=["projects"], status_code=status.HTTP_201_CREATED)
    async def create_project(payload: CreateProjectRequest, request: Request):
        return get_service(request).create_project(payload)

    @app.get("/api/v1/projects/{project_id}", tags=["projects"])
    async def get_project(project_id: str, request: Request):
        return get_service(request).get_project(project_id)

    @app.get("/api/v1/projects/{project_id}/stages/current", tags=["stages"])
    async def get_current_stage(project_id: str, request: Request):
        project = get_service(request).get_project(project_id)
        stage = next(item for item in project["stages"] if item["key"] == project["current_stage"])
        return stage

    @app.get("/api/v1/projects/{project_id}/stages/{stage_key}", tags=["stages"])
    async def get_stage(project_id: str, stage_key: str, request: Request):
        return get_service(request).get_stage(project_id, stage_key)

    @app.put("/api/v1/projects/{project_id}/stages/{stage_key}", tags=["stages"])
    async def update_stage(project_id: str, stage_key: str, payload: StageUpdateRequest, request: Request):
        return get_service(request).update_stage(project_id, stage_key, payload)

    @app.post("/api/v1/projects/{project_id}/stages/{stage_key}/draft", tags=["stages"])
    async def create_stage_draft(project_id: str, stage_key: str, payload: DraftRequest, request: Request):
        return await get_service(request).create_draft(project_id, stage_key, payload)

    @app.post("/api/v1/projects/{project_id}/stages/literature/search", tags=["literature"])
    async def search_literature(project_id: str, payload: LiteratureSearchRequest, request: Request):
        return await get_service(request).search_literature(project_id, payload)

    @app.post("/api/v1/projects/{project_id}/stages/analysis/preflight", tags=["runners"])
    async def preflight_analysis_run(project_id: str, payload: AnalysisRunRequest, request: Request):
        return get_service(request).preflight_analysis_run(project_id, payload)

    @app.post("/api/v1/projects/{project_id}/stages/analysis/runs", tags=["runners"])
    async def submit_analysis_run(project_id: str, payload: AnalysisRunRequest, request: Request):
        return await get_service(request).submit_analysis_run(project_id, payload)

    @app.post("/api/v1/projects/{project_id}/stages/delivery/export", tags=["delivery"])
    async def export_delivery(project_id: str, request: Request):
        return get_service(request).export_delivery(project_id)

    @app.get("/api/v1/projects/{project_id}/exports/{export_id}/report", tags=["delivery"])
    async def get_visual_report(project_id: str, export_id: str, request: Request):
        path = get_service(request).delivery_artifact(project_id, export_id, "report")
        return FileResponse(
            path,
            media_type="text/html; charset=utf-8",
            filename=path.name,
            content_disposition_type="inline",
        )

    @app.get("/api/v1/projects/{project_id}/exports/{export_id}/package", tags=["delivery"])
    async def download_research_package(project_id: str, export_id: str, request: Request):
        path = get_service(request).delivery_artifact(project_id, export_id, "package")
        return FileResponse(path, media_type="application/zip", filename=f"{project_id}-{export_id}.zip")

    @app.get("/api/v1/projects/{project_id}/exports/{export_id}/manifest", tags=["delivery"])
    async def get_delivery_manifest(project_id: str, export_id: str, request: Request):
        path = get_service(request).delivery_artifact(project_id, export_id, "manifest")
        return FileResponse(path, media_type="application/json; charset=utf-8", filename=path.name)

    @app.post("/api/v1/projects/{project_id}/stages/{stage_key}/decisions", tags=["approvals"])
    async def decide_stage(project_id: str, stage_key: str, payload: StageDecisionRequest, request: Request):
        try:
            return get_service(request).decide_stage(project_id, stage_key, payload)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    return app


def _json_error(status_code: int, code: str, message: str):
    from fastapi.responses import JSONResponse

    return JSONResponse(status_code=status_code, content={"error": {"code": code, "message": message}})


app = create_app()


def _entry() -> None:
    import uvicorn

    host = os.environ.get("AI4MS_HOST", "0.0.0.0")
    port = int(os.environ.get("AI4MS_PORT", "8000"))
    uvicorn.run("ai4ms.api.app:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    _entry()
