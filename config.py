from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


VALID_MODES = {"single", "multi", "auto"}


@dataclass
class AgentConfig:
    main_model: str
    sub_models: list[str]
    sources_dir: Path
    workspace_dir: Path = Path("workspace")
    max_attempts: int = 6
    max_subagent_steps: int = 10
    subagent_process_timeout_seconds: int = 180
    mode: str = "auto"
    profile_name: str = "generic"

    @classmethod
    def load(cls, config_path: str | Path) -> "AgentConfig":
        config_path = Path(config_path)
        with config_path.open("r", encoding="utf-8") as handle:
            raw = yaml.safe_load(handle) or {}

        mode = str(raw.get("mode", "auto")).strip().lower() or "auto"
        if mode not in VALID_MODES:
            raise ValueError(f"Invalid mode `{mode}`. Supported modes are: single, multi, auto.")

        workspace_raw = raw.get("workspace_dir", "workspace")
        workspace_dir = _resolve_path(config_path, str(workspace_raw)) if workspace_raw else Path("workspace")

        return cls(
            main_model=str(raw["main_model"]),
            sub_models=[str(item) for item in (raw.get("sub_models") or [str(raw["main_model"])])],
            sources_dir=_resolve_path(config_path, raw["sources_dir"]),
            workspace_dir=workspace_dir,
            max_attempts=int(raw.get("max_attempts", 6)),
            max_subagent_steps=int(raw.get("max_subagent_steps", 10)),
            subagent_process_timeout_seconds=int(raw.get("subagent_process_timeout_seconds", 180)),
            mode=mode,
            profile_name=str(raw.get("profile_name", "generic")).strip() or "generic",
        )


def _resolve_path(config_path: Path, raw_path: str) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        return path
    return (config_path.parent / path).resolve()


# Backward compatibility alias
GBAAnalysisConfig = AgentConfig
