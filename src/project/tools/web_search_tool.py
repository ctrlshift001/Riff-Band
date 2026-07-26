from __future__ import annotations

import asyncio
import html
import json
import os
import re
from typing import Any, Dict, List
from urllib.parse import parse_qs, unquote, urlparse

from pydantic import Field

from base.agent.base_action import BaseAction


if os.getenv("WEB_SEARCH_HTTP_PROXY"):
    os.environ["HTTP_PROXY"] = os.getenv("WEB_SEARCH_HTTP_PROXY", "")
if os.getenv("WEB_SEARCH_HTTPS_PROXY") or os.getenv("WEB_SEARCH_HTTP_PROXY"):
    os.environ["HTTPS_PROXY"] = (
        os.getenv("WEB_SEARCH_HTTPS_PROXY")
        or os.getenv("WEB_SEARCH_HTTP_PROXY", "")
    )


class WebSearchTool(BaseAction):
    name: str = "web_search"
    description: str = (
        "并行搜索 Serper 与 DuckDuckGo，返回可追溯的标题、摘要、URL 和来源。"
    )
    parameters: Dict[str, Any] = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "k": {"type": "integer", "default": 5},
                "gl": {"type": "string", "default": "us"},
                "hl": {"type": "string", "default": "en"},
            },
            "required": ["query"],
            "additionalProperties": False,
        }
    )

    async def __call__(
        self,
        query: str,
        k: int = 5,
        gl: str = "us",
        hl: str = "en",
    ) -> Dict[str, Any]:
        query = str(query or "").strip()
        if not query:
            return {"success": False, "message": "query must not be blank"}
        k = max(1, min(int(k), 20))

        serper_result, ddgs_result = await asyncio.gather(
            self._serper_search(query, k, gl, hl),
            self._ddgs_search(query, k),
        )
        runs = [
            self._source_run("serper", serper_result),
            self._source_run("ddgs", ddgs_result),
        ]
        results = self._merge_results(
            [
                *self._parse_output(serper_result),
                *self._parse_output(ddgs_result),
            ],
            k,
        )

        if not results and not ddgs_result.get("success"):
            fallback = await self._duckduckgo_html_search(query, k)
            runs.append(self._source_run("duckduckgo_html", fallback))
            results = self._merge_results(self._parse_output(fallback), k)

        if not results:
            fallback = await self._wikipedia_search(query, k)
            runs.append(self._source_run("wikipedia", fallback))
            results = self._merge_results(self._parse_output(fallback), k)

        if not results:
            errors = "; ".join(
                f"{run['provider']}: {run['error']}"
                for run in runs
                if run["error"]
            )
            return {
                "success": False,
                "message": errors or "all web search providers returned no results",
                "source_runs": runs,
            }

        providers = list(
            dict.fromkeys(
                provider
                for item in results
                for provider in item["provider"].split("+")
                if provider
            )
        )
        return {
            "success": True,
            "backend": "+".join(providers),
            "output": json.dumps(results, ensure_ascii=False, indent=2),
            "source_runs": runs,
        }

    @staticmethod
    def _source_run(provider: str, result: dict[str, Any]) -> dict[str, Any]:
        records = WebSearchTool._parse_output(result)
        return {
            "provider": provider,
            "success": bool(result.get("success")),
            "record_count": len(records),
            "error": (
                ""
                if result.get("success")
                else str(result.get("message") or "search failed")[:500]
            ),
        }

    @staticmethod
    def _parse_output(result: dict[str, Any]) -> list[dict[str, Any]]:
        if not result.get("success"):
            return []
        try:
            parsed = json.loads(str(result.get("output") or "[]"))
        except json.JSONDecodeError:
            return []
        return [item for item in parsed if isinstance(item, dict)]

    @staticmethod
    def _canonical_url(value: str) -> str:
        parsed = urlparse(str(value or "").strip())
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return ""
        return parsed._replace(fragment="").geturl()

    @classmethod
    def _merge_results(
        cls,
        records: list[dict[str, Any]],
        limit: int,
    ) -> list[dict[str, Any]]:
        merged: dict[str, dict[str, Any]] = {}
        for position, raw in enumerate(records, start=1):
            url = cls._canonical_url(str(raw.get("url") or raw.get("source") or ""))
            title = " ".join(str(raw.get("title") or "").split())
            snippet = " ".join(
                str(raw.get("snippet") or raw.get("content") or "").split()
            )
            if not url or not (title or snippet):
                continue
            key = url.casefold()
            provider = str(raw.get("provider") or "web").strip() or "web"
            current = merged.get(key)
            if current is None:
                merged[key] = {
                    "title": title or urlparse(url).netloc,
                    "snippet": snippet,
                    "url": url,
                    "provider": provider,
                    "rank": int(raw.get("rank") or position),
                    # Backward-compatible fields used by the legacy Agent runtime.
                    "content": snippet,
                    "source": url,
                }
                continue
            if len(title) > len(current["title"]):
                current["title"] = title
            if len(snippet) > len(current["snippet"]):
                current["snippet"] = snippet
                current["content"] = snippet
            providers = current["provider"].split("+")
            if provider not in providers:
                current["provider"] = "+".join([*providers, provider])
            current["rank"] = min(current["rank"], int(raw.get("rank") or position))
        return sorted(
            merged.values(),
            key=lambda item: (item["rank"], -len(item["snippet"])),
        )[:limit]

    def _query_terms(self, query: str) -> List[str]:
        terms = re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z0-9]{3,}", str(query or ""))
        return [term.lower() for term in terms if term.strip()]

    def _is_relevant(self, query: str, text: str) -> bool:
        terms = self._query_terms(query)
        if not terms:
            return True
        haystack = str(text or "").lower()
        return any(term in haystack for term in terms)

    async def _serper_search(
        self,
        query: str,
        k: int,
        gl: str,
        hl: str,
    ) -> Dict[str, Any]:
        api_key = os.getenv("SERPER_API_KEY", "").strip()
        if not api_key:
            return {"success": False, "message": "SERPER_API_KEY is not configured"}

        try:
            import aiohttp
        except ImportError:
            return {"success": False, "message": "aiohttp is required for Serper search"}

        endpoint = os.getenv(
            "SERPER_BASE_URL",
            "https://google.serper.dev/search",
        ).strip()
        payload = {"q": query, "num": k, "gl": gl, "hl": hl}
        headers = {"X-API-KEY": api_key, "Content-Type": "application/json"}
        try:
            timeout = aiohttp.ClientTimeout(total=30)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(endpoint, json=payload, headers=headers) as resp:
                    text = await resp.text()
                    if resp.status >= 400:
                        return {
                            "success": False,
                            "message": f"Serper HTTP {resp.status}: {text[:200]}",
                        }
                    data = json.loads(text)
        except Exception as exc:
            return {"success": False, "message": f"Serper search failed: {exc}"}

        records = []
        for rank, item in enumerate((data.get("organic") or [])[:k], start=1):
            link = str(item.get("link") or "")
            snippet = str(item.get("snippet") or "")
            title = str(item.get("title") or "")
            if link and (title or snippet):
                records.append(
                    {
                        "title": title,
                        "snippet": snippet,
                        "url": link,
                        "provider": "serper",
                        "rank": rank,
                    }
                )
        if not records:
            return {"success": False, "message": "Serper returned no usable results"}
        return {"success": True, "output": json.dumps(records, ensure_ascii=False)}

    async def _ddgs_search(self, query: str, k: int) -> Dict[str, Any]:
        try:
            from ddgs import DDGS
        except ImportError:
            try:
                from duckduckgo_search import DDGS  # type: ignore
            except ImportError:
                return {
                    "success": False,
                    "message": "install `ddgs` to enable DuckDuckGo search",
                }

        try:
            def sync_search():
                with DDGS() as ddgs:
                    try:
                        return list(ddgs.text(query=query, max_results=k))
                    except TypeError:
                        return list(ddgs.text(keywords=query, max_results=k))

            results = await asyncio.to_thread(sync_search)
        except Exception as exc:
            return {"success": False, "message": f"DDGS search failed: {exc}"}

        records = []
        for rank, item in enumerate((results or [])[:k], start=1):
            title = str(item.get("title") or "")
            snippet = str(item.get("body") or "")
            url = str(item.get("href") or "")
            if url and (title or snippet) and self._is_relevant(
                query,
                f"{title} {snippet} {url}",
            ):
                records.append(
                    {
                        "title": title,
                        "snippet": snippet,
                        "url": url,
                        "provider": "ddgs",
                        "rank": rank,
                    }
                )
        if not records:
            return {"success": False, "message": "DDGS returned no relevant results"}
        return {"success": True, "output": json.dumps(records, ensure_ascii=False)}

    async def _duckduckgo_html_search(self, query: str, k: int) -> Dict[str, Any]:
        try:
            import aiohttp
        except ImportError:
            return {
                "success": False,
                "message": "aiohttp is required for DuckDuckGo HTML fallback",
            }

        try:
            timeout = aiohttp.ClientTimeout(total=25)
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 Chrome/120 Safari/537.36"
                )
            }
            async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
                async with session.post(
                    "https://html.duckduckgo.com/html/",
                    data={"q": query},
                ) as resp:
                    text = await resp.text()
                    if resp.status >= 400:
                        return {
                            "success": False,
                            "message": f"DuckDuckGo HTML HTTP {resp.status}",
                        }
        except Exception as exc:
            return {"success": False, "message": f"DuckDuckGo HTML failed: {exc}"}

        blocks = re.findall(
            r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>.*?'
            r'(?:<a[^>]+class="result__snippet"[^>]*>(.*?)</a>|'
            r'<div[^>]+class="result__snippet"[^>]*>(.*?)</div>)',
            text,
            flags=re.S,
        )
        records = []
        for rank, (href, title, snippet_a, snippet_div) in enumerate(
            blocks[:k],
            start=1,
        ):
            title_text = html.unescape(
                " ".join(re.sub(r"<[^>]+>", " ", title).split())
            )
            snippet = html.unescape(
                " ".join(
                    re.sub(r"<[^>]+>", " ", snippet_a or snippet_div or "").split()
                )
            )
            link = html.unescape(href)
            parsed = urlparse(link)
            if parsed.path.endswith("/l/"):
                link = unquote(parse_qs(parsed.query).get("uddg", [link])[0])
            if link and (title_text or snippet):
                records.append(
                    {
                        "title": title_text,
                        "snippet": snippet,
                        "url": link,
                        "provider": "duckduckgo_html",
                        "rank": rank,
                    }
                )
        if not records:
            return {"success": False, "message": "DuckDuckGo HTML returned no results"}
        return {"success": True, "output": json.dumps(records, ensure_ascii=False)}

    async def _wikipedia_search(self, query: str, k: int) -> Dict[str, Any]:
        try:
            import aiohttp
        except ImportError:
            return {
                "success": False,
                "message": "aiohttp is required for Wikipedia fallback",
            }

        errors = []
        timeout = aiohttp.ClientTimeout(total=20)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                for lang in ("zh", "en"):
                    endpoint = f"https://{lang}.wikipedia.org/w/api.php"
                    params = {
                        "action": "opensearch",
                        "search": query,
                        "limit": k,
                        "namespace": 0,
                        "format": "json",
                    }
                    try:
                        async with session.get(endpoint, params=params) as resp:
                            if resp.status >= 400:
                                errors.append(f"{lang}: HTTP {resp.status}")
                                continue
                            data = await resp.json(content_type=None)
                    except Exception as exc:
                        errors.append(f"{lang}: {exc}")
                        continue
                    titles = data[1] if len(data) > 1 else []
                    descriptions = data[2] if len(data) > 2 else []
                    links = data[3] if len(data) > 3 else []
                    records = []
                    for rank, title in enumerate(titles[:k], start=1):
                        index = rank - 1
                        snippet = descriptions[index] if index < len(descriptions) else ""
                        url = links[index] if index < len(links) else ""
                        if url:
                            records.append(
                                {
                                    "title": str(title),
                                    "snippet": str(snippet or title),
                                    "url": str(url),
                                    "provider": "wikipedia",
                                    "rank": rank,
                                }
                            )
                    if records:
                        return {
                            "success": True,
                            "output": json.dumps(records, ensure_ascii=False),
                        }
        except Exception as exc:
            errors.append(str(exc))
        return {
            "success": False,
            "message": "; ".join(errors) or "Wikipedia returned no results",
        }
