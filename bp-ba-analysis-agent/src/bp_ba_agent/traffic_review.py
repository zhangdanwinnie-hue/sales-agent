"""Standalone traffic-decline review report for BP BA Agent demos."""

from __future__ import annotations

import argparse
import csv
import io
import json
import zipfile
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path

from .analysis_topics import get_analysis_topic


DIMENSIONS = {
    "traffic_type": "自然/线上",
    "region_route": "区域",
    "city_name_zh": "城市",
    "visit_dealer_id": "经销商",
    "leads_channel_name": "渠道",
    "leads_media_platform_name": "媒体平台",
    "register_model": "车型",
    "dealer_status_name": "经销商状态",
}


@dataclass(frozen=True)
class DimensionDelta:
    dimension: str
    value: str
    previous: int
    current: int
    delta: int
    change_rate: float | None
    contribution_to_decline: float | None


@dataclass
class TrafficDeclineReport:
    zip_path: str
    current_month: str
    previous_month: str
    total_visits: int
    previous_visits: int
    current_visits: int
    delta: int
    change_rate: float | None
    monthly_trend: list[dict[str, int | str]]
    traffic_type_delta: list[dict[str, object]]
    dimension_deltas: dict[str, list[dict[str, object]]]
    executive_summary: list[str]
    analysis_framework: dict[str, object]
    data_quality: dict[str, object]
    privacy_notes: list[str]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class TrafficDeclineAnalyzer:
    """Builds an aggregate-only single-stage traffic review from the real zip."""

    def __init__(
        self,
        zip_path: str | Path,
        *,
        current_month: str | None = None,
        previous_month: str | None = None,
        top_n: int = 10,
    ) -> None:
        self.zip_path = Path(zip_path)
        self.current_month = current_month
        self.previous_month = previous_month
        self.top_n = top_n

    def analyze(self) -> TrafficDeclineReport:
        monthly = Counter()
        total_visits = 0
        max_visit_time = ""
        required_fill = Counter()
        dimension_counts: dict[str, dict[str, Counter[str]]] = {
            key: defaultdict(Counter) for key in DIMENSIONS
        }

        with zipfile.ZipFile(self.zip_path) as archive:
            for csv_name in archive.namelist():
                if not csv_name.lower().endswith(".csv"):
                    continue
                with archive.open(csv_name) as binary_file:
                    reader = csv.DictReader(io.TextIOWrapper(binary_file, encoding="utf-8-sig", newline=""))
                    for row in reader:
                        visit_id = (row.get("visit_id") or "").strip()
                        visit_time = (row.get("visit_arrival_time") or "").strip()
                        if not visit_id or not visit_time:
                            continue
                        month = visit_time[:7]
                        if len(month) != 7:
                            continue
                        total_visits += 1
                        monthly[month] += 1
                        max_visit_time = max(max_visit_time, visit_time)
                        for field in ["visit_id", "visit_arrival_time", "visit_is_nature_sr_flag", "region_route", "city_name_zh", "visit_dealer_id", "leads_channel_name"]:
                            if row.get(field):
                                required_fill[field] += 1
                        if self._should_capture_month(month, max_visit_time):
                            # The final comparison months may be inferred after the scan, so this
                            # branch is only useful for explicitly provided months. We aggregate all
                            # comparison dimensions in a second pass below for inferred months.
                            pass

        current_month, previous_month = self._resolve_months(monthly, max_visit_time)
        self._current_for_delta = current_month
        self._previous_for_delta = previous_month
        dimension_counts = self._aggregate_comparison_dimensions(current_month, previous_month)
        previous_visits = monthly[previous_month]
        current_visits = monthly[current_month]
        delta = current_visits - previous_visits
        change_rate = round(delta / previous_visits, 4) if previous_visits else None
        total_decline = abs(delta) if delta < 0 else None

        dim_deltas = {
            key: [asdict(item) for item in self._top_dimension_deltas(label, counts, total_decline)]
            for key, label, counts in (
                (key, label, dimension_counts[key]) for key, label in DIMENSIONS.items()
            )
        }
        traffic_type_delta = dim_deltas["traffic_type"]
        framework = get_analysis_topic("single_stage_review").to_dict()
        quality = {
            "total_visit_rows": total_visits,
            "comparison_months": [previous_month, current_month],
            "required_fill_rates": {
                field: round(required_fill[field] / total_visits, 4) if total_visits else 0
                for field in required_fill
            },
            "latest_visit_time": max_visit_time,
            "month_selection_note": "默认选择最新数据月份之前的完整月份作为 current_month，避免把未完结月份误判为下降。",
        }
        return TrafficDeclineReport(
            zip_path=str(self.zip_path),
            current_month=current_month,
            previous_month=previous_month,
            total_visits=total_visits,
            previous_visits=previous_visits,
            current_visits=current_visits,
            delta=delta,
            change_rate=change_rate,
            monthly_trend=[{"month": month, "visits": monthly[month]} for month in sorted(monthly)[-18:]],
            traffic_type_delta=traffic_type_delta,
            dimension_deltas=dim_deltas,
            executive_summary=self._summary(previous_month, current_month, previous_visits, current_visits, delta, change_rate, traffic_type_delta, dim_deltas),
            analysis_framework=framework,
            data_quality=quality,
            privacy_notes=[
                "本报告只输出聚合统计，不导出手机号、客户姓名、VIN、顾问姓名等个人级字段。",
                "经销商仅使用 visit_dealer_id 聚合展示，不输出经销商人员信息。",
                "visit_is_nature_sr_flag 的 Y/N 解释需由业务确认；当前报告暂按 Y=自然客流，N=线上/非自然客流。",
            ],
        )

    def _aggregate_comparison_dimensions(self, current_month: str, previous_month: str) -> dict[str, dict[str, Counter[str]]]:
        result: dict[str, dict[str, Counter[str]]] = {key: defaultdict(Counter) for key in DIMENSIONS}
        months = {current_month, previous_month}
        with zipfile.ZipFile(self.zip_path) as archive:
            for csv_name in archive.namelist():
                if not csv_name.lower().endswith(".csv"):
                    continue
                with archive.open(csv_name) as binary_file:
                    reader = csv.DictReader(io.TextIOWrapper(binary_file, encoding="utf-8-sig", newline=""))
                    for row in reader:
                        if not row.get("visit_id") or not row.get("visit_arrival_time"):
                            continue
                        month = row["visit_arrival_time"][:7]
                        if month not in months:
                            continue
                        for key in DIMENSIONS:
                            value = self._dimension_value(row, key)
                            result[key][value][month] += 1
        return result

    def _resolve_months(self, monthly: Counter[str], max_visit_time: str) -> tuple[str, str]:
        if self.current_month and self.previous_month:
            return self.current_month, self.previous_month
        if self.current_month and not self.previous_month:
            return self.current_month, previous_month(self.current_month)
        if self.previous_month and not self.current_month:
            return next_month(self.previous_month), self.previous_month

        max_month = max_visit_time[:7]
        current = previous_month(max_month)
        previous = previous_month(current)
        if current not in monthly:
            months = sorted(monthly)
            current = months[-1]
            previous = months[-2]
        return current, previous

    @staticmethod
    def _dimension_value(row: dict[str, str], key: str) -> str:
        if key == "traffic_type":
            flag = (row.get("visit_is_nature_sr_flag") or "").strip().upper()
            if flag == "Y":
                return "自然客流(Y)"
            if flag == "N":
                return "线上/非自然客流(N)"
            return "未知"
        value = (row.get(key) or "").strip()
        return value[:80] if value else "未知"

    def _top_dimension_deltas(
        self,
        label: str,
        counts: dict[str, Counter[str]],
        total_decline: int | None,
    ) -> list[DimensionDelta]:
        rows: list[DimensionDelta] = []
        current_month, previous_month = self._resolved_current_previous
        for value, counter in counts.items():
            previous = counter[previous_month]
            current = counter[current_month]
            delta = current - previous
            rate = round(delta / previous, 4) if previous else None
            contribution = round(abs(delta) / total_decline, 4) if total_decline and delta < 0 else None
            rows.append(DimensionDelta(label, value, previous, current, delta, rate, contribution))
        rows.sort(key=lambda item: (item.delta, -item.previous))
        return rows[: self.top_n]

    @property
    def _resolved_current_previous(self) -> tuple[str, str]:
        # This property is assigned indirectly by _top_dimension_deltas callers
        # through the latest resolved months on the object.
        return self._current_for_delta, self._previous_for_delta

    def _summary(
        self,
        previous_month: str,
        current_month: str,
        previous_visits: int,
        current_visits: int,
        delta: int,
        change_rate: float | None,
        traffic_type_delta: list[dict[str, object]],
        dim_deltas: dict[str, list[dict[str, object]]],
    ) -> list[str]:
        rate = "N/A" if change_rate is None else f"{change_rate:.1%}"
        top_traffic = traffic_type_delta[0] if traffic_type_delta else {}
        top_region = dim_deltas.get("region_route", [{}])[0]
        top_city = dim_deltas.get("city_name_zh", [{}])[0]
        direction = "下降" if delta < 0 else "上升"
        return [
            f"{current_month} 客流 {current_visits:,}，较 {previous_month} 的 {previous_visits:,} {direction} {abs(delta):,}，变化率 {rate}。",
            f"按自然/线上拆解，最大负向贡献来自 {top_traffic.get('value', '待确认')}，delta={top_traffic.get('delta', 'N/A')}。",
            f"区域层面最大负向项为 {top_region.get('value', '待确认')}，城市层面最大负向项为 {top_city.get('value', '待确认')}。",
            "建议下一步用贡献拆解下钻到经销商、渠道和车型，再由 BP BA 确认自然/线上口径与业务动作。",
        ]

    def _should_capture_month(self, month: str, max_visit_time: str) -> bool:
        if self.current_month and self.previous_month:
            return month in {self.current_month, self.previous_month}
        return False


