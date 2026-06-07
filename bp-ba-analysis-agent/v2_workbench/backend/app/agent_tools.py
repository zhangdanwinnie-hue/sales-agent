from __future__ import annotations

import re

from .mock_agent import data_analysis, default_hypotheses, recommend_dimensions, refresh_artifacts, uid
from .models import AgentAction, CEAReport, Hypothesis, Stage, Task, now_iso


DIMENSION_ALIASES = {
    "渠道": "渠道维度",
    "经销商": "经销商维度",
    "门店": "经销商维度",
    "活动": "活动维度",
    "区域": "区域维度",
    "城市": "区域维度",
    "车型": "车型维度",
    "车系": "车型维度",
    "客户": "客户维度",
    "新客": "客户维度",
    "时间": "时间维度",
}


def update_task_from_message(task: Task, text: str) -> list[AgentAction]:
    actions: list[AgentAction] = []
    if any(word in text for word in ["新建", "创建", "分析"]) and any(word in text for word in ["任务", "问题", "客流", "订单", "转化"]):
        task.business_question = _extract_business_question(text) or task.business_question
        if "客流" in text:
            task.task_name = "客流下降原因分析"
            task.analysis_purpose = "定位客流下降的核心原因，并给出可执行改善动作。"
        elif "转化" in text:
            task.task_name = "转化效率分析"
            task.analysis_purpose = "拆解转化效率变化，识别关键影响因素和改善动作。"
        elif "订单" in text:
            task.task_name = "订单变化归因分析"
            task.analysis_purpose = "定位订单变化来源，形成可执行经营建议。"
        task.recommended_dimensions = recommend_dimensions(task.business_question, task.analysis_purpose)
        task.current_page = "task_creation"
        actions.append(AgentAction(type="update_task_input", title="更新任务输入", detail=f"已根据对话更新业务问题：{task.business_question}"))
    return actions


def add_dimensions_from_message(task: Task, text: str) -> list[AgentAction]:
    matched = [dimension for key, dimension in DIMENSION_ALIASES.items() if key in text]
    if not matched:
        return []
    before = set(task.selected_dimensions)
    task.selected_dimensions = list(dict.fromkeys([*task.selected_dimensions, *matched]))
    added = [dimension for dimension in task.selected_dimensions if dimension not in before]
    if not added:
        return []
    task.current_page = "analysis_design"
    if task.status == "draft":
        task.status = "input_confirmed"
    return [AgentAction(type="select_dimensions", title="补充分析维度", detail=f"已加入：{'、'.join(added)}")]


def add_hypothesis_from_message(task: Task, text: str) -> list[AgentAction]:
    if not any(word in text for word in ["假设", "猜想", "可能原因"]):
        return []
    title = _extract_after_colon(text) or _strip_command_words(text) or "新增业务假设"
    metrics = _infer_metrics(title)
    hypothesis = Hypothesis(
        id=uid("hyp"),
        title=title[:80],
        rationale=f"由 BA 在自然语言对话中补充：{title}",
        metrics=metrics,
        core=("核心" in text or "重点" in text),
        evidence_strength="待验证",
        missing_data=["待补充对应明细数据"],
        status="未验证",
    )
    task.hypotheses.append(hypothesis)
    task.current_page = "analysis_design"
    if task.status == "draft":
        task.status = "input_confirmed"
    return [AgentAction(type="add_hypothesis", title="新增假设", detail=hypothesis.title)]


