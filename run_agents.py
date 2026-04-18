from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent
SRC_PATH = REPO_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from base.engine.logs import logger
from config import GBAAnalysisConfig
from project import build_gba_analysis_project


def _read_task_from_terminal() -> str:
    if not sys.stdin.isatty():
        return sys.stdin.read().strip()

    print("请输入任务内容，输入空行表示结束:")
    lines: list[str] = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if not line.strip():
            break
        lines.append(line)
    return "\n".join(lines).strip()


async def main() -> int:
    load_dotenv()

    parser = argparse.ArgumentParser(description="运行粤港澳大湾区产业分析智能体工作流")
    parser.add_argument("--config", required=True, help="配置文件路径")
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("Aorchestra for GBA Industry Analysis")
    logger.info("=" * 60)

    cfg = GBAAnalysisConfig.load(args.config)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    cfg.timestamp = timestamp

    task_input = _read_task_from_terminal()
    if not task_input:
        raise ValueError("终端输入内容为空，请提供任务内容。")

    output_dir = (Path("workspace") / "output").resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    logger.info("任务已从终端输入加载")
    logger.info(f"报告输出目录: {output_dir}")

    project = build_gba_analysis_project(
        main_model=cfg.main_model,
        sub_models=cfg.sub_models,
        brief_text=task_input,
        sources_dir=cfg.sources_dir,
        output_dir=output_dir,
        max_attempts=cfg.max_attempts,
        max_subagent_steps=cfg.max_subagent_steps,
    )
    result = await project.run()
    # print(result.get("final_result"))
    return 0


if __name__ == "__main__":
    raise sys.exit(asyncio.run(main()))
