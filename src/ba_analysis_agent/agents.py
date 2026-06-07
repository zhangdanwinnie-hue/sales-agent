from __future__ import annotations

from typing import Any

from .llm import LLMService, apply_llm_enhancement, safe_context_from_profile
from .models import AgentSession, Stage
from .skills import AnalysisSkill, SkillContext, SkillsManager


class IntentUnderstandingAgent:
    """把自然语言问题和 BA 补充转成稳定的分析上下文。"""

    def __init__(self, skills_manager: SkillsManager | None = None, llm_service: LLMService | None = None):
        self.skills_manager = skills_manager or SkillsManager()
        self.llm_service = llm_service

    def update_context(self, session: AgentSession, user_message: str, feedback_type: str = "initial") -> dict[str, Any]:
        existing = _analysis_context(session)
        feedback = _ba_feedback(session)
        combined_question = _compose_question(session.business_question, feedback)
        skill = self.skills_manager.choose_skill(session.data_source)
        intent = getattr(skill, "parse_intent", lambda question: None)(combined_question)
        intent_data = intent.__dict__ if intent is not None else {}

        context = {
            "business_question": session.business_question,
            "latest_user_message": user_message,
            "feedback_type": feedback_type,
            "time_range": intent_data.get("time_period") or existing.get("time_range"),
            "comparison_baseline": _extract_comparison_baseline(combined_question) or existing.get("comparison_baseline"),
            "metric_focus": intent_data.get("metric_focus") or existing.get("metric_focus") or "综合",
            "metric": _metric_name(intent_data) or existing.get("metric"),
            "issue_type": intent_data.get("issue_type") or existing.get("issue_type") or "变化",
            "funnel_scope": {
                "start_stage": intent_data.get("start_stage"),
                "end_stage": intent_data.get("end_stage"),
                "mentioned_stages": intent_data.get("mentioned_stages", []),
            },
            "dimensions": intent_data.get("focus_dimensions") or existing.get("dimensions", []),
            "filters": _extract_filters(combined_question, existing.get("filters", [])),
            "audience": _extract_audience(combined_question) or existing.get("audience"),
            "open_questions": [],
            "confidence": 0.78 if self.llm_service is None else 0.84,
            "raw_user_inputs": [*existing.get("raw_user_inputs", []), user_message],
            "ba_feedback": feedback,
        }
        context["open_questions"] = _open_questions(context)
        context["understanding_summary"] = _understanding_summary(context)

        if self.llm_service is not None:
            enhanced = self.llm_service.enhance_artifact(
                stage_id="intent_understanding",
                business_problem=combined_question,
                base_artifact=context,
                safe_context=safe_context_from_profile(session.data_source),
            )
            context = _merge_llm_intent_context(
                context,
                enhanced,
                self.llm_service.provider_name,
                getattr(self.llm_service, "last_error", None),
            )
        else:
            context = apply_llm_enhancement(context, None, "disabled")

        session.extracted_params["analysis_context"] = context
        return context


