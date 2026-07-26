from __future__ import annotations

import asyncio
import html
import io
import ipaddress
import json
import os
import re
import socket
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urljoin, urlparse

from ai4ms.connectors import DataCommonsConnector, MCPConnectorError
from ai4ms.literature.broker import LiteratureBroker, SUPPORTED_BACKENDS
from project.tools.web_search_tool import WebSearchTool


SEARCH_INTENT_TERMS = (
    "联网",
    "搜索",
    "检索",
    "查找",
    "来源",
    "引用",
    "文献",
    "论文",
    "证据",
    "最新",
    "目前",
    "截至",
    "现状",
    "官方",
    "统计",
    "数据",
    "趋势",
    "search",
    "source",
    "citation",
    "paper",
    "literature",
    "evidence",
    "latest",
    "current",
    "official",
    "statistics",
)
OFFICIAL_DATA_TERMS = (
    "官方数据",
    "统计数据",
    "指标",
    "人口",
    "gdp",
    "失业率",
    "收入",
    "国家比较",
    "地区比较",
    "official data",
    "statistics",
    "indicator",
    "population",
)
ACADEMIC_STAGES = {"problem", "literature"}
BILINGUAL_RESEARCH_TERMS = (
    (("人工智能", "ai"), ("AI", "artificial intelligence")),
    (("采用", "采纳", "应用"), ("adoption",)),
    (("企业", "公司", "组织"), ("firm", "organization")),
    (("创新",), ("innovation",)),
    (("绩效", "表现"), ("performance",)),
    (("生产率", "生产力"), ("productivity",)),
    (("影响", "效应"), ("impact", "effect")),
    (("机制",), ("mechanism",)),
    (("能力",), ("capability",)),
    (("治理",), ("governance",)),
    (("竞争",), ("competition",)),
    (("供应链",), ("supply chain",)),
    (("平台",), ("platform",)),
    (("员工", "劳动力"), ("employee", "workforce")),
    (("消费者", "用户"), ("consumer", "user")),
    (("因果",), ("causal",)),
    (("实证",), ("empirical",)),
    (("综述",), ("systematic review",)),
)
OFFICIAL_DOMAINS = (
    ".gov",
    ".gov.cn",
    ".edu",
    ".edu.cn",
    "gov.cn",
    "stats.gov.cn",
    "who.int",
    "worldbank.org",
    "oecd.org",
    "un.org",
    "datacommons.org",
)
ACADEMIC_DOMAINS = (
    "doi.org",
    "arxiv.org",
    "openalex.org",
    "semanticscholar.org",
    "crossref.org",
    "pubmed.ncbi.nlm.nih.gov",
    "pmc.ncbi.nlm.nih.gov",
    "sciencedirect.com",
    "springer.com",
    "nature.com",
    "wiley.com",
    "tandfonline.com",
    "sagepub.com",
    "jstor.org",
    "informs.org",
    "acm.org",
    "ieee.org",
)


