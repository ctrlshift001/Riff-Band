from __future__ import annotations

import json
import asyncio
from pathlib import Path

from mcp_server import RiffBandMCPServer


def _write_config(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "main_model: test-model",
                "sub_models:",
                "  - test-model",
                "sources_dir: workspace/sources",
                "workspace_dir: workspace",
                "mode: auto",
                "profile_name: generic",
            ]
        ),
        encoding="utf-8",
    )


def test_mcp_initialize_and_list_tools(tmp_path):
    config_path = tmp_path / "aorchestra.yaml"
    _write_config(config_path)
    server = RiffBandMCPServer(config_path)

    init_response = asyncio.run(
        server.handle_request(
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
        )
    )
    assert init_response["result"]["capabilities"]["tools"] == {}

    tools_response = asyncio.run(
        server.handle_request(
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
        )
    )
    tools = tools_response["result"]["tools"]
    assert [tool["name"] for tool in tools] == ["research"]
    assert tools[0]["inputSchema"]["required"] == ["topic"]


def test_mcp_research_tool_calls_internal_boundary(tmp_path):
    config_path = tmp_path / "aorchestra.yaml"
    _write_config(config_path)
    server = RiffBandMCPServer(config_path)

    response = asyncio.run(
        server.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "research",
                    "arguments": {
                        "topic": "low altitude economy in the Greater Bay Area",
                        "depth": "quick",
                    },
                },
            }
        )
    )

    result = response["result"]
    assert result["isError"] is False
    payload = json.loads(result["content"][0]["text"])
    assert payload["metadata"]["trigger"] == "mcp"
    assert payload["metadata"]["topic"] == "low altitude economy in the Greater Bay Area"
    assert result["structuredContent"]["status"] == "partial"
