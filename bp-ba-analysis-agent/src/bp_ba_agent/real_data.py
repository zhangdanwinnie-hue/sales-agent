"""Streaming demo analyzer for the real register-to-order sales CSV zip."""

from __future__ import annotations

import argparse
import csv
import io
import json
import zipfile
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable

from .agent import BPBAAnalysisAgent
from .analysis_topics import list_analysis_topics, recommend_topics


STAGE_COLUMNS = {
    "register": "register_rcid",
    "leads": "leads_id",
    "oppty": "oppty_id",
    "visit": "visit_id",
    "td": "td_id",
    "order": "order_id",
}

TIME_COLUMNS = [
    "register_create_time",
    "leads_create_time",
    "oppty_create_time",
    "visit_arrival_time",
    "td_start_time",
    "order_first_confirm_time",
]

DIMENSION_COLUMNS = {
    "region": ["region_route", "region_name_zh", "sales_bmw_big_area_name_zh"],
    "brand": ["brand_route", "register_brand_code", "leads_interested_brand_code"],
    "channel": ["leads_channel_name", "register_first_channel_name", "leads_sub_channel_name"],
    "media": ["leads_media_platform_name", "register_media_platform_name"],
    "campaign": ["leads_campaign_name", "register_campaign_name"],
    "model": ["register_model", "leads_model_code_ssc", "order_model_code_ssc"],
    "dealer_status": ["dealer_status_name", "risk_dealer_type"],
}

SENSITIVE_KEYWORDS = (
    "mobile",
    "phone",
    "customer_name",
    "owner_name",
    "follow_user_name",
    "consultant_name",
    "manager_name",
    "vin",
)


