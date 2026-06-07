from __future__ import annotations

import re
from dataclasses import dataclass

from .models import DataSourceProfile
from .playbook import AutomotiveSalesCRMPlaybook, PlaybookTopic


@dataclass(frozen=True)
class SkillContext:
    business_question: str
    data_source: DataSourceProfile


@dataclass(frozen=True)
class AnalysisIntent:
    raw_question: str
    time_period: str | None
    mentioned_stages: list[str]
    start_stage: str | None
    end_stage: str | None
    focus_dimensions: list[str]
    issue_type: str
    metric_focus: str


class AnalysisSkill:
    name = "generic"
    description = "Generic BA analysis skill."

    def business_context(self, context: SkillContext) -> dict[str, object]:
        return {
            "purpose": f"围绕“{context.business_question}”完成结构化业务分析。",
            "business_background": "通用 BA 分析场景。",
            "core_problems": [context.business_question],
            "related_departments": ["业务分析", "数据团队"],
            "key_metrics": [],
            "urgency": "中等",
            "confidence": 0.5,
        }

    def clarification_questions(self, context: SkillContext) -> list[str]:
        return [
            "本次分析的时间范围是什么？是否需要对比上月、去年同期或目标值？",
            "最终希望定位到哪些维度：渠道、区域、经销商、产品还是客户分层？",
            "是否存在需要排除的数据口径，例如无效记录、取消记录或重复记录？",
        ]

    def metric_tree(self, context: SkillContext) -> list[dict[str, object]]:
        raise NotImplementedError

    def business_hypotheses(self, context: SkillContext) -> list[dict[str, object]]:
        return [
            {
                "factor": "业务结构变化",
                "hypothesis": f"“{context.business_question}”可能受到关键业务维度结构变化影响。",
                "why_it_matters": "如果高低质量客群、渠道或区域占比变化，整体指标会随结构变化波动。",
                "validation_approach": "按可用业务维度拆解指标变化，并比较各维度贡献。",
                "evidence_status": "待验证",
            }
        ]

    def required_fields(self, context: SkillContext) -> dict[str, list[str]]:
        raise NotImplementedError

    def analysis_path(self, context: SkillContext) -> list[str]:
        raise NotImplementedError

    def sql_templates(self, context: SkillContext) -> list[dict[str, object]]:
        return []


