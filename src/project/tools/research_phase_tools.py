from __future__ import annotations

import json
from datetime import datetime, timezone
from hashlib import sha1
from pathlib import Path
from typing import Any, Dict

from pydantic import Field

from base.agent.base_action import BaseAction


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            rows.append(value)
    return rows


def _append_jsonl_dedup(path: Path, row: dict[str, Any], key_fields: list[str]) -> tuple[bool, str]:
    raw = "|".join(str(row.get(field, "")).strip() for field in key_fields)
    if not raw.strip("|"):
        raw = json.dumps(row, ensure_ascii=False, sort_keys=True)
    key = str(row.get("dedup_key") or sha1(raw.encode("utf-8")).hexdigest()[:16])
    row["dedup_key"] = key

    for existing in _read_jsonl(path):
        if str(existing.get("dedup_key", "")).strip() == key:
            return False, key

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    return True, key


def _filter_rows(rows: list[dict[str, Any]], query: str, limit: int) -> list[dict[str, Any]]:
    q = str(query or "").strip().lower()
    max_rows = max(1, int(limit or 20))
    filtered: list[dict[str, Any]] = []
    for row in rows:
        if q and q not in json.dumps(row, ensure_ascii=False).lower():
            continue
        filtered.append(row)
        if len(filtered) >= max_rows:
            break
    return filtered


def _read_text_artifact(path: Path, limit_chars: int) -> dict[str, Any]:
    if not path.exists():
        return {
            "path": str(path),
            "exists": False,
            "chars": 0,
            "content": "",
        }
    text = path.read_text(encoding="utf-8")
    max_chars = max(0, int(limit_chars or 12000))
    content = text[:max_chars]
    truncated = len(text) > len(content)
    return {
        "path": str(path),
        "exists": True,
        "chars": len(text),
        "truncated": truncated,
        "content": content,
    }


class RecordPaperTool(BaseAction):
    name: str = "record_paper"
    description: str = "Record a verified literature item into papers.jsonl for downstream synthesis and citation planning."
    parameters: Dict[str, Any] = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "authors": {"type": "array", "items": {"type": "string"}},
                "year": {"type": "string"},
                "venue": {"type": "string"},
                "source_url": {"type": "string"},
                "doi": {"type": "string"},
                "abstract": {"type": "string"},
                "relevance": {"type": "string"},
                "evidence_quality": {"type": "string", "enum": ["high", "medium", "low", "uncertain"]},
                "tags": {"type": "array", "items": {"type": "string"}},
                "dedup_key": {"type": "string"},
            },
            "required": ["title"],
            "additionalProperties": False,
        }
    )
    papers_path: Path = Field(default=Path("papers.jsonl"), exclude=True)

    class Config:
        arbitrary_types_allowed = True

    async def __call__(
        self,
        title: str,
        authors: list[str] | None = None,
        year: str = "",
        venue: str = "",
        source_url: str = "",
        doi: str = "",
        abstract: str = "",
        relevance: str = "",
        evidence_quality: str = "medium",
        tags: list[str] | None = None,
        dedup_key: str = "",
    ) -> Dict[str, Any]:
        quality = str(evidence_quality or "medium").lower().strip()
        if quality not in {"high", "medium", "low", "uncertain"}:
            return {"success": False, "message": "evidence_quality must be high|medium|low|uncertain"}
        record = {
            "title": str(title).strip(),
            "authors": [str(item) for item in (authors or [])],
            "year": str(year).strip(),
            "venue": str(venue).strip(),
            "source_url": str(source_url).strip(),
            "doi": str(doi).strip(),
            "abstract": str(abstract).strip(),
            "relevance": str(relevance).strip(),
            "evidence_quality": quality,
            "tags": [str(item) for item in (tags or [])],
            "dedup_key": str(dedup_key).strip(),
            "recorded_at": _now(),
        }
        if not record["title"]:
            return {"success": False, "message": "title must not be empty"}
        added, key = _append_jsonl_dedup(self.papers_path, record, ["source_url", "doi", "title", "year"])
        verb = "Recorded" if added else "Skipped duplicate"
        return {"success": True, "output": f"{verb} paper {key} in {self.papers_path}"}


