from __future__ import annotations

import html
import json
import re
import uuid
from pathlib import Path

from .models import (
    Artifact,
    CEAReport,
    ContributionRow,
    ConversationMessage,
    DataAnalysisResponse,
    Hypothesis,
    MetricNode,
    SqlReview,
    Task,
    TaskInput,
    now_iso,
)


DIMENSIONS = ["渠道维度", "客户维度", "区域维度", "车型维度", "时间维度", "经销商维度"]


def uid(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def create_task(payload: TaskInput) -> Task:
    task = Task(
        task_id=uid("task"),
        task_name=payload.task_name,
        business_question=payload.business_question,
        analysis_purpose=payload.analysis_purpose,
        time_range=payload.time_range,
        comparison_period=payload.comparison_period,
        data_source=payload.data_source,
        recommended_dimensions=recommend_dimensions(payload.business_question, payload.analysis_purpose),
        selected_dimensions=[],
        hypotheses=default_hypotheses(payload.business_question),
        created_at=now_iso(),
        updated_at=now_iso(),
    )
    task.messages = [
        message("agent", "我已理解业务问题，先补齐口径、范围、对比周期和可用数据，再进入分析思路设计。", "task_creation")
    ]
    task.artifacts = build_artifacts(task)
    return task


def sample_task() -> Task:
    return create_task(TaskInput())


def message(role: str, content: str, stage: str) -> ConversationMessage:
    return ConversationMessage(id=uid("msg"), role=role, content=content, stage=stage, created_at=now_iso())


def clarification_questions(task: Task | TaskInput) -> list[str]:
    text = f"{task.business_question} {task.analysis_purpose}".lower()
    questions = [
        "本次下降判断使用哪个北极星指标：线索量、到店量、订单量，还是整体转化率？",
        "对比周期是否需要排除春节、活动日或门店休假等异常日期？",
        "是否需要按区域、渠道、车型和新老客户拆分贡献度？",
    ]
    if "渠道" in text or "channel" in text:
        questions.append("渠道口径是否区分自然流量、付费媒体、区域活动和经销商自建线索？")
    if "客流" in text or "到店" in text:
        questions.append("客流口径是 register、leads、visit 还是线下进店客流？")
    return questions[:5]


def recommend_dimensions(question: str, purpose: str) -> list[str]:
    text = f"{question} {purpose}"
    dims = ["渠道维度", "时间维度", "区域维度"]
    if "客户" in text or "新客" in text or "老客" in text:
        dims.append("客户维度")
    if "车型" in text or "车系" in text:
        dims.append("车型维度")
    if "经销商" in text or "门店" in text:
        dims.append("经销商维度")
    return list(dict.fromkeys(dims + ["车型维度"]))


def default_hypotheses(question: str) -> list[Hypothesis]:
    return [
        Hypothesis(
            id=uid("hyp"),
            title="高意向线索供给下降拉低北极星指标",
            rationale="如果 leads 和 oppty 同时下降，说明问题优先出在线索供给侧。",
            metrics=["leads", "oppty", "leads/register"],
            core=True,
        ),
        Hypothesis(
            id=uid("hyp"),
            title="到店转化下降导致漏斗后段损失",
            rationale="如果 visit/oppty 下降更明显，需要检查邀约、试驾、门店承接。",
            metrics=["visit/oppty", "td/visit", "order/oppty"],
        ),
        Hypothesis(
            id=uid("hyp"),
            title="区域活动和渠道结构变化造成负贡献集中",
            rationale="贡献度若集中在少数区域或渠道，优先定位局部运营问题。",
            metrics=["channel contribution", "region contribution"],
        ),
    ]


def data_analysis(task: Task) -> DataAnalysisResponse:
    tree = MetricNode(
        id="orders",
        label="订单量",
        value=8420,
        change=-12.4,
        contribution=-100,
        children=[
            MetricNode(
                id="leads",
                label="线索量",
                value=54200,
                change=-8.8,
                contribution=-46,
                children=[
                    MetricNode(id="paid", label="付费媒体线索", value=18400, change=-14.2, contribution=-24),
                    MetricNode(id="organic", label="自然流量线索", value=22100, change=-10.6, contribution=-18),
                ],
            ),
            MetricNode(
                id="visit",
                label="到店转化",
                value=0.318,
                change=-5.1,
                contribution=-31,
                children=[
                    MetricNode(id="invite", label="邀约到店", value=0.426, change=-6.7, contribution=-19),
                    MetricNode(id="dealer", label="门店承接", value=0.747, change=-3.2, contribution=-12),
                ],
            ),
            MetricNode(id="order_rate", label="成交转化", value=0.155, change=-2.3, contribution=-23),
        ],
    )
    rows = [
        ContributionRow(dimension="渠道", segment="自然流量", current=22100, previous=24720, change=-10.6, contribution=-18, insight="自然搜索和内容流量同步走弱。"),
        ContributionRow(dimension="渠道", segment="付费媒体", current=18400, previous=21445, change=-14.2, contribution=-24, insight="投放线索量下降且高意向占比降低。"),
        ContributionRow(dimension="区域", segment="华东", current=2660, previous=3240, change=-17.9, contribution=-21, insight="区域活动结束后到店恢复不足。"),
        ContributionRow(dimension="客户", segment="新客", current=6050, previous=7240, change=-16.4, contribution=-28, insight="新客获取是最大下降来源。"),
    ]
    hypotheses = []
    for index, hyp in enumerate(task.hypotheses):
        hyp = hyp.model_copy(deep=True)
        hyp.evidence_strength = ["强", "中", "弱"][index % 3]
        hyp.status = ["支持", "部分支持", "未验证"][index % 3]
        hyp.missing_data = [] if hyp.evidence_strength == "强" else ["活动排期明细", "门店邀约日志"]
        hypotheses.append(hyp)
    sql_reviews = [
        SqlReview(
            title="北极星指标漏斗汇总",
            sql=(
                "SELECT channel, region, COUNT(DISTINCT leads_id) AS leads, "
                "COUNT(DISTINCT visit_id) AS visits, COUNT(DISTINCT order_id) AS orders "
                "FROM sales_funnel WHERE biz_date BETWEEN :start AND :end GROUP BY channel, region;"
            ),
            fields=["channel", "region", "leads_id", "visit_id", "order_id", "biz_date"],
            business_explanation="按渠道和区域汇总线索、到店、订单，识别订单下降来自流量供给还是转化效率。",
        ),
        SqlReview(
            title="贡献度拆解",
            sql=(
                "SELECT dim_name, dim_value, current_orders, previous_orders, "
                "(current_orders - previous_orders) AS diff FROM contribution_view ORDER BY diff ASC;"
            ),
            fields=["dim_name", "dim_value", "current_orders", "previous_orders"],
            business_explanation="把本期和对比期订单差额按维度切开，找出负贡献最大的业务切片。",
        ),
    ]
    return DataAnalysisResponse(
        north_star_tree=tree,
        contribution_rows=rows,
        hypotheses=hypotheses,
        sql_reviews=sql_reviews,
        insight_cards=[
            "订单量下降 12.4%，主要由线索量下降和到店转化走弱共同驱动。",
            "负贡献集中在付费媒体、自然流量、华东区域和新客群体。",
            "建议优先补充渠道投放质量、区域活动排期、门店邀约过程数据。",
        ],
    )


def build_artifacts(task: Task) -> list[Artifact]:
    clarifications = clarification_questions(task)
    dimensions = task.selected_dimensions or task.recommended_dimensions
    items = [
        Artifact(
            id=f"art_clarification_{task.task_id}",
            task_id=task.task_id,
            type="clarification",
            title="需求澄清文档",
            summary="明确问题、周期、口径、数据源和待追问事项。",
            content=[
                f"业务问题：{task.business_question}",
                f"分析目的：{task.analysis_purpose}",
                f"周期：{task.time_range}；对比：{task.comparison_period}",
                *[f"AI 追问：{q}" for q in clarifications],
            ],
            status="confirmed" if task.status != "draft" else "draft",
            updated_at=now_iso(),
        ),
        Artifact(
            id=f"art_plan_{task.task_id}",
            task_id=task.task_id,
            type="analysis_plan",
            title="分析思路文档",
            summary="从北极星指标出发，按指标树、维度贡献、假设验证推进。",
            content=[
                "路径 1：北极星指标 -> 漏斗阶段 -> 关键转化率。",
                "路径 2：整体下降 -> 维度贡献 -> 负贡献切片。",
                "路径 3：业务假设 -> 证据强弱 -> 待补数据。",
            ],
            status="confirmed" if task.status in {"design_confirmed", "insight_confirmed", "report_ready"} else "draft",
            updated_at=now_iso(),
        ),
        Artifact(
            id=f"art_dimensions_{task.task_id}",
            task_id=task.task_id,
            type="dimension_recommendation",
            title="维度推荐文档",
            summary="推荐优先拆解渠道、时间、区域、客户、车型和经销商。",
            content=[f"推荐维度：{d}" for d in dimensions],
            status="updated" if task.selected_dimensions else "draft",
            updated_at=now_iso(),
        ),
        Artifact(
            id=f"art_hypotheses_{task.task_id}",
            task_id=task.task_id,
            type="hypothesis_pool",
            title="假设池文档",
            summary="沉淀 BA 可编辑、可标记核心的分析假设。",
            content=[f"{'核心' if h.core else '普通'}假设：{h.title}；指标：{', '.join(h.metrics)}" for h in task.hypotheses],
            status="updated",
            updated_at=now_iso(),
        ),
    ]
    if task.status in {"design_confirmed", "insight_confirmed", "report_ready"}:
        analysis = data_analysis(task)
        items.extend(
            [
                Artifact(
                    id=f"art_insight_{task.task_id}",
                    task_id=task.task_id,
                    type="data_insight",
                    title="数据洞察文档",
                    summary="北极星指标归因、贡献度和假设验证结论。",
                    content=analysis.insight_cards,
                    status="confirmed" if task.status in {"insight_confirmed", "report_ready"} else "draft",
                    updated_at=now_iso(),
                ),
                Artifact(
                    id=f"art_sql_{task.task_id}",
                    task_id=task.task_id,
                    type="sql_review",
                    title="SQL 业务解释文档",
                    summary="把 SQL 取数逻辑翻译为 BA 可审阅的业务语言。",
                    content=[review.business_explanation for review in analysis.sql_reviews],
                    status="draft",
                    updated_at=now_iso(),
                ),
            ]
        )
    if task.status == "report_ready":
        items.append(
            Artifact(
                id=f"art_report_{task.task_id}",
                task_id=task.task_id,
                type="cea_report",
                title="结论-证据-行动报告",
                summary="用于评审和交付的 BA 可编辑报告。",
                content=[f"结论：{task.report.conclusion}", f"证据：{task.report.evidence}", f"行动：{task.report.action}"],
                status="confirmed",
                updated_at=now_iso(),
            )
        )
    return items


def refresh_artifacts(task: Task) -> Task:
    task.artifacts = build_artifacts(task)
    task.updated_at = now_iso()
    return task


def catalog() -> dict:
    return {
        "question_types": ["下降归因", "转化漏斗", "目标拆解", "结构贡献", "异常诊断"],
        "methods": ["北极星指标树", "维度贡献度", "漏斗转化", "同期对比", "假设验证"],
        "metrics": ["register", "leads", "oppty", "visit", "td", "order", "order/oppty", "visit/oppty"],
    }


def semantic_state() -> dict:
    return {
        "entities": ["客户", "线索", "商机", "到店", "试驾", "订单", "经销商"],
        "events": ["注册", "留资", "建机", "邀约", "到店", "试驾", "成交"],
        "relationships": ["客户-线索", "线索-商机", "商机-到店", "试驾-订单"],
        "field_aliases": {
            "leads_id": ["线索ID", "leads编号"],
            "visit_id": ["到店ID", "进店记录"],
            "order_id": ["订单ID", "成交单号"],
        },
    }


def data_assets() -> dict:
    return {
        "mock_sources": [
            {"name": "sales_demo", "type": "Mock CSV", "rows": 120000, "description": "销售漏斗样例数据"},
            {"name": "semantic_model", "type": "Ontology", "rows": 86, "description": "指标口径和字段映射"},
        ],
        "real_sample": {
            "name": "ads_rpt_sal_ncs_register_to_order_sales_ssa_t",
            "description": "当前项目已有真实漏斗样例结构，V2 只读取聚合样例，不接生产库。",
        },
    }


def write_report(task: Task, export_dir: Path, fmt: str) -> tuple[str, str]:
    safe_name = re.sub(r"[^0-9A-Za-z一-龥_-]+", "_", task.task_name).strip("_") or task.task_id
    if fmt == "json":
        file_name = f"{safe_name}_{task.task_id}.json"
        payload = task.report.model_dump()
        (export_dir / file_name).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    elif fmt == "markdown":
        file_name = f"{safe_name}_{task.task_id}.md"
        text = f"# {task.task_name}\n\n## 结论\n{task.report.conclusion}\n\n## 证据\n{task.report.evidence}\n\n## 行动\n{task.report.action}\n"
        (export_dir / file_name).write_text(text, encoding="utf-8")
    else:
        file_name = f"{safe_name}_{task.task_id}.html"
        body = "".join(
            f"<section><h2>{title}</h2><p>{html.escape(content)}</p></section>"
            for title, content in [
                ("结论", task.report.conclusion),
                ("证据", task.report.evidence),
                ("行动", task.report.action),
            ]
        )
        (export_dir / file_name).write_text(
            f"<!doctype html><html lang='zh-CN'><meta charset='utf-8'><title>{html.escape(task.task_name)}</title><body>{body}</body></html>",
            encoding="utf-8",
        )
    return file_name, f"/exports/{file_name}"
