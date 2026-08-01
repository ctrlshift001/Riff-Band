from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from ai4ms.knowledge import KnowledgeEvaluationService
from ai4ms.services.models import KnowledgeEvaluationRequest


class KnowledgeEvaluationJobNotFoundError(LookupError):
    pass


class KnowledgeEvaluationJobService:
    """Run long model evaluations outside the request-response timeout window."""

    def __init__(
        self,
        projects_dir: str | Path,
        evaluator: KnowledgeEvaluationService,
    ) -> None:
        self.projects_dir = Path(projects_dir)
        self.evaluator = evaluator
        self.jobs: dict[str, dict[str, Any]] = {}
        self.tasks: dict[str, asyncio.Task[None]] = {}
        self.active_by_project: dict[str, str] = {}

    async def submit(
        self,
        project: dict[str, Any],
        request: KnowledgeEvaluationRequest,
    ) -> dict[str, Any]:
        project_id = str(project["project_id"])
        active_id = self.active_by_project.get(project_id, "")
        active_task = self.tasks.get(active_id)
        if active_id and active_task is not None and not active_task.done():
            return dict(self.jobs[active_id])

        now = datetime.now(UTC).isoformat()
        job_id = f"keval_{uuid4().hex[:12]}"
        payload = {
            "job_id": job_id,
            "project_id": project_id,
            "status": "queued",
            "created_at": now,
            "started_at": "",
            "finished_at": "",
            "error": "",
            "result": None,
        }
        self.jobs[job_id] = payload
        self.active_by_project[project_id] = job_id
        self._persist(payload)
        self.tasks[job_id] = asyncio.create_task(
            self._run(job_id, project, request)
        )
        return dict(payload)

    def get(self, project_id: str, job_id: str) -> dict[str, Any]:
        payload = self.jobs.get(job_id)
        if payload is None:
            path = self._path(project_id, job_id)
            if path.exists():
                try:
                    candidate = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    candidate = None
                if isinstance(candidate, dict):
                    payload = candidate
                    self.jobs[job_id] = payload
                    if payload.get("status") in {"queued", "running"}:
                        payload["status"] = "failed"
                        payload["error"] = "评估任务因服务重启而中断，请重新提交。"
                        payload["finished_at"] = datetime.now(UTC).isoformat()
                        self._persist(payload)
        if payload is None or payload.get("project_id") != project_id:
            raise KnowledgeEvaluationJobNotFoundError(job_id)
        return dict(payload)

    async def _run(
        self,
        job_id: str,
        project: dict[str, Any],
        request: KnowledgeEvaluationRequest,
    ) -> None:
        payload = self.jobs[job_id]
        payload["status"] = "running"
        payload["started_at"] = datetime.now(UTC).isoformat()
        self._persist(payload)
        try:
            payload["result"] = await self.evaluator.evaluate(project, request)
            payload["status"] = "succeeded"
        except asyncio.CancelledError:
            payload["status"] = "failed"
            payload["error"] = "评估任务因服务停止而中断，请重新提交。"
            raise
        except Exception as exc:
            payload["status"] = "failed"
            payload["error"] = f"{type(exc).__name__}: {str(exc)[:1000]}"
        finally:
            payload["finished_at"] = datetime.now(UTC).isoformat()
            self._persist(payload)
            project_id = str(payload["project_id"])
            if self.active_by_project.get(project_id) == job_id:
                self.active_by_project.pop(project_id, None)
            self.tasks.pop(job_id, None)

    def _persist(self, payload: dict[str, Any]) -> None:
        path = self._path(str(payload["project_id"]), str(payload["job_id"]))
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(path)

    def _path(self, project_id: str, job_id: str) -> Path:
        return (
            self.projects_dir
            / project_id
            / "artifacts"
            / "knowledge"
            / "jobs"
            / f"{job_id}.json"
        )