class ReadPapersTool(BaseAction):
    name: str = "read_papers"
    description: str = "Read verified literature records from papers.jsonl for synthesis, outlining, and drafting."
    parameters: Dict[str, Any] = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer", "default": 20},
            },
            "additionalProperties": False,
        }
    )
    papers_path: Path = Field(default=Path("papers.jsonl"), exclude=True)

    class Config:
        arbitrary_types_allowed = True

    async def __call__(self, query: str = "", limit: int = 20) -> Dict[str, Any]:
        rows = _filter_rows(_read_jsonl(self.papers_path), query, limit)
        return {"success": True, "output": _json_dumps({"path": str(self.papers_path), "count": len(rows), "papers": rows})}


class RecordPaperNoteTool(BaseAction):
    name: str = "record_paper_note"
    description: str = "Record a lightweight structured reading note for one paper into paper_notes.jsonl."
    parameters: Dict[str, Any] = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "citation_key": {"type": "string"},
                "source_url": {"type": "string"},
                "doi": {"type": "string"},
                "problem": {"type": "string"},
                "method": {"type": "string"},
                "scenario": {"type": "string"},
                "main_findings": {"type": "string"},
                "limitations": {"type": "string"},
                "relevance_to_topic": {"type": "string"},
                "evidence_source": {"type": "string", "enum": ["abstract", "web", "pdf", "metadata", "uncertain"]},
                "dedup_key": {"type": "string"},
            },
            "required": ["title"],
            "additionalProperties": False,
        }
    )
    paper_notes_path: Path = Field(default=Path("paper_notes.jsonl"), exclude=True)

    class Config:
        arbitrary_types_allowed = True

    async def __call__(
        self,
        title: str,
        citation_key: str = "",
        source_url: str = "",
        doi: str = "",
        problem: str = "",
        method: str = "",
        scenario: str = "",
        main_findings: str = "",
        limitations: str = "",
        relevance_to_topic: str = "",
        evidence_source: str = "abstract",
        dedup_key: str = "",
    ) -> Dict[str, Any]:
        source = str(evidence_source or "abstract").lower().strip()
        if source not in {"abstract", "web", "pdf", "metadata", "uncertain"}:
            return {"success": False, "message": "evidence_source must be abstract|web|pdf|metadata|uncertain"}
        record = {
            "title": str(title).strip(),
            "citation_key": str(citation_key).strip(),
            "source_url": str(source_url).strip(),
            "doi": str(doi).strip(),
            "problem": str(problem).strip(),
            "method": str(method).strip(),
            "scenario": str(scenario).strip(),
            "main_findings": str(main_findings).strip(),
            "limitations": str(limitations).strip(),
            "relevance_to_topic": str(relevance_to_topic).strip(),
            "evidence_source": source,
            "dedup_key": str(dedup_key).strip(),
            "recorded_at": _now(),
        }
        if not record["title"]:
            return {"success": False, "message": "title must not be empty"}
        added, key = _append_jsonl_dedup(self.paper_notes_path, record, ["source_url", "doi", "title"])
        verb = "Recorded" if added else "Skipped duplicate"
        return {"success": True, "output": f"{verb} paper note {key} in {self.paper_notes_path}"}


class ReadPaperNotesTool(BaseAction):
    name: str = "read_paper_notes"
    description: str = "Read lightweight structured paper notes from paper_notes.jsonl for synthesis, outlining, and drafting."
    parameters: Dict[str, Any] = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer", "default": 30},
            },
            "additionalProperties": False,
        }
    )
    paper_notes_path: Path = Field(default=Path("paper_notes.jsonl"), exclude=True)

    class Config:
        arbitrary_types_allowed = True

    async def __call__(self, query: str = "", limit: int = 30) -> Dict[str, Any]:
        rows = _filter_rows(_read_jsonl(self.paper_notes_path), query, limit)
        return {"success": True, "output": _json_dumps({"path": str(self.paper_notes_path), "count": len(rows), "paper_notes": rows})}