class SalesFunnelConversionSkill(AnalysisSkill):
    name = "sales_funnel_conversion"
    description = "销售漏斗转化分析，覆盖注册、线索、商机、到店、试驾、订单。"

    FUNNEL_STAGES = [
        ("注册", "register", "register_create_time", "register_rcid", "register_first_flag"),
        ("线索", "leads", "leads_create_time", "leads_id", "leads_first_flag"),
        ("商机", "oppty", "oppty_create_time", "oppty_id", "oppty_first_flag"),
        ("到店", "visit", "visit_arrival_time", "visit_id", "visit_first_flag"),
        ("试驾", "td", "td_start_time", "td_id", "td_first_flag"),
        ("订单", "order", "order_first_confirm_time", "order_id", "order_first_flag"),
    ]

    DIMENSIONS = [
        "brand_route",
        "region_route",
        "province_name_zh",
        "city_name_zh",
        "dealership_name_cn",
        "sales_bmw_big_area_name_zh",
        "sales_bmw_small_area_name_zh",
        "register_first_channel_name",
        "register_second_channel_name",
        "register_media_platform_name",
        "leads_channel_name",
        "leads_sub_channel_name",
        "leads_channel_group",
        "register_series",
        "register_model",
        "oppty_series_code",
        "order_series_code",
    ]

    STAGE_LABELS = [stage[0] for stage in FUNNEL_STAGES]
    STAGE_ALIASES = {
        "注册": ["注册", "register"],
        "线索": ["线索", "leads", "lead"],
        "商机": ["商机", "机会", "oppty", "opportunity"],
        "到店": ["到店", "进店", "visit"],
        "试驾": ["试驾", "td", "test drive"],
        "订单": ["订单", "成交", "下订", "order"],
    }
    DIMENSION_ALIASES = {
        "渠道": ["渠道", "来源", "媒体", "投放", "campaign", "活动", "线索来源"],
        "区域": ["区域", "大区", "省", "城市", "地区"],
        "经销商": ["经销商", "门店", "dealer", "4s"],
        "产品": ["车型", "车系", "品牌", "产品", "model", "series"],
        "时间": ["环比", "同比", "趋势"],
    }

    def business_context(self, context: SkillContext) -> dict[str, object]:
        intent = self.parse_intent(context.business_question)
        stage_scope = _stage_scope_text(intent)
        dimension_scope = "、".join(intent.focus_dimensions) if intent.focus_dimensions else "渠道、区域、经销商、产品"
        metric_focus = _metric_focus_text(intent)
        return {
            "purpose": f"解释“{context.business_question}”中{stage_scope}{metric_focus}的{intent.issue_type}原因，并形成可执行的取数和汇报方案。",
            "business_background": f"当前问题聚焦{stage_scope}{metric_focus}，优先从{dimension_scope}等方向拆解影响因素。",
            "core_problems": [
                f"{stage_scope}{metric_focus}的{intent.issue_type}主要发生在哪个阶段或节点？",
                f"{intent.issue_type}是否集中在{dimension_scope}等特定维度？",
                "数据口径、无效线索、重复线索或关闭经销商是否影响结论？",
            ],
            "related_departments": ["销售管理", "渠道投放", "区域管理", "经销商运营", "数据团队"],
            "key_metrics": _key_metrics_for_intent(intent),
            "urgency": "中等",
            "confidence": 0.9,
        }

    def clarification_questions(self, context: SkillContext) -> list[str]:
        intent = self.parse_intent(context.business_question)
        questions = []
        if intent.time_period:
            questions.append(f"{intent.time_period}的数据需要和哪个基准对比：上月、去年同期、预算目标还是业务预期？")
        else:
            questions.append("本次分析的时间范围是什么？是否需要和上月、去年同期或目标值对比？")

        if intent.start_stage and intent.end_stage:
            questions.append(f"{intent.start_stage}到{intent.end_stage}转化是否只看首次有效链路，还是允许同一客户/线索多次计入？")
        else:
            questions.append("需要分析全漏斗，还是只聚焦某两个阶段之间的转化？")

        if intent.focus_dimensions:
            questions.append(f"你提到/隐含关注{ '、'.join(intent.focus_dimensions) }，这些维度是否是本次优先拆解范围？")
        else:
            questions.append("优先拆解哪些维度：渠道、区域、经销商、车型/车系，还是客户类型？")

        questions.extend(
            [
                "是否需要排除关闭经销商、无效线索、取消订单或非目标品牌数据？",
                "最终报告面向谁：区域管理、渠道投放、销售管理还是高层经营会？",
            ]
        )
        return questions

    def metric_tree(self, context: SkillContext) -> list[dict[str, object]]:
        intent = self.parse_intent(context.business_question)
        fields = context.data_source.all_column_names()
        stages = [
            {
                "stage": label,
                "count_metric": f"{label}量",
                "time_field": time_field if time_field in fields else None,
                "id_field": id_field if id_field in fields else None,
                "first_flag": flag_field if flag_field in fields else None,
            }
            for label, _, time_field, id_field, flag_field in self.FUNNEL_STAGES
        ]
        scoped_stages = _filter_stage_metrics(stages, intent)
        conversion_metrics = _conversion_metrics_for_intent(intent)
        dimension_metrics = intent.focus_dimensions or ["渠道", "区域", "经销商", "产品"]
        tree = [
            {
                "name": f"{_stage_scope_text(intent)}规模",
                "metrics": scoped_stages,
            },
            {
                "name": "影响因素拆解",
                "metrics": [f"按{dimension}拆解贡献度" for dimension in dimension_metrics],
            },
        ]
        if intent.metric_focus in {"转化率", "综合"}:
            tree.insert(
                1,
                {
                    "name": f"{_stage_scope_text(intent)}转化率",
                    "metrics": conversion_metrics,
                },
            )
        if intent.metric_focus in {"耗时", "综合"}:
            tree.append(
                {
                    "name": "转化周期和质量",
                    "metrics": _cycle_metrics_for_intent(intent),
                }
            )
        if intent.metric_focus == "规模":
            tree.insert(
                1,
                {
                    "name": f"{_stage_scope_text(intent)}数量变化",
                    "metrics": [
                        f"{_stage_scope_text(intent)}数量",
                        f"{_stage_scope_text(intent)}环比/同比变化",
                        f"{_stage_scope_text(intent)}目标达成差异",
                    ],
                },
            )
        return tree

    def business_hypotheses(self, context: SkillContext) -> list[dict[str, object]]:
        intent = self.parse_intent(context.business_question)
        question = context.business_question
        hypotheses = []
        if intent.metric_focus == "规模":
            hypotheses.extend(_volume_hypotheses(question, intent))
        if "渠道" in intent.focus_dimensions:
            hypotheses.extend(_channel_hypotheses(question, intent))
        if "区域" in intent.focus_dimensions or "经销商" in intent.focus_dimensions:
            hypotheses.extend(_dealer_region_hypotheses(question, intent))
        if "产品" in intent.focus_dimensions:
            hypotheses.extend(_product_hypotheses(question, intent))
        hypotheses.extend(
            [
            {
                "factor": "漏斗阶段流失",
                "hypothesis": f"“{question}”可能主要由{_stage_scope_text(intent)}中的某个节点转化{intent.issue_type}造成。",
                "why_it_matters": "同样是订单转化率下降，不同阶段流失对应的业务动作完全不同。",
                "validation_approach": f"计算{_stage_scope_text(intent)}的阶段转化率，定位变化最大的阶段。",
                "related_fields": [
                    "leads_id",
                    "oppty_id",
                    "visit_id",
                    "td_id",
                    "order_id",
                ],
                "evidence_status": "待验证",
            },
            {
                "factor": "数据口径和数据质量",
                "hypothesis": "无效线索、重复线索、关闭经销商、取消订单或 first_flag 口径变化，可能造成表观转化率下降。",
                "why_it_matters": "如果口径变化没有先排除，后续业务归因可能误判。",
                "validation_approach": "先检查有效标记、首次标记、取消/关闭状态和关键字段空值，再进行业务归因。",
                "related_fields": [
                    "register_first_flag",
                    "leads_first_flag",
                    "oppty_first_flag",
                    "order_first_flag",
                    "dealer_status_name",
                ],
                "evidence_status": "待验证",
            },
            ]
        )
        if intent.start_stage == "线索" and intent.end_stage == "订单":
            hypotheses.insert(
                0,
                {
                    "factor": "线索到订单链路断点",
                    "hypothesis": "问题明确指向线索到订单转化下降，优先假设线索生成后的商机创建、到店/试驾或订单确认环节存在断点。",
                    "why_it_matters": "该假设能把分析范围从全漏斗收敛到 leads -> oppty -> visit/td -> order 后链路。",
                    "validation_approach": "从线索量开始，逐段计算 leads->oppty、oppty->visit、visit->td、td->order 的转化变化。",
                    "related_fields": [
                        "leads_create_time",
                        "leads_id",
                        "oppty_id",
                        "visit_id",
                        "td_id",
                        "order_id",
                    ],
                    "evidence_status": "待验证",
                },
            )
        return _dedupe_hypotheses(hypotheses)

    def required_fields(self, context: SkillContext) -> dict[str, list[str]]:
        intent = self.parse_intent(context.business_question)
        available = context.data_source.all_column_names()
        fields: dict[str, list[str]] = {
            "funnel_time_fields": [],
            "funnel_id_fields": [],
            "first_flag_fields": [],
            "dimension_fields": [],
            "missing_recommended_fields": [],
        }

        for _, _, time_field, id_field, flag_field in self.FUNNEL_STAGES:
            label = next(stage[0] for stage in self.FUNNEL_STAGES if stage[2] == time_field)
            if not _stage_in_intent_scope(label, intent):
                continue
            _append_available(fields, "funnel_time_fields", "missing_recommended_fields", time_field, available)
            _append_available(fields, "funnel_id_fields", "missing_recommended_fields", id_field, available)
            _append_available(fields, "first_flag_fields", "missing_recommended_fields", flag_field, available)

        for dimension in self.DIMENSIONS:
            if dimension in available and _dimension_matches_intent(dimension, intent):
                fields["dimension_fields"].append(dimension)

        return fields

    def analysis_path(self, context: SkillContext) -> list[str]:
        intent = self.parse_intent(context.business_question)
        dimension_scope = "、".join(intent.focus_dimensions) if intent.focus_dimensions else "渠道、区域、经销商、品牌/车系"
        return [
            f"明确{intent.time_period or '目标时间窗'}、对比基准、统计口径和是否只看首次转化。",
            f"先计算{_stage_scope_text(intent)}的规模和转化率，确认{intent.issue_type}是否真实存在。",
            f"按{dimension_scope}拆解差异，比较转化率变化和数量贡献。",
            f"定位对{intent.issue_type}贡献最大的阶段和维度组合。",
            "形成事实、合理推断和待 BA 业务确认事项。",
        ]

    def sql_templates(self, context: SkillContext) -> list[dict[str, object]]:
        fields = self.required_fields(context)
        return [
            {
                "id": "sales_funnel_by_dimension",
                "name": "销售漏斗分维度聚合",
                "description": "按 BA 确认的时间窗和维度统计各漏斗阶段去重数量。",
                "required_fields": (
                    fields["funnel_id_fields"]
                    + fields["first_flag_fields"]
                    + fields["dimension_fields"][:8]
                ),
                "estimated_rows": "按维度基数决定",
            }
        ]

    def parse_intent(self, question: str) -> AnalysisIntent:
        normalized = question.lower()
        mentioned_stages = [
            stage for stage, aliases in self.STAGE_ALIASES.items()
            if any(alias.lower() in normalized or alias in question for alias in aliases)
        ]
        start_stage = mentioned_stages[0] if mentioned_stages else None
        end_stage = mentioned_stages[-1] if len(mentioned_stages) >= 2 else None
        focus_dimensions = [
            dimension for dimension, aliases in self.DIMENSION_ALIASES.items()
            if any(alias.lower() in normalized or alias in question for alias in aliases)
        ]
        excluded_dimensions = _excluded_dimensions(question, self.DIMENSION_ALIASES)
        focus_dimensions = [dimension for dimension in focus_dimensions if dimension not in excluded_dimensions]
        time_period = _extract_time_period(question)
        issue_type = _issue_type(question)
        metric_focus = _metric_focus(question)
        return AnalysisIntent(
            raw_question=question,
            time_period=time_period,
            mentioned_stages=mentioned_stages,
            start_stage=start_stage,
            end_stage=end_stage,
            focus_dimensions=focus_dimensions,
            issue_type=issue_type,
            metric_focus=metric_focus,
        )


