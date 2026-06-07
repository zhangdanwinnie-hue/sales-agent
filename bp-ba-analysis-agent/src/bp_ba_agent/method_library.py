"""Question type detection and reusable analysis method library."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from .models import AnalysisMethodPlan


@dataclass(frozen=True)
class QuestionType:
    key: str
    title: str
    trigger_terms: list[str]
    default_methods: list[str]
    clarification_questions: list[str]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class AnalysisMethod:
    key: str
    title: str
    purpose: str
    required_semantic_objects: list[str]
    useful_metrics: list[str]
    useful_dimensions: list[str]
    outputs: list[str]
    confirmation_focus: list[str]

    def to_plan(self) -> AnalysisMethodPlan:
        return AnalysisMethodPlan(
            key=self.key,
            title=self.title,
            purpose=self.purpose,
            required_semantic_objects=self.required_semantic_objects,
            outputs=self.outputs,
            confirmation_focus=self.confirmation_focus,
        )

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


QUESTION_TYPES: list[QuestionType] = [
    QuestionType(
        key="metric_change",
        title="指标变化解释",
        trigger_terms=["下降", "上升", "波动", "变化", "环比", "同比", "达成", "缺口", "drop", "growth"],
        default_methods=["trend_analysis", "comparison_analysis", "contribution_analysis", "anomaly_detection"],
        clarification_questions=["请确认目标指标、基准周期和对比周期。"],
    ),
    QuestionType(
        key="root_cause_diagnosis",
        title="原因诊断",
        trigger_terms=["为什么", "原因", "归因", "影响因素", "导致", "定位", "拆解"],
        default_methods=["contribution_analysis", "funnel_analysis", "segmentation_analysis", "driver_analysis"],
        clarification_questions=["请确认希望优先验证哪些业务假设。"],
    ),
    QuestionType(
        key="conversion_diagnosis",
        title="转化链路诊断",
        trigger_terms=["转化", "漏斗", "到店", "试驾", "订单", "成交", "流失", "掉点"],
        default_methods=["funnel_analysis", "efficiency_analysis", "segmentation_analysis", "quality_analysis"],
        clarification_questions=["请确认链路起点、终点和各阶段有效口径。"],
    ),
    QuestionType(
        key="segment_comparison",
        title="分层对比",
        trigger_terms=["哪个", "哪些", "对比", "排名", "区域", "城市", "经销商", "渠道", "车型", "活动"],
        default_methods=["segmentation_analysis", "ranking_benchmark", "geo_analysis", "contribution_analysis"],
        clarification_questions=["请确认优先下钻维度和是否需要同组对标。"],
    ),
    QuestionType(
        key="quality_efficiency",
        title="质量与效率评估",
        trigger_terms=["质量", "效率", "跟进", "响应", "时长", "周期", "超时", "有效"],
        default_methods=["quality_analysis", "efficiency_analysis", "cohort_analysis", "driver_analysis"],
        clarification_questions=["请确认时效字段的起止点和空值处理规则。"],
    ),
    QuestionType(
        key="resource_planning",
        title="资源规划与策略建议",
        trigger_terms=["预算", "资源", "投放", "目标", "分配", "steering", "策略", "建议"],
        default_methods=["planning_scenario", "contribution_analysis", "comparison_analysis", "driver_analysis"],
        clarification_questions=["请确认约束条件、目标函数和可调整的业务动作。"],
    ),
    QuestionType(
        key="data_reconciliation",
        title="数据质量与口径校验",
        trigger_terms=["口径", "校验", "对账", "缺失", "重复", "数据质量", "字段", "etl"],
        default_methods=["quality_analysis", "comparison_analysis"],
        clarification_questions=["请确认权威口径来源和容忍差异阈值。"],
    ),
]


ANALYSIS_METHODS: dict[str, AnalysisMethod] = {
    "trend_analysis": AnalysisMethod(
        key="trend_analysis",
        title="趋势分析",
        purpose="按时间观察目标指标走势，识别变化发生的时间点和持续性。",
        required_semantic_objects=["time", "target_metric"],
        useful_metrics=["目标指标", "环比", "同比"],
        useful_dimensions=["日期", "月份"],
        outputs=["趋势图", "变化区间", "异常时间点"],
        confirmation_focus=["目标指标口径", "时间粒度", "对比周期"],
    ),
    "comparison_analysis": AnalysisMethod(
        key="comparison_analysis",
        title="对比分析",
        purpose="将目标期与基准期、目标值或同组对象对比，量化差异。",
        required_semantic_objects=["target_metric", "baseline"],
        useful_metrics=["差值", "差异率", "目标达成率"],
        useful_dimensions=["月份", "大区", "车型", "经销商"],
        outputs=["对比表", "差异热力表", "目标差距"],
        confirmation_focus=["基准选择", "目标值来源", "是否剔除异常样本"],
    ),
    "contribution_analysis": AnalysisMethod(
        key="contribution_analysis",
        title="贡献度拆解",
        purpose="按维度拆解整体变化，识别贡献最大或拖累最大的业务单元。",
        required_semantic_objects=["target_metric", "dimension"],
        useful_metrics=["变化贡献", "结构占比", "贡献率"],
        useful_dimensions=["区域", "城市", "经销商", "渠道", "车型", "活动"],
        outputs=["贡献瀑布", "Top 正负贡献", "结构变化说明"],
        confirmation_focus=["维度优先级", "贡献算法", "低样本过滤阈值"],
    ),
    "funnel_analysis": AnalysisMethod(
        key="funnel_analysis",
        title="漏斗链路分析",
        purpose="拆解业务链路各阶段转化，定位掉点阶段和受影响人群。",
        required_semantic_objects=["funnel_stage", "stage_time", "stage_id"],
        useful_metrics=["阶段量", "阶段转化率", "阶段流失率"],
        useful_dimensions=["渠道", "区域", "车型", "经销商"],
        outputs=["漏斗图", "阶段掉点表", "分层漏斗矩阵"],
        confirmation_focus=["阶段定义", "去重口径", "跨阶段归因方式"],
    ),
    "segmentation_analysis": AnalysisMethod(
        key="segmentation_analysis",
        title="分群下钻",
        purpose="把总体问题切到关键人群、区域、产品、渠道或组织单元中定位差异。",
        required_semantic_objects=["dimension", "target_metric"],
        useful_metrics=["分群指标", "均值/中位数", "差异率"],
        useful_dimensions=["客户阶段", "区域", "城市", "经销商", "车型", "渠道"],
        outputs=["分群对比表", "交叉矩阵", "高低表现分层"],
        confirmation_focus=["分群逻辑", "维度层级", "样本量下限"],
    ),
    "driver_analysis": AnalysisMethod(
        key="driver_analysis",
        title="影响因素分析",
        purpose="在候选因素中识别与目标指标变化最相关的因素，形成可验证假设。",
        required_semantic_objects=["target_metric", "candidate_driver"],
        useful_metrics=["相关性", "分层差异", "解释贡献"],
        useful_dimensions=["渠道", "车型", "价格带", "经销商能力", "跟进时效"],
        outputs=["候选驱动因素排序", "证据表", "待验证假设"],
        confirmation_focus=["是否允许使用统计推断", "业务可解释性", "混杂因素"],
    ),
    "anomaly_detection": AnalysisMethod(
        key="anomaly_detection",
        title="异常识别",
        purpose="识别异常波动、异常对象和可能的数据问题。",
        required_semantic_objects=["target_metric", "time", "dimension"],
        useful_metrics=["异常分数", "偏离度", "历史分位"],
        useful_dimensions=["日期", "区域", "经销商", "渠道"],
        outputs=["异常清单", "异常解释", "需人工复核项"],
        confirmation_focus=["异常阈值", "节假日/活动影响", "数据刷新延迟"],
    ),
    "cohort_analysis": AnalysisMethod(
        key="cohort_analysis",
        title="队列分析",
        purpose="按进入链路时间或客户状态分队列，观察后续转化和留存表现。",
        required_semantic_objects=["cohort_time", "entity_id", "outcome"],
        useful_metrics=["队列转化率", "N 日内转化", "留存/流失"],
        useful_dimensions=["进入月份", "渠道", "客户类型"],
        outputs=["队列表", "N 日转化曲线", "队列差异说明"],
        confirmation_focus=["队列起点", "观察窗口", "未成熟队列处理"],
    ),
    "efficiency_analysis": AnalysisMethod(
        key="efficiency_analysis",
        title="时效效率分析",
        purpose="评估响应、跟进、到店、成交等流程时长对结果的影响。",
        required_semantic_objects=["start_time", "end_time", "outcome"],
        useful_metrics=["平均时长", "中位时长", "超时率", "快慢组转化率"],
        useful_dimensions=["经销商", "渠道", "区域", "顾问"],
        outputs=["时长分布", "快慢组对比", "超时对象清单"],
        confirmation_focus=["时长字段单位", "异常时长处理", "是否输出个人级信息"],
    ),
    "quality_analysis": AnalysisMethod(
        key="quality_analysis",
        title="质量分析",
        purpose="判断数据质量或业务质量是否足以支撑结论。",
        required_semantic_objects=["required_field", "valid_flag"],
        useful_metrics=["有效率", "缺失率", "重复率", "删除/取消占比"],
        useful_dimensions=["来源系统", "渠道", "区域", "字段"],
        outputs=["质量评分", "缺失字段", "结论风险提示"],
        confirmation_focus=["有效定义", "权威来源", "差异处理规则"],
    ),
    "geo_analysis": AnalysisMethod(
        key="geo_analysis",
        title="区域地理分析",
        purpose="按大区、省市、城市群和经销商网络识别地域差异。",
        required_semantic_objects=["geo_dimension", "target_metric"],
        useful_metrics=["区域贡献", "城市排名", "区域转化差异"],
        useful_dimensions=["大区", "省份", "城市", "经销商"],
        outputs=["区域热力表", "城市下钻", "区域异常解释"],
        confirmation_focus=["区域层级口径", "经销商归属", "跨区流转处理"],
    ),
    "ranking_benchmark": AnalysisMethod(
        key="ranking_benchmark",
        title="排名与对标",
        purpose="识别高低表现对象，并在同组内做公平对标。",
        required_semantic_objects=["entity", "target_metric", "peer_group"],
        useful_metrics=["排名", "分位数", "同组差距"],
        useful_dimensions=["经销商", "渠道", "车型", "城市"],
        outputs=["Top/Bottom 排名", "同组对标", "标杆对象"],
        confirmation_focus=["同组定义", "极端样本剔除", "排名是否可对外披露"],
    ),
    "planning_scenario": AnalysisMethod(
        key="planning_scenario",
        title="策略与情景测算",
        purpose="基于当前表现和目标差距，测算资源、预算或动作调整的可能影响。",
        required_semantic_objects=["target", "constraint", "lever"],
        useful_metrics=["目标缺口", "资源效率", "情景结果"],
        useful_dimensions=["渠道", "区域", "车型", "经销商"],
        outputs=["情景表", "资源建议", "行动优先级"],
        confirmation_focus=["约束条件", "业务杠杆", "测算不是承诺结果"],
    ),
}


def list_question_types() -> list[dict[str, object]]:
    return [question_type.to_dict() for question_type in QUESTION_TYPES]


def list_analysis_methods() -> list[dict[str, object]]:
    return [method.to_dict() for method in ANALYSIS_METHODS.values()]


def detect_question_types(question: str, limit: int = 3) -> list[QuestionType]:
    lowered = question.lower()
    scored: list[tuple[int, QuestionType]] = []
    for question_type in QUESTION_TYPES:
        score = sum(1 for term in question_type.trigger_terms if term.lower() in lowered)
        if score:
            scored.append((score, question_type))
    scored.sort(key=lambda item: item[0], reverse=True)
    if scored:
        return [question_type for _, question_type in scored[:limit]]
    return [
        QuestionType(
            key="exploratory_analysis",
            title="探索式业务分析",
            trigger_terms=[],
            default_methods=["trend_analysis", "segmentation_analysis", "quality_analysis"],
            clarification_questions=["请确认最关心的目标指标、分析对象和输出用途。"],
        )
    ]


def select_methods(question: str, *, limit: int = 6) -> list[AnalysisMethodPlan]:
    selected: list[str] = []
    question_types = detect_question_types(question, limit=4)
    question_types.sort(key=lambda item: 0 if item.key == "metric_change" else 1)
    for question_type in question_types:
        for method_key in question_type.default_methods:
            if method_key not in selected:
                selected.append(method_key)
    return [ANALYSIS_METHODS[key].to_plan() for key in selected[:limit]]


def clarification_questions_for(question: str) -> list[str]:
    questions: list[str] = []
    for question_type in detect_question_types(question):
        for item in question_type.clarification_questions:
            if item not in questions:
                questions.append(item)
    return questions
