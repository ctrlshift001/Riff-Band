from __future__ import annotations

import json
import asyncio
import io
import sys
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
    tool_names = [tool["name"] for tool in tools]
    assert "research" in tool_names
    assert "cancel_research" in tool_names
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


def test_mcp_research_visual_mode(tmp_path):
    config_path = tmp_path / "aorchestra.yaml"
    _write_config(config_path)
    server = RiffBandMCPServer(config_path)

    response = asyncio.run(
        server.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "research",
                    "arguments": {
                        "topic": "AI trends 2026",
                        "mode": "visual",
                        "depth": "quick",
                        "output_format": "html",
                    },
                },
            }
        )
    )

    result = response["result"]
    assert result["isError"] is False
    payload = json.loads(result["content"][0]["text"])
    assert payload["metadata"]["mode"] == "visual"
    artifact_paths = [a["path"] for a in payload["artifacts"]]
    assert any("report_visual.html" in p for p in artifact_paths)


def test_mcp_cancel_research_idle(tmp_path):
    config_path = tmp_path / "aorchestra.yaml"
    _write_config(config_path)
    server = RiffBandMCPServer(config_path)

    response = asyncio.run(
        server.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {
                    "name": "cancel_research",
                    "arguments": {},
                },
            }
        )
    )

    result = response["result"]
    assert result["cancelled"] is False
    assert "No running research" in result["reason"]


def test_mcp_progress_notification_format():
    server = RiffBandMCPServer.__new__(RiffBandMCPServer)

    captured = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = captured
    try:
        server._emit_progress("test progress message")
    finally:
        sys.stdout = old_stdout

    output = captured.getvalue().strip()
    notification = json.loads(output)
    assert notification["jsonrpc"] == "2.0"
    assert "id" not in notification  # notifications have no id
    assert notification["method"] == "notifications/progress"
    assert notification["params"]["message"] == "test progress message"


def test_mcp_tool_description_includes_visual():
    config_path = Path("dummy.yaml")
    server = RiffBandMCPServer.__new__(RiffBandMCPServer)

    # Mock _tool_definitions by calling it on a bare instance
    # Since _tool_definitions doesn't use self attributes, we can call it
    tools = server._tool_definitions()
    research_tool = [t for t in tools if t["name"] == "research"][0]
    desc = research_tool["description"]
    assert "visual" in desc.lower()
    assert "report_visual.html" in desc


def test_mcp_research_invalid_mode_rejected(tmp_path):
    config_path = tmp_path / "aorchestra.yaml"
    _write_config(config_path)
    server = RiffBandMCPServer(config_path)

    response = asyncio.run(
        server.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 6,
                "method": "tools/call",
                "params": {
                    "name": "research",
                    "arguments": {
                        "topic": "test",
                        "mode": "invalid_mode",
                    },
                },
            }
        )
    )

    assert response["result"]["isError"] is True


def test_mcp_error_on_empty_topic(tmp_path):
    config_path = tmp_path / "aorchestra.yaml"
    _write_config(config_path)
    server = RiffBandMCPServer(config_path)

    response = asyncio.run(
        server.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 7,
                "method": "tools/call",
                "params": {
                    "name": "research",
                    "arguments": {
                        "mode": "academic",
                    },
                },
            }
        )
    )

    assert response["result"]["isError"] is True