class SkillsManager:
    """轻量 Skills 库管理器。

    当前实现只使用本地 skill 元数据，后续可以把 registry 换成向量库、
    文件库、数据库或远程知识库。
    """

    def __init__(
        self,
        skills: list[AnalysisSkill] | None = None,
        playbook: AutomotiveSalesCRMPlaybook | None = None,
    ):
        self.skills = skills or [SalesFunnelConversionSkill()]
        self.playbook = playbook if playbook is not None else AutomotiveSalesCRMPlaybook.load_default()

    def choose_skill(self, data_source: DataSourceProfile, requested: str | None = None) -> AnalysisSkill:
        if requested:
            for skill in self.skills:
                if skill.name == requested:
                    return skill
        domains = set(data_source.business_domains)
        if {"register", "leads", "oppty", "order"} & domains:
            return self._get("sales_funnel_conversion")
        return self.skills[0]

    def search_business_context(self, problem: str, data_source: DataSourceProfile) -> dict[str, object]:
        skill = self.choose_skill(data_source)
        context = skill.business_context(SkillContext(problem, data_source))
        return {"skill": skill.name, **context}

    def search_metrics(self, problem: str, data_source: DataSourceProfile) -> list[dict[str, object]]:
        skill = self.choose_skill(data_source)
        return skill.metric_tree(SkillContext(problem, data_source))

    def extract_field_requirements(self, problem: str, data_source: DataSourceProfile) -> dict[str, list[str]]:
        skill = self.choose_skill(data_source)
        return skill.required_fields(SkillContext(problem, data_source))

    def design_analysis_path(self, problem: str, data_source: DataSourceProfile) -> list[str]:
        skill = self.choose_skill(data_source)
        return skill.analysis_path(SkillContext(problem, data_source))

    def find_data_sources_for_fields(
        self,
        field_requirements: dict[str, list[str]],
        data_source: DataSourceProfile,
    ) -> list[dict[str, object]]:
        available = data_source.all_column_names()
        primary_table = data_source.tables_or_sheets[0].name if data_source.tables_or_sheets else ""
        mapped: list[dict[str, object]] = []
        for field_group, fields in field_requirements.items():
            for field in fields:
                if field in available:
                    mapped.append(
                        {
                            "field": field,
                            "source_table": primary_table,
                            "source_column": field,
                            "field_group": field_group,
                            "confidence": 1.0,
                        }
                    )
        return mapped

    def find_sql_templates(self, problem: str, data_source: DataSourceProfile) -> list[dict[str, object]]:
        skill = self.choose_skill(data_source)
        return skill.sql_templates(SkillContext(problem, data_source))

    def matched_playbook_topics(self, problem: str, limit: int = 2) -> list[PlaybookTopic]:
        if self.playbook is None:
            return []
        return self.playbook.match_topics(problem, limit=limit)

    def apply_playbook_to_design(
        self,
        problem: str,
        artifact: dict[str, object],
        data_source: DataSourceProfile,
    ) -> dict[str, object]:
        if self.playbook is None:
            artifact["playbook_guidance"] = {
                "enabled": False,
                "reason": "playbook_not_found",
            }
            return artifact

        topics = self.matched_playbook_topics(problem)
        available = data_source.all_column_names()
        playbook_fields = _topic_fields(topics)
        available_playbook_fields = [field for field in playbook_fields if field in available]
        missing_playbook_fields = [field for field in playbook_fields if field not in available]

        field_requirements = artifact.get("field_requirements", {})
        if isinstance(field_requirements, dict):
            field_requirements["playbook_recommended_fields"] = available_playbook_fields
            field_requirements["missing_playbook_fields"] = missing_playbook_fields

        metric_tree = artifact.get("metrics_tree", [])
        if isinstance(metric_tree, list) and topics:
            metric_tree.append(
                {
                    "name": "Playbook重点诊断",
                    "metrics": _topic_metrics(topics),
                }
            )

        analysis_path = artifact.get("analysis_path", [])
        if isinstance(analysis_path, list) and topics:
            playbook_steps = _topic_approach(topics)[:5]
            artifact["analysis_path"] = playbook_steps + analysis_path

        hypotheses = artifact.get("business_hypotheses", [])
        if isinstance(hypotheses, list):
            artifact["business_hypotheses"] = _playbook_hypotheses(topics) + hypotheses

        artifact["playbook_guidance"] = {
            "enabled": True,
            "path": str(self.playbook.path),
            "thinking_pattern": self.playbook.thinking_pattern[:8],
            "matched_topics": [topic.to_dict() for topic in topics],
            "available_playbook_fields": available_playbook_fields,
            "missing_playbook_fields": missing_playbook_fields,
        }
        return artifact

    def _get(self, name: str) -> AnalysisSkill:
        for skill in self.skills:
            if skill.name == name:
                return skill
        raise ValueError(f"Skill {name} is not registered.")


