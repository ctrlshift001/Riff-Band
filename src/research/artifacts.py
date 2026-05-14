from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any

from research.schema import ResearchArtifact, ResearchRequest


def _slugify(text: str, max_len: int = 48) -> str:
    raw = re.sub(r"[^\w\u4e00-\u9fff]+", "-", str(text).lower()).strip("-")
    raw = re.sub(r"-{2,}", "-", raw)
    return (raw[:max_len].strip("-") or "research")


@dataclass(frozen=True)
class ResearchArtifacts:
    """Filesystem layout for one research-mode run."""

    run_dir: Path
    report_md: Path
    paper_tex: Path
    references_bib: Path
    report_html: Path
    findings: Path
    papers: Path
    paper_notes: Path
    claims: Path
    debate_log: Path
    outline: Path
    review: Path
    scratchpad: Path
    manifest: Path

    @classmethod
    def create(cls, workspace_dir: Path, request: ResearchRequest) -> "ResearchArtifacts":
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        slug = _slugify(request.topic)
        run_dir = workspace_dir / "output" / f"research_{stamp}_{slug}"
        artifacts = cls(
            run_dir=run_dir,
            report_md=run_dir / "research_report.md",
            paper_tex=run_dir / "paper.tex",
            references_bib=run_dir / "references.bib",
            report_html=run_dir / "report.html",
            findings=run_dir / "findings.jsonl",
            papers=run_dir / "papers.jsonl",
            paper_notes=run_dir / "paper_notes.jsonl",
            claims=run_dir / "claims.jsonl",
            debate_log=run_dir / "debate_log.md",
            outline=run_dir / "outline.md",
            review=run_dir / "review_report.md",
            scratchpad=run_dir / "scratchpad" / "shared.md",
            manifest=run_dir / "manifest.json",
        )
        artifacts.ensure_dirs()
        return artifacts

    def ensure_dirs(self) -> None:
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.scratchpad.parent.mkdir(parents=True, exist_ok=True)

    def to_artifacts(self, output_format: str) -> list[ResearchArtifact]:
        items = [
            ResearchArtifact(type="report", path=str(self.report_md), description="Canonical markdown research report"),
            ResearchArtifact(type="findings", path=str(self.findings), description="Structured research findings"),
            ResearchArtifact(type="papers", path=str(self.papers), description="Literature records and citation candidates"),
            ResearchArtifact(type="paper_notes", path=str(self.paper_notes), description="Lightweight structured notes extracted from paper abstracts or full text"),
            ResearchArtifact(type="claims", path=str(self.claims), description="Generated literature-review claims, research gaps, and future directions"),
            ResearchArtifact(type="debate", path=str(self.debate_log), description="Cross-perspective debate log"),
            ResearchArtifact(type="outline", path=str(self.outline), description="Structured report or paper outline"),
            ResearchArtifact(type="review", path=str(self.review), description="Multi-agent review notes"),
        ]
        if output_format == "latex":
            items.insert(0, ResearchArtifact(type="latex", path=str(self.paper_tex), description="LaTeX literature review draft"))
            items.insert(1, ResearchArtifact(type="bibtex", path=str(self.references_bib), description="BibTeX references for the LaTeX draft"))
        elif output_format == "html":
            items.insert(0, ResearchArtifact(type="html", path=str(self.report_html), description="HTML research report"))
        return items

    def write_manifest(self, request: ResearchRequest, step_records: list[dict[str, Any]]) -> None:
        payload = {
            "topic": request.topic,
            "depth": request.depth,
            "output_format": request.output_format,
            "constraints": request.constraints,
            "sources": request.sources,
            "artifacts": {
                "report_md": str(self.report_md),
                "paper_tex": str(self.paper_tex),
                "references_bib": str(self.references_bib),
                "report_html": str(self.report_html),
                "findings": str(self.findings),
                "papers": str(self.papers),
                "paper_notes": str(self.paper_notes),
                "claims": str(self.claims),
                "debate_log": str(self.debate_log),
                "outline": str(self.outline),
                "review": str(self.review),
                "scratchpad": str(self.scratchpad),
            },
            "steps": step_records,
        }
        self.manifest.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
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


def ensure_text_artifact(path: Path, title: str, body: str) -> None:
    if path.exists() and path.read_text(encoding="utf-8").strip():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"# {title}\n\n{body.strip()}\n", encoding="utf-8")


