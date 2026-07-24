from __future__ import annotations

import asyncio
import json

from ai4ms.runners.jobs import AnalysisJobService
from ai4ms.services.models import AnalysisRunRequest


class _ControllableRunner:
    def __init__(self) -> None:
        self.block = True
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.timeouts: list[int] = []

    def preflight(self, _project, _project_dir, request) -> dict:
        return {
            "status": "ready",
            "reason_code": "ready",
            "input_asset_id": request.input_asset_id,
        }

    async def submit(self, _project, project_dir, request, run_id=None) -> dict:
        self.timeouts.append(request.timeout_seconds)
        self.started.set()
        if self.block:
            await self.release.wait()
        run = {
            "run_id": run_id,
            "status": "succeeded",
            "reason_code": "completed",
            "finished_at": "2026-07-24T00:00:01+00:00",
            "manifest_path": f"artifacts/runs/{run_id}/manifest.json",
            "structured_results": [],
            "output_artifacts": [],
        }
        manifest = project_dir / run["manifest_path"]
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text(json.dumps(run), encoding="utf-8")
        return run

    async def cancel(self, _run_id: str) -> bool:
        return False


def test_background_job_cancel_persist_and_rerun(tmp_path):
    async def scenario():
        project = {"project_id": "prj_jobs"}
        recorded: list[dict] = []
        runner = _ControllableRunner()
        service = AnalysisJobService(
            tmp_path,
            runner,
            lambda _project_id: project,
            lambda _project_id, run: recorded.append(run) or project,
        )

        first = await service.submit(
            "prj_jobs",
            AnalysisRunRequest(input_artifact_path="input.dta", timeout_seconds=23),
        )
        await runner.started.wait()
        await service.cancel("prj_jobs", first["run_id"])
        for _ in range(20):
            await asyncio.sleep(0)
            canceled = service.get("prj_jobs", first["run_id"])
            if canceled["status"] == "canceled":
                break

        assert canceled["status"] == "canceled"
        assert canceled["reason_code"] == "user_canceled"
        persisted = json.loads(
            (
                tmp_path
                / "prj_jobs"
                / "artifacts"
                / "jobs"
                / f"{first['run_id']}.json"
            ).read_text(encoding="utf-8")
        )
        assert persisted["status"] == "canceled"

        runner.block = False
        rerun = await service.rerun(
            "prj_jobs",
            first["run_id"],
            timeout_seconds=41,
        )
        for _ in range(20):
            await asyncio.sleep(0)
            completed = service.get("prj_jobs", rerun["run_id"])
            if completed["status"] == "succeeded":
                break

        assert completed["status"] == "succeeded"
        assert completed["parent_run_id"] == first["run_id"]
        assert runner.timeouts == [23, 41]
        assert service.result("prj_jobs", rerun["run_id"])["status"] == "succeeded"
        assert [run["status"] for run in recorded] == ["canceled", "succeeded"]

    asyncio.run(scenario())
