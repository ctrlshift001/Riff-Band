from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from pydantic import Field

from base.agent.base_action import BaseAction


class CompleteTaskTool(BaseAction):
    """Finalize the orchestration with quality checks before completion."""

    name: str = "complete_task"
    description: str = "Finish the overall task only when the report passes quality checks"
    parameters: Dict[str, Any] = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "executive_summary": {"type": "string", "description": "Short final summary"},
                "report_path": {"type": "string", "description": "Path to the generated report"},
                "confidence": {"type": "string", "description": "high | medium | low"},
                "findings_path": {"type": "string", "description": "Optional findings jsonl path"},
                "required_sections": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Required markdown section titles",
                },
                "min_findings": {"type": "integer", "description": "Minimum finding records required"},
            },
            "required": ["executive_summary", "report_path", "confidence"],
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
        report_path: str,
        confidence: str,
        findings_path: str = "",
        required_sections: List[str] | None = None,
        min_findings: int = 5,
    ) -> Dict[str, Any]:
        issues: List[str] = []
        confidence = str(confidence).lower().strip()
        if confidence not in {"high", "medium", "low"}:
            issues.append("confidence must be one of high|medium|low")

        report_file = Path(report_path)
        if not report_file.exists():
            issues.append(f"report file not found: {report_path}")
            return {
                "success": False,
                "done": False,
                "issues": issues,
                "quality_gate_passed": False,
            }

        text = report_file.read_text(encoding="utf-8").strip()
        if not text:
            issues.append("report file is empty")
        if self._count_headings(text) < 3:
            issues.append("report contains fewer than 3 level-2 sections")

        required = [item.strip() for item in (required_sections or []) if str(item).strip()]
        if required:
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

        if "http://" not in text and "https://" not in text:
            issues.append("report does not contain explicit source links")

        passed = not issues
        return {
            "success": passed,
            "done": passed,
            "executive_summary": executive_summary,
            "report_path": report_path,
            "confidence": confidence,
            "findings_path": findings_path,
            "findings_count": len(findings_rows),
            "quality_gate_passed": passed,
            "issues": issues,
        }
