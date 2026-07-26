from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from html import escape
from pathlib import Path, PurePosixPath
from typing import Any
from uuid import uuid4
from zipfile import ZIP_DEFLATED, ZipFile

from ai4ms.delivery.renderers import (
    build_visual_assets,
    enhance_interactive_html,
    render_docx,
    render_pdf,
    reproduction_readme,
)
from ai4ms.services.stage_generation import StageContentValidationError, StageGenerationService
from research.artifacts import export_visual_html


PUBLIC_ARTIFACT_SUFFIXES = {
    ".csv",
    ".do",
    ".gph",
    ".json",
    ".log",
    ".pdf",
    ".png",
    ".smcl",
    ".ster",
    ".svg",
    ".txt",
    ".xlsx",
}


class DeliveryExportError(RuntimeError):
    pass


class DeliveryExportService:
    def __init__(self, projects_dir: str | Path) -> None:
        self.projects_dir = Path(projects_dir)

    def export(self, project: dict[str, Any]) -> dict[str, Any]:
        delivery = self._stage(project, "delivery")
        if delivery.get("revision", 0) < 1:
            raise DeliveryExportError("S9 尚无可导出的 revision")
        try:
            StageGenerationService.validate_stage_content(project, "delivery", delivery.get("content", {}))
        except StageContentValidationError as exc:
            raise DeliveryExportError(f"S9 交付校验未通过：{exc}") from exc

        project_id = str(project["project_id"])
        project_dir = self.projects_dir / project_id
        export_id = f"export_{uuid4().hex[:12]}"
        export_dir = project_dir / "exports" / export_id
        export_dir.mkdir(parents=True, exist_ok=False)

        report_md = export_dir / "report.md"
        report_html = export_dir / "report.html"
        report_docx = export_dir / "report.docx"
        report_pdf = export_dir / "report.pdf"
        snapshot_path = export_dir / "project_snapshot.json"
        manifest_path = export_dir / "manifest.json"
        stata_package_path = export_dir / "stata_reproduction.zip"
        package_path = export_dir / "research_package.zip"

        visual_assets = build_visual_assets(project, export_dir)
        report_md.write_text(self._render_markdown(project), encoding="utf-8")
        export_visual_html(
            report_md,
            report_html,
            str(delivery.get("content", {}).get("title") or project.get("title", "AI4MS 研究报告")),
            mode_label="AI4MS",
            product_label="AI4MS 管理科学科研工作台",
        )
        enhance_interactive_html(report_html, export_dir, visual_assets)
        render_docx(project, report_docx, export_dir, visual_assets)
        render_pdf(project, report_pdf, visual_assets)
        snapshot_path.write_text(
            json.dumps(project, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )

        run_artifacts = self._public_run_artifacts(project, project_dir)
        self._build_stata_package(
            project,
            export_dir,
            stata_package_path,
            run_artifacts,
        )
        package_files: list[tuple[Path, str, str]] = [
            (report_md, "report/report.md", "generated_report"),
            (report_html, "report/report.html", "visual_report"),
            (report_docx, "report/report.docx", "editable_word_report"),
            (report_pdf, "report/report.pdf", "fixed_pdf_report"),
            (snapshot_path, "project/project_snapshot.json", "project_snapshot"),
            (
                stata_package_path,
                "reproduction/stata_reproduction.zip",
                "stata_reproduction_package",
            ),
        ]
        package_files.extend(self._visual_files(export_dir))
        package_files.extend(run_artifacts)
        generated_at = datetime.now(UTC).isoformat()
        manifest = {
            "schema_version": "ai4ms.research-package.v2",
            "export_id": export_id,
            "project_id": project_id,
            "generated_at": generated_at,
            "source_revisions": {
                stage["key"]: {
                    "revision": stage.get("revision", 0),
                    "content_hash": stage.get("content_hash", ""),
                    "status": stage.get("status", ""),
                }
                for stage in project.get("stages", [])
            },
            "files": [
                {
                    "path": archive_path,
                    "role": role,
                    "bytes": source.stat().st_size,
                    "sha256": self._sha256(source),
                }
                for source, archive_path, role in package_files
            ],
            "data_policy": {
                "raw_data_included": False,
                "excluded_extensions": [".dta"],
                "note": "原始研究数据默认不进入交付包；包内仅包含白名单结果和复现产物。",
            },
        }
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )

        with ZipFile(package_path, "w", compression=ZIP_DEFLATED) as archive:
            for source, archive_path, _role in package_files:
                archive.write(source, archive_path)
            archive.write(manifest_path, "manifest.json")

        relative = export_dir.relative_to(project_dir).as_posix()
        return {
            "export_id": export_id,
            "generated_at": generated_at,
            "source_delivery_revision": delivery.get("revision", 0),
            "source_delivery_hash": delivery.get("content_hash", ""),
            "source_content_fingerprint": self.delivery_fingerprint(delivery.get("content", {})),
            "visual_report_path": f"{relative}/report.html",
            "word_report_path": f"{relative}/report.docx",
            "pdf_report_path": f"{relative}/report.pdf",
            "stata_package_path": f"{relative}/stata_reproduction.zip",
            "research_package_path": f"{relative}/research_package.zip",
            "manifest_path": f"{relative}/manifest.json",
            "file_count": len(manifest["files"]) + 1,
            "word_sha256": self._sha256(report_docx),
            "pdf_sha256": self._sha256(report_pdf),
            "stata_package_sha256": self._sha256(stata_package_path),
            "package_sha256": self._sha256(package_path),
        }

    @staticmethod
    def delivery_fingerprint(content: dict[str, Any]) -> str:
        scientific_content = {
            key: value
            for key, value in content.items()
            if key
            not in {
                "_workspace",
                "exports",
                "visual_report_path",
                "word_report_path",
                "pdf_report_path",
                "stata_package_path",
                "research_package_path",
                "manifest_path",
            }
        }
        payload = json.dumps(scientific_content, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def artifact_path(self, project: dict[str, Any], export_id: str, kind: str) -> Path:
        if kind not in {"report", "word", "pdf", "stata", "package", "manifest"}:
            raise DeliveryExportError(f"不支持的交付产物类型：{kind}")
        delivery = self._stage(project, "delivery").get("content", {})
        export_record = next(
            (
                item
                for item in delivery.get("exports", [])
                if isinstance(item, dict) and item.get("export_id") == export_id
            ),
            None,
        )
        if export_record is None:
            raise DeliveryExportError(f"交付记录不存在：{export_id}")
        field = {
            "report": "visual_report_path",
            "word": "word_report_path",
            "pdf": "pdf_report_path",
            "stata": "stata_package_path",
            "package": "research_package_path",
            "manifest": "manifest_path",
        }[kind]
        relative = str(export_record.get(field, ""))
        project_dir = (self.projects_dir / str(project["project_id"])).resolve()
        path = (project_dir / relative).resolve()
        if not path.is_relative_to(project_dir) or not path.is_file():
            raise DeliveryExportError(f"交付文件不可用：{relative}")
        return path

    @staticmethod
    def _stage(project: dict[str, Any], key: str) -> dict[str, Any]:
        return next((stage for stage in project.get("stages", []) if stage.get("key") == key), {})

    def _public_run_artifacts(
        self,
        project: dict[str, Any],
        project_dir: Path,
    ) -> list[tuple[Path, str, str]]:
        analysis = self._stage(project, "analysis").get("content", {})
        found: list[tuple[Path, str, str]] = []
        seen: set[Path] = set()
        root = project_dir.resolve()
        for run in analysis.get("runs", []):
            if not isinstance(run, dict):
                continue
            candidates: list[Any] = list(run.get("output_artifacts", []))
            if run.get("manifest_path"):
                candidates.append({"path": run["manifest_path"]})
            for item in candidates:
                value = item.get("path") if isinstance(item, dict) else item
                if not value:
                    continue
                relative = PurePosixPath(str(value).replace("\\", "/"))
                if relative.is_absolute() or ".." in relative.parts:
                    continue
                source = (project_dir / Path(*relative.parts)).resolve()
                if (
                    not source.is_relative_to(root)
                    or not source.is_file()
                    or source.suffix.lower() not in PUBLIC_ARTIFACT_SUFFIXES
                    or source in seen
                ):
                    continue
                seen.add(source)
                archive_path = relative.as_posix()
                if not archive_path.startswith("artifacts/"):
                    archive_path = f"artifacts/{archive_path}"
                found.append((source, archive_path, "run_artifact"))
        return found

    @staticmethod
    def _visual_files(export_dir: Path) -> list[tuple[Path, str, str]]:
        found: list[tuple[Path, str, str]] = []
        for folder in ("charts", "diagrams"):
            root = export_dir / folder
            if not root.is_dir():
                continue
            for source in sorted(root.rglob("*")):
                if not source.is_file():
                    continue
                suffix = source.suffix.lower()
                role = (
                    "mermaid_source"
                    if suffix == ".mmd"
                    else "visual_specification"
                    if suffix == ".json"
                    else "visual_asset"
                )
                found.append(
                    (
                        source,
                        source.relative_to(export_dir).as_posix(),
                        role,
                    )
                )
        return found

    def _build_stata_package(
        self,
        project: dict[str, Any],
        export_dir: Path,
        package_path: Path,
        run_artifacts: list[tuple[Path, str, str]],
    ) -> None:
        reproduction_dir = export_dir / "reproduction"
        reproduction_dir.mkdir(parents=True, exist_ok=True)
        stages = {
            str(stage.get("key")): stage
            for stage in project.get("stages", [])
            if isinstance(stage, dict) and stage.get("key")
        }
        analysis = stages.get("analysis", {}).get("content", {})
        identification = stages.get("identification", {}).get("content", {})
        runs = [
            run
            for run in analysis.get("runs", [])
            if isinstance(run, dict)
        ]
        do_file = str(
            analysis.get("do_file")
            or identification.get("stata_do_file")
            or "* 尚无获批 Stata do-file\n"
        )
        (reproduction_dir / "analysis.do").write_text(do_file, encoding="utf-8")
        (reproduction_dir / "README.md").write_text(
            reproduction_readme(project), encoding="utf-8"
        )
        data_assets = [
            {
                key: asset.get(key)
                for key in (
                    "asset_id",
                    "original_name",
                    "media_type",
                    "size_bytes",
                    "sha256",
                    "created_at",
                    "metadata",
                )
            }
            for asset in project.get("data_assets", [])
            if isinstance(asset, dict)
        ]
        (reproduction_dir / "data-assets.json").write_text(
            json.dumps(data_assets, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        runner_profile = next(
            (
                run.get("runner_profile", {})
                for run in reversed(runs)
                if isinstance(run.get("runner_profile"), dict)
            ),
            {},
        )
        (reproduction_dir / "runner-profile.json").write_text(
            json.dumps(runner_profile, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        run_index = [
            {
                key: run.get(key)
                for key in (
                    "run_id",
                    "status",
                    "reason_code",
                    "exit_code",
                    "requested_at",
                    "started_at",
                    "finished_at",
                    "duration_seconds",
                    "analysis_plan_revision",
                    "analysis_plan_hash",
                    "do_file_sha256",
                    "input_asset_id",
                    "data_signature",
                    "manifest_path",
                )
            }
            for run in runs
        ]
        (reproduction_dir / "run-index.json").write_text(
            json.dumps(run_index, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )

        files: list[tuple[Path, str, str]] = [
            (reproduction_dir / "README.md", "README.md", "instructions"),
            (reproduction_dir / "analysis.do", "analysis.do", "approved_do_file"),
            (
                reproduction_dir / "data-assets.json",
                "data-assets.json",
                "input_metadata",
            ),
            (
                reproduction_dir / "runner-profile.json",
                "runner-profile.json",
                "runner_environment",
            ),
            (reproduction_dir / "run-index.json", "run-index.json", "run_index"),
        ]
        for source, archive_path, _role in run_artifacts:
            normalized = archive_path
            if normalized.startswith("artifacts/"):
                normalized = normalized[len("artifacts/") :]
            files.append((source, normalized, "run_artifact"))

        manifest = {
            "schema_version": "ai4ms.stata-reproduction.v1",
            "project_id": project["project_id"],
            "raw_data_included": False,
            "required_input_hashes": [
                {
                    "asset_id": item.get("asset_id", ""),
                    "filename": item.get("original_name", ""),
                    "sha256": item.get("sha256", ""),
                }
                for item in data_assets
            ],
            "files": [
                {
                    "path": archive_path,
                    "role": role,
                    "bytes": source.stat().st_size,
                    "sha256": self._sha256(source),
                }
                for source, archive_path, role in files
            ],
        }
        reproduction_manifest = reproduction_dir / "manifest.json"
        reproduction_manifest.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        with ZipFile(package_path, "w", compression=ZIP_DEFLATED) as archive:
            for source, archive_path, _role in files:
                archive.write(source, archive_path)
            archive.write(reproduction_manifest, "manifest.json")

    def _render_markdown(self, project: dict[str, Any]) -> str:
        stages = {stage["key"]: stage for stage in project.get("stages", [])}
        delivery = stages.get("delivery", {}).get("content", {})
        evidence = stages.get("evidence", {}).get("content", {})
        robustness = stages.get("robustness", {}).get("content", {})
        analysis = stages.get("analysis", {}).get("content", {})
        conclusions = delivery.get("conclusions", [])
        claims = evidence.get("claims", [])

        lines = [
            f"# {self._md(delivery.get('title') or project.get('title', 'AI4MS 研究报告'))}",
            "",
            "## 执行摘要",
            "",
            self._md(delivery.get("executive_summary", "")),
            "",
            "## 研究流程与审批状态",
            "",
            self._table_marker(
                ["阶段", "资产", "状态", "Revision", "内容哈希"],
                [
                    [
                        stage.get("code", ""),
                        stage.get("title", ""),
                        stage.get("status", ""),
                        stage.get("revision", 0),
                        str(stage.get("content_hash", ""))[:12],
                    ]
                    for stage in project.get("stages", [])
                ],
            ),
            "",
            "## 核心结论",
            "",
            self._table_marker(
                ["结论 ID", "结论", "状态", "主张 ID", "证据 ID", "适用边界"],
                [
                    [
                        item.get("conclusion_id", ""),
                        item.get("statement", ""),
                        item.get("status", ""),
                        ", ".join(item.get("claim_ids", [])),
                        ", ".join(item.get("evidence_ids", [])),
                        item.get("scope_note", ""),
                    ]
                    for item in conclusions
                    if isinstance(item, dict)
                ],
            ),
            "",
            "## Claim-Evidence 可追溯矩阵",
            "",
            self._table_marker(
                ["主张 ID", "主张", "类型", "状态", "置信度", "证据", "稳健性检查"],
                [
                    [
                        claim.get("claim_id", ""),
                        claim.get("claim_text", ""),
                        claim.get("claim_type", ""),
                        claim.get("status", ""),
                        claim.get("confidence", ""),
                        "; ".join(
                            f"{item.get('evidence_id', '')}:{item.get('direction', '')}/{item.get('strength', '')}@{item.get('artifact_id', '')}"
                            for item in claim.get("evidence", [])
                            if isinstance(item, dict)
                        ),
                        ", ".join(claim.get("robustness_check_ids", [])),
                    ]
                    for claim in claims
                    if isinstance(claim, dict)
                ],
            ),
            "",
            "## 机制、异质性与反证",
            "",
        ]
        for mechanism in evidence.get("mechanisms", []):
            if isinstance(mechanism, dict):
                lines.append(
                    f"- **{self._md(mechanism.get('mechanism_id', ''))}** "
                    f"{self._md(mechanism.get('statement', ''))}（{self._md(mechanism.get('status', ''))}）"
                )
        for item in evidence.get("heterogeneity", []):
            if isinstance(item, dict):
                lines.append(
                    f"- **{self._md(item.get('dimension', ''))}**：{self._md(item.get('finding', ''))}"
                )
        lines.extend(
            [
                "",
                "## 稳健性与运行记录",
                "",
                self._table_marker(
                    ["检查 ID", "类别", "状态", "结果摘要", "解释影响"],
                    [
                        [
                            item.get("check_id", ""),
                            item.get("category", ""),
                            item.get("status", ""),
                            item.get("result_summary", ""),
                            item.get("implication", ""),
                        ]
                        for item in robustness.get("robustness_matrix", [])
                        if isinstance(item, dict)
                    ],
                ),
                "",
                self._table_marker(
                    ["Run ID", "状态", "原因", "退出码", "do-file SHA-256"],
                    [
                        [
                            run.get("run_id", ""),
                            run.get("status", ""),
                            run.get("reason_code", ""),
                            run.get("exit_code", ""),
                            str(run.get("do_file_sha256", ""))[:16],
                        ]
                        for run in analysis.get("runs", [])
                        if isinstance(run, dict)
                    ],
                ),
                "",
                "## 政策与管理含义",
                "",
            ]
        )
        for item in delivery.get("policy_implications", []):
            if isinstance(item, dict):
                lines.append(
                    f"- **{self._md(item.get('audience', ''))}**：{self._md(item.get('statement', ''))} "
                    f"风险：{self._md(item.get('risk_note', ''))}"
                )
        lines.extend(["", "## 局限与披露", ""])
        for limitation in delivery.get("limitations", []):
            lines.append(f"- {self._md(limitation)}")
        lines.extend(["", self._md(delivery.get("disclosure", "")), "", "## 参考文献", ""])
        for paper in delivery.get("references", []):
            if isinstance(paper, dict):
                authors = ", ".join(str(value) for value in paper.get("authors", []))
                lines.append(
                    f"- [{self._md(paper.get('paper_id', ''))}] {self._md(authors)}. "
                    f"{self._md(paper.get('title', ''))}. {self._md(paper.get('year', ''))}. "
                    f"DOI: {self._md(paper.get('doi', ''))}"
                )
        lines.extend(
            [
                "",
                "## 可复现性说明",
                "",
                *[f"- {self._md(item)}" for item in delivery.get("reproducibility_notes", [])],
                "",
                f"S8 revision `{stages.get('evidence', {}).get('revision', 0)}` · "
                f"S9 revision `{stages.get('delivery', {}).get('revision', 0)}`",
            ]
        )
        return "\n".join(lines).strip() + "\n"

    @staticmethod
    def _table_marker(headers: list[str], rows: list[list[Any]]) -> str:
        payload = json.dumps({"headers": headers, "rows": rows}, ensure_ascii=False, separators=(",", ":"))
        return f"![table](data:{payload})"

    @staticmethod
    def _md(value: Any) -> str:
        return escape(str(value or ""), quote=False).replace("\r", " ").replace("\n", " ")

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
