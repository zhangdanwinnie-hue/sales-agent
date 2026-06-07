"""Seed business knowledge for the BP BA analysis agent.

This file intentionally keeps the POC knowledge human-readable. In production,
the same concepts should be loaded from KM/AMP, a metric semantic layer, and BI
metadata rather than being hardcoded in Python.
"""

from __future__ import annotations

from .models import MetricDefinition


DEFAULT_DIMENSIONS = [
    "日期",
    "大区",
    "城市",
    "经销商",
    "车型",
    "渠道",
    "活动",
    "客户阶段",
]


SCENARIOS: dict[str, dict[str, object]] = {
    "media": {
        "label": "媒体投流策略",
        "keywords": ["媒体", "投流", "渠道", "线索", "归因", "转化"],
        "default_purpose": "评估渠道投流效率，定位线索到订单转化中的关键损耗点。",
        "hypotheses": [
            "投流效率下降可能来自渠道线索质量下降，而不是单纯预算不足。",
            "不同归因口径会改变渠道贡献判断，需要同时看平均归因、首归因和运营口径。",
            "线索量、客流和订单之间存在区域或车型结构性差异。",
        ],
        "core_dimensions": ["渠道", "大区", "车型", "活动", "客户阶段"],
    },
    "model_conversion": {
        "label": "车型转化问题",
        "keywords": ["车型", "转化", "订单", "试驾", "留资"],
        "default_purpose": "定位车型转化差异，解释从线索到订单的漏斗损耗。",
        "hypotheses": [
            "车型转化差异可能由线索结构、经销商承接能力或促销政策差异共同造成。",
            "高线索车型不一定高订单，需要按漏斗阶段拆解。",
            "转化异常需要结合区域和经销商分布判断是否为局部问题。",
        ],
        "core_dimensions": ["车型", "大区", "经销商", "渠道", "客户阶段"],
    },
    "dealer_operation": {
        "label": "经销商运营问题",
        "keywords": ["经销商", "门店", "运营", "客流", "异常"],
        "default_purpose": "识别经销商运营表现异常，并给出可行动的改善方向。",
        "hypotheses": [
            "经销商表现异常可能由客流不足、线索跟进不足或订单转化不足导致。",
            "同区域同车型对标能更公平地识别经销商运营问题。",
            "短期波动需要与历史趋势和活动周期交叉验证。",
        ],
        "core_dimensions": ["经销商", "大区", "城市", "车型", "日期"],
    },
    "target_steering": {
        "label": "Target steering",
        "keywords": ["target", "目标", "steering", "归因", "月度", "订单目标"],
        "default_purpose": "基于订单目标、投流和客流政策，拆解目标达成路径和资源分配建议。",
        "hypotheses": [
            "订单目标应拆解到大区、车型、渠道和经销商，避免高维目标无法执行。",
            "目标差距需要同时用线索、客流、转化效率和激励政策解释。",
            "平均归因、首归因和运营口径应并行呈现，支持不同管理决策。",
        ],
        "core_dimensions": ["大区", "车型", "渠道", "经销商", "月份"],
    },
}