def previous_month(month: str) -> str:
    year, mon = [int(part) for part in month.split("-")]
    if mon == 1:
        return f"{year - 1}-12"
    return f"{year}-{mon - 1:02d}"


def next_month(month: str) -> str:
    year, mon = [int(part) for part in month.split("-")]
    if mon == 12:
        return f"{year + 1}-01"
    return f"{year}-{mon + 1:02d}"


def write_markdown(report: TrafficDeclineReport, output_path: str | Path) -> None:
    lines = [
        "# 客流下降单环节复盘报告",
        "",
        "## Executive Summary",
        *[f"- {item}" for item in report.executive_summary],
        "",
        "## Monthly Trend",
        "| Month | Visits |",
        "|---|---:|",
    ]
    for item in report.monthly_trend:
        lines.append(f"| {item['month']} | {int(item['visits']):,} |")
    lines.extend(["", "## 自然 / 线上拆解", *_delta_table(report.traffic_type_delta)])
    for key in ["region_route", "city_name_zh", "visit_dealer_id", "leads_channel_name", "register_model"]:
        lines.extend(["", f"## {DIMENSIONS[key]} 负向贡献 Top", *_delta_table(report.dimension_deltas[key])])
    lines.extend(
        [
            "",
            "## Analysis Framework",
            f"- 主题：{report.analysis_framework['title']}",
            f"- 推荐维度：{', '.join(report.analysis_framework['default_dimensions'])}",
            f"- 核心指标：{', '.join(report.analysis_framework['core_metrics'])}",
            "",
            "## Data Quality",
            "```json",
            json.dumps(report.data_quality, ensure_ascii=False, indent=2),
            "```",
            "",
            "## Privacy Notes",
            *[f"- {item}" for item in report.privacy_notes],
            "",
        ]
    )
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text("\n".join(lines), encoding="utf-8")