@dataclass
class RealDataDemoReport:
    zip_path: str
    files: list[str]
    total_rows: int
    column_count: int
    rows_by_file: dict[str, int]
    stage_counts: dict[str, int]
    conversion_rates: dict[str, float | None]
    date_ranges: dict[str, dict[str, str | None]]
    top_dimensions: dict[str, list[dict[str, int | str]]]
    data_quality: dict[str, object]
    analysis_case: dict[str, object]
    executive_summary: list[str] = field(default_factory=list)
    privacy_notes: list[str] = field(default_factory=list)
    available_analysis_topics: list[dict[str, object]] = field(default_factory=list)
    recommended_analysis_topics: list[dict[str, object]] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class RealSalesFunnelAnalyzer:
    """Aggregates large CSV files directly from a zip without extracting them."""

    def __init__(self, zip_path: str | Path, *, top_n: int = 10, max_rows: int | None = None) -> None:
        self.zip_path = Path(zip_path)
        self.top_n = top_n
        self.max_rows = max_rows

    def analyze(self, business_question: str = "基于真实数据演示 register-to-order 销售漏斗") -> RealDataDemoReport:
        if not self.zip_path.exists():
            raise FileNotFoundError(f"Data zip not found: {self.zip_path}")

        rows_by_file: dict[str, int] = {}
        stage_counts = Counter()
        date_ranges: dict[str, dict[str, str | None]] = {
            col: {"min": None, "max": None} for col in TIME_COLUMNS
        }
        top_counters: dict[str, Counter[str]] = {name: Counter() for name in DIMENSION_COLUMNS}
        non_empty_counts = Counter()
        header: list[str] = []
        total_rows = 0

        with zipfile.ZipFile(self.zip_path) as archive:
            csv_files = [name for name in archive.namelist() if name.lower().endswith(".csv")]
            for csv_name in csv_files:
                file_rows = 0
                with archive.open(csv_name) as binary_file:
                    text_file = io.TextIOWrapper(binary_file, encoding="utf-8-sig", newline="")
                    reader = csv.DictReader(text_file)
                    if not header:
                        header = reader.fieldnames or []
                    for row in reader:
                        total_rows += 1
                        file_rows += 1
                        self._update_stage_counts(row, stage_counts)
                        self._update_date_ranges(row, date_ranges)
                        self._update_dimensions(row, top_counters)
                        self._update_quality_counts(row, non_empty_counts)
                        if self.max_rows and total_rows >= self.max_rows:
                            rows_by_file[csv_name] = file_rows
                            return self._build_report(
                                business_question,
                                csv_files,
                                header,
                                total_rows,
                                rows_by_file,
                                stage_counts,
                                date_ranges,
                                top_counters,
                                non_empty_counts,
                                truncated=True,
                            )
                rows_by_file[csv_name] = file_rows

        return self._build_report(
            business_question,
            csv_files,
            header,
            total_rows,
            rows_by_file,
            stage_counts,
            date_ranges,
            top_counters,
            non_empty_counts,
            truncated=False,
        )

    def _build_report(
        self,
        business_question: str,
        files: list[str],
        header: list[str],
        total_rows: int,
        rows_by_file: dict[str, int],
        stage_counts: Counter[str],
        date_ranges: dict[str, dict[str, str | None]],
        top_counters: dict[str, Counter[str]],
        non_empty_counts: Counter[str],
        *,
        truncated: bool,
    ) -> RealDataDemoReport:
        case = BPBAAnalysisAgent().run(
            business_question,
            scenario="media",
            analysis_purpose="用真实 register-to-order 链路数据演示 BP BA Agent 如何完成漏斗分析、数据校验和交付草稿。",
            target_object="全量样本" if not truncated else f"前 {total_rows:,} 行样本",
            time_range=self._overall_time_range(date_ranges),
            dimensions=["渠道", "大区", "车型", "经销商"],
            deliverable_type="management_report",
        )
        top_dimensions = {
            name: [{"value": key, "rows": count} for key, count in counter.most_common(self.top_n)]
            for name, counter in top_counters.items()
        }
        quality = self._data_quality(header, total_rows, non_empty_counts, truncated)
        report = RealDataDemoReport(
            zip_path=str(self.zip_path),
            files=files,
            total_rows=total_rows,
            column_count=len(header),
            rows_by_file=rows_by_file,
            stage_counts=dict(stage_counts),
            conversion_rates=self._conversion_rates(stage_counts),
            date_ranges=date_ranges,
            top_dimensions=top_dimensions,
            data_quality=quality,
            analysis_case=case.to_dict(),
            executive_summary=self._executive_summary(total_rows, stage_counts, top_dimensions, truncated),
            privacy_notes=[
                "演示输出仅包含聚合统计，不导出手机号、VIN、客户姓名、顾问姓名等个人级字段。",
                "CSV 从 zip 中流式读取，默认不解压原始明细到工作区。",
                "当前转化率按记录行中阶段 ID 非空计算；正式生产可替换为去重 ID 或语义层指标。",
            ],
            available_analysis_topics=list_analysis_topics(),
            recommended_analysis_topics=[topic.to_dict() for topic in recommend_topics(business_question)],
        )
        return report

    @staticmethod
    def _update_stage_counts(row: dict[str, str], stage_counts: Counter[str]) -> None:
        for stage, column in STAGE_COLUMNS.items():
            if row.get(column):
                stage_counts[stage] += 1

    @staticmethod
    def _update_date_ranges(row: dict[str, str], date_ranges: dict[str, dict[str, str | None]]) -> None:
        for column in TIME_COLUMNS:
            value = (row.get(column) or "").strip()
            if not value:
                continue
            current = date_ranges[column]
            if current["min"] is None or value < current["min"]:
                current["min"] = value
            if current["max"] is None or value > current["max"]:
                current["max"] = value

    @staticmethod
    def _first_available(row: dict[str, str], columns: Iterable[str]) -> str:
        for column in columns:
            value = (row.get(column) or "").strip()
            if value:
                return value
        return ""

    def _update_dimensions(self, row: dict[str, str], top_counters: dict[str, Counter[str]]) -> None:
        for dimension, columns in DIMENSION_COLUMNS.items():
            value = self._first_available(row, columns)
            if value:
                top_counters[dimension][self._safe_label(value)] += 1

    @staticmethod
    def _update_quality_counts(row: dict[str, str], non_empty_counts: Counter[str]) -> None:
        for column in [*STAGE_COLUMNS.values(), *TIME_COLUMNS, "region_route", "brand_route", "leads_channel_name"]:
            if row.get(column):
                non_empty_counts[column] += 1

    def _data_quality(
        self,
        header: list[str],
        total_rows: int,
        non_empty_counts: Counter[str],
        truncated: bool,
    ) -> dict[str, object]:
        critical_columns = [*STAGE_COLUMNS.values(), *TIME_COLUMNS, "region_route", "brand_route"]
        missing_columns = [column for column in critical_columns if column not in header]
        fill_rates = {
            column: round(non_empty_counts[column] / total_rows, 4) if total_rows else 0
            for column in critical_columns
            if column in header
        }
        sensitive_columns = [column for column in header if self._is_sensitive_column(column)]
        return {
            "critical_missing_columns": missing_columns,
            "critical_fill_rates": fill_rates,
            "sensitive_column_count": len(sensitive_columns),
            "sensitive_column_examples": sensitive_columns[:20],
            "truncated_by_max_rows": truncated,
        }

    @staticmethod
    def _conversion_rates(stage_counts: Counter[str]) -> dict[str, float | None]:
        def rate(numerator: str, denominator: str) -> float | None:
            base = stage_counts.get(denominator, 0)
            if not base:
                return None
            return round(stage_counts.get(numerator, 0) / base, 4)

        return {
            "leads_per_register": rate("leads", "register"),
            "oppty_per_leads": rate("oppty", "leads"),
            "visit_per_oppty": rate("visit", "oppty"),
            "td_per_visit": rate("td", "visit"),
            "order_per_leads": rate("order", "leads"),
            "order_per_oppty": rate("order", "oppty"),
        }

    @staticmethod
    def _overall_time_range(date_ranges: dict[str, dict[str, str | None]]) -> str:
        minimums = [item["min"] for item in date_ranges.values() if item["min"]]
        maximums = [item["max"] for item in date_ranges.values() if item["max"]]
        if not minimums or not maximums:
            return "待确认周期"
        return f"{min(minimums)} 至 {max(maximums)}"

    @staticmethod
    def _executive_summary(
        total_rows: int,
        stage_counts: Counter[str],
        top_dimensions: dict[str, list[dict[str, int | str]]],
        truncated: bool,
    ) -> list[str]:
        prefix = "样本" if truncated else "全量"
        channel = top_dimensions.get("channel", [{}])[0].get("value", "未识别") if top_dimensions.get("channel") else "未识别"
        region = top_dimensions.get("region", [{}])[0].get("value", "未识别") if top_dimensions.get("region") else "未识别"
        return [
            f"{prefix}读取 {total_rows:,} 行 register-to-order 链路记录。",
            f"漏斗阶段覆盖：register {stage_counts.get('register', 0):,}、leads {stage_counts.get('leads', 0):,}、oppty {stage_counts.get('oppty', 0):,}、visit {stage_counts.get('visit', 0):,}、td {stage_counts.get('td', 0):,}、order {stage_counts.get('order', 0):,}。",
            f"当前记录量最高的渠道为 {channel}，最高的区域路由为 {region}。",
            "该报告可作为 BP BA Agent 演示：先自动出漏斗口径、校验点和故事线，再由 BP BA 审核结论。",
        ]

    @staticmethod
    def _is_sensitive_column(column: str) -> bool:
        lowered = column.lower()
        return any(keyword in lowered for keyword in SENSITIVE_KEYWORDS)

    @staticmethod
    def _safe_label(value: str) -> str:
        value = value.strip().replace("\n", " ")
        if len(value) > 80:
            return f"{value[:77]}..."
        return value