class AnalysisDesignAgent:
    """分析思路拆解 Agent。"""

    def __init__(
        self,
        skill: AnalysisSkill,
        skills_manager: SkillsManager | None = None,
        llm_service: LLMService | None = None,
    ):
        self.skill = skill
        self.skills_manager = skills_manager or SkillsManager([skill])
        self.llm_service = llm_service

    def run(self, input_data: dict[str, Any]) -> dict[str, object]:
        session: AgentSession = input_data["session"]
        return self.draft(session)

    def draft(self, session: AgentSession) -> dict[str, object]:
        if _llm_enabled(self.llm_service):
            llm_artifact = self._draft_with_llm(session)
            if llm_artifact is not None:
                return llm_artifact

        return self._draft_with_skill(session)

    def _draft_with_llm(self, session: AgentSession) -> dict[str, object] | None:
        if self.llm_service is None:
            return None
        skeleton = _analysis_design_skeleton(session)
        enhanced = self.llm_service.enhance_artifact(
            stage_id="analysis_design_llm_first",
            business_problem=_question_for_analysis(session),
            base_artifact=skeleton,
            safe_context=safe_context_from_profile(session.data_source),
        )
        if not enhanced:
            return None
        artifact = apply_llm_enhancement(
            skeleton,
            enhanced,
            self.llm_service.provider_name,
            getattr(self.llm_service, "last_error", None),
        )
        return _complete_analysis_design_artifact(artifact, skeleton)

    def _draft_with_skill(self, session: AgentSession) -> dict[str, object]:
        business_question = _question_for_analysis(session)
        context = SkillContext(business_question, session.data_source)
        intent = getattr(self.skill, "parse_intent", lambda question: None)(business_question)
        business_context = self.skill.business_context(context)
        clarification_questions = self.skill.clarification_questions(context)
        metric_tree = self.skill.metric_tree(context)
        business_hypotheses = self.skill.business_hypotheses(context)
        field_requirements = self.skill.required_fields(context)
        analysis_path = self.skill.analysis_path(context)

        artifact = {
            "analysis_agent": "分析思路拆解和设计 Agent",
            "skill": self.skill.name,
            "original_business_question": session.business_question,
            "ba_feedback": _ba_feedback(session),
            "analysis_context": _analysis_context(session),
            "detected_intent": intent.__dict__ if intent is not None else {},
            "analysis_purpose": business_context["purpose"],
            "business_context": business_context,
            "clarification_questions": _analysis_context(session).get("open_questions") or clarification_questions,
            "business_hypotheses": business_hypotheses,
            "analysis_defaults": {
                "时间范围": "默认使用 BA 在确认阶段补充的分析时间窗。",
                "数据口径": "默认只输出聚合结果，不输出客户级明细。",
                "统计口径": "默认优先使用 first_flag 字段统计首次有效转化。",
                "分析对象": "围绕销售漏斗阶段、渠道、区域、经销商和车系进行拆解。",
            },
            "metrics_tree": metric_tree,
            "field_requirements": field_requirements,
            "analysis_path": analysis_path,
            "confidence_score": business_context.get("confidence", 0.8),
            "ba_confirmation_required": True,
        }
        artifact = self.skills_manager.apply_playbook_to_design(
            business_question,
            artifact,
            session.data_source,
        )
        return _enhance_with_llm(self.llm_service, "analysis_design", session, artifact)


