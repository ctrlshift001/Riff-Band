from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from pydantic import ValidationError

from config import AgentConfig
from research import ResearchRequest, run_research


JSONRPC_VERSION = "2.0"
MCP_PROTOCOL_VERSION = "2024-11-05"
ERROR_CODE_CANCELLED = -32000


class RiffBandMCPServer:
    """Minimal stdio MCP server for Riff Band.

    The server intentionally avoids an SDK dependency for now. It implements the
    small JSON-RPC surface needed by MCP clients to discover and call tools.
    """

    def __init__(self, config_path: str | Path = "aorchestra.yaml"):
        load_dotenv()
        self.config_path = Path(config_path)
        self.config = AgentConfig.load(self.config_path)
        self._current_task: asyncio.Task | None = None

    @staticmethod
    def _success(request_id: Any, result: dict[str, Any]) -> dict[str, Any]:
        return {"jsonrpc": JSONRPC_VERSION, "id": request_id, "result": result}

    @staticmethod
    def _error(request_id: Any, code: int, message: str, data: Any = None) -> dict[str, Any]:
        error: dict[str, Any] = {"code": code, "message": message}
        if data is not None:
            error["data"] = data
        return {"jsonrpc": JSONRPC_VERSION, "id": request_id, "error": error}

    @staticmethod
    def _text_content(text: str) -> list[dict[str, str]]:
        return [{"type": "text", "text": text}]

    def _emit_progress(self, message: str) -> None:
        """Emit a progress notification on stdout for MCP clients."""
        notification = {
            "jsonrpc": JSONRPC_VERSION,
            "method": "notifications/progress",
            "params": {"message": message},
        }
        sys.stdout.write(json.dumps(notification, ensure_ascii=False) + "\n")
        sys.stdout.flush()

    def _tool_definitions(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "research",
                "description": (
                    "Run Riff Band fixed research pipeline for a topic. "
                    "Supports two modes: academic (9-step literature review, "
                    "outputs paper.tex + references.bib) and visual "
                    "(10-step general research, outputs report_visual.html "
                    "with ECharts, TOC, dark/light toggle)."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "topic": {
                            "type": "string",
                            "description": "Research topic or question.",
                        },
                        "mode": {
                            "type": "string",
                            "enum": ["academic", "visual"],
                            "default": "academic",
                        },
                        "depth": {
                            "type": "string",
                            "enum": ["quick", "standard", "deep"],
                            "default": "standard",
                        },
                        "output_format": {
                            "type": "string",
                            "enum": ["markdown", "latex", "html", "json"],
                            "default": "latex",
                        },
                        "sources": {
                            "type": "array",
                            "items": {"type": "string"},
                            "default": [],
                        },
                        "constraints": {
                            "type": "string",
                            "default": "",
                        },
                    },
                    "required": ["topic"],
                },
            },
            {
                "name": "cancel_research",
                "description": "Cancel the currently running research task.",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                },
            },
        ]

    async def handle_request(self, message: dict[str, Any]) -> dict[str, Any] | None:
        method = str(message.get("method", ""))
        request_id = message.get("id")
        params = message.get("params") or {}

        # Notifications do not require responses.
        if request_id is None and method in {"notifications/initialized", "initialized"}:
            return None

        if method == "initialize":
            return self._success(
                request_id,
                {
                    "protocolVersion": MCP_PROTOCOL_VERSION,
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "riff-band", "version": "0.1.0"},
                },
            )

        if method == "ping":
            return self._success(request_id, {})

        if method == "tools/list":
            return self._success(request_id, {"tools": self._tool_definitions()})

        if method == "tools/call":
            return await self._handle_tool_call(request_id, params)

        if method == "resources/list":
            return self._success(request_id, {"resources": []})

        if method == "prompts/list":
            return self._success(request_id, {"prompts": []})

        return self._error(request_id, -32601, f"Method not found: {method}")

    async def _handle_tool_call(self, request_id: Any, params: dict[str, Any]) -> dict[str, Any]:
        name = str(params.get("name", ""))
        arguments = params.get("arguments") or {}

        if name == "cancel_research":
            return self._handle_cancel(request_id)

        if name != "research":
            return self._error(request_id, -32602, f"Unknown tool: {name}")
        if not isinstance(arguments, dict):
            return self._error(request_id, -32602, "Tool arguments must be an object.")

        try:
            request = ResearchRequest(
                topic=arguments.get("topic", ""),
                mode=arguments.get("mode", "academic"),
                depth=arguments.get("depth", "standard"),
                output_format=arguments.get("output_format", "latex"),
                sources=list(arguments.get("sources") or []),
                constraints=str(arguments.get("constraints", "") or ""),
                trigger="mcp",
                metadata={
                    "mcp_tool": name,
                    "config_path": str(self.config_path),
                },
            )
        except (TypeError, ValidationError, ValueError) as exc:
            return self._success(
                request_id,
                {
                    "content": self._text_content(f"Invalid research request: {exc}"),
                    "isError": True,
                },
            )

        try:
            self._current_task = asyncio.current_task()
            self._emit_progress(f"Research started: {request.topic!r} mode={request.mode}")
            result = await run_research(
                request, self.config, progress_callback=self._emit_progress
            )
        except asyncio.CancelledError:
            self._emit_progress("Research cancelled by client")
            return self._error(request_id, ERROR_CODE_CANCELLED, "Research cancelled")
        finally:
            self._current_task = None

        payload = result.model_dump()
        return self._success(
            request_id,
            {
                "content": self._text_content(
                    json.dumps(payload, ensure_ascii=False, indent=2)
                ),
                "structuredContent": payload,
                "isError": result.status == "blocked",
            },
        )

    def _handle_cancel(self, request_id: Any) -> dict[str, Any]:
        if self._current_task is not None and not self._current_task.done():
            self._current_task.cancel()
            return self._success(request_id, {"cancelled": True})
        return self._success(request_id, {"cancelled": False, "reason": "No running research"})

    async def serve_stdio(self) -> int:
        for raw_line in sys.stdin:
            line = raw_line.strip()
            if not line:
                continue
            try:
                message = json.loads(line)
            except json.JSONDecodeError as exc:
                response = self._error(None, -32700, "Parse error", str(exc))
            else:
                if not isinstance(message, dict):
                    response = self._error(None, -32600, "Invalid Request")
                else:
                    response = await self.handle_request(message)
            if response is None:
                continue
            sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
            sys.stdout.flush()
        return 0


async def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Riff Band MCP stdio server")
    parser.add_argument("--config", default="aorchestra.yaml", help="Path to config YAML")
    args = parser.parse_args(argv)

    server = RiffBandMCPServer(args.config)
    return await server.serve_stdio()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
else:
    def _entry():
        raise SystemExit(asyncio.run(main()))
