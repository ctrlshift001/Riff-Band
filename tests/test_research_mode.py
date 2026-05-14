from __future__ import annotations

import unittest
from pathlib import Path

from config import AgentConfig
from research import ResearchRequest, run_research


class TestResearchMode(unittest.IsolatedAsyncioTestCase):
    def test_request_requires_topic(self):
        with self.assertRaises(ValueError):
            ResearchRequest(topic="")

    async def test_run_research_returns_pipeline_result(self):
        cfg = AgentConfig(
            main_model="test-model",
            sub_models=["test-model"],
            sources_dir=Path("workspace/sources"),
        )
        request = ResearchRequest(topic="Zimbabwe economic history", trigger="cli")

        result = await run_research(request, cfg)

        # With a fake model LLM config is unavailable, so pipeline falls back to
        # offline scaffold mode and returns partial because gates fail.
        self.assertIn(result.status, {"done", "partial"})
        self.assertTrue(len(result.steps) > 0)
        self.assertEqual(result.metadata["topic"], request.topic)
        self.assertEqual(result.metadata["trigger"], "cli")
        # Offline mode: no live agent execution, so final gate reports issues.
        self.assertTrue(len(result.open_issues) > 0)


if __name__ == "__main__":
    unittest.main()