class DataAnalysisInsightAgent:
    """数据分析和洞察 Agent。"""

    def __init__(self, skills_manager: SkillsManager | None = None, llm_service: LLMService | None = None):
        self.skills_manager = skills_manager or SkillsManager()
        self.llm_service = llm_service

    def run(self, input_data: dict[str, Any]) -> dict[str, object]:
        session: AgentSession = input_data["session"]
        return self.draft(session)

    def draft(self, session: AgentSession) -> dict[str, object]:
        design = session.require_confirmed(Stage.ANALYSIS_DESIGN)
        table = session.data_source.tables_or_sheets[0]
        available = session.data_source.all_column_names()
        fields = design.payload["field_requirements"]
        dimensions = fields.get("dimension_fields", [])[:8]
        funnel_ids = fields.get("funnel_id_fields", [])
        first_flags = fields.get("first_flag_fields", [])
        time_fields = fields.get("funnel_time_fields", [])
        data_sources = self.skills_manager.find_data_sources_for_fields(fields, session.data_source)
        sql_templates = self.skills_manager.find_sql_templates(_question_for_analysis(session), session.data_source)

        artifact = {
            "analysis_agent": "数据分析和洞察 Agent",
            "original_business_question": session.business_question,
            "ba_feedback": _ba_feedback(session),
            "analysis_context": _analysis_context(session),
            "data_source_plan": {
                "source_type": session.data_source.source_type,
                "source_name": session.data_source.source_name,
                "primary_table_or_sheet": table.name,
                "mapped_fields": data_sources,
                "unmapped_fields": fields.get("missing_recommended_fields", []),
                "privacy_policy": session.data_source.privacy_policy,
                "note": "仅使用字段元数据生成计划；不读取或外传客户级明细样本。",
            },
            "sql_plan": {
                "templates": sql_templates,
                "grain": "按 BA 确认的时间窗和维度聚合，不输出客户明细。",
                "filters_to_confirm": [
                    "分析时间窗",
                    "有效线索/有效订单口径",
                    "是否仅统计 first_flag = 'Y'",
                    "是否排除关闭经销商或取消订单",
                ],
                "fields": {
                    "time_fields": time_fields,
                    "id_fields": funnel_ids,
                    "first_flag_fields": first_flags,
                    "dimension_fields": dimensions,
                },
                "sql_queries": [
                    {
                        "id": "sales_funnel_by_dimension",
                        "name": "销售漏斗分维度聚合",
                        "purpose": "统计各阶段去重数量，支持阶段转化率和维度贡献分析。",
                        "sql": _sql_draft(table.name, available, dimensions, funnel_ids, first_flags),
                        "execution_status": "planned_only",
                    }
                ],
                "execution_order": ["sales_funnel_by_dimension"],
                "estimated_total_time": "< 5 minutes after BA-confirmed filters",
            },
            "data_quality_report": {
                "status": "planned",
                "checks": [
                    "校验各阶段 ID 去重计数不大于原始行数。",
                    "校验关键时间字段的空值率、时间范围和异常未来日期。",
                    "校验 first_flag 字段取值是否仅包含 Y/N/空。",
                    "校验订单、试驾、到店等后链路记录是否存在早于前序阶段的异常时间。",
                    "校验分维度聚合合计是否等于整体口径结果。",
                ],
                "quality_score_rule": "执行数据后按缺失率、异常时间、口径一致性生成评分。",
            },
            "insight_cards": [
                {
                    "title": "漏斗规模和转化率",
                    "claim_type": "待业务确认",
                    "summary": "按阶段统计注册、线索、商机、到店、试驾、订单数量和阶段转化率。",
                    "recommended_chart": "funnel",
                },
                {
                    "title": "最大流失阶段",
                    "claim_type": "待业务确认",
                    "summary": "比较相邻阶段转化率，定位对注册到订单总转化率影响最大的阶段。",
                    "recommended_chart": "bar",
                },
                {
                    "title": "维度贡献拆解",
                    "claim_type": "待业务确认",
                    "summary": "按渠道、区域、经销商和车系拆解转化差异，识别主要贡献项。",
                    "recommended_chart": "stacked_bar",
                },
            ],
            "pending_items": [
                "请确认以上数据来源和分析逻辑是否正确。",
                "请确认 SQL 方言版本：Hive、Spark SQL、PostgreSQL 或其他。",
                "请确认是否允许在本地执行 CSV/XLSX 聚合分析，或仍只生成取数计划。",
            ],
            "ba_confirmation_required": True,
        }
        return _enhance_with_llm(self.llm_service, "data_plan", session, artifact)


