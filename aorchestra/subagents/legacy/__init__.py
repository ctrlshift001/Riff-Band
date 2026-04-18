"""Legacy benchmark-specific subagents kept for the research stack."""

from aorchestra.subagents.legacy.gaia_agent import OrchestraGAIAAgent
from aorchestra.subagents.legacy.swebench_agent import SWEBenchSubAgent
from aorchestra.subagents.legacy.terminalbench_agent import ReAcTAgent

__all__ = [
    "OrchestraGAIAAgent",
    "SWEBenchSubAgent",
    "ReAcTAgent",
]
