import csv
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parent
CSV_PATH = WORKSPACE / "ads_rpt_sal_ncs_register_to_order_sales_ssa_t_202605151845" / "ads_rpt_sal_ncs_register_to_order_sales_ssa_t_202605151845.csv"
OUT_PATH = ROOT / "prototype" / "data" / "analysis-case.json"


FIELDS = [
    "register_rcid",
    "register_create_time",
    "leads_id",
    "leads_create_time",
    "leads_channel_name",
    "leads_sub_channel_name",
    "leads_media_platform_name",
    "leads_campaign_name",
    "leads_star_level",
    "leads_first_follow_mindiff",
    "oppty_id",
    "oppty_create_time",
    "oppty_opportunity_follow_times",
    "oppty_first_oppty_follow_mindiff",
    "oppty_opportunity_status_desc",
    "oppty_pipeline_stage_desc",
    "oppty_battle_fail_primary_reason_desc",
    "oppty_battle_fail_secondary_reason_desc",
    "visit_id",
    "visit_arrival_time",
    "visit_valid_flag",
    "visit_customer_visit_type_desc",
    "td_id",
    "td_start_time",
    "td_test_drive_status_desc",
    "order_id",
    "order_create_time",
    "order_cancel_time",
    "order_handover_time",
    "order_cancel_flag",
    "order_cancel_reason",
    "order_brand_code",
    "order_series_code",
    "order_model_code",
    "order_so_status_desc",
    "region_name_zh",
    "city_name_zh",
    "dealership_name_cn",
    "dealer_status_name",
    "sales_bmw_big_area_name_zh",
    "sales_bmw_small_area_name_zh",
    "brand_route",
    "region_route",
    "etl_batch_time",
]


def month(value):
    if not value:
        return None
    value = value.strip().strip('"')
    if len(value) < 7:
        return None
    return value[:7]


def safe_float(value):
    if value in (None, ""):
        return None
    try:
        return float(value)
    except ValueError:
        return None


def pct(num, den):
    if not den:
        return None
    return round(num / den * 100, 1)


def change_pct(cur, prev):
    if not prev:
        return None
    return round((cur - prev) / prev * 100, 1)


class DistinctAgg:
    def __init__(self):
        self.registers = set()
        self.leads = set()
        self.oppties = set()
        self.visits = set()
        self.valid_visits = set()
        self.tds = set()
        self.orders = set()
        self.cancel_orders = set()
        self.handovers = set()
        self.follow_latencies = []
        self.oppty_follow_latencies = []
        self.oppty_follow_times = []

    def add(self, row):
        if row["register_rcid"]:
            self.registers.add(row["register_rcid"])
        if row["leads_id"]:
            self.leads.add(row["leads_id"])
        if row["oppty_id"]:
            self.oppties.add(row["oppty_id"])
        if row["visit_id"]:
            self.visits.add(row["visit_id"])
            if row["visit_valid_flag"] == "Y" or row["visit_valid_flag"] == "有效":
                self.valid_visits.add(row["visit_id"])
        if row["td_id"]:
            self.tds.add(row["td_id"])
        if row["order_id"]:
            self.orders.add(row["order_id"])
            if row.get("order_cancel_flag") == "Y" or row.get("order_cancel_time"):
                self.cancel_orders.add(row["order_id"])
            if row["order_handover_time"]:
                self.handovers.add(row["order_id"])

        lead_latency = safe_float(row["leads_first_follow_mindiff"])
        if lead_latency is not None and 0 <= lead_latency <= 10080:
            self.follow_latencies.append(lead_latency)

        oppty_latency = safe_float(row["oppty_first_oppty_follow_mindiff"])
        if oppty_latency is not None and 0 <= oppty_latency <= 10080:
            self.oppty_follow_latencies.append(oppty_latency)

        follow_times = safe_float(row["oppty_opportunity_follow_times"])
        if follow_times is not None and 0 <= follow_times <= 200:
            self.oppty_follow_times.append(follow_times)

    def metrics(self):
        leads = len(self.leads)
        oppties = len(self.oppties)
        visits = len(self.visits)
        valid_visits = len(self.valid_visits)
        tds = len(self.tds)
        orders = len(self.orders)
        cancel_orders = len(self.cancel_orders)
        handovers = len(self.handovers)
        avg_follow = round(sum(self.follow_latencies) / len(self.follow_latencies), 1) if self.follow_latencies else None
        avg_oppty_follow = round(sum(self.oppty_follow_latencies) / len(self.oppty_follow_latencies), 1) if self.oppty_follow_latencies else None
        avg_follow_times = round(sum(self.oppty_follow_times) / len(self.oppty_follow_times), 1) if self.oppty_follow_times else None
        return {
            "registers": len(self.registers),
            "leads": leads,
            "opportunities": oppties,
            "visits": visits,
            "validVisits": valid_visits,
            "testDrives": tds,
            "orders": orders,
            "cancelOrders": cancel_orders,
            "handovers": handovers,
            "leadToOpportunityRate": pct(oppties, leads),
            "opportunityToVisitRate": pct(visits, oppties),
            "visitToTestDriveRate": pct(tds, visits),
            "testDriveToOrderRate": pct(orders, tds),
            "leadToOrderRate": pct(orders, leads),
            "cancelRate": pct(cancel_orders, orders),
            "handoverRate": pct(handovers, orders),
            "avgLeadFirstFollowMin": avg_follow,
            "avgOpptyFirstFollowMin": avg_oppty_follow,
            "avgOpptyFollowTimes": avg_follow_times,
        }