def _delta_table(rows: list[dict[str, object]]) -> list[str]:
    lines = ["| Value | Previous | Current | Delta | Change | Decline contribution |", "|---|---:|---:|---:|---:|---:|"]
    for row in rows:
        rate = "N/A" if row["change_rate"] is None else f"{float(row['change_rate']):.1%}"
        contribution = "N/A" if row["contribution_to_decline"] is None else f"{float(row['contribution_to_decline']):.1%}"
        lines.append(
            f"| {row['value']} | {int(row['previous']):,} | {int(row['current']):,} | {int(row['delta']):,} | {rate} | {contribution} |"
        )
    return lines


def write_html(report: TrafficDeclineReport, output_path: str | Path) -> None:
    max_visits = max(int(item["visits"]) for item in report.monthly_trend) if report.monthly_trend else 1
    trend = "\n".join(
        f"""<div class="bar-row"><span>{item['month']}</span><b style="width:{int(item['visits']) / max_visits * 100:.1f}%"></b><strong>{int(item['visits']):,}</strong></div>"""
        for item in report.monthly_trend
    )
    summary = "\n".join(f"<li>{escape(item)}</li>" for item in report.executive_summary)
    traffic = html_table(report.traffic_type_delta)
    region = html_table(report.dimension_deltas["region_route"])
    city = html_table(report.dimension_deltas["city_name_zh"])
    dealer = html_table(report.dimension_deltas["visit_dealer_id"])
    channel = html_table(report.dimension_deltas["leads_channel_name"])
    model = html_table(report.dimension_deltas["register_model"])
    quality = escape(json.dumps(report.data_quality, ensure_ascii=False, indent=2))
    rate = "N/A" if report.change_rate is None else f"{report.change_rate:.1%}"
    html = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>客流下降单环节复盘</title>
  <style>
    :root {{ --ink:#15231f; --muted:#68736c; --paper:#f5efe4; --card:#fffaf0; --line:#d8c9b2; --green:#0f6b57; --orange:#d47635; --dark:#102724; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; background:radial-gradient(circle at 8% 0%, #eab77a55, transparent 28rem), linear-gradient(135deg,#fbf8ef,#edf3ec); color:var(--ink); font-family:"Segoe UI","Microsoft YaHei",sans-serif; }}
    main {{ width:min(1180px, calc(100vw - 32px)); margin:0 auto; padding:42px 0 56px; }}
    .hero {{ display:grid; grid-template-columns:1.15fr .85fr; gap:18px; }}
    .panel {{ background:rgba(255,250,240,.92); border:1px solid var(--line); border-radius:26px; padding:26px; box-shadow:0 22px 60px rgba(44,50,39,.10); }}
    h1 {{ font-size:clamp(36px,5vw,64px); line-height:1; letter-spacing:-.05em; margin:0 0 18px; }}
    h2 {{ margin:0 0 18px; font-size:24px; }}
    h3 {{ margin:0 0 14px; font-size:18px; color:var(--green); }}
    .eyebrow {{ color:var(--green); font-size:12px; font-weight:900; letter-spacing:.14em; text-transform:uppercase; }}
    .summary {{ color:var(--muted); line-height:1.75; padding-left:20px; }}
    .kpis {{ display:grid; grid-template-columns:repeat(3,1fr); gap:14px; margin-top:18px; }}
    .kpi {{ border:1px solid var(--line); border-radius:20px; background:#fffdf8; padding:18px; }}
    .kpi small {{ color:var(--muted); font-weight:700; }}
    .kpi strong {{ display:block; margin-top:12px; font-size:34px; color:var(--orange); }}
    .grid {{ display:grid; grid-template-columns:1fr 1fr; gap:18px; margin-top:18px; }}
    table {{ width:100%; border-collapse:collapse; font-size:14px; }}
    th,td {{ border-bottom:1px solid var(--line); padding:9px 0; text-align:left; }}
    th:not(:first-child),td:not(:first-child) {{ text-align:right; font-variant-numeric:tabular-nums; }}
    .bar-row {{ display:grid; grid-template-columns:80px 1fr 90px; gap:12px; align-items:center; margin:10px 0; }}
    .bar-row b {{ display:block; height:18px; border-radius:99px; background:linear-gradient(90deg,var(--green),var(--orange)); }}
    .bar-row strong {{ text-align:right; color:var(--muted); }}
    pre {{ white-space:pre-wrap; word-break:break-word; background:var(--dark); color:#eaf7ef; border-radius:18px; padding:18px; }}
    @media(max-width:860px) {{ .hero,.grid,.kpis {{ grid-template-columns:1fr; }} }}
  </style>
</head>
<body>
<main>
  <section class="hero">
    <div class="panel">
      <p class="eyebrow">BP BA Agent · Single-stage Review</p>
      <h1>客流下降复盘</h1>
      <ul class="summary">{summary}</ul>
    </div>
    <div class="panel">
      <h2>Comparison</h2>
      <div class="kpis">
        <div class="kpi"><small>{report.previous_month}</small><strong>{report.previous_visits:,}</strong></div>
        <div class="kpi"><small>{report.current_month}</small><strong>{report.current_visits:,}</strong></div>
        <div class="kpi"><small>Change</small><strong>{report.delta:,}<br>{rate}</strong></div>
      </div>
    </div>
  </section>
  <section class="panel" style="margin-top:18px"><h2>Monthly trend</h2>{trend}</section>
  <section class="grid">
    <div class="panel"><h3>自然 / 线上拆解</h3>{traffic}</div>
    <div class="panel"><h3>区域负向贡献</h3>{region}</div>
    <div class="panel"><h3>城市负向贡献</h3>{city}</div>
    <div class="panel"><h3>经销商负向贡献</h3>{dealer}</div>
    <div class="panel"><h3>渠道负向贡献</h3>{channel}</div>
    <div class="panel"><h3>车型负向贡献</h3>{model}</div>
  </section>
  <section class="panel" style="margin-top:18px"><h2>Data Quality</h2><pre>{quality}</pre></section>
</main>
</body>
</html>"""
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text(html, encoding="utf-8")


def html_table(rows: list[dict[str, object]]) -> str:
    body = "\n".join(
        f"<tr><td>{escape(str(row['value']))}</td><td>{int(row['previous']):,}</td><td>{int(row['current']):,}</td><td>{int(row['delta']):,}</td></tr>"
        for row in rows[:8]
    )
    return f"<table><thead><tr><th>Value</th><th>Prev</th><th>Curr</th><th>Delta</th></tr></thead><tbody>{body}</tbody></table>"


def escape(value: str) -> str:
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a standalone traffic decline review report.")
    parser.add_argument("zip_path")
    parser.add_argument("--current-month")
    parser.add_argument("--previous-month")
    parser.add_argument("--top-n", type=int, default=10)
    parser.add_argument("--json-out")
    parser.add_argument("--md-out")
    parser.add_argument("--html-out")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    analyzer = TrafficDeclineAnalyzer(
        args.zip_path,
        current_month=args.current_month,
        previous_month=args.previous_month,
        top_n=args.top_n,
    )
    report = analyzer.analyze()
    if args.json_out:
        Path(args.json_out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json_out).write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    if args.md_out:
        write_markdown(report, args.md_out)
    if args.html_out:
        write_html(report, args.html_out)
    if not args.json_out and not args.md_out and not args.html_out:
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(f"comparison={report.previous_month}->{report.current_month}")
        print(f"visits={report.previous_visits:,}->{report.current_visits:,} delta={report.delta:,}")


if __name__ == "__main__":
    main()