class SynthesizeFindingsTool(BaseAction):
    name: str = "synthesize_findings"
    description: str = "Persist a research synthesis: themes, consensus, disagreements, gaps, and evidence-quality notes."
    parameters: Dict[str, Any] = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "themes": {"type": "array", "items": {"type": "string"}},
                "consensus": {"type": "array", "items": {"type": "string"}},
                "disagreements": {"type": "array", "items": {"type": "string"}},
                "gaps": {"type": "array", "items": {"type": "string"}},
                "evidence_quality": {"type": "array", "items": {"type": "string"}},
                "note_title": {"type": "string", "default": "Knowledge Synthesis"},
            },
            "required": ["themes"],
            "additionalProperties": False,
        }
    )
    scratchpad_path: Path = Field(default=Path("scratchpad/shared.md"), exclude=True)

    class Config:
        arbitrary_types_allowed = True

    async def __call__(
        self,
        themes: list[str],
        consensus: list[str] | None = None,
        disagreements: list[str] | None = None,
        gaps: list[str] | None = None,
        evidence_quality: list[str] | None = None,
        note_title: str = "Knowledge Synthesis",
    ) -> Dict[str, Any]:
        if not themes:
            return {"success": False, "message": "themes must not be empty"}
        title = str(note_title or "Knowledge Synthesis").strip()
        payload = {
            "themes": [str(item) for item in themes],
            "consensus": [str(item) for item in (consensus or [])],
            "disagreements": [str(item) for item in (disagreements or [])],
            "gaps": [str(item) for item in (gaps or [])],
            "evidence_quality": [str(item) for item in (evidence_quality or [])],
            "updated_at": _now(),
        }
        self.scratchpad_path.parent.mkdir(parents=True, exist_ok=True)
        existing = self.scratchpad_path.read_text(encoding="utf-8").strip() if self.scratchpad_path.exists() else "# Shared Scratchpad"
        block = f"## {title}\n\n```json\n{_json_dumps(payload)}\n```\n"
        self.scratchpad_path.write_text(f"{existing.rstrip()}\n\n{block}", encoding="utf-8")
        return {"success": True, "output": f"Synthesis note '{title}' written to {self.scratchpad_path}"}


class RecordResearchClaimTool(BaseAction):
    name: str = "record_research_claim"
    description: str = "Record a candidate literature-review claim, research gap, future direction, or testable question into claims.jsonl."
    parameters: Dict[str, Any] = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "claim": {"type": "string"},
                "claim_type": {"type": "string", "enum": ["claim", "gap", "future_direction", "research_question", "limitation"]},
                "evidence_basis": {"type": "string"},
                "source_urls": {"type": "array", "items": {"type": "string"}},
                "uncertainty": {"type": "string"},
                "priority": {"type": "string", "enum": ["high", "medium", "low"]},
                "validation_path": {"type": "string"},
                "dedup_key": {"type": "string"},
            },
            "required": ["claim"],
            "additionalProperties": False,
        }
    )
    claims_path: Path = Field(default=Path("claims.jsonl"), exclude=True)

    class Config:
        arbitrary_types_allowed = True

    async def __call__(
        self,
        claim: str,
        claim_type: str = "claim",
        evidence_basis: str = "",
        source_urls: list[str] | None = None,
        uncertainty: str = "",
        priority: str = "medium",
        validation_path: str = "",
        dedup_key: str = "",
    ) -> Dict[str, Any]:
        ctype = str(claim_type or "claim").strip()
        if ctype not in {"claim", "gap", "future_direction", "research_question", "limitation"}:
            return {"success": False, "message": "claim_type is invalid"}
        prio = str(priority or "medium").lower().strip()
        if prio not in {"high", "medium", "low"}:
            return {"success": False, "message": "priority must be high|medium|low"}
        record = {
            "claim": str(claim).strip(),
            "claim_type": ctype,
            "evidence_basis": str(evidence_basis).strip(),
            "source_urls": [str(item).strip() for item in (source_urls or []) if str(item).strip()],
            "uncertainty": str(uncertainty).strip(),
            "priority": prio,
            "validation_path": str(validation_path).strip(),
            "dedup_key": str(dedup_key).strip(),
            "recorded_at": _now(),
        }
        if not record["claim"]:
            return {"success": False, "message": "claim must not be empty"}
        added, key = _append_jsonl_dedup(self.claims_path, record, ["claim", "claim_type"])
        verb = "Recorded" if added else "Skipped duplicate"
        return {"success": True, "output": f"{verb} research claim {key} in {self.claims_path}"}


class ReadResearchClaimsTool(BaseAction):
    name: str = "read_research_claims"
    description: str = "Read candidate claims, gaps, future directions, and research questions from claims.jsonl."
    parameters: Dict[str, Any] = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer", "default": 20},
            },
            "additionalProperties": False,
        }
    )
    claims_path: Path = Field(default=Path("claims.jsonl"), exclude=True)

    class Config:
        arbitrary_types_allowed = True

    async def __call__(self, query: str = "", limit: int = 20) -> Dict[str, Any]:
        rows = _filter_rows(_read_jsonl(self.claims_path), query, limit)
        return {"success": True, "output": _json_dumps({"path": str(self.claims_path), "count": len(rows), "claims": rows})}


