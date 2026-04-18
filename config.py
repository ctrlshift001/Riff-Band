from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class GBAAnalysisConfig:
    main_model: str
    sub_models: list[str]

    #brief_path: Path
    sources_dir: Path 

    # output
    #output_dir: Path
    max_attempts: int = 6
    max_subagent_steps: int = 10

    @classmethod
    def load(cls, config_path: str | Path) -> "GBAAnalysisConfig":
        config_path = Path(config_path)
        with config_path.open("r", encoding="utf-8") as handle:
            raw = yaml.safe_load(handle) or {}

        return cls(
            main_model=str(raw["main_model"]),
            sub_models=[str(item) for item in raw["sub_models"]],
            # brief_path=_resolve_path(config_path, raw["brief_path"]),
            sources_dir=_resolve_path(config_path, raw["sources_dir"]),
            # output_dir=_resolve_path(config_path, raw["output_dir"]),
            max_attempts=int(raw.get("max_attempts", 6)),
            max_subagent_steps=int(raw.get("max_subagent_steps", 10)),
        )


def _resolve_path(config_path: Path, raw_path: str) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        return path
    return (config_path.parent / path).resolve()