class PublicPageReader:
    """Read bounded public HTTP content and reject private-network targets."""

    def __init__(self) -> None:
        self.timeout_seconds = float(
            os.getenv("AI4MS_WEB_READ_TIMEOUT_SECONDS", "18")
        )
        self.max_bytes = int(os.getenv("AI4MS_WEB_READ_MAX_BYTES", "2000000"))
        self.max_chars = int(os.getenv("AI4MS_WEB_READ_MAX_CHARS", "12000"))

    async def read(self, url: str) -> dict[str, Any]:
        try:
            import aiohttp
        except ImportError:
            return {"success": False, "url": url, "error": "aiohttp unavailable"}

        current = url
        timeout = aiohttp.ClientTimeout(total=self.timeout_seconds)
        headers = {
            "User-Agent": "AI4MS-Research-Workbench/0.3 (+local research assistant)",
            "Accept": "text/html,application/xhtml+xml,application/pdf,text/plain",
        }
        try:
            async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
                for _ in range(4):
                    await self._assert_public_url(current)
                    async with session.get(
                        current,
                        allow_redirects=False,
                    ) as response:
                        if response.status in {301, 302, 303, 307, 308}:
                            location = response.headers.get("Location", "").strip()
                            if not location:
                                raise ValueError("redirect response has no Location")
                            current = urljoin(current, location)
                            continue
                        if response.status >= 400:
                            return {
                                "success": False,
                                "url": current,
                                "error": f"HTTP {response.status}",
                            }
                        content_type = response.headers.get(
                            "Content-Type",
                            "",
                        ).lower()
                        body = await self._read_bounded(response)
                        if "pdf" in content_type or current.lower().endswith(".pdf"):
                            text = await asyncio.to_thread(self._pdf_text, body)
                            title = ""
                        elif (
                            content_type.startswith("text/")
                            or "html" in content_type
                            or not content_type
                        ):
                            decoded = body.decode(
                                response.charset or "utf-8",
                                errors="replace",
                            )
                            title, text = self._html_text(decoded)
                        else:
                            return {
                                "success": False,
                                "url": current,
                                "error": f"unsupported content type: {content_type[:80]}",
                            }
                        return {
                            "success": bool(text),
                            "url": current,
                            "title": title,
                            "text": text[: self.max_chars],
                            "content_type": content_type,
                            "error": "" if text else "page contained no readable text",
                        }
                return {
                    "success": False,
                    "url": current,
                    "error": "too many redirects",
                }
        except Exception as exc:
            return {"success": False, "url": current, "error": str(exc)[:500]}

    async def _assert_public_url(self, url: str) -> None:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("only public HTTP(S) URLs can be read")
        hostname = parsed.hostname.rstrip(".").lower()
        if hostname in {"localhost"} or hostname.endswith(".local"):
            raise ValueError("private or local network targets are not allowed")
        addresses = await asyncio.to_thread(
            socket.getaddrinfo,
            hostname,
            parsed.port or (443 if parsed.scheme == "https" else 80),
            0,
            socket.SOCK_STREAM,
        )
        if not addresses:
            raise ValueError("hostname did not resolve")
        for address in addresses:
            ip = ipaddress.ip_address(address[4][0])
            if not ip.is_global:
                raise ValueError("private or non-global network targets are not allowed")

    async def _read_bounded(self, response) -> bytes:
        chunks: list[bytes] = []
        size = 0
        async for chunk in response.content.iter_chunked(64 * 1024):
            size += len(chunk)
            if size > self.max_bytes:
                raise ValueError("page exceeds the configured read limit")
            chunks.append(chunk)
        return b"".join(chunks)

    @staticmethod
    def _html_text(document: str) -> tuple[str, str]:
        title_match = re.search(
            r"<title[^>]*>(.*?)</title>",
            document,
            flags=re.I | re.S,
        )
        title = html.unescape(
            " ".join(re.sub(r"<[^>]+>", " ", title_match.group(1)).split())
        ) if title_match else ""
        cleaned = re.sub(
            r"<(script|style|noscript|svg|nav|footer)[^>]*>.*?</\1>",
            " ",
            document,
            flags=re.I | re.S,
        )
        cleaned = re.sub(r"<[^>]+>", " ", cleaned)
        text = html.unescape(" ".join(cleaned.split()))
        return title[:500], text

    @staticmethod
    def _pdf_text(body: bytes) -> str:
        try:
            from pypdf import PdfReader

            reader = PdfReader(io.BytesIO(body))
            return " ".join(
                text
                for page in reader.pages[:25]
                if (text := (page.extract_text() or "").strip())
            )
        except Exception:
            return ""