def export_latex(markdown_path: Path, tex_path: Path, title: str, papers_path: Path | None = None, bib_path: Path | None = None) -> None:
    markdown = markdown_path.read_text(encoding="utf-8") if markdown_path.exists() else ""
    papers = read_jsonl(papers_path) if papers_path is not None else []
    url_to_key = export_bibtex(papers, bib_path) if bib_path is not None else {}
    lines = [
        r"\documentclass{article}",
        r"\usepackage[utf8]{inputenc}",
        r"\usepackage{ctex}",
        r"\usepackage{geometry}",
        r"\usepackage{hyperref}",
        r"\geometry{margin=1in}",
        r"\title{" + _escape_latex(title) + "}",
        r"\author{Riff-Band Research Mode}",
        r"\date{\today}",
        r"\begin{document}",
        r"\maketitle",
        r"\begin{abstract}",
        _escape_latex(_first_nonempty_paragraph(markdown) or f"本文围绕“{title}”整理已有文献、研究空白和未来方向。"),
        r"\end{abstract}",
        "",
    ]
    for raw in markdown.splitlines():
        line = raw.strip()
        if not line:
            lines.append("")
            continue
        line = _replace_urls_with_cites(line, url_to_key)
        if line.startswith("# "):
            lines.append(r"\section*{" + _escape_latex(line[2:].strip()) + "}")
        elif line.startswith("## "):
            lines.append(r"\section{" + _escape_latex(line[3:].strip()) + "}")
        elif line.startswith("### "):
            lines.append(r"\subsection{" + _escape_latex(line[4:].strip()) + "}")
        elif line.startswith("- "):
            lines.append(r"\noindent " + _escape_latex_preserving_citations(line[2:].strip()) + r"\\")
        elif re.match(r"^\d+\.\s+", line):
            lines.append(r"\noindent " + _escape_latex_preserving_citations(line) + r"\\")
        else:
            lines.append(_escape_latex_preserving_citations(line))
    if bib_path is not None and url_to_key:
        lines.extend(["", r"\bibliographystyle{plain}", r"\bibliography{references}"])
    lines.append(r"\end{document}")
    tex_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def export_bibtex(papers: list[dict[str, Any]], bib_path: Path | None) -> dict[str, str]:
    if bib_path is None:
        return {}
    entries: list[str] = []
    url_to_key: dict[str, str] = {}
    used: set[str] = set()
    for row in papers:
        title = str(row.get("title", "")).strip()
        if not title:
            continue
        authors = [str(item).strip() for item in (row.get("authors", []) or []) if str(item).strip()]
        year = str(row.get("year", "") or row.get("published", "") or "n.d.")[:4]
        key_base = _bib_key(authors[0] if authors else "ref", year, title)
        key = key_base
        suffix = 2
        while key in used:
            key = f"{key_base}{suffix}"
            suffix += 1
        used.add(key)
        source_url = str(row.get("source_url", "")).strip()
        if source_url:
            url_to_key[source_url] = key
        fields = {
            "title": title,
            "author": " and ".join(authors),
            "year": year if year.isdigit() else "",
            "journal": row.get("venue", ""),
            "doi": row.get("doi", "") or (row.get("external_ids", {}) or {}).get("DOI", ""),
            "url": row.get("source_url", ""),
        }
        body = "\n".join(
            f"  {name} = {{{_escape_bibtex(value)}}},"
            for name, value in fields.items()
            if str(value or "").strip()
        )
        entries.append(f"@article{{{key},\n{body}\n}}")
    bib_path.parent.mkdir(parents=True, exist_ok=True)
    bib_path.write_text("\n\n".join(entries) + ("\n" if entries else ""), encoding="utf-8")
    return url_to_key


def _first_nonempty_paragraph(markdown: str) -> str:
    for block in re.split(r"\n\s*\n", markdown):
        text = " ".join(line.strip() for line in block.splitlines() if line.strip() and not line.strip().startswith("#"))
        if text:
            return text[:800]
    return ""


def _replace_urls_with_cites(text: str, url_to_key: dict[str, str]) -> str:
    def repl(match: re.Match[str]) -> str:
        url = match.group(0).rstrip(".,;)")
        suffix = match.group(0)[len(url):]
        key = url_to_key.get(url)
        if key:
            return f"\\cite{{{key}}}{suffix}"
        return f"\\url{{{url}}}{suffix}"

    return re.sub(r"https?://[^\s)\]>\"']+", repl, text)


def _escape_latex_preserving_citations(text: str) -> str:
    escaped = _escape_latex(text)
    escaped = escaped.replace(r"\textbackslash{}cite\{", r"\cite{")
    escaped = escaped.replace(r"\textbackslash{}url\{", r"\url{")
    escaped = escaped.replace(r"\}", "}")
    return escaped


def _bib_key(author: str, year: str, title: str) -> str:
    family = str(author or "ref").split()[-1]
    raw = f"{family}-{year}-{title}"
    key = re.sub(r"[^A-Za-z0-9]+", "", raw.title())
    return key[:64] or "ref"


def _escape_bibtex(value: Any) -> str:
    return str(value or "").replace("\\", "\\textbackslash{}").replace("{", "\\{").replace("}", "\\}")


def export_html(markdown_path: Path, html_path: Path, title: str) -> None:
    markdown = markdown_path.read_text(encoding="utf-8") if markdown_path.exists() else ""
    body: list[str] = []
    for raw in markdown.splitlines():
        line = raw.strip()
        if line.startswith("# "):
            body.append(f"<h1>{escape(line[2:].strip())}</h1>")
        elif line.startswith("## "):
            body.append(f"<h2>{escape(line[3:].strip())}</h2>")
        elif line.startswith("- "):
            body.append(f"<p class=\"bullet\">{escape(line[2:].strip())}</p>")
        elif line:
            body.append(f"<p>{escape(line)}</p>")
    html = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)}</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 0; color: #172026; background: #f7f8fa; }}
    main {{ max-width: 920px; margin: 0 auto; padding: 40px 24px 72px; background: #fff; min-height: 100vh; }}
    h1 {{ font-size: 32px; line-height: 1.2; margin: 0 0 24px; }}
    h2 {{ font-size: 21px; margin: 32px 0 12px; border-bottom: 1px solid #d8dee4; padding-bottom: 8px; }}
    p {{ line-height: 1.7; margin: 10px 0; }}
    .bullet {{ padding-left: 18px; position: relative; }}
    .bullet::before {{ content: "•"; position: absolute; left: 0; color: #59636e; }}
  </style>
</head>
<body><main>
{chr(10).join(body)}
</main></body>
</html>
"""
    html_path.write_text(html, encoding="utf-8")


def _escape_latex(text: str) -> str:
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    return "".join(replacements.get(ch, ch) for ch in str(text))