def _topic_fields(topics: list[PlaybookTopic]) -> list[str]:
    seen: set[str] = set()
    fields: list[str] = []
    for topic in topics:
        for field in topic.fields:
            if field not in seen:
                seen.add(field)
                fields.append(field)
    return fields


def _topic_metrics(topics: list[PlaybookTopic]) -> list[str]:
    metrics: list[str] = []
    for topic in topics:
        metrics.extend([f"{topic.title}: {metric}" for metric in topic.core_metrics[:5]])
        if topic.recommended_cuts:
            metrics.append(f"{topic.title}: recommended cuts = {', '.join(topic.recommended_cuts[:8])}")
    return metrics


def _topic_approach(topics: list[PlaybookTopic]) -> list[str]:
    steps: list[str] = []
    for topic in topics:
        for approach in topic.analysis_approach[:4]:
            steps.append(f"[{topic.title}] {approach}")
    return steps


def _playbook_hypotheses(topics: list[PlaybookTopic]) -> list[dict[str, object]]:
    hypotheses = []
    for topic in topics:
        if not topic.analysis_approach:
            continue
        hypotheses.append(
            {
                "factor": f"Playbook主题: {topic.title}",
                "hypothesis": topic.analysis_approach[0],
                "why_it_matters": "该假设来自 Automotive Sales CRM Analysis Playbook 的匹配章节。",
                "validation_approach": topic.analysis_approach[1] if len(topic.analysis_approach) > 1 else "按 playbook 推荐字段和切分维度验证。",
                "related_fields": topic.fields[:12],
                "evidence_status": "待验证",
            }
        )
    return hypotheses


