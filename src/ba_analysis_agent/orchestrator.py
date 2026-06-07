from __future__ import annotations

from copy import deepcopy
from uuid import uuid4

from .agents import AnalysisDesignAgent, DataAnalysisInsightAgent, IntentUnderstandingAgent, ReportGenerationAgent
from .llm import LLMService, create_llm_service
from .models import (
    AgentSession,
    AgentState,
    DataSourceProfile,
    RevisionRecord,
    Stage,
    StageArtifact,
    StageStatus,
    utc_now,
)
from .skills import SkillsManager
from .workflow import WorkflowConfig, get_workflow_config


class MasterAnalyticsAgent:
    """主协调 Agent。

    这是贴合当前本地 CLI 的轻量实现：保留同步 API，但内部结构按
    Master Agent 的职责组织，包括工作流配置、阶段执行、审批状态、
    修订历史和事件历史。
    """

    def __init__(
        self,
        data_source: DataSourceProfile,
        workspace_type: str = "analytics",
        skills_manager: SkillsManager | None = None,
        llm_service: LLMService | None = None,
    ):
        self.data_source = data_source
        self.workspace_type = workspace_type
        self.workflow_config: WorkflowConfig = get_workflow_config(workspace_type)
        self.skills_manager = skills_manager or SkillsManager()
        self.llm_service = llm_service or create_llm_service()
        self.intent_agent = IntentUnderstandingAgent(self.skills_manager, None if self.llm_service.provider_name == "disabled" else self.llm_service)
        self.session: AgentSession | None = None
        self.agents = {
            "analytics": {
                Stage.ANALYSIS_DESIGN: None,
                Stage.DATA_PLAN: None,
                Stage.INSIGHT_REVIEW: None,
                Stage.REPORT_PLAN: None,
                Stage.FINAL_REVIEW: None,
            }
        }

    def start(
        self,
        business_question: str,
        skill_name: str | None = None,
        extracted_params: dict[str, object] | None = None,
        user_id: str = "ba_user",
    ) -> StageArtifact:
        session_id = f"session_{uuid4().hex[:12]}"
        first_stage = self.workflow_config.first_stage()
        self.session = AgentSession(
            business_question=business_question,
            data_source=self.data_source,
            session_id=session_id,
            workspace_type=self.workspace_type,
            agent_state=AgentState.RUNNING,
            active_stage=first_stage,
            extracted_params=extracted_params or {},
        )
        self._record("workflow_started", user_id, None, {"workspace_type": self.workspace_type})
        self._update_analysis_context(business_question, "initial")
        artifact = self._run_stage(first_stage, skill_name=skill_name)
        self._request_approval(first_stage)
        return artifact

    def current_artifact(self) -> StageArtifact:
        session = self._session()
        artifact = session.artifacts.get(session.active_stage)
        if artifact is None:
            artifact = self._run_stage(session.active_stage)
            self._request_approval(session.active_stage)
        return artifact

    def confirm_current(self, actor: str = "ba_user", feedback: str | None = None) -> StageArtifact:
        session = self._session()
        artifact = self.current_artifact()
        artifact.status = StageStatus.BA_CONFIRMED
        artifact.updated_at = utc_now()
        self._record("stage_approved", actor, session.active_stage, {"feedback": feedback})

        next_stage = self.workflow_config.next_stage(session.active_stage)
        if next_stage == Stage.DONE:
            session.active_stage = Stage.DONE
            session.agent_state = AgentState.COMPLETED
            self._record("workflow_completed", "system", None)
            return artifact

        session.active_stage = next_stage
        session.agent_state = AgentState.RUNNING
        next_artifact = self._run_stage(next_stage)
        self._request_approval(next_stage)
        return next_artifact

    def request_revision(self, note: str, actor: str = "ba_user") -> StageArtifact:
        session = self._session()
        artifact = self.current_artifact()
        before = deepcopy(artifact.payload)
        _append_session_feedback(session, "revision", note)
        self._update_analysis_context(note, "revision")
        revised_artifact = self._rerun_active_stage()
        revised_artifact.revision_notes.append(note)
        revised_artifact.payload["revision_requested"] = note
        session.revisions.append(
            RevisionRecord(
                stage=session.active_stage,
                revision_type="manual_feedback",
                feedback=note,
                before=before,
                after=deepcopy(revised_artifact.payload),
                actor=actor,
            )
        )
        session.agent_state = AgentState.WAITING_APPROVAL
        self._record("stage_changes_requested", actor, session.active_stage, {"feedback": note})
        return revised_artifact

    def add_ba_feedback(self, note: str, actor: str = "ba_user", feedback_type: str = "clarification") -> StageArtifact:
        session = self._session()
        artifact = self.current_artifact()
        before = deepcopy(artifact.payload)
        _append_session_feedback(session, feedback_type, note)
        self._update_analysis_context(note, feedback_type)
        updated_artifact = self._rerun_active_stage()
        session.revisions.append(
            RevisionRecord(
                stage=session.active_stage,
                revision_type=feedback_type,
                feedback=note,
                before=before,
                after=deepcopy(updated_artifact.payload),
                actor=actor,
            )
        )
        session.agent_state = AgentState.WAITING_APPROVAL
        self._record("ba_feedback_added", actor, session.active_stage, {"feedback": note, "feedback_type": feedback_type})
        return updated_artifact

    def reject_current(self, note: str, actor: str = "ba_user") -> StageArtifact:
        session = self._session()
        artifact = self.current_artifact()
        artifact.status = StageStatus.REJECTED
        artifact.revision_notes.append(note)
        artifact.updated_at = utc_now()
        self._record("stage_rejected", actor, session.active_stage, {"feedback": note})
        return artifact

    def status(self) -> dict[str, object]:
        session = self._session()
        return {
            "session_id": session.session_id,
            "workspace_type": session.workspace_type,
            "workflow": self.workflow_config.name,
            "agent_state": session.agent_state.value,
            "business_question": session.business_question,
            "active_stage": session.active_stage.value,
            "stages": {
                stage.value: session.artifacts[stage].status.value
                for stage in session.artifacts
            },
            "operation_count": len(session.operations),
            "revision_count": len(session.revisions),
        }

    def history(self) -> dict[str, object]:
        session = self._session()
        return {
            "operations": session.operations,
            "revisions": session.revisions,
        }

    def workflow(self) -> WorkflowConfig:
        return self.workflow_config

    def llm_status(self) -> dict[str, object]:
        return {
            "provider": self.llm_service.provider_name,
            "enabled": self.llm_service.provider_name != "disabled",
            "privacy_policy": self.data_source.privacy_policy,
            "data_boundary": "metadata_only",
            "last_error": getattr(self.llm_service, "last_error", None),
        }

    def _run_stage(self, stage: Stage, skill_name: str | None = None) -> StageArtifact:
        session = self._session()
        stage_config = self.workflow_config.stage_config(stage)
        self._record("stage_started", "system", stage, {"stage_name": stage_config.name})
        try:
            agent = self._initialize_agent(stage, skill_name)
            payload = agent.run(self._prepare_agent_input(stage))
            artifact = StageArtifact(stage, StageStatus.DRAFT, payload)
            session.artifacts[stage] = artifact
            session.agent_state = AgentState.WAITING_APPROVAL if stage_config.require_approval else AgentState.RUNNING
            self._record("stage_completed", "system", stage, {"stage_name": stage_config.name})
            return artifact
        except Exception as exc:
            session.agent_state = AgentState.ERROR
            artifact = StageArtifact(
                stage=stage,
                status=StageStatus.ERROR,
                payload={"error": str(exc), "ba_confirmation_required": False},
            )
            session.artifacts[stage] = artifact
            self._record("stage_error", "system", stage, {"error": str(exc)})
            raise

    def _rerun_active_stage(self) -> StageArtifact:
        session = self._session()
        self.agents[self.workspace_type][session.active_stage] = None
        artifact = self._run_stage(session.active_stage)
        self._request_approval(session.active_stage)
        return artifact

    def _update_analysis_context(self, user_message: str, feedback_type: str) -> dict[str, object]:
        self.intent_agent = IntentUnderstandingAgent(
            self.skills_manager,
            None if self.llm_service.provider_name == "disabled" else self.llm_service,
        )
        return self.intent_agent.update_context(self._session(), user_message, feedback_type)

    def _initialize_agent(self, stage: Stage, skill_name: str | None = None):
        cached = self.agents[self.workspace_type].get(stage)
        if cached is not None:
            return cached

        if stage == Stage.ANALYSIS_DESIGN:
            skill = self.skills_manager.choose_skill(self.data_source, skill_name)
            agent = AnalysisDesignAgent(skill, self.skills_manager, self.llm_service)
        elif stage == Stage.DATA_PLAN:
            agent = DataAnalysisInsightAgent(self.skills_manager, self.llm_service)
        elif stage == Stage.REPORT_PLAN:
            agent = ReportGenerationAgent(self.llm_service)
        elif stage == Stage.INSIGHT_REVIEW:
            agent = StaticStageAgent(_insight_review_payload())
        elif stage == Stage.FINAL_REVIEW:
            agent = StaticStageAgent(_final_review_payload())
        else:
            raise ValueError(f"No agent configured for stage {stage.value}.")

        self.agents[self.workspace_type][stage] = agent
        return agent

    def _prepare_agent_input(self, stage: Stage) -> dict[str, object]:
        session = self._session()
        return {
            "stage_id": stage.value,
            "business_problem": session.business_question,
            "session": session,
            "data_source": session.data_source,
            **session.extracted_params,
        }

    def _request_approval(self, stage: Stage) -> None:
        session = self._session()
        stage_config = self.workflow_config.stage_config(stage)
        if stage_config.require_approval:
            session.agent_state = AgentState.WAITING_APPROVAL
            self._record(
                "approval_requested",
                "system",
                stage,
                {"stage_name": stage_config.name},
            )

    def _record(
        self,
        operation_type: str,
        actor: str,
        stage: Stage | None,
        details: dict[str, object] | None = None,
    ) -> None:
        self._session().add_operation(operation_type, actor, stage, details)

    def _session(self) -> AgentSession:
        if self.session is None:
            raise RuntimeError("No active session. Start with a business question first.")
        return self.session