class ReportGenerationAgent:
    """报告产出和生成 Agent。"""

    def __init__(self, llm_service: LLMService | None = None):
        self.llm_service = llm_service

    def run(self, input_data: dict[str, Any]) -> dict[str, object]:
        session: AgentSession = input_data["session"]
        return self.draft(session)

    def draft(self, session: AgentSession) -> dict[str, object]:
        session.require_confirmed(Stage.DATA_PLAN)
        session.require_confirmed(Stage.INSIGHT_REVIEW)
        artifact = {
            "analysis_agent": "报告产出和生成 Agent",
            "executive_summary": [
                {
                    "claim_type": "待业务确认",
                    "text": "本报告将围绕销售漏斗规模、阶段转化、异常维度和行动建议展开。",
                },
                {
                    "claim_type": "合理推断",
                    "text": "若转化率下降集中在单一阶段，应优先定位该阶段对应的渠道、区域或经销商结构变化。",
                },
            ],
            "ppt_storyline": [
                "1. 业务问题和分析口径",
                "2. 销售漏斗整体表现",
                "3. 阶段转化和流失定位",
                "4. 渠道/区域/经销商/车系拆解",
                "5. 关键洞察、待确认事项和行动建议",
            ],
            "excel_tabs": [
                "README_口径说明",
                "Data_Profile_字段元数据",
                "Funnel_Overall_整体漏斗",
                "Funnel_By_Dimension_维度拆解",
                "Validation_Checks_校验结果",
                "Insight_Cards_洞察卡片",
            ],
            "brd_structure": [
                "背景和问题定义",
                "分析目标和范围",
                "数据源和字段口径",
                "指标树和计算逻辑",
                "核心发现",
                "业务建议",
                "风险、限制和后续需求",
            ],
            "final_review_checklist": [
                "所有结论是否有对应数据证据或明确标记为推断。",
                "敏感字段是否未出现在报告明细中。",
                "口径、时间窗、过滤条件是否已由 BA 确认。",
                "PPT、Excel、BRD 三类产物是否口径一致。",
            ],
            "ba_confirmation_required": True,
        }
        return _enhance_with_llm(self.llm_service, "report_plan", session, artifact)


def _sql_draft(
    table_name: str,
    available: set[str],
    dimensions: list[str],
    funnel_ids: list[str],
    first_flags: list[str],
) -> str:
    safe_dimensions = [dimension for dimension in dimensions if dimension in available][:4]
    select_parts = safe_dimensions.copy()
    for field in funnel_ids:
        if field in available:
            alias = field.replace("_id", "").replace("_rcid", "")
            select_parts.append(f"COUNT(DISTINCT CASE WHEN {field} IS NOT NULL THEN {field} END) AS {alias}_cnt")

    filter_comments = ["-- TODO: add BA-confirmed date range"]
    for flag in first_flags:
        if flag in available:
            filter_comments.append(f"-- Optional filter after BA confirmation: {flag} = 'Y'")

    select_sql = ",\n  ".join(select_parts) if select_parts else "COUNT(*) AS row_cnt"
    group_sql = f"\nGROUP BY {', '.join(safe_dimensions)}" if safe_dimensions else ""
    comment_sql = "\n".join(filter_comments)
    return (
        f"SELECT\n  {select_sql}\n"
        f"FROM {table_name}\n"
        f"WHERE 1 = 1\n"
        f"{comment_sql}"
        f"{group_sql};"
    )


def _enhance_with_llm(
    llm_service: LLMService | None,
    stage_id: str,
    session: AgentSession,
    artifact: dict[str, Any],
) -> dict[str, Any]:
    if llm_service is None:
        return apply_llm_enhancement(artifact, None, "disabled")
    safe_context = safe_context_from_profile(session.data_source)
    enhanced = llm_service.enhance_artifact(
        stage_id=stage_id,
        business_problem=_question_for_analysis(session),
        base_artifact=artifact,
        safe_context=safe_context,
    )
    return apply_llm_enhancement(
        artifact,
        enhanced,
        llm_service.provider_name,
        getattr(llm_service, "last_error", None),
    )


def _llm_enabled(llm_service: LLMService | None) -> bool:
    return llm_service is not None and getattr(llm_service, "provider_name", "disabled") != "disabled"


