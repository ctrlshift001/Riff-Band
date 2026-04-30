"""AOrchestra interactive shell entry point."""
import sys
from pathlib import Path

SRC_PATH = Path(__file__).resolve().parent / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from ui.shell import main
import asyncio

if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
