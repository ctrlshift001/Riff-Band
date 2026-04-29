from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from pydantic import Field

from base.agent.base_action import BaseAction


class CompleteTaskTool(BaseAction):
    """Finalize the orchestration with optional artifact-specific quality checks."""

    name: str = "complete_task"
    description: str = "验证交付物并说明剩余问题后，结束整体任务。"
    parameters: Dict[str, Any] = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "executive_summary": {"type": "string", "description": "简短最终总结"},
                "status": {"type": "string", "description": "done | partial | blocked"},
                "report_path": {"type": "string", "description": "生成报告路径"},
                "confidence": {"type": "string", "description": "high | medium | low"},
                "artifacts": {
                    "type": "array",
                    "items": {"type": "object"},
                    "description": "Delivered artifacts such as files, reports, data, or notes",
                },
                "verification": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "完成前执行过的检查",
                },
                "open_issues": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "partial 或 blocked 状态下的已知剩余问题",
                },
                "findings_path": {"type": "string", "description": "可选 findings jsonl 路径"},
                "required_sections": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Required markdown section titles",
                },
                "min_findings": {"type": "integer", "description": "Minimum finding records required"},
            },
            "required": ["executive_summary", "confidence"],
            "additionalProperties": False,
        }
    )

    @staticmethod
    def _count_headings(text: str) -> int:
        return sum(1 for line in text.splitlines() if line.strip().startswith("## "))

    @staticmethod
    def _read_findings(path: Path) -> List[Dict[str, Any]]:
        if not path.exists():
            return []
        rows: List[Dict[str, Any]] = []
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    item = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(item, dict):
                    rows.append(item)
        return rows

    async def __call__(
        self,
        executive_summary: str,
        confidence: str,
        status: str = "done",
        report_path: str = "",
        artifacts: List[Dict[str, Any]] | None = None,
        verification: List[str] | None = None,
        open_issues: List[str] | None = None,
        findings_path: str = "",
        required_sections: List[str] | None = None,
        min_findings: int = 5,
    ) -> Dict[str, Any]:
        issues: List[str] = []
        artifacts = list(artifacts or [])
        verification = [str(item).strip() for item in (verification or []) if str(item).strip()]
        open_issues = [str(item).strip() for item in (open_issues or []) if str(item).strip()]
        status = str(status or "done").lower().strip()
        if status not in {"done", "partial", "blocked"}:
            issues.append("status must be one of done|partial|blocked")
        confidence = str(confidence).lower().strip()
        if confidence not in {"high", "medium", "low"}:
            issues.append("confidence must be one of high|medium|low")

        text = ""
        if report_path:
            report_file = Path(report_path)
            if not report_file.exists():
                issues.append(f"report file not found: {report_path}")
            else:
                text = report_file.read_text(encoding="utf-8").strip()
                if not text:
                    issues.append("report file is empty")
                if self._count_headings(text) < 3:
                    issues.append("report contains fewer than 3 level-2 sections")
                if "http://" not in text and "https://" not in text:
                    issues.append("report does not contain explicit source links")

        required = [item.strip() for item in (required_sections or []) if str(item).strip()]
        if required and report_path and text:
            missing = [title for title in required if f"## {title}" not in text]
            if missing:
                issues.append(f"missing required sections: {missing}")

        if not executive_summary.strip():
            issues.append("executive_summary cannot be empty")

        findings_rows: List[Dict[str, Any]] = []
        path_for_findings = findings_path.strip()
        if path_for_findings:
            findings_file = Path(path_for_findings)
            findings_rows = self._read_findings(findings_file)
            if len(findings_rows) < int(min_findings):
                issues.append(f"findings count is {len(findings_rows)} < min_findings {int(min_findings)}")

            evidence_coverage = 0
            for row in findings_rows:
                has_source = bool(str(row.get("source_url", "")).strip()) or bool(str(row.get("evidence", "")).strip())
                if has_source:
                    evidence_coverage += 1
            if findings_rows and evidence_coverage < max(1, int(len(findings_rows) * 0.8)):
                issues.append("less than 80% findings include source_url or evidence")

        if status == "done" and open_issues:
            issues.append("status is done but open_issues is not empty")

        passed = not issues and status == "done"
        return {
            "success": passed,
            "done": passed,
            "status": status,
            "executive_summary": executive_summary,
            "report_path": report_path,
            "confidence": confidence,
            "artifacts": artifacts,
            "verification": verification,
            "open_issues": open_issues,
            "findings_path": findings_path,
            "findings_count": len(findings_rows),
            "quality_gate_passed": passed,
            "issues": issues,
        }
