from __future__ import annotations

import asyncio
import json
import os
from typing import Any, Dict

from pydantic import Field

from base.agent.base_action import BaseAction


os.environ["HTTP_PROXY"] = "代理端口"


class WebSearchTool(BaseAction):
    name: str = "web_search"
    description: str = "Search the web for evidence snippets via Serper with DuckDuckGo fallback."
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

    class Config:
        arbitrary_types_allowed = True

    async def __call__(self, query: str, k: int = 5, gl: str = "us", hl: str = "en") -> Dict[str, Any]:
        del gl, hl
        k = max(1, int(k))

        serper_result = await self._serper_search(query, k)
        if serper_result["success"]:
            return serper_result

        ddgs_result = await self._ddgs_search(query, k)
        if ddgs_result["success"]:
            return ddgs_result

        return {
            "success": False,
            "message": (
                f"Both search backends failed. Serper: {serper_result.get('message', '')}; "
                f"DuckDuckGo: {ddgs_result.get('message', '')}"
            ),
        }

    async def _serper_search(self, query: str, k: int) -> Dict[str, Any]:
        api_key = os.getenv("SERPER_API_KEY")
        if not api_key:
            return {"success": False, "message": "SERPER_API_KEY is not configured."}

        try:
            import aiohttp
        except ImportError:
            return {"success": False, "message": "aiohttp is required for Serper search."}

        payload = {"q": query, "num": k}
        headers = {
            "X-API-KEY": api_key,
            "Content-Type": "application/json",
        }

        try:
            timeout = aiohttp.ClientTimeout(total=30)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    "https://google.serper.dev/search",
                    json=payload,
                    headers=headers,
                ) as resp:
                    text = await resp.text()
                    if resp.status >= 400:
                        return {"success": False, "message": f"Serper HTTP {resp.status}: {text[:200]}"}
                    data = json.loads(text)
        except Exception as exc:
            return {"success": False, "message": f"Serper search failed: {exc}"}

        snippets = []
        for item in (data.get("organic") or [])[:k]:
            snippet = item.get("snippet")
            link = item.get("link")
            if snippet:
                snippets.append({"content": str(snippet), "source": str(link or "")})

        if not snippets:
            return {"success": False, "message": "Serper returned no usable text results."}

        return {"success": True, "output": json.dumps(snippets, ensure_ascii=False, indent=2)}

    async def _ddgs_search(self, query: str, k: int) -> Dict[str, Any]:
        try:
            from ddgs import DDGS
        except ImportError:
            try:
                from duckduckgo_search import DDGS  # type: ignore
            except ImportError:
                return {
                    "success": False,
                    "message": "DuckDuckGo backend is unavailable. Install `ddgs` or `duckduckgo-search`.",
                }

        try:
            def sync_search():
                with DDGS() as ddgs:
                    return list(ddgs.text(
                        query=query,
                        region="cn-zh",
                        max_results=k,
                    ))
            results = await asyncio.to_thread(sync_search)

        except Exception as exc:
            return {"success": False, "message": f"DDGS搜索失败: {str(exc)}"}

        snippets = []
        for item in (results or [])[:k]:
            body = item.get("body")
            href = item.get("href")
            if body:
                snippets.append({"content": str(body), "source": str(href or "")})

        if not snippets:
            return {"success": False, "message": "DDGS no results"}

        return {"success": True, "output": json.dumps(snippets, ensure_ascii=False, indent=2)}
    
