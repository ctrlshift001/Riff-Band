from __future__ import annotations

import unittest

from project.build_project import _default_model_routing, _default_subtask_toolkits, _default_worker_tools


class TestBriefInjection(unittest.TestCase):
    def test_toolkits_do_not_include_read_brief(self):
        toolkits = _default_subtask_toolkits()
        for tools in toolkits.values():
            self.assertNotIn("read_brief", tools)

    def test_default_worker_tools_are_general_purpose(self):
        tools = _default_worker_tools()
        self.assertIn("read_source", tools)
        self.assertIn("record_finding", tools)
        self.assertIn("write_report_section", tools)
        self.assertIn("verify_artifacts", tools)

    def test_default_model_routing_uses_second_submodel_when_available(self):
        routing = _default_model_routing(["moonshot-v1-32k", "Gemini-2.5-Flash-Lite"])
        self.assertEqual(routing["policy_research"], "moonshot-v1-32k")
        self.assertEqual(routing["financial_metrics"], "moonshot-v1-32k")
        self.assertEqual(routing["general_research"], "Gemini-2.5-Flash-Lite")
        self.assertEqual(routing["news_signals"], "Gemini-2.5-Flash-Lite")


if __name__ == "__main__":
    unittest.main()