def choose_skill(data_source: DataSourceProfile, requested: str | None = None) -> AnalysisSkill:
    return SkillsManager().choose_skill(data_source, requested)


def _append_available(
    fields: dict[str, list[str]],
    available_key: str,
    missing_key: str,
    field_name: str,
    available: set[str],
) -> None:
    if field_name in available:
        fields[available_key].append(field_name)
    else:
        fields[missing_key].append(field_name)


def _extract_time_period(question: str) -> str | None:
    patterns = [
        r"(\d{4}年\d{1,2}月)",
        r"(\d{1,2}月)",
        r"(本月|上月|上周|本周|今年|去年|近\d+天|过去\d+天|最近\d+天)",
    ]
    for pattern in patterns:
        match = re.search(pattern, question)
        if match:
            return match.group(1)
    return None


def _issue_type(question: str) -> str:
    if any(token in question for token in ("下降", "下滑", "降低", "变差", "减少")):
        return "下降"
    if any(token in question for token in ("提升", "上涨", "增长", "变好", "增加")):
        return "提升"
    if any(token in question for token in ("异常", "波动", "变化")):
        return "异常波动"
    if any(token in question for token in ("对比", "比较", "差异")):
        return "差异"
    return "变化"


def _metric_focus(question: str) -> str:
    if any(token in question for token in ("转化", "转化率", "conversion")):
        return "转化率"
    if any(token in question for token in ("线索量", "数量", "规模", "volume", "量下降", "量提升")):
        return "规模"
    if any(token in question for token in ("耗时", "周期", "时长", "效率", "跟进")):
        return "耗时"
    return "综合"