def _analysis_design_skeleton(session: AgentSession) -> dict[str, Any]:
    context = _analysis_context(session)
    return {
        "analysis_agent": "分析思路拆解和设计 Agent",
        "skill": "llm_generated",
        "generation_mode": "llm_first_no_skill",
        "original_business_question": session.business_question,
        "ba_feedback": _ba_feedback(session),
        "analysis_context": context,
        "detected_intent": {
            "time_period": context.get("time_range"),
            "focus_dimensions": context.get("dimensions", []),
            "issue_type": context.get("issue_type"),
            "metric_focus": context.get("metric_focus"),
            "funnel_scope": context.get("funnel_scope", {}),
        },
        "analysis_purpose": "",
        "business_context": {},
        "clarification_questions": context.get("open_questions", []),
        "business_hypotheses": [],
        "analysis_defaults": {
            "数据边界": "只使用字段元数据和 BA 确认口径生成方案，不输出客户级明细。",
            "字段约束": "所有字段需求必须来自当前 data source profile。",
        },
        "metrics_tree": [],
        "field_requirements": {
            "funnel_time_fields": [],
            "funnel_id_fields": [],
            "first_flag_fields": [],
            "dimension_fields": [],
            "metric_fields": [],
            "missing_recommended_fields": [],
        },
        "analysis_path": [],
        "confidence_score": context.get("confidence", 0.75),
        "ba_confirmation_required": True,
    }


def _complete_analysis_design_artifact(artifact: dict[str, Any], skeleton: dict[str, Any]) -> dict[str, Any]:
    completed = dict(skeleton)
    completed.update(artifact)
    completed["analysis_agent"] = skeleton["analysis_agent"]
    completed["skill"] = skeleton["skill"]
    completed["generation_mode"] = skeleton["generation_mode"]
    completed["ba_confirmation_required"] = True
    completed["analysis_context"] = artifact.get("analysis_context") or skeleton.get("analysis_context", {})
    completed["detected_intent"] = artifact.get("detected_intent") or skeleton.get("detected_intent", {})
    completed["business_context"] = artifact.get("business_context") if isinstance(artifact.get("business_context"), dict) else {}
    completed["clarification_questions"] = _normalize_string_list(
        artifact.get("clarification_questions") or skeleton.get("clarification_questions", [])
    )
    completed["business_hypotheses"] = artifact.get("business_hypotheses") if isinstance(artifact.get("business_hypotheses"), list) else []
    completed["metrics_tree"] = artifact.get("metrics_tree") if isinstance(artifact.get("metrics_tree"), list) else []
    completed["field_requirements"] = (
        artifact.get("field_requirements") if isinstance(artifact.get("field_requirements"), dict) else skeleton["field_requirements"]
    )
    completed["analysis_path"] = _normalize_string_list(artifact.get("analysis_path", []))
    completed["analysis_purpose"] = artifact.get("analysis_purpose") or "基于 BA 问题和字段元数据生成分析设计。"
    return completed


def _ba_feedback(session: AgentSession) -> list[dict[str, str]]:
    value = session.extracted_params.get("ba_feedback", [])
    return value if isinstance(value, list) else []


def _analysis_context(session: AgentSession) -> dict[str, Any]:
    value = session.extracted_params.get("analysis_context", {})
    return value if isinstance(value, dict) else {}


def _question_for_analysis(session: AgentSession) -> str:
    context = _analysis_context(session)
    feedback = _ba_feedback(session)
    pieces = [session.business_question]
    if context.get("time_range"):
        pieces.append(f"时间范围是{context['time_range']}")
    if context.get("comparison_baseline"):
        pieces.append(f"对比基准是{context['comparison_baseline']}")
    if context.get("metric"):
        pieces.append(f"核心指标是{context['metric']}")
    if context.get("dimensions"):
        pieces.append(f"优先按{'、'.join(context['dimensions'])}拆解")
    if context.get("filters"):
        pieces.append(f"过滤口径包括{'、'.join(context['filters'])}")
    if context.get("audience"):
        pieces.append(f"报告对象是{context['audience']}")
    if feedback:
        pieces.append("BA补充：" + "；".join(str(item.get("text", "")) for item in feedback if isinstance(item, dict)))
    return "。".join(piece for piece in pieces if piece)


