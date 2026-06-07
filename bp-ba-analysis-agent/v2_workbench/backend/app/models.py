from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


Stage = Literal["task_creation", "analysis_design", "data_insight", "report_generation"]
ArtifactType = Literal[
    "clarification",
    "analysis_plan",
    "dimension_recommendation",
    "hypothesis_pool",
    "data_insight",
    "sql_review",
    "cea_report",
]


class ConversationMessage(BaseModel):
    id: str
    role: Literal["agent", "ba", "system"]
    content: str
    stage: Stage
    created_at: str


class Artifact(BaseModel):
    id: str
    task_id: str
    type: ArtifactType
    title: str
    summary: str
    content: list[str] = Field(default_factory=list)
    status: Literal["draft", "confirmed", "updated"] = "draft"
    updated_at: str


class Hypothesis(BaseModel):
    id: str
    title: str
    rationale: str
    metrics: list[str] = Field(default_factory=list)
    core: bool = False
    evidence_strength: Literal["强", "中", "弱", "待验证"] = "待验证"
    missing_data: list[str] = Field(default_factory=list)
    status: Literal["未验证", "支持", "部分支持", "不支持"] = "未验证"


class MetricNode(BaseModel):
    id: str
    label: str
    value: float
    change: float
    contribution: float
    children: list["MetricNode"] = Field(default_factory=list)


class ContributionRow(BaseModel):
    dimension: str
    segment: str
    current: float
    previous: float
    change: float
    contribution: float
    insight: str


class SqlReview(BaseModel):
    title: str
    sql: str
    fields: list[str]
    business_explanation: str


class CEAReport(BaseModel):
    conclusion: str
    evidence: str
    action: str


class TaskInput(BaseModel):
    task_name: str = "客流下降原因分析"
    business_question: str = "近期客流下降明显，想分析是哪些渠道在下降，以及新客获取和老客回店的表现变化。"
    analysis_purpose: str = "定位客流下降的核心原因，并给出可执行改善动作。"
    time_range: str = "2026/01/01 - 2026/03/31"
    comparison_period: str = "2025/10/01 - 2025/12/31"
    data_source: str = "sales_demo"


class Task(BaseModel):
    task_id: str
    task_name: str
    business_question: str
    analysis_purpose: str
    time_range: str
    comparison_period: str
    data_source: str
    status: Literal["draft", "input_confirmed", "design_confirmed", "insight_confirmed", "report_ready"] = "draft"
    current_page: Stage = "task_creation"
    selected_dimensions: list[str] = Field(default_factory=list)
    recommended_dimensions: list[str] = Field(default_factory=list)
    hypotheses: list[Hypothesis] = Field(default_factory=list)
    report: CEAReport = Field(
        default_factory=lambda: CEAReport(
            conclusion="客流下降主要由高意向线索减少和到店转化下降共同驱动。",
            evidence="渠道贡献度显示自然流量和区域活动线索的负贡献最高，visit/oppty 转化率同步下降。",
            action="优先修复高意向线索供给，针对下降区域补充邀约动作，并建立周度漏斗监控。",
        )
    )
    artifacts: list[Artifact] = Field(default_factory=list)
    messages: list[ConversationMessage] = Field(default_factory=list)
    created_at: str
    updated_at: str


class TaskListResponse(BaseModel):
    tasks: list[Task]
    stats: dict[str, int]


class DataAnalysisResponse(BaseModel):
    north_star_tree: MetricNode
    contribution_rows: list[ContributionRow]
    hypotheses: list[Hypothesis]
    sql_reviews: list[SqlReview]
    insight_cards: list[str]


class ReportExportResponse(BaseModel):
    file_name: str
    download_url: str
    format: Literal["html", "markdown", "json"]


class AgentAction(BaseModel):
    type: str
    title: str
    detail: str


class ChatRequest(BaseModel):
    message: str
    active_page: Stage = "task_creation"
    allow_task_update: bool = True
    client_context: dict = Field(default_factory=dict)


class ChatResponse(BaseModel):
    assistant_message: ConversationMessage
    actions: list[AgentAction] = Field(default_factory=list)
    task: Task
    artifacts: list[Artifact]
    next_page: Stage | None = None


class ChatStartRequest(ChatRequest):
    pass


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")