def _excluded_dimensions(question: str, dimension_aliases: dict[str, list[str]]) -> set[str]:
    excluded: set[str] = set()
    negative_markers = ("不看", "不要看", "先不看", "不按", "不用", "排除", "不拆")
    for dimension, aliases in dimension_aliases.items():
        if any(f"{marker}{alias}" in question for marker in negative_markers for alias in aliases):
            excluded.add(dimension)
    return excluded


def _metric_focus_text(intent: AnalysisIntent) -> str:
    if intent.metric_focus == "综合":
        return ""
    return intent.metric_focus


def _stage_scope_text(intent: AnalysisIntent) -> str:
    if intent.start_stage and intent.end_stage and intent.start_stage != intent.end_stage:
        return f"{intent.start_stage}到{intent.end_stage}"
    if intent.mentioned_stages:
        return "、".join(intent.mentioned_stages)
    return "注册到订单全漏斗"


def _volume_hypotheses(question: str, intent: AnalysisIntent) -> list[dict[str, object]]:
    scope = _stage_scope_text(intent)
    return [
        {
            "factor": f"{scope}供给变化",
            "hypothesis": f"“{question}”可能由上游流量、活动投放、线索采集入口或经销商自建线索供给减少导致。",
            "why_it_matters": "规模下降和转化下降的根因不同，先判断是不是上游供给减少。",
            "validation_approach": f"按时间、渠道和来源拆解{scope}数量变化，识别下降贡献最大的来源。",
            "related_fields": [
                "leads_create_time",
                "register_first_channel_name",
                "register_media_platform_name",
                "leads_channel_name",
                "leads_id",
            ],
            "evidence_status": "待验证",
        },
        {
            "factor": f"{scope}有效性变化",
            "hypothesis": "有效线索占比、重复线索、无效手机号或合规过滤变化，可能让可分析数量下降。",
            "why_it_matters": "如果数量下降来自清洗或口径变化，不应直接解释为业务需求下降。",
            "validation_approach": "检查 valid/compliant/first_flag/重复计数等字段，并比较过滤前后数量变化。",
            "related_fields": [
                "register_valid_flag",
                "register_compliant_desc",
                "leads_first_flag",
                "leads_phone_status",
            ],
            "evidence_status": "待验证",
        },
    ]


