from __future__ import annotations

import os
from typing import Any

from ai4ms.connectors.mcp_client import MCPConnectorError, StreamableHTTPMCPClient


READ_ONLY_TOOLS = {
    "search_indicators",
    "get_observations",
}


class DataCommonsConnector:
    """Read-only connector for Google's hosted Data Commons MCP server."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        url: str | None = None,
        client_factory=None,
    ) -> None:
        self.api_key = (
            api_key
            if api_key is not None
            else os.getenv("AI4MS_DATACOMMONS_API_KEY")
            or os.getenv("DC_API_KEY", "")
        ).strip()
        self.url = (
            url
            or os.getenv(
                "AI4MS_DATACOMMONS_MCP_URL",
                "https://api.datacommons.org/mcp",
            )
        ).strip()
        self.timeout_seconds = float(
            os.getenv("AI4MS_MCP_TIMEOUT_SECONDS", "45")
        )
        self.client_factory = client_factory or StreamableHTTPMCPClient

    def status(self) -> dict[str, Any]:
        configured = bool(self.api_key)
        return {
            "connector_id": "datacommons",
            "name": "Google Data Commons",
            "kind": "mcp",
            "transport": "streamable_http",
            "url": self.url,
            "configured": configured,
            "read_only": True,
            "allowed_tools": sorted(READ_ONLY_TOOLS),
            "reason": (
                ""
                if configured
                else "AI4MS_DATACOMMONS_API_KEY or DC_API_KEY is not configured"
            ),
        }

    async def list_tools(self) -> list[dict[str, Any]]:
        self._require_configured()
        tools = await self._client().list_tools()
        return [tool for tool in tools if tool["name"] in READ_ONLY_TOOLS]

    async def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        self._require_configured()
        if tool_name not in READ_ONLY_TOOLS:
            raise MCPConnectorError(
                f"Data Commons tool is not in the read-only allowlist: {tool_name}"
            )
        result = await self._client().call_tool(tool_name, arguments)
        if result.get("is_error"):
            raise MCPConnectorError(
                str(result.get("text") or f"{tool_name} returned an MCP error")[:1000]
            )
        return {
            "connector_id": "datacommons",
            "tool_name": tool_name,
            "arguments": arguments,
            "result": result,
        }

    async def search_indicators(self, query: str) -> dict[str, Any]:
        tools = await self.list_tools()
        tool = next(
            (item for item in tools if item["name"] == "search_indicators"),
            None,
        )
        if tool is None:
            raise MCPConnectorError(
                "Data Commons MCP server did not expose search_indicators"
            )
        arguments = self._query_arguments(tool.get("input_schema") or {}, query)
        return await self.call_tool("search_indicators", arguments)

    @staticmethod
    def _query_arguments(schema: dict[str, Any], query: str) -> dict[str, Any]:
        properties = schema.get("properties")
        properties = properties if isinstance(properties, dict) else {}
        required = schema.get("required")
        required = required if isinstance(required, list) else []
        candidates = (
            "query",
            "queries",
            "prompt",
            "question",
            "text",
            "description",
        )
        for name in candidates:
            definition = properties.get(name)
            if not isinstance(definition, dict):
                continue
            if definition.get("type") == "array":
                return {name: [query]}
            return {name: query}
        if len(required) == 1:
            name = str(required[0])
            definition = properties.get(name, {})
            return {name: [query] if definition.get("type") == "array" else query}
        raise MCPConnectorError(
            "cannot infer the natural-language query field from MCP tool schema"
        )

    def _client(self):
        return self.client_factory(
            self.url,
            headers={"X-API-Key": self.api_key},
            timeout_seconds=self.timeout_seconds,
        )

    def _require_configured(self) -> None:
        if not self.api_key:
            raise MCPConnectorError(self.status()["reason"])


__all__ = ["DataCommonsConnector", "MCPConnectorError"]
