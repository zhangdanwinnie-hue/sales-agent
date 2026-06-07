from __future__ import annotations

from dataclasses import dataclass

from .models import Stage


@dataclass(frozen=True)
class WorkflowStageConfig:
    id: Stage
    name: str
    description: str
    order: int
    require_approval: bool = True


@dataclass(frozen=True)
class WorkflowConfig:
    workspace_type: str
    name: str
    stages: list[WorkflowStageConfig]

    def first_stage(self) -> Stage:
        return sorted(self.stages, key=lambda item: item.order)[0].id

    def next_stage(self, current: Stage) -> Stage:
        ordered = sorted(self.stages, key=lambda item: item.order)
        for index, stage in enumerate(ordered):
            if stage.id == current:
                if index + 1 >= len(ordered):
                    return Stage.DONE
                return ordered[index + 1].id
        raise ValueError(f"Stage {current.value} is not configured for {self.workspace_type}.")

    def stage_config(self, stage: Stage) -> WorkflowStageConfig:
        for config in self.stages:
            if config.id == stage:
                return config
        raise ValueError(f"Stage {stage.value} is not configured for {self.workspace_type}.")


ANALYTICS_WORKFLOW = WorkflowConfig(
    workspace_type="analytics",
    name="数据分析工作流",
    stages=[
        WorkflowStageConfig(
            id=Stage.ANALYSIS_DESIGN,
            name="分析设计",
            description="分析思路拆解、澄清问题、业务假设、指标树和字段需求",
            order=1,
            require_approval=True,
        ),
        WorkflowStageConfig(
            id=Stage.DATA_PLAN,
            name="数据分析计划",
            description="数据源计划、SQL/取数计划、校验计划和初步洞察卡片",
            order=2,
            require_approval=True,
        ),
        WorkflowStageConfig(
            id=Stage.INSIGHT_REVIEW,
            name="洞察确认",
            description="BA 确认数据结果、洞察卡片和待确认事项",
            order=3,
            require_approval=True,
        ),
        WorkflowStageConfig(
            id=Stage.REPORT_PLAN,
            name="报告产出",
            description="结论摘要、PPT 故事线、Excel tabs、BRD 结构",
            order=4,
            require_approval=True,
        ),
        WorkflowStageConfig(
            id=Stage.FINAL_REVIEW,
            name="发布前审核",
            description="最终质量、安全和口径一致性检查",
            order=5,
            require_approval=True,
        ),
    ],
)


WORKFLOW_CONFIGS = {
    "analytics": ANALYTICS_WORKFLOW,
}


def get_workflow_config(workspace_type: str = "analytics") -> WorkflowConfig:
    return WORKFLOW_CONFIGS.get(workspace_type, ANALYTICS_WORKFLOW)