def _channel_hypotheses(question: str, intent: AnalysisIntent) -> list[dict[str, object]]:
    metric = _metric_focus_text(intent) or "表现"
    return [
        {
            "factor": "渠道流量或投放变化",
            "hypothesis": f"“{question}”可能由某些渠道、媒体平台、campaign 的流量或投放策略变化导致。",
            "why_it_matters": f"当问题明确关注渠道时，应先判断是渠道供给变化还是渠道质量变化影响了{metric}。",
            "validation_approach": "按一级渠道、二级渠道、媒体平台、campaign 拆解数量、占比和变化贡献。",
            "related_fields": [
                "register_first_channel_name",
                "register_second_channel_name",
                "register_media_platform_name",
                "leads_channel_name",
                "leads_sub_channel_name",
                "leads_channel_group",
            ],
            "evidence_status": "待验证",
        },
        {
            "factor": "渠道质量变化",
            "hypothesis": "渠道带来的客户意向、车型偏好或区域分布变化，可能影响后链路转化质量。",
            "why_it_matters": "线索量下降或转化下降都可能由渠道结构从高质量来源转向低质量来源造成。",
            "validation_approach": "比较各渠道的线索到商机、到店、试驾、订单转化率和渠道结构占比。",
            "related_fields": [
                "leads_channel_name",
                "leads_sub_channel_name",
                "leads_channel_group",
                "oppty_id",
                "visit_id",
                "order_id",
            ],
            "evidence_status": "待验证",
        },
    ]


def _dealer_region_hypotheses(question: str, intent: AnalysisIntent) -> list[dict[str, object]]:
    return [
        {
            "factor": "区域/经销商承接能力",
            "hypothesis": f"“{question}”可能由部分区域、城市或经销商的跟进、邀约、到店承接能力变化导致。",
            "why_it_matters": "同一渠道来的线索，如果经销商承接效率下降，也会表现为后链路表现变差。",
            "validation_approach": "按区域、城市、经销商拆解数量、转化率和阶段耗时，识别贡献最大的异常单元。",
            "related_fields": [
                "region_route",
                "province_name_zh",
                "city_name_zh",
                "dealership_name_cn",
                "sales_bmw_big_area_name_zh",
                "sales_bmw_small_area_name_zh",
            ],
            "evidence_status": "待验证",
        }
    ]


