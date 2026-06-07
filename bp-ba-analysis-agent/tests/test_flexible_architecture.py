from __future__ import annotations

import unittest

from bp_ba_agent import BPBAAnalysisAgent
from bp_ba_agent.method_library import detect_question_types, select_methods
from bp_ba_agent.semantic_layer import build_semantic_matches


class FlexibleArchitectureTests(unittest.TestCase):
    def test_question_type_detection_combines_multiple_methods(self) -> None:
        question_types = detect_question_types("为什么 4 月订单下降，需要按区域、经销商和渠道拆解原因")
        method_keys = [method.key for method in select_methods("为什么 4 月订单下降，需要按区域、经销商和渠道拆解原因")]

        self.assertIn("指标变化解释", [item.title for item in question_types])
        self.assertIn("原因诊断", [item.title for item in question_types])
        self.assertIn("trend_analysis", method_keys)
        self.assertIn("contribution_analysis", method_keys)
        self.assertIn("funnel_analysis", method_keys)

    def test_semantic_layer_marks_available_and_missing_fields(self) -> None:
        matches = build_semantic_matches(
            question="分析订单下降和经销商承接问题",
            method_object_keys=["target_metric", "geo_dimension"],
            requested_dimensions=["大区", "经销商", "渠道"],
            available_fields=["order_id", "order_create_time", "leads_dealer_id"],
        )

        order_match = next(item for item in matches if item.business_object == "订单")
        dealer_match = next(item for item in matches if item.business_object == "经销商")

        self.assertEqual(order_match.status, "partially_available")
        self.assertIn("order_id", order_match.available_fields)
        self.assertIn("order_first_confirm_time", order_match.missing_fields)
        self.assertIn("大区", dealer_match.matched_dimensions)

    def test_agent_case_contains_question_methods_and_data_availability(self) -> None:
        case = BPBAAnalysisAgent().run(
            "为什么 4 月订单下降？判断是渠道、区域、经销商承接还是转化效率的问题",
            time_range="2026-04 vs 2026-03",
            target_object="全国",
            dimensions=["月份", "大区", "城市", "经销商", "渠道", "车型"],
            available_fields=["order_id", "order_create_time", "leads_id", "leads_create_time", "leads_channel_name"],
        )

        self.assertTrue(case.question_types)
        self.assertTrue(case.selected_methods)
        self.assertTrue(case.semantic_matches)
        self.assertTrue(case.data_availability)
        self.assertTrue(any(item.status in {"available", "partially_available"} for item in case.data_availability))


if __name__ == "__main__":
    unittest.main()
