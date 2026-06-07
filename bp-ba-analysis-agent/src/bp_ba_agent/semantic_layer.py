"""Business semantic layer for flexible BP BA analysis planning."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable

from .models import DataAvailabilityItem, SemanticMatch


@dataclass(frozen=True)
class BusinessObject:
    key: str
    title: str
    description: str
    id_candidates: list[str]
    time_candidates: list[str]
    metric_names: list[str]
    dimension_names: list[str]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class SemanticMetric:
    key: str
    title: str
    definition: str
    business_object: str
    physical_field_candidates: list[str]
    default_aggregation: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class SemanticDimension:
    key: str
    title: str
    description: str
    physical_field_candidates: list[str]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


BUSINESS_OBJECTS: dict[str, BusinessObject] = {
    "customer": BusinessObject(
        key="customer",
        title="客户",
        description="客户身份、保客/新客、跨店、重复留资等客户级分析对象。",
        id_candidates=["customer_id", "customer_spark_id", "leads_mobile_phone_number"],
        time_candidates=["leads_create_time", "register_create_time"],
        metric_names=["客户数", "保客数", "重复留资客户数"],
        dimension_names=["客户类型", "客户阶段", "渠道", "区域"],
    ),
    "lead": BusinessObject(
        key="lead",
        title="线索",
        description="注册、留资、线索生成和线索质量分析对象。",
        id_candidates=["leads_id", "register_rcid"],
        time_candidates=["leads_create_time", "register_create_time"],
        metric_names=["线索量", "有效线索率", "首跟进时长"],
        dimension_names=["渠道", "活动", "车型", "区域", "经销商"],
    ),
    "opportunity": BusinessObject(
        key="opportunity",
        title="机会",
        description="机会创建、跟进、战败、承接和销售过程分析对象。",
        id_candidates=["oppty_id", "leads_opportunity_id"],
        time_candidates=["oppty_create_time", "oppty_opportunity_time"],
        metric_names=["机会量", "机会转化率", "战败率"],
        dimension_names=["阶段", "战败原因", "销售顾问", "经销商"],
    ),
    "visit": BusinessObject(
        key="visit",
        title="到店/客流",
        description="客户到店、自然客流、线上客流、复访和邀约分析对象。",
        id_candidates=["visit_id"],
        time_candidates=["visit_arrival_time", "visit_create_time"],
        metric_names=["客流量", "到店率", "复访率"],
        dimension_names=["自然/线上", "区域", "城市", "经销商", "车型"],
    ),
    "test_drive": BusinessObject(
        key="test_drive",
        title="试驾",
        description="试驾预约、试驾执行和试驾后转化分析对象。",
        id_candidates=["td_id"],
        time_candidates=["td_start_time", "td_create_time"],
        metric_names=["试驾量", "试驾率", "试驾后订单率"],
        dimension_names=["车型", "经销商", "销售顾问", "渠道"],
    ),
    "order": BusinessObject(
        key="order",
        title="订单",
        description="订单创建、取消、交付和成交结果分析对象。",
        id_candidates=["order_id", "order_so_no"],
        time_candidates=["order_create_time", "order_first_confirm_time", "order_handover_time"],
        metric_names=["订单量", "成交率", "取消率", "交付率"],
        dimension_names=["品牌", "车系", "车型", "区域", "经销商", "渠道"],
    ),
    "dealer": BusinessObject(
        key="dealer",
        title="经销商",
        description="经销商网络、运营承接、状态、风险和区域归属分析对象。",
        id_candidates=["dealer_id", "leads_dealer_id", "order_dealer_id", "visit_dealer_id"],
        time_candidates=["etl_batch_time"],
        metric_names=["经销商数", "经销商转化率", "风险经销商占比"],
        dimension_names=["大区", "省份", "城市", "经销商状态", "投资人"],
    ),
    "channel_campaign": BusinessObject(
        key="channel_campaign",
        title="渠道与活动",
        description="媒体、渠道、活动、投流和归因分析对象。",
        id_candidates=["leads_channel_name", "leads_campaign_id", "register_campaign_id"],
        time_candidates=["leads_create_time", "register_create_time"],
        metric_names=["渠道线索量", "渠道订单量", "活动转化率"],
        dimension_names=["渠道", "媒体平台", "活动", "活动类型"],
    ),
}


SEMANTIC_METRICS: dict[str, SemanticMetric] = {
    "lead_count": SemanticMetric("lead_count", "线索量", "指定周期内进入销售链路的线索数量。", "lead", ["leads_id"], "count_distinct"),
    "visit_count": SemanticMetric("visit_count", "客流量", "指定周期内有效到店或访问数量。", "visit", ["visit_id"], "count_distinct"),
    "test_drive_count": SemanticMetric("test_drive_count", "试驾量", "指定周期内试驾记录数量。", "test_drive", ["td_id"], "count_distinct"),
    "order_count": SemanticMetric("order_count", "订单量", "指定周期内有效订单数量。", "order", ["order_id"], "count_distinct"),
    "lead_to_order_rate": SemanticMetric("lead_to_order_rate", "线索到订单转化率", "订单量除以线索量。", "order", ["order_id", "leads_id"], "ratio"),
    "visit_to_order_rate": SemanticMetric("visit_to_order_rate", "到店到订单转化率", "订单量除以客流量。", "order", ["order_id", "visit_id"], "ratio"),
    "cancel_rate": SemanticMetric("cancel_rate", "订单取消率", "取消订单占订单总量比例。", "order", ["order_cancel_flag", "order_cancel_time"], "ratio"),
    "follow_up_speed": SemanticMetric("follow_up_speed", "首跟进时长", "线索生成到首次跟进的时间差。", "lead", ["leads_first_follow_mindiff"], "median"),
}


SEMANTIC_DIMENSIONS: dict[str, SemanticDimension] = {
    "time": SemanticDimension("time", "时间", "日期、周、月和活动前后周期。", ["register_create_time", "leads_create_time", "order_create_time"]),
    "region": SemanticDimension("region", "区域", "大区、省份、城市和销售小区。", ["region_route", "register_cyd_region_name_zh", "register_cyd_city_name_zh", "city_name_zh"]),
    "dealer": SemanticDimension("dealer", "经销商", "经销商 ID、名称、状态和归属。", ["leads_dealer_id", "order_dealer_id", "visit_dealer_id", "dealer_id"]),
    "channel": SemanticDimension("channel", "渠道", "一级渠道、二级渠道、媒体平台和来源。", ["leads_channel_name", "register_first_channel_name", "leads_media_platform_name"]),
    "campaign": SemanticDimension("campaign", "活动", "活动 ID、名称、类型和投放范围。", ["leads_campaign_id", "leads_campaign_name", "register_campaign_name"]),
    "model": SemanticDimension("model", "车型", "品牌、车系、车型、能源类型和配置。", ["register_model", "leads_model_code_ssc", "order_model_code_ssc", "brand_route"]),
    "sales": SemanticDimension("sales", "销售组织/人员", "销售顾问、跟进人、确认人和组织角色。", ["oppty_follow_user_id", "order_consultant_id", "td_executive_user_id"]),
    "customer": SemanticDimension("customer", "客户类型", "新客、保客、跨店、重复留资等客户分层。", ["customer_loyal_flag", "leads_new_flag_nation_180d", "leads_dealer_cnt_nation_ytd"]),
}


def list_business_objects() -> list[dict[str, object]]:
    return [item.to_dict() for item in BUSINESS_OBJECTS.values()]


def list_semantic_metrics() -> list[dict[str, object]]:
    return [item.to_dict() for item in SEMANTIC_METRICS.values()]


def list_semantic_dimensions() -> list[dict[str, object]]:
    return [item.to_dict() for item in SEMANTIC_DIMENSIONS.values()]


def build_semantic_matches(
    *,
    question: str,
    method_object_keys: Iterable[str],
    requested_dimensions: Iterable[str],
    available_fields: Iterable[str] | None = None,
) -> list[SemanticMatch]:
    field_set = {field.lower() for field in available_fields or []}
    object_keys = _infer_business_objects(question, method_object_keys)
    matches: list[SemanticMatch] = []
    for object_key in object_keys:
        business_object = BUSINESS_OBJECTS[object_key]
        required_fields = business_object.id_candidates + business_object.time_candidates
        available, missing = _field_availability(required_fields, field_set)
        status = _status(available_fields, missing)
        dimensions = _matched_dimensions(business_object, requested_dimensions, question)
        matches.append(
            SemanticMatch(
                business_object=business_object.title,
                matched_metrics=business_object.metric_names,
                matched_dimensions=dimensions,
                available_fields=available,
                missing_fields=missing,
                status=status,
            )
        )
    return matches


def build_data_availability(
    matches: Iterable[SemanticMatch],
    selected_method_titles: Iterable[str],
    available_fields: Iterable[str] | None = None,
) -> list[DataAvailabilityItem]:
    items: list[DataAvailabilityItem] = []
    has_physical_fields = available_fields is not None
    for match in matches:
        items.append(
            DataAvailabilityItem(
                requirement=f"{match.business_object} 语义对象",
                status=match.status,
                available_fields=match.available_fields,
                missing_fields=match.missing_fields,
                note="已接入字段清单，可判断物理字段覆盖。" if has_physical_fields else "尚未接入字段清单，需要 BA 在数据资产页确认映射。",
            )
        )
    for method_title in selected_method_titles:
        items.append(
            DataAvailabilityItem(
                requirement=f"{method_title} 方法输入",
                status="requires_ba_confirmation",
                available_fields=[],
                missing_fields=[],
                note="需要 BA 确认目标指标、时间范围、过滤条件和下钻维度后才能执行。",
            )
        )
    return items


def _infer_business_objects(question: str, method_object_keys: Iterable[str]) -> list[str]:
    lowered = question.lower()
    keys: list[str] = []
    term_map = {
        "customer": ["客户", "保客", "新客", "重复", "跨店"],
        "lead": ["线索", "留资", "注册", "leads", "register"],
        "opportunity": ["机会", "战败", "oppty"],
        "visit": ["客流", "到店", "自然客流", "线上客流", "visit"],
        "test_drive": ["试驾", "td"],
        "order": ["订单", "成交", "交付", "取消", "order"],
        "dealer": ["经销商", "门店", "dealer"],
        "channel_campaign": ["渠道", "媒体", "活动", "campaign", "投流"],
    }
    for key, terms in term_map.items():
        if any(term.lower() in lowered for term in terms):
            keys.append(key)
    for method_object in method_object_keys:
        if method_object in {"target_metric", "outcome", "target"} and "order" not in keys:
            keys.append("order")
        if method_object in {"funnel_stage", "stage_id"}:
            for funnel_key in ["lead", "opportunity", "visit", "test_drive", "order"]:
                if funnel_key not in keys:
                    keys.append(funnel_key)
        if method_object in {"geo_dimension", "peer_group"} and "dealer" not in keys:
            keys.append("dealer")
    if not keys:
        keys = ["lead", "order", "dealer"]
    return keys[:7]


def _field_availability(required_fields: Iterable[str], field_set: set[str]) -> tuple[list[str], list[str]]:
    if not field_set:
        return [], list(required_fields)
    available: list[str] = []
    missing: list[str] = []
    for field in required_fields:
        if field.lower() in field_set:
            available.append(field)
        else:
            missing.append(field)
    return available, missing


def _status(available_fields: Iterable[str] | None, missing: list[str]) -> str:
    if available_fields is None:
        return "requires_mapping"
    if not missing:
        return "available"
    return "partially_available"


def _matched_dimensions(business_object: BusinessObject, requested_dimensions: Iterable[str], question: str) -> list[str]:
    requested = list(requested_dimensions)
    if requested:
        return requested[:6]
    lowered = question.lower()
    matched = [dimension for dimension in business_object.dimension_names if dimension.lower() in lowered]
    return matched or business_object.dimension_names[:4]