def _compose_question(business_question: str, feedback: list[dict[str, str]]) -> str:
    if not feedback:
        return business_question
    feedback_text = "；".join(str(item.get("text", "")) for item in feedback if isinstance(item, dict) and item.get("text"))
    if not feedback_text:
        return business_question
    return f"{business_question}。BA补充：{feedback_text}"


def _extract_comparison_baseline(text: str) -> str | None:
    markers = ["对比", "相比", "较", "比"]
    candidates = ["上月", "上周", "去年同期", "同期", "预算", "目标", "2月", "3月", "4月", "5月", "6月", "7月", "8月", "9月", "10月", "11月", "12月", "1月"]
    for marker in markers:
        if marker not in text:
            continue
        after = text.split(marker, 1)[1]
        for candidate in candidates:
            if candidate in after:
                return candidate
    return None


def _extract_filters(text: str, existing: list[str]) -> list[str]:
    filters = list(existing)
    candidates = [
        ("首次", "仅统计首次有效链路/first_flag"),
        ("first_flag", "仅统计首次有效链路/first_flag"),
        ("有效", "仅保留有效线索/有效订单"),
        ("无效", "排除无效记录"),
        ("关闭经销商", "排除关闭经销商"),
        ("取消订单", "排除取消订单"),
        ("非目标品牌", "排除非目标品牌"),
    ]
    for token, label in candidates:
        if token in text and label not in filters:
            filters.append(label)
    return filters


def _extract_audience(text: str) -> str | None:
    audiences = ["高层经营会", "销售管理", "渠道投放", "区域管理", "经销商运营", "数据团队", "BA"]
    for audience in audiences:
        if audience in text:
            return audience
    return None


def _metric_name(intent_data: dict[str, Any]) -> str | None:
    focus = intent_data.get("metric_focus")
    start = intent_data.get("start_stage")
    end = intent_data.get("end_stage")
    stages = intent_data.get("mentioned_stages") or []
    if start and end and start != end:
        scope = f"{start}到{end}"
    elif stages:
        scope = "、".join(stages)
    else:
        scope = "注册到订单全漏斗"
    if focus == "转化率":
        return f"{scope}转化率"
    if focus == "规模":
        return f"{scope}数量"
    if focus == "耗时":
        return f"{scope}转化周期"
    return f"{scope}综合表现"


def _open_questions(context: dict[str, Any]) -> list[str]:
    questions = []
    if not context.get("time_range"):
        questions.append("本次分析的时间范围是什么？")
    if context.get("issue_type") in {"下降", "提升", "异常波动", "差异"} and not context.get("comparison_baseline"):
        questions.append("需要和哪个基准比较：上月、去年同期、预算目标还是业务预期？")
    if not context.get("dimensions"):
        questions.append("优先拆解哪些维度：渠道、区域、经销商、车型/车系，还是客户类型？")
    if not context.get("filters"):
        questions.append("是否只看首次有效链路？是否需要排除无效线索、关闭经销商或取消订单？")
    if not context.get("audience"):
        questions.append("最终报告面向谁：销售管理、渠道投放、区域管理还是高层经营会？")
    return questions


def _understanding_summary(context: dict[str, Any]) -> str:
    parts = [
        f"问题类型是{context.get('issue_type', '变化')}",
        f"核心指标是{context.get('metric') or '待确认'}",
        f"时间范围是{context.get('time_range') or '待确认'}",
        f"对比基准是{context.get('comparison_baseline') or '待确认'}",
    ]
    dimensions = context.get("dimensions") or []
    parts.append(f"优先拆解维度是{'、'.join(dimensions) if dimensions else '待确认'}")
    return "；".join(parts) + "。"


