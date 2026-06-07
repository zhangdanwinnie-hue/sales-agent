from __future__ import annotations

import unittest

from bp_ba_agent import BPBAAnalysisAgent


class BPBAAnalysisAgentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.agent = BPBAAnalysisAgent()

    def test_media_case_generates_end_to_end_analysis_case(self) -> None:
        case = self.agent.run(
            "媒体投流转化下降，想定位渠道和归因问题",
            scenario="media",
            time_range="2026年4月",
            target_object="华东大区",
        )

        self.assertEqual(case.scenario, "media")
        self.assertGreaterEqual(len(case.metric_tree), 5)
        self.assertTrue(any(metric.name == "平均归因订单贡献" for metric in case.metric_tree))
        self.assertTrue(case.sql_plan)
        self.assertTrue(case.validation_plan)
        self.assertIsNotNone(case.deliverable)
        self.assertTrue(case.human_review_checkpoints)

    def test_target_steering_uses_target_delivery_template(self) -> None:
        case = self.agent.run(
            "Target steering 月度订单目标如何拆解到大区和车型",
            scenario="target_steering",
        )

        self.assertEqual(case.scenario, "target_steering")
        self.assertTrue(any(metric.name == "目标达成率" for metric in case.metric_tree))
        self.assertIsNotNone(case.deliverable)
        assert case.deliverable is not None
        self.assertIn("Target Breakdown", case.deliverable.excel_tabs)
        self.assertIn("月度目标全景", case.deliverable.ppt_storyline)

    def test_missing_scope_creates_clarification_questions(self) -> None:
        case = self.agent.run("分析车型转化问题", scenario="model_conversion")

        self.assertTrue(any("分析目的" in item for item in case.clarification_questions))
        self.assertTrue(any("目标对象" in item for item in case.clarification_questions))
        self.assertTrue(any("分析周期" in item for item in case.clarification_questions))
        self.assertTrue(case.dimensions)

    def test_data_access_is_read_only(self) -> None:
        case = self.agent.run("经销商运营表现异常", scenario="dealer_operation")

        self.assertGreaterEqual(len(case.data_sources), 3)
        self.assertTrue(all(source.read_only for source in case.data_sources))
        self.assertTrue(any(source.source_type == "warehouse" for source in case.data_sources))
        self.assertTrue(any(source.source_type == "bi_metadata" for source in case.data_sources))
        self.assertTrue(any(source.source_type == "knowledge_base" for source in case.data_sources))


if __name__ == "__main__":
    unittest.main()