def _product_hypotheses(question: str, intent: AnalysisIntent) -> list[dict[str, object]]:
    return [
        {
            "factor": "车型/品牌需求结构",
            "hypothesis": f"“{question}”可能由品牌、车系或车型结构变化导致，例如高意向车系占比下降或低转化车型占比提升。",
            "why_it_matters": "产品结构变化会同时影响线索规模、客户意向和订单转化难度。",
            "validation_approach": "按品牌、车系、车型拆解数量、占比、阶段转化率和变化贡献。",
            "related_fields": [
                "brand_route",
                "register_series",
                "register_model",
                "oppty_series_code",
                "order_series_code",
            ],
            "evidence_status": "待验证",
        }
    ]


def _dedupe_hypotheses(hypotheses: list[dict[str, object]]) -> list[dict[str, object]]:
    seen: set[str] = set()
    result: list[dict[str, object]] = []
    for hypothesis in hypotheses:
        factor = str(hypothesis.get("factor", ""))
        if factor in seen:
            continue
        seen.add(factor)
        result.append(hypothesis)
    return result



def _stage_in_intent_scope(stage: str, intent: AnalysisIntent) -> bool:
    if not intent.mentioned_stages:
        return True
    labels = SalesFunnelConversionSkill.STAGE_LABELS
    if intent.start_stage and intent.end_stage:
        start = labels.index(intent.start_stage)
        end = labels.index(intent.end_stage)
        low, high = sorted((start, end))
        return low <= labels.index(stage) <= high
    return stage in intent.mentioned_stages


def _filter_stage_metrics(
    stages: list[dict[str, object]],
    intent: AnalysisIntent,
) -> list[dict[str, object]]:
    return [stage for stage in stages if _stage_in_intent_scope(str(stage["stage"]), intent)]


def _conversion_metrics_for_intent(intent: AnalysisIntent) -> list[str]:
    labels = SalesFunnelConversionSkill.STAGE_LABELS
    if intent.start_stage and intent.end_stage:
        start = labels.index(intent.start_stage)
        end = labels.index(intent.end_stage)
        low, high = sorted((start, end))
        scoped = labels[low : high + 1]
    elif intent.mentioned_stages:
        scoped = intent.mentioned_stages
    else:
        scoped = labels

    metrics = [f"{scoped[index]}->{scoped[index + 1]}" for index in range(len(scoped) - 1)]
    if len(scoped) >= 2:
        metrics.append(f"{scoped[0]}->{scoped[-1]}")
    return metrics or [f"{scoped[0]}阶段数量变化"]


def _cycle_metrics_for_intent(intent: AnalysisIntent) -> list[str]:
    metrics = [
        conversion.replace("->", "到") + "耗时"
        for conversion in _conversion_metrics_for_intent(intent)
        if "->" in conversion
    ]
    return metrics or ["阶段耗时", "阶段有效率"]


def _key_metrics_for_intent(intent: AnalysisIntent) -> list[str]:
    scope = _stage_scope_text(intent)
    return [
        f"{scope}阶段数量",
        f"{scope}转化率",
        f"{scope}{intent.issue_type}幅度",
        f"{scope}阶段耗时",
        "维度贡献度",
    ]


def _dimension_matches_intent(field_name: str, intent: AnalysisIntent) -> bool:
    if not intent.focus_dimensions:
        return True
    dimension_tokens = {
        "渠道": ("channel", "media", "campaign", "source", "platform"),
        "区域": ("region", "province", "city", "area"),
        "经销商": ("dealer", "dealership"),
        "产品": ("brand", "series", "model", "variant"),
        "时间": ("time", "date"),
    }
    lowered = field_name.lower()
    return any(
        any(token in lowered for token in dimension_tokens.get(dimension, ()))
        for dimension in intent.focus_dimensions
    )
