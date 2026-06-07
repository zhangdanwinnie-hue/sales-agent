"""Reusable BP BA analysis topics and field maps for sales funnel data."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class AnalysisTopic:
    key: str
    title: str
    business_questions: list[str]
    required_fields: list[str]
    optional_fields: list[str]
    default_dimensions: list[str]
    core_metrics: list[str]
    output_template: list[str]
    cautions: list[str]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


ANALYSIS_TOPICS: list[AnalysisTopic] = [
    AnalysisTopic(
        key="sales_funnel_conversion",
        title="销售漏斗转化分析",
        business_questions=[
            "register 到 leads/oppty/visit/td/order 哪个阶段掉点最大？",
            "不同渠道、区域、车型、经销商的漏斗表现是否异常？",
        ],
        required_fields=[
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
        ],
        optional_fields=["region_route", "brand_route", "leads_channel_name", "register_model", "dealer_status_name"],
        default_dimensions=["渠道", "区域", "车型", "经销商状态"],
        core_metrics=["阶段记录量", "阶段转化率", "order/leads", "order/oppty", "阶段缺失率"],
        output_template=["漏斗总览", "掉点阶段定位", "维度下钻", "异常原因假设", "待确认口径"],
        cautions=["先确认表粒度；演示可按 ID 非空行数，正式分析建议 distinct ID 或语义层口径。"],
    ),
    AnalysisTopic(
        key="media_channel_efficiency",
        title="媒体投流与渠道效率分析",
        business_questions=[
            "哪些渠道量高但订单转化低？",
            "汽车之家、懂车帝、DMO、抖音、易车等渠道质量差异在哪里？",
        ],
        required_fields=["leads_id", "oppty_id", "visit_id", "order_id", "leads_channel_name"],
        optional_fields=[
            "leads_sub_channel_name",
            "leads_media_platform_name",
            "register_first_channel_name",
            "register_media_platform_name",
            "leads_campaign_name",
            "register_campaign_name",
            "region_route",
            "register_model",
        ],
        default_dimensions=["渠道", "媒体平台", "Campaign", "区域", "车型"],
        core_metrics=["线索量", "机会量", "到店量", "订单量", "到店率", "订单转化率"],
        output_template=["渠道贡献排行", "渠道效率矩阵", "低效渠道定位", "区域/车型交叉拆解", "投流优化建议"],
        cautions=["渠道字段存在 register 与 leads 两套口径，必须说明使用哪套归因口径。"],
    ),
    AnalysisTopic(
        key="model_conversion",
        title="车型转化分析",
        business_questions=[
            "哪些车型线索高但订单转化低？",
            "车型问题发生在线索质量、到店、试驾还是成交阶段？",
        ],
        required_fields=["leads_id", "oppty_id", "visit_id", "td_id", "order_id"],
        optional_fields=[
            "register_model",
            "register_series",
            "leads_model_code_ssc",
            "oppty_model_code_ssc",
            "visit_model_code_ssc",
            "td_model_code_ssc",
            "order_model_code_ssc",
            "brand_route",
        ],
        default_dimensions=["品牌", "车系", "车型", "渠道", "区域"],
        core_metrics=["车型线索量", "车型到店率", "车型试驾率", "车型订单率", "车型阶段掉点"],
        output_template=["车型漏斗排行", "高量低转车型", "车型 x 渠道交叉", "车型 x 区域交叉", "定位结论"],
        cautions=["不同阶段车型字段可能不一致，需要标注 register/leads/order 车型口径。"],
    ),
    AnalysisTopic(
        key="dealer_operation",
        title="经销商运营分析",
        business_questions=[
            "哪些经销商线索多但承接弱？",
            "同区域同车型下，哪些经销商到店或成交异常？",
        ],
        required_fields=["leads_id", "oppty_id", "visit_id", "order_id"],
        optional_fields=[
            "register_dealer_id",
            "leads_dealer_id",
            "oppty_dealer_id",
            "visit_dealer_id",
            "td_dealer_id",
            "order_dealer_id",
            "dealer_status_name",
            "risk_dealer_type",
            "dealership_type_name_cn",
            "region_route",
            "city_name_zh",
            "province_name_zh",
        ],
        default_dimensions=["经销商", "区域", "城市", "车型", "经销商状态"],
        core_metrics=["经销商线索量", "经销商到店率", "经销商订单率", "风险/关闭状态占比", "异常排名"],
        output_template=["经销商表现矩阵", "异常经销商清单", "同区域对标", "承接问题假设", "行动建议"],
        cautions=["经销商名称和人员字段可能敏感；输出优先使用脱敏 ID 或聚合排名。"],
    ),
    AnalysisTopic(
        key="regional_performance",
        title="区域/大区表现分析",
        business_questions=[
            "East/North/West/South 漏斗效率差异在哪里？",
            "区域差异是渠道结构、车型结构还是经销商承接导致？",
        ],
        required_fields=["leads_id", "oppty_id", "visit_id", "order_id", "region_route"],
        optional_fields=[
            "region_name_zh",
            "sales_bmw_big_area_name_zh",
            "sales_bmw_small_area_name_zh",
            "province_name_zh",
            "city_name_zh",
            "leads_channel_name",
            "register_model",
        ],
        default_dimensions=["区域", "大区", "省份", "城市", "渠道", "车型"],
        core_metrics=["区域线索量", "区域到店率", "区域订单率", "区域结构占比", "区域异常变化"],
        output_template=["区域漏斗对比", "区域结构拆解", "区域异常定位", "城市/经销商下钻", "管理建议"],
        cautions=["区域字段可能存在 route 与中文区域名称两套体系，需固定口径。"],
    ),
    AnalysisTopic(
        key="campaign_effectiveness",
        title="Campaign 活动效果分析",
        business_questions=[
            "哪些 campaign 带来高质量线索？",
            "活动效果是否集中在特定车型、渠道或区域？",
        ],
        required_fields=["leads_id", "oppty_id", "visit_id", "order_id"],
        optional_fields=[
            "leads_campaign_id",
            "leads_campaign_name",
            "leads_campaign_type_cmc",
            "register_campaign_id",
            "register_campaign_name",
            "register_campaign_type_cmc",
            "leads_channel_name",
            "region_route",
            "register_model",
        ],
        default_dimensions=["Campaign", "活动类型", "渠道", "区域", "车型"],
        core_metrics=["活动线索量", "活动到店率", "活动订单率", "活动贡献占比", "活动质量排名"],
        output_template=["Campaign 排行", "活动质量矩阵", "渠道/车型/区域下钻", "异常活动解释", "复盘建议"],
        cautions=["Campaign 名称可能很长且口径混杂，建议同时保留 campaign_id 和 campaign_name。"],
    ),
    AnalysisTopic(
        key="follow_up_efficiency",
        title="销售跟进效率分析",
        business_questions=[
            "跟进速度是否影响订单转化？",
            "哪些经销商或渠道线索响应慢？",
        ],
        required_fields=["leads_id", "oppty_id", "order_id"],
        optional_fields=[
            "leads_first_follow_mindiff",
            "oppty_first_oppty_follow_mindiff",
            "oppty_leads_sr_datediff",
            "oppty_sr_datediff",
            "oppty_td_datediff",
            "oppty_order_datediff",
            "order_first_sr_order_datediff",
            "order_last_sr_order_datediff",
            "leads_channel_name",
            "leads_dealer_id",
        ],
        default_dimensions=["渠道", "经销商", "区域", "车型"],
        core_metrics=["首次跟进时长", "到店间隔", "试驾间隔", "订单间隔", "超时线索订单率"],
        output_template=["跟进时效分布", "快慢组转化对比", "渠道/经销商响应排行", "影响判断", "改进建议"],
        cautions=["时长字段需确认单位和起止点；空值不能简单按 0 处理。"],
    ),
    AnalysisTopic(
        key="conversion_cycle_analysis",
        title="转化周期分析",
        business_questions=[
            "线上线索到到店需要多久？周期变长是否影响订单转化？",
            "到店到订单的成交周期在哪些区域、城市、经销商或车型上异常？",
        ],
        required_fields=[
            "leads_id",
            "visit_id",
            "order_id",
            "leads_create_time",
            "visit_arrival_time",
            "order_first_confirm_time",
        ],
        optional_fields=[
            "register_create_time",
            "oppty_create_time",
            "td_start_time",
            "leads_first_follow_mindiff",
            "oppty_leads_sr_datediff",
            "oppty_td_datediff",
            "oppty_order_datediff",
            "order_first_sr_order_datediff",
            "leads_channel_name",
            "leads_media_platform_name",
            "region_route",
            "city_name_zh",
            "leads_dealer_id",
            "register_model",
        ],
        default_dimensions=["周期分层", "渠道", "区域", "城市", "经销商", "车型"],
        core_metrics=[
            "线索到到店周期",
            "到店到订单周期",
            "7/14/30 天内到店率",
            "7/14/30 天内成交率",
            "周期分层订单率",
        ],
        output_template=[
            "周期分布总览",
            "快慢周期分层转化对比",
            "渠道/区域/经销商周期异常定位",
            "周期变长原因假设",
            "缩短周期行动建议",
        ],
        cautions=[
            "必须确认起止时间字段：线上线索用 leads_create_time，到店用 visit_arrival_time，订单用 order_first_confirm_time。",
            "周期分析要排除空时间、倒挂时间和极端异常值，再输出业务结论。",
        ],
    ),
    AnalysisTopic(
        key="battle_fail_loss",
        title="战败/流失原因分析",
        business_questions=[
            "机会为什么没有转化？",
            "战败集中在哪些车型、渠道、区域、经销商？",
        ],
        required_fields=["oppty_id", "oppty_opportunity_status_desc"],
        optional_fields=[
            "oppty_battle_fail_type_desc",
            "oppty_battle_fail_time",
            "oppty_battle_fail_primary_reason_desc",
            "oppty_battle_fail_secondary_reason_desc",
            "oppty_status_flag_nation",
            "oppty_status_flag_region",
            "oppty_pipeline_stage_desc",
            "leads_channel_name",
            "register_model",
            "region_route",
        ],
        default_dimensions=["战败原因", "渠道", "车型", "区域", "经销商"],
        core_metrics=["战败机会量", "战败率", "主原因占比", "阶段分布", "高战败组合"],
        output_template=["战败总览", "原因 Pareto", "维度交叉定位", "典型问题假设", "挽回/优化建议"],
        cautions=["战败原因依赖销售填写质量，需同时看空值率和异常原因值。"],
    ),
    AnalysisTopic(
        key="customer_repeat_cross_dealer",
        title="客户重复/跨店/跨区域分析",
        business_questions=[
            "客户是否多次留资或跨店流转？",
            "多店询价是否影响成交？",
        ],
        required_fields=["leads_id"],
        optional_fields=[
            "customer_spark_id",
            "customer_id",
            "leads_dealer_cnt_nation_ytd",
            "leads_dealer_cnt_nation_6m",
            "leads_dealer_cnt_city_mtd",
            "leads_channel_cnt_nation_ytd",
            "transfer_ticket_flag",
            "transfer_source_dealer_id",
            "transfer_target_dealer_id",
            "order_id",
        ],
        default_dimensions=["客户重复度", "跨店", "跨城市", "跨区域", "渠道"],
        core_metrics=["重复留资率", "跨店线索占比", "跨店订单率", "转派成功率", "多渠道触达数"],
        output_template=["重复/跨店总览", "客户流转路径", "成交差异", "风险与机会", "治理建议"],
        cautions=["客户级分析权限风险最高；默认只输出聚合，不导出手机号、姓名、明细 ID。"],
    ),
    AnalysisTopic(
        key="loyal_customer_new_car_sales",
        title="保客新车销售分析",
        business_questions=[
            "保客再购表现如何？保客线索、到店、订单转化是否高于新客？",
            "保客到店转化低，是渠道触达问题、车型匹配问题还是经销商承接问题？",
        ],
        required_fields=["leads_id", "visit_id", "order_id", "customer_loyal_flag"],
        optional_fields=[
            "customer_spark_id",
            "customer_id",
            "customer_group_desc",
            "customer_source_desc",
            "customer_loyal_vehicle_cnt",
            "customer_loyal_eseries",
            "customer_loyal_vehicle_age",
            "customer_loyal_last_order_mile",
            "customer_loyal_afs_level",
            "leads_channel_name",
            "leads_media_platform_name",
            "brand_route",
            "register_model",
            "region_route",
            "city_name_zh",
            "leads_dealer_id",
            "order_id",
        ],
        default_dimensions=["保客/新客", "车龄", "历史车系", "渠道", "区域", "经销商", "意向车型"],
        core_metrics=[
            "保客线索量",
            "保客到店率",
            "保客订单率",
            "保客再购率",
            "保客 vs 新客转化差异",
        ],
        output_template=[
            "保客新车漏斗总览",
            "保客/新客转化对比",
            "车龄/历史车系分层",
            "渠道/区域/经销商定位",
            "保客运营动作建议",
        ],
        cautions=[
            "保客分析涉及客户级字段，默认只做聚合分层，不导出手机号、姓名、客户明细 ID。",
            "customer_loyal_flag 的业务定义需先确认：是否代表有效保客、历史车主或会员状态。",
        ],
    ),
    AnalysisTopic(
        key="single_stage_review",
        title="单环节复盘分析",
        business_questions=[
            "客流下降是自然客流下降，还是线上客流下降？",
            "某一环节下降应如何按区域、城市、经销商、渠道、车型拆解贡献？",
        ],
        required_fields=["visit_id", "visit_arrival_time"],
        optional_fields=[
            "leads_id",
            "register_rcid",
            "oppty_id",
            "order_id",
            "visit_create_time",
            "visit_is_nature_sr_flag",
            "visit_first_visit_flag_dealer_mtd",
            "visit_first_visit_flag_city_mtd",
            "visit_first_visit_flag_region_mtd",
            "visit_first_sr_flag_dealer_mtd",
            "visit_first_sr_flag_city_mtd",
            "visit_first_sr_flag_region_mtd",
            "visit_dealer_id",
            "leads_channel_name",
            "leads_media_platform_name",
            "leads_campaign_name",
            "region_route",
            "province_name_zh",
            "city_name_zh",
            "register_model",
            "dealer_status_name",
        ],
        default_dimensions=["环节", "自然/线上", "区域", "城市", "经销商", "渠道", "车型"],
        core_metrics=[
            "环节量级",
            "环比/同比变化",
            "自然客流量",
            "线上客流量",
            "维度贡献度",
        ],
        output_template=[
            "单环节趋势总览",
            "自然 vs 线上拆解",
            "区域/城市/经销商贡献拆解",
            "渠道/车型结构变化",
            "下降原因假设与验证清单",
        ],
        cautions=[
            "单环节复盘要先定义环节口径：客流、线索、到店、试驾或订单；不同环节使用不同主时间字段。",
            "下降归因建议使用贡献拆解，而不是只看 Top 排名，避免高基数维度天然靠前。",
        ],
    ),
    AnalysisTopic(
        key="data_quality_reconciliation",
        title="数据质量和口径校验分析",
        business_questions=[
            "核心字段缺失率是否影响结论？",
            "leads/oppty/order 链路是否存在断层或口径差异？",
        ],
        required_fields=["leads_id", "oppty_id", "order_id", "etl_batch_time"],
        optional_fields=[
            "register_rcid",
            "visit_id",
            "td_id",
            "register_valid_flag",
            "visit_valid_flag",
            "order_deleted_desc",
            "leads_channel_name",
            "region_route",
            "brand_route",
            "register_model",
        ],
        default_dimensions=["阶段", "字段", "渠道", "区域", "车型"],
        core_metrics=["字段填充率", "阶段断层率", "重复率", "删除/无效记录占比", "口径差异清单"],
        output_template=["字段健康度", "链路断层检查", "口径差异解释", "影响评估", "修复/确认清单"],
        cautions=["质量结论要先于业务结论；严重缺失字段不能支撑强业务判断。"],
    ),
]

TOPIC_TRIGGER_TERMS: dict[str, list[str]] = {
    "sales_funnel_conversion": ["漏斗", "转化", "掉点", "register", "leads", "oppty", "visit", "td", "order"],
    "media_channel_efficiency": ["媒体", "投流", "渠道", "汽车之家", "懂车帝", "dmo", "抖音", "易车", "线索多", "订单转化低"],
    "model_conversion": ["车型", "车系", "model", "高线索低订单", "试驾率"],
    "dealer_operation": ["经销商", "门店", "承接", "dealer", "运营", "风险经销商"],
    "regional_performance": ["区域", "大区", "east", "north", "west", "south", "城市", "省份"],
    "campaign_effectiveness": ["campaign", "活动", "活动效果", "活动质量"],
    "follow_up_efficiency": ["跟进", "响应", "时长", "mindiff", "datediff", "首次跟进"],
    "conversion_cycle_analysis": ["转化周期", "周期", "线上线索到到店", "到店到订单", "线索-到店", "到店-订单", "成交周期"],
    "battle_fail_loss": ["战败", "流失", "battle", "失败原因", "未转化原因"],
    "customer_repeat_cross_dealer": ["重复", "跨店", "跨区域", "多次留资", "转派", "transfer"],
    "loyal_customer_new_car_sales": ["保客", "再购", "复购", "老客", "保客到店", "保客新车", "loyal"],
    "single_stage_review": ["单环节", "复盘", "客流下降", "自然客流", "线上客流", "下降", "贡献拆解"],
    "data_quality_reconciliation": ["数据质量", "口径", "校验", "缺失", "断层", "填充率", "etl"],
}


def list_analysis_topics() -> list[dict[str, object]]:
    return [topic.to_dict() for topic in ANALYSIS_TOPICS]


def get_analysis_topic(key: str) -> AnalysisTopic:
    for topic in ANALYSIS_TOPICS:
        if topic.key == key:
            return topic
    valid = ", ".join(topic.key for topic in ANALYSIS_TOPICS)
    raise KeyError(f"Unknown analysis topic: {key}. Valid topics: {valid}")


def recommend_topics(question: str, limit: int = 3) -> list[AnalysisTopic]:
    question_lower = question.lower()
    scored: list[tuple[int, AnalysisTopic]] = []
    for topic in ANALYSIS_TOPICS:
        haystack = " ".join([topic.title, *topic.business_questions, *topic.default_dimensions, *topic.core_metrics]).lower()
        score = sum(1 for token in _tokens(question_lower) if token and token in haystack)
        score += sum(3 for term in TOPIC_TRIGGER_TERMS.get(topic.key, []) if term.lower() in question_lower)
        if topic.key in question_lower:
            score += 5
        if score:
            scored.append((score, topic))
    scored.sort(key=lambda item: item[0], reverse=True)
    if not scored:
        return ANALYSIS_TOPICS[:limit]
    return [topic for _, topic in scored[:limit]]


def _tokens(text: str) -> list[str]:
    separators = " ，,。？?：:、/\\|-_()（）"
    tokens: list[str] = []
    current = []
    for char in text:
        if char in separators:
            if current:
                tokens.append("".join(current))
                current = []
        else:
            current.append(char)
    if current:
        tokens.append("".join(current))
    return tokens