class StaticStageAgent:
    def __init__(self, payload: dict[str, object]):
        self.payload = payload

    def run(self, input_data: dict[str, object]) -> dict[str, object]:
        return deepcopy(self.payload)


def _insight_review_payload() -> dict[str, object]:
    return {
        "analysis_agent": "数据分析和洞察 Agent",
        "purpose": "等待 BA 执行或确认取数结果后，沉淀洞察卡片。",
        "required_input": [
            "已执行的聚合结果或 BA 粘贴的结果摘要",
            "校验结果",
            "业务口径补充说明",
        ],
        "insight_card_template": {
            "title": "",
            "claim_type": "已验证事实 | 合理推断 | 待业务确认",
            "evidence": "",
            "impact": "",
            "next_action": "",
        },
        "ba_confirmation_required": True,
    }


def _final_review_payload() -> dict[str, object]:
    return {
        "analysis_agent": "Orchestrator / Plan Agent",
        "purpose": "发布前最终审核。",
        "checklist": [
            "分析设计、取数计划、洞察和报告结构均已 BA 确认。",
            "未输出客户级敏感明细。",
            "所有字段均来自数据源 profile。",
            "结论类型标注完整。",
        ],
        "ba_confirmation_required": True,
    }


BAAnalysisOrchestrator = MasterAnalyticsAgent


def _append_session_feedback(session: AgentSession, feedback_type: str, note: str) -> None:
    feedback = session.extracted_params.setdefault("ba_feedback", [])
    if isinstance(feedback, list):
        feedback.append(
            {
                "type": feedback_type,
                "text": note,
                "timestamp": utc_now(),
            }
        )
