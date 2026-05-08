from __future__ import annotations

import unittest
from pathlib import Path

from config import AgentConfig
from research import ResearchRequest, run_research


class TestResearchMode(unittest.IsolatedAsyncioTestCase):
    def test_request_requires_topic(self):
        with self.assertRaises(ValueError):
            ResearchRequest(topic="")

    async def test_run_research_returns_stable_placeholder_result(self):
        cfg = AgentConfig(
            main_model="test-model",
            sub_models=["test-model"],
            sources_dir=Path("workspace/sources"),
        )
        request = ResearchRequest(topic="Zimbabwe economic history", trigger="cli")

        result = await run_research(request, cfg)

        self.assertEqual(result.status, "partial")
        self.assertIn("not been implemented", result.summary)
        self.assertEqual(result.metadata["topic"], request.topic)
        self.assertEqual(result.metadata["trigger"], "cli")


if __name__ == "__main__":
    unittest.main()
