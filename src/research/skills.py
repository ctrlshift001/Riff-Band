from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


SKILLS_DIR = Path(__file__).resolve().parent / "skills"


@dataclass(frozen=True)
class ResearchSkill:
    name: str
    path: Path
    text: str


class ResearchSkillRegistry:
    """Loads markdown skills used by the fixed research workflow."""

    def __init__(self, skills_dir: Path = SKILLS_DIR):
        self.skills_dir = skills_dir

    def load(self, name: str) -> ResearchSkill:
        path = self.skills_dir / f"{name}.md"
        if not path.exists():
            raise FileNotFoundError(f"Research skill not found: {path}")
        return ResearchSkill(name=name, path=path, text=path.read_text(encoding="utf-8"))

    def load_text(self, name: str) -> str:
        return self.load(name).text
