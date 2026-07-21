from __future__ import annotations

import asyncio
import json

from ai4ms.runners.service import AnalysisRunnerService
from ai4ms.runners.stata import StataPolicyScanner
from ai4ms.services.models import AnalysisRunRequest


SAFE_DO_FILE = """version 18.0
set more off
set varabbrev off
args project_dir run_id input_dta output_dir
use `"`input_dta'"', clear
set seed 20260721
summarize outcome treatment
"""


def _project(status: str = "approved", binding_hash: str = "hash_plan") -> dict:
    return {
        "project_id": "prj_runner",
        "stages": [
            {
                "key": "identification",
                "status": status,
                "revision": 3,
                "content_hash": "hash_plan",
                "content": {
                    "execution_engine": "stata",
                    "stata_do_file": SAFE_DO_FILE,
                    "seed": 20260721,
                    "variable_roles": [
                        {"source_variable": "outcome"},
                        {"source_variable": "treatment"},
                    ],
                },
            },
            {
                "key": "analysis",
                "status": "in_progress",
                "revision": 1,
                "content": {
                    "approved_analysis_plan_revision": 3,
                    "approved_analysis_plan_hash": binding_hash,
                    "do_file": SAFE_DO_FILE,
                    "runs": [],
                },
            },
        ],
    }


def _profile(available: bool = True) -> dict:
    return {
        "available": available,
        "engine": "stata",
        "mode": "batch",
        "executable": "fake-stata",
        "executable_name": "fake-stata",
        "version": "19",
        "edition": "MP",
        "license_mode": "user_byol",
        "license_confirmed": available,
        "max_concurrency": 1,
        "reason": "" if available else "not found",
    }


def test_stata_policy_blocks_external_process_install_network_and_traversal():
    issues = StataPolicyScanner.scan(
        "version 18\nshell whoami\nssc install reghdfe\ncopy https://example.com/x x\nuse ../secret.dta\nsave `\"`input_dta'\"', replace"
    )

    assert {item["code"] for item in issues} == {
        "external_process",
        "dynamic_install",
        "network_access",
        "parent_traversal",
        "overwrite_input",
    }


def test_preflight_reports_no_runner_without_leaking_executable_path(tmp_path):
    project_dir = tmp_path / "prj_runner"
    project_dir.mkdir()
    (project_dir / "input.dta").write_bytes(b"fixture")
    service = AnalysisRunnerService(profile_factory=lambda: _profile(False))

    result = service.preflight(
        _project(), project_dir, AnalysisRunRequest(input_artifact_path="input.dta")
    )

    assert result["status"] == "blocked"
    assert result["reason_code"] == "no_runner"
    assert result["checks"]["gate_passed"] is True
    assert "executable" not in result["runner_profile"]


def test_preflight_blocks_unapproved_gate_stale_binding_and_path_traversal(tmp_path):
    project_dir = tmp_path / "prj_runner"
    project_dir.mkdir()
    service = AnalysisRunnerService(profile_factory=lambda: _profile())

    gate = service.preflight(
        _project(status="needs_review"),
        project_dir,
        AnalysisRunRequest(input_artifact_path="../outside.dta"),
    )
    stale = service.preflight(
        _project(binding_hash="old_hash"),
        project_dir,
        AnalysisRunRequest(input_artifact_path="../outside.dta"),
    )

    assert gate["reason_code"] == "gate_not_approved"
    assert stale["reason_code"] == "stale_plan_binding"
    assert any(item["code"] == "invalid_input" for item in stale["issues"])


class _FakeAdapter:
    async def execute(self, _profile, _do_file, _project_dir, _run_id, _input, output_dir, _timeout):
        (output_dir / "results.csv").write_text("term,estimate\ntreatment,0.2\n", encoding="utf-8")
        return {
            "status": "succeeded",
            "reason_code": "completed",
            "exit_code": 0,
            "started_at": "2026-07-21T00:00:00+00:00",
            "finished_at": "2026-07-21T00:00:01+00:00",
            "duration_seconds": 1.0,
        }


def test_submit_writes_immutable_manifest_and_output_hashes(tmp_path):
    project_dir = tmp_path / "prj_runner"
    project_dir.mkdir()
    (project_dir / "input.dta").write_bytes(b"fixture")
    service = AnalysisRunnerService(
        adapter=_FakeAdapter(), profile_factory=lambda: _profile()
    )

    run = asyncio.run(
        service.submit(
            _project(),
            project_dir,
            AnalysisRunRequest(input_artifact_path="input.dta", timeout_seconds=30),
        )
    )

    assert run["status"] == "succeeded"
    assert run["analysis_plan_hash"] == "hash_plan"
    assert run["input_artifacts"][0]["sha256"]
    assert any(item["path"].endswith("results.csv") and len(item["sha256"]) == 64 for item in run["output_artifacts"])
    manifest = project_dir / run["manifest_path"]
    assert json.loads(manifest.read_text(encoding="utf-8"))["run_id"] == run["run_id"]