def write_markdown(report: RealDataDemoReport, output_path: str | Path) -> None:
    data = report.to_dict()
    lines = [
        "# BP BA Agent 真实数据演示报告",
        "",
        "## Executive Summary",
        *[f"- {item}" for item in report.executive_summary],
        "",
        "## Funnel Snapshot",
        "| Stage | Rows |",
        "|---|---:|",
    ]
    for stage in ["register", "leads", "oppty", "visit", "td", "order"]:
        lines.append(f"| {stage} | {report.stage_counts.get(stage, 0):,} |")
    lines.extend(["", "## Conversion Rates", "| Metric | Rate |", "|---|---:|"])
    for key, value in report.conversion_rates.items():
        rendered = "N/A" if value is None else f"{value:.2%}"
        lines.append(f"| {key} | {rendered} |")
    lines.extend(["", "## Top Dimensions"])
    for dimension, rows in report.top_dimensions.items():
        lines.extend([f"### {dimension}", "| Value | Rows |", "|---|---:|"])
        for row in rows:
            lines.append(f"| {row['value']} | {int(row['rows']):,} |")
        lines.append("")
    lines.extend(
        [
            "## Data Quality",
            "```json",
            json.dumps(data["data_quality"], ensure_ascii=False, indent=2),
            "```",
            "",
            "## Agent Storyline Draft",
        ]
    )
    deliverable = report.analysis_case.get("deliverable") or {}
    for item in deliverable.get("ppt_storyline", []):
        lines.append(f"- {item}")
    lines.extend(["", "## Recommended Analysis Topics"])
    for topic in report.recommended_analysis_topics:
        lines.append(f"- **{topic['title']}** (`{topic['key']}`): {', '.join(topic['core_metrics'][:4])}")
    lines.extend(["", "## Privacy Notes", *[f"- {item}" for item in report.privacy_notes], ""])
    Path(output_path).write_text("\n".join(lines), encoding="utf-8")