class WebResearchService:
    """Search, read, rank and persist evidence for stage chat."""

    def __init__(
        self,
        projects_dir: str | Path,
        *,
        web_search_factory: Callable[[], Any] | None = None,
        literature_broker: LiteratureBroker | None = None,
        page_reader: PublicPageReader | None = None,
        data_commons: DataCommonsConnector | None = None,
    ) -> None:
        self.projects_dir = Path(projects_dir)
        self.web_search_factory = web_search_factory or WebSearchTool
        self.literature_broker = literature_broker or LiteratureBroker()
        self.page_reader = page_reader or PublicPageReader()
        self.data_commons = data_commons or DataCommonsConnector()
        self.max_citations = max(
            3,
            min(int(os.getenv("AI4MS_SEARCH_MAX_CITATIONS", "8")), 15),
        )
        self.read_top_k = max(
            0,
            min(int(os.getenv("AI4MS_SEARCH_READ_TOP_K", "4")), 8),
        )

    async def probe_search(self) -> dict[str, Any]:
        """Verify that the configured Serper backend works from this process."""

        configured = bool(os.getenv("SERPER_API_KEY", "").strip())
        if not configured:
            return {
                "status": "failed",
                "configured": False,
                "provider": "serper",
                "record_count": 0,
                "error": "SERPER_API_KEY is not configured",
            }

        result = await self.web_search_factory()(
            query="management science research methods",
            k=3,
        )
        serper_run = next(
            (
                run
                for run in result.get("source_runs", [])
                if run.get("provider") == "serper"
            ),
            None,
        )
        if not serper_run or not serper_run.get("success"):
            return {
                "status": "failed",
                "configured": True,
                "provider": "serper",
                "record_count": int((serper_run or {}).get("record_count") or 0),
                "error": str(
                    (serper_run or {}).get("error")
                    or result.get("message")
                    or "Serper did not return a successful search result"
                )[:500],
            }

        return {
            "status": "ok",
            "configured": True,
            "provider": "serper",
            "record_count": int(serper_run.get("record_count") or 0),
            "backend": str(result.get("backend") or "serper"),
        }

    @staticmethod
    def should_search(stage_key: str, query: str, mode: str) -> bool:
        if mode == "off":
            return False
        if mode == "on":
            return True
        lowered = query.casefold()
        if any(term in lowered for term in SEARCH_INTENT_TERMS):
            return True
        return stage_key in ACADEMIC_STAGES and any(
            term in lowered
            for term in ("研究", "问题", "空白", "影响", "关系", "机制")
        )

    async def research(
        self,
        project_id: str,
        stage_key: str,
        query: str,
        mode: str = "auto",
    ) -> dict[str, Any]:
        search_id = f"web_{uuid.uuid4().hex[:12]}"
        searched_at = datetime.now(UTC).isoformat()
        if not self.should_search(stage_key, query, mode):
            return {
                "search_id": search_id,
                "status": "skipped",
                "mode": mode,
                "searched": False,
                "searched_at": searched_at,
                "queries": [],
                "citations": [],
                "source_runs": [],
                "snapshot_path": "",
            }

        queries = self._plan_queries(stage_key, query)
        web_tasks = [
            self.web_search_factory()(query=item, k=6)
            for item in queries
        ]
        literature_task = (
            self.literature_broker.search(
                [queries[-1]],
                list(SUPPORTED_BACKENDS),
                limit_per_backend=4,
            )
            if stage_key in ACADEMIC_STAGES
            else None
        )
        official_task = (
            self._official_data_search(query)
            if self._wants_official_data(query)
            else None
        )

        tasks = [*web_tasks]
        if literature_task is not None:
            tasks.append(literature_task)
        if official_task is not None:
            tasks.append(official_task)
        raw = await asyncio.gather(*tasks, return_exceptions=True)

        candidates: list[dict[str, Any]] = []
        source_runs: list[dict[str, Any]] = []
        for index, planned_query in enumerate(queries):
            result = raw[index]
            if isinstance(result, Exception):
                source_runs.append(
                    {
                        "provider": "web",
                        "query": planned_query,
                        "success": False,
                        "record_count": 0,
                        "error": str(result)[:500],
                    }
                )
                continue
            records = self._web_candidates(result, planned_query)
            candidates.extend(records)
            runs = result.get("source_runs") or []
            if runs:
                source_runs.extend(
                    [{**run, "query": planned_query} for run in runs]
                )
            else:
                source_runs.append(
                    {
                        "provider": str(result.get("backend") or "web"),
                        "query": planned_query,
                        "success": bool(result.get("success")),
                        "record_count": len(records),
                        "error": str(result.get("message") or "")[:500],
                    }
                )

        cursor = len(queries)
        if literature_task is not None:
            literature_result = raw[cursor]
            cursor += 1
            if isinstance(literature_result, Exception):
                source_runs.append(
                    {
                        "provider": "academic_broker",
                        "query": query,
                        "success": False,
                        "record_count": 0,
                        "error": str(literature_result)[:500],
                    }
                )
            else:
                candidates.extend(
                    self._paper_candidates(literature_result.papers, query)
                )
                source_runs.extend(
                    [
                        {
                            "provider": run["backend"],
                            "query": run["query"],
                            "success": run["success"],
                            "record_count": run["record_count"],
                            "error": run["error"],
                        }
                        for run in literature_result.source_runs
                    ]
                )

        if official_task is not None:
            official_result = raw[cursor]
            if isinstance(official_result, Exception):
                source_runs.append(
                    {
                        "provider": "datacommons_mcp",
                        "query": query,
                        "success": False,
                        "record_count": 0,
                        "error": str(official_result)[:500],
                    }
                )
            else:
                source_runs.append(official_result["source_run"])
                if official_result.get("candidate"):
                    candidates.append(official_result["candidate"])

        candidates = self._deduplicate(candidates)
        candidates.sort(
            key=lambda item: self._score(item, query),
            reverse=True,
        )
        await self._read_top_pages(candidates)
        candidates.sort(
            key=lambda item: self._score(item, query),
            reverse=True,
        )
        citations = [
            self._public_citation(item, index)
            for index, item in enumerate(
                candidates[: self.max_citations],
                start=1,
            )
        ]
        successes = sum(1 for run in source_runs if run.get("success"))
        failures = sum(1 for run in source_runs if not run.get("success"))
        status = (
            "complete"
            if citations and successes and not failures
            else "partial"
            if citations
            else "failed"
        )
        payload = {
            "schema_version": 1,
            "search_id": search_id,
            "status": status,
            "mode": mode,
            "searched": True,
            "searched_at": searched_at,
            "queries": queries,
            "citations": citations,
            "source_runs": source_runs,
        }
        relative_path = Path("artifacts") / "search" / f"{search_id}.json"
        target = self.projects_dir / project_id / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(target)
        payload["snapshot_path"] = relative_path.as_posix()
        return payload

    @staticmethod
    def prompt_context(trace: dict[str, Any]) -> str:
        rows = []
        for citation in trace.get("citations") or []:
            excerpt = str(
                citation.get("excerpt") or citation.get("snippet") or ""
            )[:2200]
            rows.append(
                f"[{citation['citation_id']}] {citation['title']}\n"
                f"URL: {citation['url']}\n"
                f"类型: {citation['source_type']}；来源: {citation['provider']}\n"
                f"证据摘录: {excerpt}"
            )
        return "\n\n".join(rows)

    @staticmethod
    def _plan_queries(stage_key: str, query: str) -> list[str]:
        clean = " ".join(query.split())
        queries = [clean]
        lowered = clean.casefold()
        translated: list[str] = []
        english_tokens = re.findall(r"\b[A-Za-z][A-Za-z0-9-]{1,}\b", clean)
        translated.extend(english_tokens)
        for source_terms, target_terms in BILINGUAL_RESEARCH_TERMS:
            if any(term.casefold() in lowered for term in source_terms):
                translated.extend(target_terms)
        translated = list(dict.fromkeys(item for item in translated if item))
        if stage_key in ACADEMIC_STAGES:
            core = " ".join(translated) if len(translated) >= 2 else clean
            queries.append(f"{core} research evidence systematic review")
        else:
            core = " ".join(translated) if len(translated) >= 2 else clean
            queries.append(f"{core} evidence official source")
        return list(dict.fromkeys(queries))[:2]

    @staticmethod
    def _wants_official_data(query: str) -> bool:
        lowered = query.casefold()
        return any(term in lowered for term in OFFICIAL_DATA_TERMS)

    async def _official_data_search(self, query: str) -> dict[str, Any]:
        if not self.data_commons.status()["configured"]:
            return {
                "source_run": {
                    "provider": "datacommons_mcp",
                    "query": query,
                    "success": False,
                    "record_count": 0,
                    "error": self.data_commons.status()["reason"],
                },
                "candidate": None,
            }
        try:
            result = await self.data_commons.search_indicators(query)
            text = str(result["result"].get("text") or "")[:12000]
            return {
                "source_run": {
                    "provider": "datacommons_mcp",
                    "query": query,
                    "success": True,
                    "record_count": 1 if text else 0,
                    "error": "",
                },
                "candidate": {
                    "title": "Google Data Commons 指标检索",
                    "url": "https://datacommons.org/",
                    "snippet": text[:1200],
                    "excerpt": text,
                    "provider": "datacommons_mcp",
                    "source_type": "official_data",
                    "is_official": True,
                    "rank": 1,
                    "matched_queries": [query],
                    "paper_id": "",
                    "read_success": True,
                } if text else None,
            }
        except MCPConnectorError as exc:
            return {
                "source_run": {
                    "provider": "datacommons_mcp",
                    "query": query,
                    "success": False,
                    "record_count": 0,
                    "error": str(exc)[:500],
                },
                "candidate": None,
            }

    @staticmethod
    def _web_candidates(
        result: dict[str, Any],
        query: str,
    ) -> list[dict[str, Any]]:
        if not result.get("success"):
            return []
        try:
            records = json.loads(str(result.get("output") or "[]"))
        except json.JSONDecodeError:
            return []
        candidates = []
        for item in records if isinstance(records, list) else []:
            if not isinstance(item, dict):
                continue
            url = str(item.get("url") or item.get("source") or "").strip()
            domain = urlparse(url).hostname or ""
            source_type, is_official = WebResearchService._classify_domain(domain)
            candidates.append(
                {
                    "title": str(item.get("title") or domain or url).strip(),
                    "url": url,
                    "snippet": str(
                        item.get("snippet") or item.get("content") or ""
                    ).strip(),
                    "excerpt": "",
                    "provider": str(item.get("provider") or "web"),
                    "source_type": source_type,
                    "is_official": is_official,
                    "rank": int(item.get("rank") or len(candidates) + 1),
                    "matched_queries": [query],
                    "paper_id": "",
                    "read_success": False,
                }
            )
        return [item for item in candidates if item["url"]]

    @staticmethod
    def _paper_candidates(
        papers: list[dict[str, Any]],
        query: str,
    ) -> list[dict[str, Any]]:
        candidates = []
        for rank, paper in enumerate(papers[:12], start=1):
            urls = paper.get("source_urls")
            urls = urls if isinstance(urls, list) else []
            url = str(
                (urls[0] if urls else "")
                or paper.get("source_url")
                or (
                    f"https://doi.org/{paper['doi']}"
                    if paper.get("doi")
                    else ""
                )
            ).strip()
            if not url:
                continue
            abstract = str(paper.get("abstract") or "").strip()
            authors = paper.get("authors")
            author_text = ", ".join(authors[:4]) if isinstance(authors, list) else ""
            details = " · ".join(
                value
                for value in (
                    author_text,
                    str(paper.get("venue") or ""),
                    str(paper.get("year") or ""),
                )
                if value
            )
            candidates.append(
                {
                    "title": str(paper.get("title") or url),
                    "url": url,
                    "snippet": abstract[:1400] or details,
                    "excerpt": abstract,
                    "provider": "+".join(paper.get("backends") or ["academic"]),
                    "source_type": "academic",
                    "is_official": False,
                    "rank": rank,
                    "matched_queries": [query],
                    "paper_id": str(paper.get("paper_id") or ""),
                    "read_success": bool(abstract),
                }
            )
        return candidates

    @staticmethod
    def _classify_domain(domain: str) -> tuple[str, bool]:
        lowered = domain.casefold()
        if any(
            lowered == suffix or lowered.endswith(f".{suffix}")
            for suffix in ACADEMIC_DOMAINS
        ):
            return "academic", False
        if any(
            lowered == suffix.lstrip(".") or lowered.endswith(suffix)
            for suffix in OFFICIAL_DOMAINS
        ):
            return "official", True
        return "web", False

    @staticmethod
    def _deduplicate(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
        merged: dict[str, dict[str, Any]] = {}
        for item in candidates:
            parsed = urlparse(item["url"])
            key = parsed._replace(fragment="", query="").geturl().casefold()
            current = merged.get(key)
            if current is None:
                merged[key] = dict(item)
                continue
            if len(item["snippet"]) > len(current["snippet"]):
                current["snippet"] = item["snippet"]
            if len(item["excerpt"]) > len(current["excerpt"]):
                current["excerpt"] = item["excerpt"]
            current["is_official"] = (
                current["is_official"] or item["is_official"]
            )
            if current["source_type"] == "web" and item["source_type"] != "web":
                current["source_type"] = item["source_type"]
            providers = current["provider"].split("+")
            for provider in item["provider"].split("+"):
                if provider not in providers:
                    providers.append(provider)
            current["provider"] = "+".join(providers)
            current["rank"] = min(current["rank"], item["rank"])
            for matched_query in item.get("matched_queries") or []:
                if matched_query not in current["matched_queries"]:
                    current["matched_queries"].append(matched_query)
        return list(merged.values())

    async def _read_top_pages(self, candidates: list[dict[str, Any]]) -> None:
        targets = [
            item
            for item in candidates
            if item["source_type"] != "official_data"
        ][: self.read_top_k]
        if not targets:
            return
        results = await asyncio.gather(
            *(self.page_reader.read(item["url"]) for item in targets),
            return_exceptions=True,
        )
        for item, result in zip(targets, results):
            if isinstance(result, Exception) or not result.get("success"):
                continue
            text = str(result.get("text") or "")
            item["excerpt"] = text[: self.page_reader.max_chars]
            item["read_success"] = True
            if result.get("title") and len(item["title"]) < 8:
                item["title"] = str(result["title"])
            item["url"] = str(result.get("url") or item["url"])

    @staticmethod
    def _tokens(text: str) -> set[str]:
        tokens = {
            token.casefold()
            for token in re.findall(r"[A-Za-z0-9]{2,}", text)
        }
        for sequence in re.findall(r"[\u4e00-\u9fff]{2,}", text):
            tokens.add(sequence)
            for width in (2, 3, 4):
                tokens.update(
                    sequence[index : index + width]
                    for index in range(max(0, len(sequence) - width + 1))
                )
        return tokens

    @classmethod
    def _score(cls, item: dict[str, Any], query: str) -> float:
        text_tokens = cls._tokens(
            f"{item['title']} {item['snippet']} {item['excerpt'][:3000]}"
        )
        query_variants = [
            query,
            *(item.get("matched_queries") or []),
        ]
        overlap = max(
            (
                len(query_tokens & text_tokens) / max(1, len(query_tokens))
                for candidate_query in query_variants
                if (query_tokens := cls._tokens(candidate_query))
            ),
            default=0,
        )
        type_bonus = {
            "official_data": 2.8,
            "official": 2.2,
            "academic": 2.0,
            "web": 0.6,
        }.get(item["source_type"], 0)
        return (
            overlap * 5
            + type_bonus
            + (0.8 if item["read_success"] else 0)
            + 1 / max(1, item["rank"])
        )

    @staticmethod
    def _public_citation(item: dict[str, Any], index: int) -> dict[str, Any]:
        return {
            "citation_id": str(index),
            "title": item["title"][:500],
            "url": item["url"],
            "domain": urlparse(item["url"]).hostname or "",
            "snippet": item["snippet"][:1800],
            "excerpt": item["excerpt"][:6000],
            "provider": item["provider"],
            "source_type": item["source_type"],
            "is_official": bool(item["is_official"]),
            "paper_id": item["paper_id"],
            "retrieved_at": datetime.now(UTC).isoformat(),
        }
