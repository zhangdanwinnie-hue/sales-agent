from __future__ import annotations

import unittest

from bp_ba_agent.analysis_topics import get_analysis_topic, list_analysis_topics, recommend_topics


class AnalysisTopicsTests(unittest.TestCase):
    def test_topic_registry_contains_expected_themes(self) -> None:
        topics = list_analysis_topics()
        keys = {topic["key"] for topic in topics}

        self.assertEqual(len(topics), 13)
        self.assertIn("sales_funnel_conversion", keys)
        self.assertIn("media_channel_efficiency", keys)
        self.assertIn("conversion_cycle_analysis", keys)
        self.assertIn("loyal_customer_new_car_sales", keys)
        self.assertIn("single_stage_review", keys)
        self.assertIn("data_quality_reconciliation", keys)

    def test_topic_has_required_fields_and_cautions(self) -> None:
        topic = get_analysis_topic("media_channel_efficiency")

        self.assertIn("leads_channel_name", topic.required_fields)
        self.assertIn("order_id", topic.required_fields)
        self.assertTrue(topic.core_metrics)
        self.assertTrue(topic.cautions)

    def test_recommend_topics_returns_relevant_topic(self) -> None:
        topics = recommend_topics("分析汽车之家线索多但订单转化低的原因")
        keys = [topic.key for topic in topics]

        self.assertEqual(keys[0], "media_channel_efficiency")

    def test_recommend_topics_for_added_frameworks(self) -> None:
        self.assertEqual(recommend_topics("分析线上线索到到店、到店到订单的转化周期")[0].key, "conversion_cycle_analysis")
        self.assertEqual(recommend_topics("做一个保客再购和保客到店转化分析")[0].key, "loyal_customer_new_car_sales")
        self.assertEqual(recommend_topics("复盘客流下降，区分自然客流下降和线上客流下降")[0].key, "single_stage_review")


if __name__ == "__main__":
    unittest.main()
