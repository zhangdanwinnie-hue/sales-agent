"""Three-agent BP BA analysis workflow with BA confirmation gates."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any
from uuid import uuid4

from .agent import BPBAAnalysisAgent
from .analysis_topics import recommend_topics
from .models import AnalysisCase


DESIGN_STEP = "analysis_design"
INSIGHT_STEP = "data_insight"
REPORT_STEP = "report_generation"


@dataclass(frozen=True)
class BAConfirmation:
    step_id: str
    confirmed: bool
    confirmed_by: str
    feedback: str = ""
    confirmed_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AgentContract:
    agent_id: str
    name: str
    responsibility: str
    input_schema: dict[str, str]
    output_schema: dict[str, str]
    ba_confirmation_gate: str
    next_agent: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AgentStepResult:
    step_id: str
    agent_id: str
    agent_name: str
    input_payload: dict[str, Any]
    output_payload: dict[str, Any]
    ba_confirmation_required: bool
    confirmation_prompt: str
    status: str = "waiting_ba_confirmation"
    created_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class WorkflowSession:
    session_id: str
    business_question: str
    case: AnalysisCase
    current_step: str
    status: str
    results: dict[str, AgentStepResult] = field(default_factory=dict)
    confirmations: dict[str, BAConfirmation] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "business_question": self.business_question,
            "current_step": self.current_step,
            "status": self.status,
            "created_at": self.created_at,
            "case": self.case.to_dict(),
            "results": {key: value.to_dict() for key, value in self.results.items()},
            "confirmations": {key: value.to_dict() for key, value in self.confirmations.items()},
        }


class BAConfirmationRequiredError(RuntimeError):
    """Raised when a workflow step is executed without the required BA signoff."""


def workflow_contracts() -> list[AgentContract]:
    return [
        AgentContract(
            agent_id=DESIGN_STEP,
            name="分析思路拆解和设计 Agent",
            responsibility="把业务问题转成可审核的分析框架，包括问题类型、语义对象、分析方法、指标树、维度和字段需求。",
            input_schema={
                "business_question": "BA 或业务方提出的自然语言问题",
                "scenario": "可选业务场景，例如媒体投流、车型转化、经销商运营、Target steering、客流复盘",
                "analysis_purpose": "可选分析目的；缺失时 Agent 给默认理解并要求 BA 确认",
                "target_object": "可选分析对象，例如大区、城市、经销商、车型、渠道",
                "time_range": "可选分析周期",
                "dimensions": "可选下钻维度列表",
                "available_fields": "可选字段清单，用于判断当前数据是否能支撑分析计划",
            },
            output_schema={
                "clarification_questions": "需要 BA 确认或补充的问题",
                "scenario": "Agent 推荐的业务场景",
                "question_types": "Agent 识别的问题类型",
                "selected_methods": "动态组合的分析方法",
                "semantic_matches": "业务对象、指标、维度和物理字段的语义匹配",
                "data_availability": "可用、部分可用或需要补充的数据需求",
                "analysis_framework": "业务假设、指标树、维度、字段需求、分析路径",
                "ba_decision_needed": "BA 是否认可分析目的、范围、指标和维度",
            },
            ba_confirmation_gate="BA 确认分析目的、范围、目标对象、时间周期、指标树和下钻维度后，才能进入数据分析。",
            next_agent=INSIGHT_STEP,
        ),
        AgentContract(
            agent_id=INSIGHT_STEP,
            name="数据分析和洞察 Agent",
            responsibility="基于已确认的分析设计生成取数计划、SQL 草稿、校验路径和初步洞察。",
            input_schema={
                "confirmed_analysis_design": "BA 已确认的分析框架",
                "data_sources": "数仓、BI/Tableau 元数据、历史 Excel/知识库，首期只读",
                "metric_definitions": "已确认的指标口径和维度粒度",
            },
            output_schema={
                "data_access_plan": "数据源、用途、负责人、只读标识",
                "sql_plan": "可审核 SQL/取数计划",
                "validation_plan": "跨来源对账、口径一致性、异常波动、缺失值检查",
                "insight_cards": "初步洞察卡片和待人工确认解释",
            },
            ba_confirmation_gate="BA 确认数据源、表字段、过滤条件、指标口径、校验差异解释后，才能进入报告产出。",
            next_agent=REPORT_STEP,
        ),
        AgentContract(
            agent_id=REPORT_STEP,
            name="报告产出和生成 Agent",
            responsibility="把已确认的数据洞察转成 Excel/PPT/BRD/报告页草稿，并保留结论强度和口径说明。",
            input_schema={
                "confirmed_data_insights": "BA 已确认的数据分析、校验结果和洞察",
                "deliverable_type": "管理汇报、业务讨论、数据校验、Target steering 或复盘报告",
                "audience": "目标受众",
            },
            output_schema={
                "executive_summary": "结论摘要草稿",
                "ppt_storyline": "PPT 故事线",
                "excel_tabs": "Excel 分析表结构",
                "brd_sections": "BRD/分析说明结构",
                "ba_final_review": "发布前需要 BA 最终确认的事项",
            },
            ba_confirmation_gate="BA 确认结论强度、业务表达、口径说明和发布范围后，才能对外交付。",
            next_agent=None,
        ),
    ]


class AnalysisDesignAgent:
    agent_id = DESIGN_STEP
    name = "分析思路拆解和设计 Agent"

    def __init__(self, base_agent: BPBAAnalysisAgent | None = None) -> None:
        self.base_agent = base_agent or BPBAAnalysisAgent()

    def run(
        self,
        *,
        business_question: str,
        scenario: str | None = None,
        analysis_purpose: str | None = None,
        target_object: str | None = None,
        time_range: str | None = None,
        dimensions: list[str] | None = None,
        deliverable_type: str = "management_report",
        audience: str = "Sales BP / BI stakeholders",
        available_fields: list[str] | None = None,
    ) -> tuple[AnalysisCase, AgentStepResult]:
        case = self.base_agent.run(
            business_question,
            scenario=scenario,
            analysis_purpose=analysis_purpose,
            target_object=target_object,
            time_range=time_range,
            dimensions=dimensions,
            deliverable_type=deliverable_type,
            audience=audience,
            available_fields=available_fields,
        )
        output = {
            "scenario": case.scenario,
            "question_types": case.question_types,
            "recommended_topics": [topic.to_dict() for topic in recommend_topics(case.business_question)],
            "analysis_purpose": case.analysis_purpose,
            "target_object": case.target_object,
            "time_range": case.time_range,
            "dimensions": case.dimensions,
            "clarification_questions": case.clarification_questions,
            "hypotheses": case.hypotheses,
            "selected_methods": [asdict(method) for method in case.selected_methods],
            "semantic_matches": [asdict(match) for match in case.semantic_matches],
            "data_availability": [asdict(item) for item in case.data_availability],
            "metric_tree": [asdict(metric) for metric in case.metric_tree],
            "field_requirements": _field_requirements(case),
            "analysis_path": [
                "确认业务问题和边界",
                "建立业务假设和指标树",
                "按核心维度拆解差异",
                "生成取数和校验计划",
                "输出结论草稿并由 BA 审核",
            ],
        }
        return case, AgentStepResult(
            step_id=DESIGN_STEP,
            agent_id=self.agent_id,
            agent_name=self.name,
            input_payload={
                "business_question": business_question,
                "scenario": scenario,
                "analysis_purpose": analysis_purpose,
                "target_object": target_object,
                "time_range": time_range,
                "dimensions": dimensions or [],
                "deliverable_type": deliverable_type,
                "audience": audience,
                "available_fields": available_fields or [],
            },
            output_payload=output,
            ba_confirmation_required=True,
            confirmation_prompt="请 BA 确认：分析目的、范围、目标对象、周期、指标树和下钻维度是否可用于取数分析。",
        )


class DataInsightAgent:
    agent_id = INSIGHT_STEP
    name = "数据分析和洞察 Agent"

    def run(self, case: AnalysisCase, confirmation: BAConfirmation) -> AgentStepResult:
        _require_confirmation(confirmation, DESIGN_STEP)
        output = {
            "confirmed_design_feedback": confirmation.feedback,
            "data_access_plan": [asdict(source) for source in case.data_sources],
            "sql_plan": [asdict(sql) for sql in case.sql_plan],
            "validation_plan": [asdict(check) for check in case.validation_plan],
            "insight_cards": self._build_insight_cards(case),
            "method_execution_plan": [
                {
                    "method": method.title,
                    "purpose": method.purpose,
                    "expected_outputs": method.outputs,
                    "ba_confirmation_focus": method.confirmation_focus,
                }
                for method in case.selected_methods
            ],
            "semantic_data_availability": [asdict(item) for item in case.data_availability],
            "ba_review_items": [
                "确认 SQL 草稿中的表、字段、过滤条件和指标公式是否与生产口径一致。",
                "确认数仓、Tableau/BI、历史 Excel 之间的差异解释是否合理。",
                "确认样本量、缺失值、异常波动是否足以支撑结论强度。",
            ],
        }
        return AgentStepResult(
            step_id=INSIGHT_STEP,
            agent_id=self.agent_id,
            agent_name=self.name,
            input_payload={
                "case_id": case.case_id,
                "confirmed_step": confirmation.to_dict(),
                "metric_count": len(case.metric_tree),
                "dimension_count": len(case.dimensions),
            },
            output_payload=output,
            ba_confirmation_required=True,
            confirmation_prompt="请 BA 确认：数据源、SQL/取数计划、口径校验和洞察解释是否可进入报告产出。",
        )

    @staticmethod
    def _build_insight_cards(case: AnalysisCase) -> list[dict[str, Any]]:
        cards: list[dict[str, Any]] = []
        for metric in case.metric_tree[:4]:
            cards.append(
                {
                    "title": metric.name,
                    "signal": metric.business_meaning,
                    "recommended_cut": case.dimensions[:4],
                    "validation": metric.validation_sources,
                    "status": "draft_requires_ba_review",
                }
            )
        if not cards:
            cards.append(
                {
                    "title": "待生成洞察",
                    "signal": "需要先确认指标树和维度。",
                    "recommended_cut": case.dimensions,
                    "validation": [],
                    "status": "blocked",
                }
            )
        return cards


class ReportGenerationAgent:
    agent_id = REPORT_STEP
    name = "报告产出和生成 Agent"

    def run(self, case: AnalysisCase, confirmation: BAConfirmation) -> AgentStepResult:
        _require_confirmation(confirmation, INSIGHT_STEP)
        deliverable = case.deliverable
        output = {
            "confirmed_insight_feedback": confirmation.feedback,
            "executive_summary": deliverable.executive_summary if deliverable else [],
            "ppt_storyline": deliverable.ppt_storyline if deliverable else [],
            "excel_tabs": deliverable.excel_tabs if deliverable else [],
            "brd_sections": deliverable.brd_sections if deliverable else [],
            "report_structure": [
                "业务背景和问题定义",
                "分析范围、口径和数据来源",
                "核心指标和维度拆解",
                "关键洞察和业务解释",
                "行动建议、风险和待确认事项",
            ],
            "ba_final_review_items": [
                "确认结论是否能对外发布，哪些只能作为内部假设。",
                "确认图表、口径说明、异常解释和行动建议是否匹配业务语境。",
                "确认最终材料是否需要回写知识库形成复用案例。",
            ],
        }
        return AgentStepResult(
            step_id=REPORT_STEP,
            agent_id=self.agent_id,
            agent_name=self.name,
            input_payload={
                "case_id": case.case_id,
                "confirmed_step": confirmation.to_dict(),
                "deliverable_type": case.deliverable_type,
                "audience": case.audience,
            },
            output_payload=output,
            ba_confirmation_required=True,
            confirmation_prompt="请 BA 最终确认：结论强度、业务表达、发布范围和知识库回写内容。",
        )


class MultiAgentWorkflow:
    """In-memory orchestrator for the gated three-agent workflow."""

    def __init__(self) -> None:
        self.design_agent = AnalysisDesignAgent()
        self.data_agent = DataInsightAgent()
        self.report_agent = ReportGenerationAgent()
        self.sessions: dict[str, WorkflowSession] = {}

    def start(
        self,
        *,
        business_question: str,
        scenario: str | None = None,
        analysis_purpose: str | None = None,
        target_object: str | None = None,
        time_range: str | None = None,
        dimensions: list[str] | None = None,
        deliverable_type: str = "management_report",
        audience: str = "Sales BP / BI stakeholders",
        available_fields: list[str] | None = None,
    ) -> WorkflowSession:
        case, design_result = self.design_agent.run(
            business_question=business_question,
            scenario=scenario,
            analysis_purpose=analysis_purpose,
            target_object=target_object,
            time_range=time_range,
            dimensions=dimensions,
            deliverable_type=deliverable_type,
            audience=audience,
            available_fields=available_fields,
        )
        session = WorkflowSession(
            session_id=f"workflow-{uuid4().hex[:8]}",
            business_question=business_question,
            case=case,
            current_step=DESIGN_STEP,
            status="waiting_ba_confirmation",
            results={DESIGN_STEP: design_result},
        )
        self.sessions[session.session_id] = session
        return session

    def confirm_step(
        self,
        session_id: str,
        *,
        step_id: str,
        confirmed_by: str,
        feedback: str = "",
        confirmed: bool = True,
    ) -> WorkflowSession:
        session = self.sessions[session_id]
        confirmation = BAConfirmation(
            step_id=step_id,
            confirmed=confirmed,
            confirmed_by=confirmed_by,
            feedback=feedback,
        )
        if not confirmed:
            session.confirmations[step_id] = confirmation
            session.status = "ba_revision_requested"
            session.current_step = step_id
            return session

        if step_id == DESIGN_STEP:
            data_result = self.data_agent.run(session.case, confirmation)
            session.confirmations[DESIGN_STEP] = confirmation
            session.results[DESIGN_STEP].status = "ba_confirmed"
            session.results[INSIGHT_STEP] = data_result
            session.current_step = INSIGHT_STEP
            session.status = "waiting_ba_confirmation"
            return session

        if step_id == INSIGHT_STEP:
            report_result = self.report_agent.run(session.case, confirmation)
            session.confirmations[INSIGHT_STEP] = confirmation
            session.results[INSIGHT_STEP].status = "ba_confirmed"
            session.results[REPORT_STEP] = report_result
            session.current_step = REPORT_STEP
            session.status = "waiting_ba_confirmation"
            return session

        if step_id == REPORT_STEP:
            _require_confirmation(confirmation, REPORT_STEP)
            session.confirmations[REPORT_STEP] = confirmation
            session.results[REPORT_STEP].status = "ba_confirmed"
            session.current_step = "completed"
            session.status = "completed"
            return session

        raise ValueError(f"Unsupported step_id: {step_id}")

    def get_session(self, session_id: str) -> WorkflowSession:
        return self.sessions[session_id]


def _require_confirmation(confirmation: BAConfirmation, expected_step: str) -> None:
    if confirmation.step_id != expected_step or not confirmation.confirmed:
        raise BAConfirmationRequiredError(f"{expected_step} must be confirmed by BA before continuing.")


def _field_requirements(case: AnalysisCase) -> list[dict[str, Any]]:
    fields: list[dict[str, Any]] = []
    seen: set[str] = set()
    for metric in case.metric_tree:
        for table in metric.source_tables:
            key = f"{metric.name}:{table}"
            if key in seen:
                continue
            seen.add(key)
            fields.append(
                {
                    "metric": metric.name,
                    "source_table": table,
                    "dimensions": metric.dimensions,
                    "validation_sources": metric.validation_sources,
                }
            )
    return fields