def generate_report_from_message(task: Task, text: str) -> list[AgentAction]:
    if not any(word in text for word in ["生成报告", "写报告", "报告", "结论", "老板"]):
        return []
    analysis = data_analysis(task)
    boss_tone = "老板" in text or "管理层" in text
    task.report = CEAReport(
        conclusion=(
            "客流和订单下滑不是单点问题，而是线索供给下降、到店转化走弱、区域承接不足叠加造成。"
            if boss_tone
            else "客流下降主要由高意向线索减少和到店转化下降共同驱动。"
        ),
        evidence="；".join(analysis.insight_cards[:3]),
        action=(
            "建议先抓三件事：恢复高意向线索供给，锁定负贡献区域做邀约修复，把渠道-区域-门店漏斗监控改成周度复盘。"
            if boss_tone
            else "优先修复高意向线索供给，针对下降区域补充邀约动作，并建立周度漏斗监控。"
        ),
    )
    task.status = "report_ready"
    task.current_page = "report_generation"
    return [AgentAction(type="generate_report", title="生成报告草稿", detail="已按结论-证据-行动结构更新报告。")]


def generate_insight_from_message(task: Task, text: str) -> list[AgentAction]:
    if not any(word in text for word in ["洞察", "归因", "贡献度", "验证"]):
        return []
    if task.status in {"draft", "input_confirmed"}:
        task.status = "design_confirmed"
    task.current_page = "data_insight"
    return [AgentAction(type="generate_insight", title="生成数据洞察", detail="已切换到数据洞察，并刷新归因树、贡献度和假设验证。")]


def apply_rule_actions(task: Task, text: str, active_page: Stage) -> tuple[Task, list[AgentAction], Stage | None]:
    actions: list[AgentAction] = []
    text = text.strip()
    if any(word in text for word in ["删除任务", "清空", "覆盖全部", "全部删除"]):
        return task, [AgentAction(type="needs_confirmation", title="需要确认", detail="删除或覆盖类操作不会直接执行，请使用页面按钮或再次明确确认。")], None

    actions.extend(update_task_from_message(task, text))
    actions.extend(add_dimensions_from_message(task, text))
    actions.extend(add_hypothesis_from_message(task, text))
    actions.extend(generate_insight_from_message(task, text))
    actions.extend(generate_report_from_message(task, text))

    if not actions:
        task.current_page = active_page
        actions.append(AgentAction(type="answer", title="回复建议", detail="已基于当前任务上下文给出下一步建议。"))

    task.updated_at = now_iso()
    refresh_artifacts(task)
    return task, actions, task.current_page


def build_rule_reply(task: Task, user_message: str, actions: list[AgentAction]) -> str:
    if actions and actions[0].type == "needs_confirmation":
        return f"我理解你的意思，但这个操作风险较高：{actions[0].detail}"
    if actions and actions[0].type != "answer":
        summary = "；".join(action.detail for action in actions)
        return f"已处理。{summary} 你可以继续用自然语言让我补维度、加假设、生成洞察或改报告。"
    return (
        "我已经读取当前任务上下文。你可以直接说："
        "“把维度加上经销商和活动”、“新增一个假设：渠道投放质量下降”、"
        "“基于现在的洞察生成报告”，我会直接更新工作台和过程文档。"
    )


def _extract_after_colon(text: str) -> str:
    parts = re.split(r"[:：]", text, maxsplit=1)
    return parts[1].strip() if len(parts) == 2 else ""


def _strip_command_words(text: str) -> str:
    cleaned = re.sub(r"^(帮我|请|新增|添加|补充|一个|一条|假设|：|:)+", "", text).strip()
    return cleaned


def _extract_business_question(text: str) -> str:
    if "分析" in text:
        return text[text.find("分析") :].strip("。 ")
    return text.strip("。 ")


def _infer_metrics(text: str) -> list[str]:
    metrics = []
    if any(word in text for word in ["渠道", "投放", "媒体"]):
        metrics.extend(["leads", "channel contribution", "leads/register"])
    if any(word in text for word in ["转化", "到店", "邀约"]):
        metrics.extend(["visit/oppty", "td/visit", "order/oppty"])
    if any(word in text for word in ["订单", "成交"]):
        metrics.extend(["orders", "order/oppty"])
    return list(dict.fromkeys(metrics or ["待补指标"]))
