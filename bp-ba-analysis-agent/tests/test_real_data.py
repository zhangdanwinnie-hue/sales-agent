from __future__ import annotations

import csv
import tempfile
import unittest
import zipfile
from pathlib import Path

from bp_ba_agent.real_data import RealSalesFunnelAnalyzer


class RealSalesFunnelAnalyzerTests(unittest.TestCase):
    def test_analyzer_builds_aggregate_report_without_detail_export(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            zip_path = Path(tmp) / "demo.zip"
            csv_path = Path(tmp) / "demo.csv"
            fields = [
                "register_rcid",
                "leads_id",
                "oppty_id",
                "visit_id",
                "td_id",
                "order_id",
                "register_create_time",
                "leads_create_time",
                "oppty_create_time",
                "visit_arrival_time",
                "td_start_time",
                "order_first_confirm_time",
                "region_route",
                "brand_route",
                "leads_channel_name",
                "leads_media_platform_name",
                "register_model",
                "customer_mobile_phone_number",
            ]
            rows = [
                {
                    "register_rcid": "r1",
                    "leads_id": "l1",
                    "oppty_id": "o1",
                    "visit_id": "v1",
                    "td_id": "t1",
                    "order_id": "ord1",
                    "register_create_time": "2026-01-01 10:00:00",
                    "leads_create_time": "2026-01-01 10:01:00",
                    "oppty_create_time": "2026-01-01 10:02:00",
                    "visit_arrival_time": "2026-01-02 10:00:00",
                    "td_start_time": "2026-01-02 11:00:00",
                    "order_first_confirm_time": "2026-01-03 10:00:00",
                    "region_route": "East",
                    "brand_route": "BMW",
                    "leads_channel_name": "Paid Media",
                    "leads_media_platform_name": "Platform A",
                    "register_model": "Model A",
                    "customer_mobile_phone_number": "13800000000",
                },
                {
                    "register_rcid": "r2",
                    "leads_id": "l2",
                    "oppty_id": "",
                    "visit_id": "",
                    "td_id": "",
                    "order_id": "",
                    "register_create_time": "2026-01-02 10:00:00",
                    "leads_create_time": "2026-01-02 10:01:00",
                    "oppty_create_time": "",
                    "visit_arrival_time": "",
                    "td_start_time": "",
                    "order_first_confirm_time": "",
                    "region_route": "East",
                    "brand_route": "BMW",
                    "leads_channel_name": "Paid Media",
                    "leads_media_platform_name": "Platform A",
                    "register_model": "Model B",
                    "customer_mobile_phone_number": "13900000000",
                },
            ]
            with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fields)
                writer.writeheader()
                writer.writerows(rows)
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
                archive.write(csv_path, "demo.csv")

            report = RealSalesFunnelAnalyzer(zip_path).analyze()

        self.assertEqual(report.total_rows, 2)
        self.assertEqual(report.stage_counts["register"], 2)
        self.assertEqual(report.stage_counts["order"], 1)
        self.assertEqual(report.conversion_rates["order_per_leads"], 0.5)
        self.assertEqual(report.top_dimensions["channel"][0]["value"], "Paid Media")
        self.assertGreaterEqual(report.data_quality["sensitive_column_count"], 1)
        self.assertIn("analysis_case", report.to_dict())


if __name__ == "__main__":
    unittest.main()
