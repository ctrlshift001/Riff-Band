from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from pydantic import Field

from base.agent.base_action import BaseAction


class WriteReportSectionTool(BaseAction):
    name: str = "write_report_section"
    description: str = "Write or replace one markdown report section."
    parameters: Dict[str, Any] = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "section_title": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["section_title", "content"],
        }
    )
    report_path: Path = Field(default=Path("report.md"), exclude=True)

    class Config:
        arbitrary_types_allowed = True

    @staticmethod
    def _default_report_header() -> str:
        return "# Greater Bay Area Industry Analysis Report\n"

    async def __call__(self, section_title: str, content: str) -> Dict[str, Any]:
        self.report_path.parent.mkdir(parents=True, exist_ok=True)
        header = f"## {section_title}"
        existing = (
            self.report_path.read_text(encoding="utf-8")
            if self.report_path.exists()
            else self._default_report_header()
        )
        if header in existing:
            before, _, rest = existing.partition(header)
            next_idx = rest.find("\n## ", len(header))
            remainder = rest[next_idx:] if next_idx >= 0 else ""
            updated = f"{before}{header}\n\n{content.strip()}\n{remainder}"
        else:
            updated = f"{existing.rstrip()}\n\n{header}\n\n{content.strip()}\n"
        self.report_path.write_text(updated.rstrip() + "\n", encoding="utf-8")
        return {"success": True, "output": f"Updated section '{section_title}'."}
