from __future__ import annotations

import unittest

from project.build_project import _default_model_routing, _default_subtask_toolkits


class TestBriefInjection(unittest.TestCase):
    def test_toolkits_do_not_include_read_brief(self):
        toolkits = _default_subtask_toolkits()
        for tools in toolkits.values():
            self.assertNotIn("read_brief", tools)

    def test_default_model_routing_uses_second_submodel_when_available(self):
        routing = _default_model_routing(["moonshot-v1-32k", "Gemini-2.5-Flash-Lite"])
        self.assertEqual(routing["policy_research"], "moonshot-v1-32k")
        self.assertEqual(routing["financial_metrics"], "moonshot-v1-32k")
        self.assertEqual(routing["general_research"], "Gemini-2.5-Flash-Lite")
        self.assertEqual(routing["news_signals"], "Gemini-2.5-Flash-Lite")


if __name__ == "__main__":
    unittest.main()
