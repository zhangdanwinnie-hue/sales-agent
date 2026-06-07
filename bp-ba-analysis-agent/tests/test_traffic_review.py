from __future__ import annotations

import csv
import tempfile
import unittest
import zipfile
from pathlib import Path

from bp_ba_agent.traffic_review import TrafficDeclineAnalyzer, write_html, write_markdown


class TrafficDeclineAnalyzerTests(unittest.TestCase):
    def test_defaults_to_latest_complete_month_before_partial_month(self) -> None:
        zip_path = self._build_demo_zip()

        report = TrafficDeclineAnalyzer(zip_path).analyze()

        self.assertEqual(report.previous_month, "2026-03")
        self.assertEqual(report.current_month, "2026-04")
        self.assertEqual(report.previous_visits, 3)
        self.assertEqual(report.current_visits, 1)
        self.assertEqual(report.delta, -2)
        self.assertEqual(report.change_rate, -0.6667)
        self.assertIn("线上", report.traffic_type_delta[0]["value"])
        self.assertEqual(report.traffic_type_delta[0]["delta"], -2)

    def test_writes_standalone_report_files(self) -> None:
        zip_path = self._build_demo_zip()
        report = TrafficDeclineAnalyzer(zip_path, current_month="2026-04", previous_month="2026-03").analyze()

        with tempfile.TemporaryDirectory() as tmp:
            md_path = Path(tmp) / "traffic.md"
            html_path = Path(tmp) / "traffic.html"
            write_markdown(report, md_path)
            write_html(report, html_path)

            self.assertIn("客流下降", md_path.read_text(encoding="utf-8"))
            self.assertIn("<html", html_path.read_text(encoding="utf-8"))

    def _build_demo_zip(self) -> Path:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        zip_path = root / "traffic.zip"
        csv_path = root / "traffic.csv"
        fields = [
            "visit_id",
            "visit_arrival_time",
            "visit_is_nature_sr_flag",
            "region_route",
            "city_name_zh",
            "visit_dealer_id",
            "leads_channel_name",
            "leads_media_platform_name",
            "register_model",
            "dealer_status_name",
        ]
        rows = [
            self._row("v1", "2026-03-02 10:00:00", "Y", "East", "Shanghai", "D001", "DMO", "Platform A", "Model A"),
            self._row("v2", "2026-03-03 10:00:00", "N", "East", "Shanghai", "D001", "Autohome", "Platform B", "Model A"),
            self._row("v3", "2026-03-04 10:00:00", "N", "West", "Chengdu", "D002", "DMO", "Platform A", "Model B"),
            self._row("v4", "2026-04-02 10:00:00", "Y", "East", "Shanghai", "D001", "DMO", "Platform A", "Model A"),
            self._row("v5", "2026-05-02 10:00:00", "Y", "West", "Chengdu", "D002", "DMO", "Platform A", "Model B"),
        ]
        with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.write(csv_path, "traffic.csv")
        return zip_path

    @staticmethod
    def _row(
        visit_id: str,
        visit_time: str,
        natural_flag: str,
        region: str,
        city: str,
        dealer: str,
        channel: str,
        platform: str,
        model: str,
    ) -> dict[str, str]:
        return {
            "visit_id": visit_id,
            "visit_arrival_time": visit_time,
            "visit_is_nature_sr_flag": natural_flag,
            "region_route": region,
            "city_name_zh": city,
            "visit_dealer_id": dealer,
            "leads_channel_name": channel,
            "leads_media_platform_name": platform,
            "register_model": model,
            "dealer_status_name": "营业中",
        }


if __name__ == "__main__":
    unittest.main()