def top_items(counter, total=None, limit=8):
    if total is None:
        total = sum(counter.values())
    rows = []
    for name, value in counter.most_common(limit):
        rows.append({
            "name": name or "未填",
            "value": value,
            "share": pct(value, total),
        })
    return rows


def main():
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with CSV_PATH.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        header = next(reader)
        indices = {field: header.index(field) for field in FIELDS if field in header}

    monthly = defaultdict(DistinctAgg)
    all_data = DistinctAgg()
    region_order_ids = defaultdict(set)
    dealer_order_ids = defaultdict(set)
    city_order_ids = defaultdict(set)
    channel_leads = defaultdict(set)
    channel_orders = defaultdict(set)
    series_orders = defaultdict(set)
    brand_orders = defaultdict(set)
    reason_counter = Counter()
    cancel_reason_counter = Counter()
    status_counter = Counter()
    row_count = 0
    etl_batch_time = None

    with CSV_PATH.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        header = next(reader)
        for raw in reader:
            if len(raw) < len(header):
                raw += [""] * (len(header) - len(raw))
            row = {field: raw[idx] if idx < len(raw) else "" for field, idx in indices.items()}
            row_count += 1
            if row.get("etl_batch_time"):
                etl_batch_time = row["etl_batch_time"]

            all_data.add(row)
            for field in ["leads_create_time", "oppty_create_time", "visit_arrival_time", "td_start_time", "order_create_time"]:
                m = month(row.get(field, ""))
                if m:
                    monthly[m].add(row)

            order_id = row.get("order_id")
            lead_id = row.get("leads_id")
            channel = row.get("leads_channel_name") or row.get("leads_media_platform_name") or "未填"
            region = row.get("region_name_zh") or row.get("sales_bmw_big_area_name_zh") or "未填"
            dealer = row.get("dealership_name_cn") or "未填"
            city = row.get("city_name_zh") or "未填"
            series = row.get("order_series_code") or row.get("order_model_code") or "未填"
            brand = row.get("order_brand_code") or row.get("brand_route") or "未填"

            if lead_id:
                channel_leads[channel].add(lead_id)
            if order_id:
                region_order_ids[region].add(order_id)
                dealer_order_ids[dealer].add(order_id)
                city_order_ids[city].add(order_id)
                channel_orders[channel].add(order_id)
                series_orders[series].add(order_id)
                brand_orders[brand].add(order_id)
                if row.get("order_so_status_desc"):
                    status_counter[row["order_so_status_desc"]] += 1
                if row.get("order_cancel_reason"):
                    cancel_reason_counter[row["order_cancel_reason"]] += 1

            for reason_field in ["oppty_battle_fail_primary_reason_desc", "oppty_battle_fail_secondary_reason_desc"]:
                if row.get(reason_field):
                    reason_counter[row[reason_field]] += 1

    month_rows = []
    for m in sorted(monthly):
        values = monthly[m].metrics()
        values["month"] = m
        month_rows.append(values)

    previous = None
    for item in month_rows:
        if previous:
            item["orderMoM"] = change_pct(item["orders"], previous["orders"])
            item["leadMoM"] = change_pct(item["leads"], previous["leads"])
            item["leadToOrderRateChange"] = None if item["leadToOrderRate"] is None or previous["leadToOrderRate"] is None else round(item["leadToOrderRate"] - previous["leadToOrderRate"], 1)
        else:
            item["orderMoM"] = None
            item["leadMoM"] = None
            item["leadToOrderRateChange"] = None
        previous = item

    latest_month = max((m for m in monthly if monthly[m].metrics()["orders"] > 0), default=month_rows[-1]["month"] if month_rows else None)
    latest_metrics = monthly[latest_month].metrics() if latest_month else all_data.metrics()
    overall_metrics = all_data.metrics()

    channel_rows = []
    for name, leads in channel_leads.items():
        lead_count = len(leads)
        order_count = len(channel_orders.get(name, set()))
        channel_rows.append({
            "name": name,
            "leads": lead_count,
            "orders": order_count,
            "leadToOrderRate": pct(order_count, lead_count),
        })
    channel_rows.sort(key=lambda x: (x["orders"], x["leads"]), reverse=True)

    output = {
        "generatedAt": datetime.now().isoformat(timespec="seconds"),
        "source": {
            "file": CSV_PATH.name,
            "rows": row_count,
            "columnsUsed": len(indices),
            "encoding": "utf-8-sig",
            "etlBatchTime": etl_batch_time,
        },
        "case": {
            "title": "真实 CSV 案例：销售线索到订单全链路诊断",
            "question": "当前数据中，销售漏斗各阶段表现如何？订单主要集中在哪些区域、渠道、车系和经销商？",
            "scope": "全量样本，按当前 CSV 可用字段聚合",
            "latestMonth": latest_month,
        },
        "overall": overall_metrics,
        "latestMonth": latest_metrics,
        "monthlyTrend": month_rows,
        "dimensionBreakdown": {
            "regionsByOrders": top_items(Counter({k: len(v) for k, v in region_order_ids.items()}), limit=8),
            "citiesByOrders": top_items(Counter({k: len(v) for k, v in city_order_ids.items()}), limit=8),
            "dealersByOrders": top_items(Counter({k: len(v) for k, v in dealer_order_ids.items()}), limit=10),
            "seriesByOrders": top_items(Counter({k: len(v) for k, v in series_orders.items()}), limit=8),
            "brandsByOrders": top_items(Counter({k: len(v) for k, v in brand_orders.items()}), limit=6),
            "channels": channel_rows[:10],
            "battleFailReasons": top_items(reason_counter, limit=8),
            "cancelReasons": top_items(cancel_reason_counter, limit=8),
            "orderStatuses": top_items(status_counter, limit=8),
        },
        "insights": [],
        "limitations": [
            "当前案例基于单个宽表 CSV 聚合，跨阶段去重已使用各对象 ID，但仍需业务确认最终口径。",
            "CSV 不包含销售目标、投放成本、库存、价格、优惠政策、竞品大盘，因此目标缺口和外部因素只能提示为待补充验证。",
            "手机号、VIN、客户 ID 等敏感字段未输出到前端案例中。",
        ],
    }

    overall = output["overall"]
    regions = output["dimensionBreakdown"]["regionsByOrders"]
    channels = output["dimensionBreakdown"]["channels"]
    reasons = output["dimensionBreakdown"]["battleFailReasons"]
    top_region = regions[0] if regions else {"name": "无", "share": None}
    top_channel = channels[0] if channels else {"name": "无", "orders": 0, "leadToOrderRate": None}
    top_reason = reasons[0] if reasons else {"name": "无", "share": None}

    output["insights"] = [
        {
            "title": "当前 CSV 已能支撑全链路漏斗诊断",
            "type": "事实",
            "confidence": "高",
            "evidence": f"全量样本包含 {overall['leads']:,} 个线索、{overall['opportunities']:,} 个机会、{overall['visits']:,} 个到店、{overall['testDrives']:,} 个试驾、{overall['orders']:,} 个订单。",
            "recommendation": "第一版 Agent 可以把该链路作为基础分析能力，但入口仍保持业务问题驱动。",
        },
        {
            "title": "订单集中度可用于快速定位 BP 复盘对象",
            "type": "事实",
            "confidence": "中高",
            "evidence": f"订单 Top 区域为 {top_region['name']}，占订单样本 {top_region['share']}%。",
            "recommendation": "在报告中默认输出区域、城市、经销商 Top/Bottom 清单，支持 BA 选择是否下钻。",
        },
        {
            "title": "渠道质量需要用后链路转化判断",
            "type": "推断",
            "confidence": "中",
            "evidence": f"订单最多的线索渠道为 {top_channel['name']}，该渠道线索到订单转化率为 {top_channel['leadToOrderRate']}%。",
            "recommendation": "补充投放成本后，可把渠道分析升级为 CPL/CPA/订单贡献的 ROI 分析。",
        },
        {
            "title": "战败和取消原因能形成运营改进清单",
            "type": "事实",
            "confidence": "中",
            "evidence": f"出现最多的战败/拒绝原因是 {top_reason['name']}，占原因记录 {top_reason['share']}%。",
            "recommendation": "建议在洞察审核页让 BA 复核原因枚举，避免系统字段含义被误读。",
        },
    ]

    OUT_PATH.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {OUT_PATH}")
    print(json.dumps({
        "rows": row_count,
        "latestMonth": latest_month,
        "overall": overall_metrics,
        "topRegion": top_region,
        "topChannel": top_channel,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
