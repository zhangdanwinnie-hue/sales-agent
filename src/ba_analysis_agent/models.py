from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Literal


SourceType = Literal["xlsx", "csv", "database"]
PrivacyPolicy = Literal["metadata_only"]


class Stage(str, Enum):
    ANALYSIS_DESIGN = "analysis_design"
    DATA_PLAN = "data_plan"
    INSIGHT_REVIEW = "insight_review"
    REPORT_PLAN = "report_plan"
    FINAL_REVIEW = "final_review"
    DONE = "done"


class AgentState(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    PAUSED = "paused"
    ERROR = "error"
    COMPLETED = "completed"


class StageStatus(str, Enum):
    DRAFT = "draft"
    BA_CONFIRMED = "ba_confirmed"
    NEEDS_REVISION = "needs_revision"
    REJECTED = "rejected"
    ERROR = "error"


@dataclass(frozen=True)
class ColumnProfile:
    name: str
    dtype: str = "unknown"
    business_domain: str = "general"
    is_sensitive: bool = False
    sample_allowed: bool = False


@dataclass(frozen=True)
class TableProfile:
    name: str
    row_count: int | None
    columns: list[ColumnProfile]

    def column_names(self) -> set[str]:
        return {column.name for column in self.columns}


@dataclass(frozen=True)
class DataSourceProfile:
    source_type: SourceType
    source_name: str
    tables_or_sheets: list[TableProfile]
    business_domains: list[str]
    privacy_policy: PrivacyPolicy = "metadata_only"

    def all_column_names(self) -> set[str]:
        names: set[str] = set()
        for table in self.tables_or_sheets:
            names.update(table.column_names())
        return names


@dataclass
class StageArtifact:
    stage: Stage
    status: StageStatus
    payload: dict[str, Any]
    revision_notes: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: utc_now())
    updated_at: str = field(default_factory=lambda: utc_now())


@dataclass
class OperationRecord:
    operation_type: str
    actor: str
    stage: Stage | None
    details: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: utc_now())


@dataclass
class RevisionRecord:
    stage: Stage
    revision_type: str
    feedback: str
    before: dict[str, Any]
    after: dict[str, Any]
    actor: str
    timestamp: str = field(default_factory=lambda: utc_now())


@dataclass
class AgentSession:
    business_question: str
    data_source: DataSourceProfile
    session_id: str
    workspace_type: str = "analytics"
    agent_state: AgentState = AgentState.IDLE
    active_stage: Stage = Stage.ANALYSIS_DESIGN
    artifacts: dict[Stage, StageArtifact] = field(default_factory=dict)
    operations: list[OperationRecord] = field(default_factory=list)
    revisions: list[RevisionRecord] = field(default_factory=list)
    extracted_params: dict[str, Any] = field(default_factory=dict)

    def require_confirmed(self, stage: Stage) -> StageArtifact:
        artifact = self.artifacts.get(stage)
        if artifact is None:
            raise ValueError(f"Stage {stage.value} has not been drafted.")
        if artifact.status != StageStatus.BA_CONFIRMED:
            raise ValueError(f"Stage {stage.value} must be BA confirmed first.")
        return artifact

    def add_operation(
        self,
        operation_type: str,
        actor: str,
        stage: Stage | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.operations.append(
            OperationRecord(
                operation_type=operation_type,
                actor=actor,
                stage=stage,
                details=details or {},
            )
        )


def utc_now() -> str:
    return datetime.now(UTC).isoformat()
