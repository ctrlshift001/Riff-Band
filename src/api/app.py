from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from db import ProjectStore
from domains import MANAGEMENT_SCIENCE_PROFILE
from services.models import CreateProjectRequest, DraftRequest, StageDecisionRequest, StageUpdateRequest
from services.project_service import (
    ProjectNotFoundError,
    ProjectService,
    StageLockedError,
    StageNotFoundError,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_ROOT = Path(__file__).resolve().parents[1] / "web" / "static"


def _default_data_dir() -> Path:
    configured = os.environ.get("AI4MS_DATA_DIR", "").strip()
    return Path(configured) if configured else REPO_ROOT / "workspace" / "ai4ms"


def create_app(data_dir: str | Path | None = None) -> FastAPI:
    resolved_data_dir = Path(data_dir) if data_dir is not None else _default_data_dir()
    service = ProjectService(ProjectStore(resolved_data_dir / "ai4ms.db"), resolved_data_dir)

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
        return get_service(request).create_draft(project_id, stage_key, payload)

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
    uvicorn.run("api.app:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    _entry()
