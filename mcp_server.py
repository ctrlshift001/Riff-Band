"""Compatibility entry point for the Riff Band MCP stdio server."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

SRC_PATH = Path(__file__).resolve().parent / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from mcp_server import main


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