def _merge_llm_intent_context(
    rule_context: dict[str, Any],
    enhanced: dict[str, Any] | None,
    provider_name: str,
    error: str | None = None,
) -> dict[str, Any]:
    if not enhanced:
        return apply_llm_enhancement(rule_context, None, provider_name, error)

    source = enhanced.get("analysis_context") if isinstance(enhanced.get("analysis_context"), dict) else enhanced
    merged = dict(rule_context)

    scalar_keys = {
        "business_question",
        "latest_user_message",
        "feedback_type",
        "time_range",
        "comparison_baseline",
        "metric_focus",
        "metric",
        "issue_type",
        "audience",
        "understanding_summary",
    }
    for key in scalar_keys:
        value = source.get(key)
        if isinstance(value, str) and value.strip():
            merged[key] = value.strip()

    if isinstance(source.get("funnel_scope"), dict):
        merged["funnel_scope"] = _normalize_funnel_scope(source["funnel_scope"], rule_context.get("funnel_scope", {}))

    if isinstance(source.get("dimensions"), list):
        dimensions = _normalize_dimensions(source["dimensions"])
        if dimensions:
            merged["dimensions"] = dimensions

    if isinstance(source.get("filters"), list):
        merged["filters"] = _normalize_string_list(source["filters"])

    if isinstance(source.get("open_questions"), list):
        merged["open_questions"] = _normalize_string_list(source["open_questions"])
    else:
        merged["open_questions"] = _open_questions(merged)

    if isinstance(source.get("confidence"), (int, float)):
        merged["confidence"] = max(0.0, min(float(source["confidence"]), 1.0))
    else:
        merged["confidence"] = max(float(rule_context.get("confidence", 0.0)), 0.86)

    merged["raw_user_inputs"] = rule_context.get("raw_user_inputs", [])
    merged["ba_feedback"] = rule_context.get("ba_feedback", [])
    if not merged.get("understanding_summary"):
        merged["understanding_summary"] = _understanding_summary(merged)

    merged["llm_enrichment"] = {
        "enabled": provider_name != "disabled",
        "provider": provider_name,
        "status": "applied",
        "error": None,
    }
    return merged


def _normalize_funnel_scope(value: dict[str, Any], fallback: Any) -> dict[str, Any]:
    fallback_dict = fallback if isinstance(fallback, dict) else {}
    valid_stages = ["注册", "线索", "商机", "到店", "试驾", "订单"]
    start = value.get("start_stage") if value.get("start_stage") in valid_stages else fallback_dict.get("start_stage")
    end = value.get("end_stage") if value.get("end_stage") in valid_stages else fallback_dict.get("end_stage")
    mentioned = _normalize_stage_list(value.get("mentioned_stages", []))
    if not mentioned:
        mentioned = _normalize_stage_list(fallback_dict.get("mentioned_stages", []))
    return {
        "start_stage": start,
        "end_stage": end,
        "mentioned_stages": mentioned,
    }


def _normalize_stage_list(value: Any) -> list[str]:
    valid = ["注册", "线索", "商机", "到店", "试驾", "订单"]
    if not isinstance(value, list):
        return []
    return [item for item in value if item in valid]


def _normalize_dimensions(value: Any) -> list[str]:
    valid = ["渠道", "区域", "经销商", "产品", "时间"]
    aliases = {
        "车型": "产品",
        "车系": "产品",
        "品牌": "产品",
        "城市": "区域",
        "大区": "区域",
        "媒体": "渠道",
        "campaign": "渠道",
        "活动": "渠道",
        "门店": "经销商",
        "dealer": "经销商",
    }
    if not isinstance(value, list):
        return []
    normalized = []
    for item in value:
        text = str(item).strip()
        dimension = aliases.get(text, text)
        if dimension in valid and dimension not in normalized:
            normalized.append(dimension)
    return normalized


def _normalize_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    result = []
    for item in value:
        text = str(item).strip()
        if text and text not in result:
            result.append(text)
    return result
