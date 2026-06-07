"""Workflow orchestration for the BP BA analysis agent POC."""

from __future__ import annotations

from .knowledge_base import (
    DEFAULT_DIMENSIONS,
    DELIVERABLE_TEMPLATES,
    SCENARIOS,
    detect_scenario,
    metrics_for_scenario,
    scenario_label,
)
from .method_library import clarification_questions_for, detect_question_types, select_methods
from .models import (
    AnalysisCase,
    DataSourcePlan,
    DeliverableDraft,
    SqlPlan,
    ValidationCheck,
)
from .semantic_layer import build_data_availability, build_semantic_matches


class BPBAAnalysisAgent:
    """Turns a business question into an auditable end-to-end analysis case."""

    def run(
        self,
        business_question: str,
        *,
        scenario: str | None = None,
        analysis_purpose: str | None = None,
        target_object: str | None = None,
        time_range: str | None = None,
        dimensions: list[str] | None = None,
        deliverable_type: str = "management_report",
        audience: str = "Sales BP / BI stakeholders",
        available_fields: list[str] | None = None,
    ) -> AnalysisCase:
        case = AnalysisCase(
            business_question=business_question,
            scenario=scenario or detect_scenario(business_question),
            analysis_purpose=analysis_purpose,
            target_object=target_object,
            time_range=time_range,
            dimensions=dimensions or [],
            deliverable_type=deliverable_type,
            audience=audience,
        )
        self.clarify(case)
        self.classify_question(case)
        self.build_analysis_framework(case)
        self.decompose_metrics(case)
        self.plan_methods_and_semantics(case, available_fields=available_fields)
        self.plan_data_access(case)
        self.plan_validation(case)
        self.generate_deliverable(case)
        self.add_human_review(case)
        return case

    def clarify(self, case: AnalysisCase) -> None:
        scenario_config = SCENARIOS.get(case.scenario or "", SCENARIOS["media"])
        if not case.analysis_purpose:
            case.analysis_purpose = str(scenario_config["default_purpose"])
            case.clarification_questions.append("请确认本次分析目的是否与 Agent 默认理解一致。")
        if not case.target_object:
            case.clarification_questions.append("请确认目标对象：大区、经销商、车型、渠道或活动？")
        if not case.time_range:
            case.clarification_questions.append("请确认分析周期：日、周、月，或活动前后对比周期？")
        if not case.dimensions:
            case.dimensions = list(scenario_config.get("core_dimensions", DEFAULT_DIMENSIONS))
            case.clarification_questions.append("请确认维度范围是否需要增加城市、活动或客户阶段。")
        for question in clarification_questions_for(case.business_question):
            if question not in case.clarification_questions:
                case.clarification_questions.append(question)

    def classify_question(self, case: AnalysisCase) -> None:
        case.question_types = [question_type.title for question_type in detect_question_types(case.business_question)]

    def build_analysis_framework(self, case: AnalysisCase) -> None:
        scenario_config = SCENARIOS.get(case.scenario or "", SCENARIOS["media"])
        case.hypotheses = list(scenario_config["hypotheses"])
        case.knowledge_tags = [
            scenario_label(case.scenario or "media"),
            *case.question_types,
            "需求澄清",
            "分析框架",
            "语义层匹配",
            "方法库编排",
            "指标拆解",
            "数据校验",
            "交付生成",
        ]

    def decompose_metrics(self, case: AnalysisCase) -> None:
        case.metric_tree = metrics_for_scenario(case.scenario or "media")

    def plan_methods_and_semantics(self, case: AnalysisCase, *, available_fields: list[str] | None) -> None:
        case.selected_methods = select_methods(case.business_question)
        method_object_keys = [
            semantic_object
            for method in case.selected_methods
            for semantic_object in method.required_semantic_objects
        ]
        case.semantic_matches = build_semantic_matches(
            question=case.business_question,
            method_object_keys=method_object_keys,
            requested_dimensions=case.dimensions,
            available_fields=available_fields,
        )
        case.data_availability = build_data_availability(
            case.semantic_matches,
            [method.title for method in case.selected_methods],
            available_fields=available_fields,
        )

    def plan_data_access(self, case: AnalysisCase) -> None:
        case.data_sources = [
            DataSourcePlan(
                name="Data Center / 数仓",
                source_type="warehouse",
                read_only=True,
                purpose="执行指标明细查询、聚合查询和样本抽查。",
                owner="ETL 大数据开发 / Data Center",
            ),
            DataSourcePlan(
                name="Tableau / BI 看板元数据",
                source_type="bi_metadata",
                read_only=True,
                purpose="复用已有看板口径，进行跨报表对账。",
                owner="BI 产品团队",
            ),
            DataSourcePlan(
                name="KM / AMP 知识库",
                source_type="knowledge_base",
                read_only=True,
                purpose="检索历史分析案例、BRD、指标说明和隐性经验。",
                owner="BP BA / 知识管理平台",
            ),
        ]
        case.sql_plan = [self._build_sql_plan(metric.name, metric.source_tables, case) for metric in case.metric_tree]

    def plan_validation(self, case: AnalysisCase) -> None:
        case.validation_plan = [
            ValidationCheck(
                name="跨来源指标对账",
                check_type="source_reconciliation",
                method="同一指标在数仓、Tableau、历史 Excel 中按相同周期和维度聚合后比较。",
                pass_criteria="核心指标差异在业务约定阈值内；超阈值必须生成差异说明。",
            ),
            ValidationCheck(
                name="口径一致性检查",
                check_type="semantic_consistency",
                method="检查指标公式、过滤条件、归因口径和维度粒度是否与指标字典一致。",
                pass_criteria="所有交付指标都有可追溯口径；口径差异需显式标注。",
            ),
            ValidationCheck(
                name="异常波动识别",
                check_type="outlier_detection",
                method="按日/周/月趋势识别环比、同比或活动前后异常波动。",
                pass_criteria="异常波动必须给出候选原因或标记为待人工确认。",
            ),
            ValidationCheck(
                name="样本量和缺失值提示",
                check_type="data_quality",
                method="检查样本量、空值、重复主键和维度覆盖率。",
                pass_criteria="关键维度无严重缺失；不足样本不得输出强结论。",
            ),
        ]

    def generate_deliverable(self, case: AnalysisCase) -> None:
        template_key = case.deliverable_type
        if (case.scenario or "") == "target_steering":
            template_key = "target_steering"
        template = DELIVERABLE_TEMPLATES.get(template_key, DELIVERABLE_TEMPLATES["management_report"])
        metric_names = "、".join(metric.name for metric in case.metric_tree[:5])
        case.deliverable = DeliverableDraft(
            executive_summary=[
                f"业务问题：{case.business_question}",
                f"分析目的：{case.analysis_purpose}",
                f"核心指标：{metric_names}",
                "当前结论为 Agent 草稿，需 BP BA 基于真实数据审核后发布。",
            ],
            excel_tabs=template["excel_tabs"],
            ppt_storyline=template["ppt_storyline"],
            brd_sections=template["brd_sections"],
        )

    def add_human_review(self, case: AnalysisCase) -> None:
        case.human_review_checkpoints = [
            "需求澄清完成后，BP BA 确认分析目的、场景、范围和交付形式。",
            "SQL/取数计划执行前，BP BA 或 ETL 确认表、字段、过滤条件和指标口径。",
            "数据校验完成后，BP BA 确认差异解释和待人工确认事项。",
            "PPT/Excel/BRD 草稿发布前，BP BA 确认结论强度和业务表述。",
        ]

    def _build_sql_plan(self, metric_name: str, source_tables: list[str], case: AnalysisCase) -> SqlPlan:
        table = source_tables[0]
        dimension_sql = ", ".join(self._sql_identifier(dimension) for dimension in case.dimensions[:4])
        select_dimensions = f"{dimension_sql}, " if dimension_sql else ""
        filters = ["time_range", "target_object"]
        sql = (
            f"select {select_dimensions}'{metric_name}' as metric_name, /* metric_formula */ as metric_value\n"
            f"from {table}\n"
            "where event_date between :start_date and :end_date\n"
            "  and (:target_object is null or target_object = :target_object)\n"
            f"group by {dimension_sql if dimension_sql else '1'};"
        )
        return SqlPlan(
            metric=metric_name,
            purpose=f"计算并校验 {metric_name}",
            sql=sql,
            required_filters=filters,
            review_notes=[
                "SQL 为可审核计划，不直接写入生产。",
                "执行前需将 metric_formula 替换为指标字典确认后的真实公式。",
                "中文维度名需要在真实语义层映射为物理字段名。",
            ],
        )

    @staticmethod
    def _sql_identifier(name: str) -> str:
        mapping = {
            "日期": "event_date",
            "月份": "month_id",
            "大区": "region_name",
            "城市": "city_name",
            "经销商": "dealer_id",
            "车型": "model_name",
            "渠道": "channel_name",
            "活动": "campaign_id",
            "客户阶段": "customer_stage",
        }
        return mapping.get(name, name)