def write_html(report: RealDataDemoReport, output_path: str | Path) -> None:
    data = report.to_dict()
    max_stage = max(report.stage_counts.values()) if report.stage_counts else 1
    stage_rows = "\n".join(
        f"""
        <div class="bar-row">
          <span class="label">{_escape(stage)}</span>
          <div class="track"><span style="width:{(report.stage_counts.get(stage, 0) / max_stage) * 100:.1f}%"></span></div>
          <strong>{report.stage_counts.get(stage, 0):,}</strong>
        </div>
        """
        for stage in ["register", "leads", "oppty", "visit", "td", "order"]
    )
    rate_cards = "\n".join(
        f"""
        <article class="metric-card">
          <small>{_escape(key)}</small>
          <strong>{"N/A" if value is None else f"{value:.2%}"}</strong>
        </article>
        """
        for key, value in report.conversion_rates.items()
    )
    dimension_sections = "\n".join(
        _dimension_html(name, rows)
        for name, rows in report.top_dimensions.items()
        if rows
    )
    summary = "\n".join(f"<li>{_escape(item)}</li>" for item in report.executive_summary)
    storyline = "\n".join(
        f"<li>{_escape(item)}</li>"
        for item in (report.analysis_case.get("deliverable") or {}).get("ppt_storyline", [])
    )
    topics = "\n".join(
        f"<li><strong>{_escape(str(topic['title']))}</strong> <code>{_escape(str(topic['key']))}</code><br><span>{_escape(', '.join(topic['core_metrics'][:4]))}</span></li>"
        for topic in report.recommended_analysis_topics
    )
    privacy = "\n".join(f"<li>{_escape(item)}</li>" for item in report.privacy_notes)
    quality = _escape(json.dumps(data["data_quality"], ensure_ascii=False, indent=2))
    html = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>BP BA Agent 真实数据演示</title>
  <style>
    :root {{
      --ink: #17211b;
      --muted: #66736c;
      --paper: #f6f2e8;
      --card: #fffaf0;
      --line: #ded3be;
      --accent: #0f6b57;
      --accent-2: #d47a37;
      --deep: #102c2a;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      color: var(--ink);
      background:
        radial-gradient(circle at 10% 0%, rgba(212,122,55,.18), transparent 32rem),
        linear-gradient(135deg, #fbf7ee 0%, var(--paper) 48%, #e8efe7 100%);
      font-family: "Segoe UI", "Microsoft YaHei", sans-serif;
    }}
    main {{ width: min(1180px, calc(100vw - 32px)); margin: 0 auto; padding: 42px 0 56px; }}
    .hero {{
      display: grid;
      grid-template-columns: 1.3fr .7fr;
      gap: 22px;
      align-items: stretch;
    }}
    .panel {{
      background: rgba(255,250,240,.88);
      border: 1px solid var(--line);
      border-radius: 26px;
      box-shadow: 0 22px 60px rgba(44,50,39,.12);
      padding: 28px;
    }}
    h1 {{ font-size: clamp(34px, 5vw, 64px); line-height: .98; margin: 0 0 18px; letter-spacing: -0.05em; }}
    h2 {{ margin: 0 0 18px; font-size: 22px; letter-spacing: -0.02em; }}
    h3 {{ margin: 0 0 12px; font-size: 16px; }}
    .eyebrow {{ color: var(--accent); font-weight: 800; text-transform: uppercase; letter-spacing: .12em; font-size: 12px; }}
    .summary {{ margin: 0; padding-left: 20px; color: var(--muted); line-height: 1.75; }}
    .big-number {{ font-size: 48px; font-weight: 900; letter-spacing: -0.04em; color: var(--deep); }}
    .subtle {{ color: var(--muted); }}
    .grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-top: 18px; }}
    .metric-card {{
      background: #fffdf8;
      border: 1px solid var(--line);
      border-radius: 20px;
      padding: 18px;
      min-height: 104px;
    }}
    .metric-card small {{ display: block; color: var(--muted); margin-bottom: 18px; }}
    .metric-card strong {{ font-size: 28px; color: var(--accent); }}
    .section {{ margin-top: 22px; }}
    .bar-row {{ display: grid; grid-template-columns: 80px 1fr 110px; gap: 14px; align-items: center; margin: 13px 0; }}
    .bar-row .label {{ font-weight: 800; }}
    .track {{ height: 16px; background: #eadfcb; border-radius: 99px; overflow: hidden; }}
    .track span {{ display: block; height: 100%; background: linear-gradient(90deg, var(--accent), var(--accent-2)); border-radius: inherit; }}
    .dim-grid {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 16px; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
    th, td {{ border-bottom: 1px solid var(--line); padding: 9px 0; text-align: left; }}
    td:last-child, th:last-child {{ text-align: right; font-variant-numeric: tabular-nums; }}
    pre {{ white-space: pre-wrap; word-break: break-word; background: #122724; color: #eaf6ef; padding: 18px; border-radius: 18px; overflow: auto; }}
    .story {{ columns: 2; line-height: 1.8; }}
    @media (max-width: 860px) {{
      .hero, .grid, .dim-grid {{ grid-template-columns: 1fr; }}
      .story {{ columns: 1; }}
      .bar-row {{ grid-template-columns: 70px 1fr; }}
      .bar-row strong {{ grid-column: 2; }}
    }}
  </style>
</head>
<body>
  <main>
    <section class="hero">
      <div class="panel">
        <p class="eyebrow">BP BA Analysis Agent · Real Data Demo</p>
        <h1>Register-to-order 漏斗演示</h1>
        <ul class="summary">{summary}</ul>
      </div>
      <aside class="panel">
        <p class="subtle">Rows scanned</p>
        <div class="big-number">{report.total_rows:,}</div>
        <p class="subtle">{len(report.files)} CSV files · {report.column_count} columns</p>
      </aside>
    </section>

    <section class="panel section">
      <h2>Funnel Snapshot</h2>
      {stage_rows}
    </section>

    <section class="section">
      <h2>Conversion Rates</h2>
      <div class="grid">{rate_cards}</div>
    </section>

    <section class="section">
      <h2>Top Dimensions</h2>
      <div class="dim-grid">{dimension_sections}</div>
    </section>

    <section class="panel section">
      <h2>Agent Storyline Draft</h2>
      <ol class="story">{storyline}</ol>
    </section>

    <section class="panel section">
      <h2>Recommended Analysis Skills</h2>
      <ol class="story">{topics}</ol>
    </section>

    <section class="panel section">
      <h2>Data Quality</h2>
      <pre>{quality}</pre>
    </section>

    <section class="panel section">
      <h2>Privacy Notes</h2>
      <ul class="summary">{privacy}</ul>
    </section>
  </main>
</body>
</html>"""
    Path(output_path).write_text(html, encoding="utf-8")


def _dimension_html(name: str, rows: list[dict[str, int | str]]) -> str:
    body = "\n".join(
        f"<tr><td>{_escape(str(row['value']))}</td><td>{int(row['rows']):,}</td></tr>"
        for row in rows[:10]
    )
    return f"""<article class="panel"><h3>{_escape(name)}</h3><table><thead><tr><th>Value</th><th>Rows</th></tr></thead><tbody>{body}</tbody></table></article>"""


def _escape(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run BP BA Agent demo on real sales funnel zip data.")
    parser.add_argument("zip_path", help="Path to register-to-order sales CSV zip.")
    parser.add_argument("--question", default="基于真实数据演示 register-to-order 销售漏斗")
    parser.add_argument("--max-rows", type=int, default=None, help="Optional row cap for quick demo.")
    parser.add_argument("--top-n", type=int, default=10)
    parser.add_argument("--json-out", default=None)
    parser.add_argument("--md-out", default=None)
    parser.add_argument("--html-out", default=None)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    report = RealSalesFunnelAnalyzer(args.zip_path, top_n=args.top_n, max_rows=args.max_rows).analyze(args.question)
    if args.json_out:
        Path(args.json_out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json_out).write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    if args.md_out:
        Path(args.md_out).parent.mkdir(parents=True, exist_ok=True)
        write_markdown(report, args.md_out)
    if args.html_out:
        Path(args.html_out).parent.mkdir(parents=True, exist_ok=True)
        write_html(report, args.html_out)
    if not args.json_out and not args.md_out and not args.html_out:
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(f"rows={report.total_rows:,}")
        print(f"stage_counts={report.stage_counts}")
        print(f"conversion_rates={report.conversion_rates}")


if __name__ == "__main__":
    main()
