from __future__ import annotations

import json
from contextlib import asynccontextmanager
from typing import Any

try:
    from builtins import BaseExceptionGroup
except ImportError:  # pragma: no cover - Python 3.10 compatibility
    from exceptiongroup import BaseExceptionGroup


class MCPConnectorError(RuntimeError):
    pass


class StreamableHTTPMCPClient:
    """Small async client around the official MCP Python SDK."""

    def __init__(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        timeout_seconds: float = 45,
    ) -> None:
        self.url = url
        self.headers = dict(headers or {})
        self.timeout_seconds = timeout_seconds

    async def list_tools(self) -> list[dict[str, Any]]:
        async with self._session() as session:
            response = await session.list_tools()
            return [
                {
                    "name": tool.name,
                    "description": tool.description or "",
                    "input_schema": tool.inputSchema or {},
                }
                for tool in response.tools
            ]

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        async with self._session() as session:
            response = await session.call_tool(name, arguments)
            content = []
            for block in response.content:
                if hasattr(block, "model_dump"):
                    content.append(block.model_dump(mode="json"))
                else:
                    content.append({"type": "text", "text": str(block)})
            structured = getattr(response, "structuredContent", None)
            return {
                "is_error": bool(response.isError),
                "content": content,
                "structured_content": structured,
                "text": self._content_text(content, structured),
            }

    @staticmethod
    def _content_text(
        content: list[dict[str, Any]],
        structured: Any,
    ) -> str:
        parts = [
            str(item.get("text") or "").strip()
            for item in content
            if item.get("type") == "text" and str(item.get("text") or "").strip()
        ]
        if parts:
            return "\n".join(parts)
        if structured is not None:
            return json.dumps(structured, ensure_ascii=False, default=str)
        return ""

    @asynccontextmanager
    async def _session(self):
        try:
            import httpx
            from mcp import ClientSession
            from mcp.client.streamable_http import streamable_http_client
        except ImportError as exc:
            raise MCPConnectorError(
                "MCP client dependency is unavailable; install `mcp>=1.28,<2`"
            ) from exc

        try:
            async with httpx.AsyncClient(
                headers=self.headers,
                follow_redirects=True,
                timeout=self.timeout_seconds,
            ) as client:
                async with streamable_http_client(
                    self.url,
                    http_client=client,
                ) as (read, write, _):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        yield session
        except MCPConnectorError:
            raise
        except BaseExceptionGroup as exc:
            raise MCPConnectorError(
                f"MCP connection failed: {self._group_message(exc)}"
            ) from exc
        except Exception as exc:
            raise MCPConnectorError(f"MCP connection failed: {exc}") from exc

    @staticmethod
    def _group_message(group: BaseExceptionGroup) -> str:
        messages: list[str] = []

        def collect(error: BaseException) -> None:
            if isinstance(error, BaseExceptionGroup):
                for nested in error.exceptions:
                    collect(nested)
                return
            text = str(error).strip()
            if text and text not in messages:
                messages.append(text)

        collect(group)
        return "; ".join(messages)[:1000] or group.__class__.__name__