class ReadClaimDebateLogTool(BaseAction):
    name: str = "read_claim_debate_log"
    description: str = "Read debate_log.md, the structured claim debate and prioritization artifact."
    parameters: Dict[str, Any] = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "limit_chars": {"type": "integer", "default": 12000},
            },
            "additionalProperties": False,
        }
    )
    debate_log_path: Path = Field(default=Path("debate_log.md"), exclude=True)

    class Config:
        arbitrary_types_allowed = True

    async def __call__(self, limit_chars: int = 12000) -> Dict[str, Any]:
        return {"success": True, "output": _json_dumps(_read_text_artifact(self.debate_log_path, limit_chars))}


class RecordClaimDebateTool(BaseAction):
    name: str = "record_claim_debate"
    description: str = "Write a structured claim-debate decision record to debate_log.md."
    parameters: Dict[str, Any] = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "claim": {"type": "string"},
                "decision": {"type": "string", "enum": ["keep", "revise", "downgrade", "remove"]},
                "rationale": {"type": "string"},
                "evidence_issues": {"type": "array", "items": {"type": "string"}},
                "revision": {"type": "string"},
                "priority": {"type": "string", "enum": ["high", "medium", "low"]},
            },
            "required": ["claim", "decision", "rationale"],
            "additionalProperties": False,
        }
    )
    debate_log_path: Path = Field(default=Path("debate_log.md"), exclude=True)

    class Config:
        arbitrary_types_allowed = True

    async def __call__(
        self,
        claim: str,
        decision: str,
        rationale: str,
        evidence_issues: list[str] | None = None,
        revision: str = "",
        priority: str = "medium",
    ) -> Dict[str, Any]:
        decision = str(decision or "").strip()
        if decision not in {"keep", "revise", "downgrade", "remove"}:
            return {"success": False, "message": "decision must be keep|revise|downgrade|remove"}
        priority = str(priority or "medium").lower().strip()
        if priority not in {"high", "medium", "low"}:
            return {"success": False, "message": "priority must be high|medium|low"}
        self.debate_log_path.parent.mkdir(parents=True, exist_ok=True)
        existing = self.debate_log_path.read_text(encoding="utf-8").strip() if self.debate_log_path.exists() else "# Claim Debate Log"
        block = [
            f"## {str(claim).strip()[:120] or 'Untitled Claim'}",
            "",
            f"- Decision: {decision}",
            f"- Priority: {priority}",
            f"- Rationale: {str(rationale).strip()}",
        ]
        for issue in evidence_issues or []:
            block.append(f"- Evidence issue: {str(issue).strip()}")
        if str(revision).strip():
            block.append(f"- Revision: {str(revision).strip()}")
        block.append(f"- Recorded at: {_now()}")
        self.debate_log_path.write_text(existing.rstrip() + "\n\n" + "\n".join(block) + "\n", encoding="utf-8")
        return {"success": True, "output": f"Debate record written to {self.debate_log_path}"}


class BuildResearchOutlineTool(BaseAction):
    name: str = "build_research_outline"
    description: str = "Write a structured research outline and claim-evidence map to outline.md."
    parameters: Dict[str, Any] = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "sections": {"type": "array", "items": {"type": "string"}},
                "claim_evidence_map": {"type": "array", "items": {"type": "string"}},
                "missing_material": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["sections"],
            "additionalProperties": False,
        }
    )
    outline_path: Path = Field(default=Path("outline.md"), exclude=True)

    class Config:
        arbitrary_types_allowed = True

    async def __call__(
        self,
        sections: list[str],
        title: str = "Research Outline",
        claim_evidence_map: list[str] | None = None,
        missing_material: list[str] | None = None,
    ) -> Dict[str, Any]:
        if not sections:
            return {"success": False, "message": "sections must not be empty"}
        lines = [f"# {str(title or 'Research Outline').strip()}", "", "## Sections", ""]
        lines.extend(f"- {str(item).strip()}" for item in sections if str(item).strip())
        lines.extend(["", "## Claim-Evidence Map", ""])
        lines.extend(f"- {str(item).strip()}" for item in (claim_evidence_map or []) if str(item).strip())
        lines.extend(["", "## Missing Material", ""])
        lines.extend(f"- {str(item).strip()}" for item in (missing_material or []) if str(item).strip())
        self.outline_path.parent.mkdir(parents=True, exist_ok=True)
        self.outline_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
        return {"success": True, "output": f"Research outline written to {self.outline_path}"}


