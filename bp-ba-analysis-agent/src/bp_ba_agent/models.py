"""Core data contracts for the BP BA analysis workflow."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any
from uuid import uuid4


@dataclass(frozen=True)
class MetricDefinition:
    name: str
    business_meaning: str
    formula: str
    dimensions: list[str]
    source_tables: list[str]
    validation_sources: list[str]


@dataclass(frozen=True)
class DataSourcePlan:
    name: str
    source_type: str
    read_only: bool
    purpose: str
    owner: str


@dataclass(frozen=True)
class SqlPlan:
    metric: str
    purpose: str
    sql: str
    required_filters: list[str]
    review_notes: list[str]


@dataclass(frozen=True)
class ValidationCheck:
    name: str
    check_type: str
    method: str
    pass_criteria: str
    human_review_required: bool = True


@dataclass(frozen=True)
class DeliverableDraft:
    executive_summary: list[str]
    excel_tabs: list[str]
    ppt_storyline: list[str]
    brd_sections: list[str]


@dataclass(frozen=True)
class AnalysisMethodPlan:
    key: str
    title: str
    purpose: str
    required_semantic_objects: list[str]
    outputs: list[str]
    confirmation_focus: list[str]


@dataclass(frozen=True)
class SemanticMatch:
    business_object: str
    matched_metrics: list[str]
    matched_dimensions: list[str]
    available_fields: list[str]
    missing_fields: list[str]
    status: str


@dataclass(frozen=True)
class DataAvailabilityItem:
    requirement: str
    status: str
    available_fields: list[str]
    missing_fields: list[str]
    note: str


@dataclass
class AnalysisCase:
    business_question: str
    scenario: str | None = None
    analysis_purpose: str | None = None
    target_object: str | None = None
    time_range: str | None = None
    dimensions: list[str] = field(default_factory=list)
    deliverable_type: str = "management_report"
    audience: str = "Sales BP / BI stakeholders"
    case_id: str = field(default_factory=lambda: f"case-{uuid4().hex[:8]}")
    created_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    clarification_questions: list[str] = field(default_factory=list)
    question_types: list[str] = field(default_factory=list)
    hypotheses: list[str] = field(default_factory=list)
    metric_tree: list[MetricDefinition] = field(default_factory=list)
    selected_methods: list[AnalysisMethodPlan] = field(default_factory=list)
    semantic_matches: list[SemanticMatch] = field(default_factory=list)
    data_availability: list[DataAvailabilityItem] = field(default_factory=list)
    data_sources: list[DataSourcePlan] = field(default_factory=list)
    sql_plan: list[SqlPlan] = field(default_factory=list)
    validation_plan: list[ValidationCheck] = field(default_factory=list)
    deliverable: DeliverableDraft | None = None
    human_review_checkpoints: list[str] = field(default_factory=list)
    knowledge_tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