METRICS: dict[str, MetricDefinition] = {
    "线索量": MetricDefinition(
        name="线索量",
        business_meaning="指定周期内进入销售链路的有效潜客数量。",
        formula="count(distinct lead_id)",
        dimensions=["日期", "渠道", "大区", "车型", "经销商"],
        source_tables=["dwd_sales_lead"],
        validation_sources=["Tableau 线索看板", "历史 Excel 分析"],
    ),
    "客流量": MetricDefinition(
        name="客流量",
        business_meaning="指定周期内到店或线上有效咨询的客户访问量。",
        formula="count(distinct visitor_id)",
        dimensions=["日期", "大区", "城市", "经销商", "车型"],
        source_tables=["dwd_customer_traffic"],
        validation_sources=["Tableau 客流看板", "Data Center 数据质量监控"],
    ),
    "订单量": MetricDefinition(
        name="订单量",
        business_meaning="指定周期内产生的有效订单数量。",
        formula="count(distinct order_id)",
        dimensions=["日期", "大区", "车型", "经销商", "渠道"],
        source_tables=["dwd_sales_order"],
        validation_sources=["Tableau 订单看板", "月度销售报告"],
    ),
    "线索到订单转化率": MetricDefinition(
        name="线索到订单转化率",
        business_meaning="衡量线索最终转化为订单的效率。",
        formula="订单量 / 线索量",
        dimensions=["日期", "渠道", "大区", "车型", "经销商"],
        source_tables=["dwd_sales_lead", "dwd_sales_order"],
        validation_sources=["Tableau 转化漏斗", "历史 Excel 分析"],
    ),
    "平均归因订单贡献": MetricDefinition(
        name="平均归因订单贡献",
        business_meaning="将订单贡献平均分摊到多个触点，用于评估整体渠道协同贡献。",
        formula="sum(order_credit / touchpoint_count)",
        dimensions=["渠道", "活动", "车型", "大区"],
        source_tables=["dws_attribution_touchpoint"],
        validation_sources=["归因模型报表", "BI 渠道分析看板"],
    ),
    "首归因订单贡献": MetricDefinition(
        name="首归因订单贡献",
        business_meaning="将订单贡献归给首个触点，用于观察拉新渠道效果。",
        formula="count(distinct order_id where is_first_touch = true)",
        dimensions=["渠道", "活动", "车型", "大区"],
        source_tables=["dws_attribution_touchpoint"],
        validation_sources=["归因模型报表", "BI 渠道分析看板"],
    ),
    "目标达成率": MetricDefinition(
        name="目标达成率",
        business_meaning="衡量实际订单与目标订单之间的达成情况。",
        formula="订单量 / 订单目标",
        dimensions=["月份", "大区", "车型", "经销商"],
        source_tables=["ads_sales_target", "dwd_sales_order"],
        validation_sources=["月度 Target 报告", "Tableau 订单看板"],
    ),
}


SCENARIO_METRICS: dict[str, list[str]] = {
    "media": ["线索量", "订单量", "线索到订单转化率", "平均归因订单贡献", "首归因订单贡献"],
    "model_conversion": ["线索量", "客流量", "订单量", "线索到订单转化率"],
    "dealer_operation": ["线索量", "客流量", "订单量", "线索到订单转化率"],
    "target_steering": ["订单量", "目标达成率", "线索量", "客流量", "平均归因订单贡献"],
}


DELIVERABLE_TEMPLATES: dict[str, dict[str, list[str]]] = {
    "management_report": {
        "excel_tabs": ["Case Overview", "Metric Detail", "Cross Validation", "Key Findings"],
        "ppt_storyline": ["业务问题与结论先行", "指标漏斗与差异定位", "关键原因拆解", "行动建议与待确认事项"],
        "brd_sections": ["背景与目标", "分析范围", "指标口径", "数据来源", "校验逻辑", "交付物"],
    },
    "data_validation": {
        "excel_tabs": ["Metric Mapping", "Source Compare", "Mismatch Log", "Review Signoff"],
        "ppt_storyline": ["校验范围", "口径差异", "异常数据", "修复建议"],
        "brd_sections": ["数据口径", "来源系统", "校验规则", "差异处理", "验收标准"],
    },
    "target_steering": {
        "excel_tabs": ["Target Breakdown", "Attribution", "Regional Gap", "Action List"],
        "ppt_storyline": ["月度目标全景", "区域/车型差距", "渠道与归因解释", "资源分配建议"],
        "brd_sections": ["目标定义", "拆解维度", "归因口径", "目标差距", "行动机制"],
    },
}


def detect_scenario(question: str) -> str:
    lowered = question.lower()
    for scenario, config in SCENARIOS.items():
        if any(keyword.lower() in lowered for keyword in config["keywords"]):
            return scenario
    return "media"


def scenario_label(scenario: str) -> str:
    return str(SCENARIOS.get(scenario, SCENARIOS["media"])["label"])


def metrics_for_scenario(scenario: str) -> list[MetricDefinition]:
    metric_names = SCENARIO_METRICS.get(scenario, SCENARIO_METRICS["media"])
    return [METRICS[name] for name in metric_names]