class ReadResearchOutlineTool(BaseAction):
    name: str = "read_research_outline"
    description: str = "Read outline.md, the structured research outline and claim-evidence map."
    parameters: Dict[str, Any] = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "limit_chars": {"type": "integer", "default": 12000},
            },
            "additionalProperties": False,
        }
    )
    outline_path: Path = Field(default=Path("outline.md"), exclude=True)

    class Config:
        arbitrary_types_allowed = True

    async def __call__(self, limit_chars: int = 12000) -> Dict[str, Any]:
        return {"success": True, "output": _json_dumps(_read_text_artifact(self.outline_path, limit_chars))}


class ReadResearchReportTool(BaseAction):
    name: str = "read_research_report"
    description: str = "Read the canonical markdown research_report.md for drafting continuation or final review."
    parameters: Dict[str, Any] = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "limit_chars": {"type": "integer", "default": 20000},
            },
            "additionalProperties": False,
        }
    )
    report_path: Path = Field(default=Path("research_report.md"), exclude=True)

    class Config:
        arbitrary_types_allowed = True

    async def __call__(self, limit_chars: int = 20000) -> Dict[str, Any]:
        return {"success": True, "output": _json_dumps(_read_text_artifact(self.report_path, limit_chars))}


class ReviewResearchReportTool(BaseAction):
    name: str = "review_research_report"
    description: str = "Review research report completeness, evidence coverage, claims, and citation risks; writes review_report.md."
    parameters: Dict[str, Any] = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "required_sections": {"type": "array", "items": {"type": "string"}},
                "major_issues": {"type": "array", "items": {"type": "string"}},
                "recommendation": {"type": "string", "enum": ["accept", "revise", "blocked"]},
            },
            "additionalProperties": False,
        }
    )
    report_path: Path = Field(default=Path("research_report.md"), exclude=True)
    findings_path: Path = Field(default=Path("findings.jsonl"), exclude=True)
    claims_path: Path = Field(default=Path("claims.jsonl"), exclude=True)
    review_path: Path = Field(default=Path("review_report.md"), exclude=True)

    class Config:
        arbitrary_types_allowed = True

    async def __call__(
        self,
        required_sections: list[str] | None = None,
        major_issues: list[str] | None = None,
        recommendation: str = "revise",
    ) -> Dict[str, Any]:
        recommendation = str(recommendation or "revise").lower().strip()
        if recommendation not in {"accept", "revise", "blocked"}:
            return {"success": False, "message": "recommendation must be accept|revise|blocked"}
        report_text = self.report_path.read_text(encoding="utf-8") if self.report_path.exists() else ""
        findings = _read_jsonl(self.findings_path)
        claims = _read_jsonl(self.claims_path)
        missing = [title for title in (required_sections or []) if f"## {title}" not in report_text]
        uncited_claims = [
            row.get("claim", "")
            for row in claims
            if not row.get("source_urls") and not str(row.get("evidence_basis", "")).strip()
        ]
        issues = [str(item) for item in (major_issues or [])]
        if not report_text.strip():
            issues.append("report is missing or empty")
        if missing:
            issues.append(f"missing sections: {missing}")
        if uncited_claims:
            issues.append(f"claims without evidence basis: {uncited_claims[:5]}")
        if not findings:
            issues.append("no structured findings found")

        lines = [
            "# Multi-Agent Review",
            "",
            f"- Recommendation: {recommendation}",
            f"- Report chars: {len(report_text)}",
            f"- Findings: {len(findings)}",
            f"- Claims: {len(claims)}",
            f"- Reviewed at: {_now()}",
            "",
            "## Issues",
            "",
        ]
        lines.extend(f"- {issue}" for issue in issues) if issues else lines.append("- No blocking issues recorded.")
        self.review_path.parent.mkdir(parents=True, exist_ok=True)
        self.review_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
        return {
            "success": True,
            "output": _json_dumps(
                {
                    "passed": not issues and recommendation == "accept",
                    "recommendation": recommendation,
                    "issues": issues,
                    "review_path": str(self.review_path),
                }
            ),
        }
