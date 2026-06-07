from __future__ import annotations

from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .agent_runtime import AgentOrchestrator, event_line
from .mock_agent import (
    catalog,
    clarification_questions,
    create_task,
    data_analysis,
    data_assets,
    message,
    recommend_dimensions,
    refresh_artifacts,
    semantic_state,
    write_report,
)
from .models import CEAReport, ChatRequest, ChatResponse, Hypothesis, ReportExportResponse, TaskInput, TaskListResponse
from .store import TaskStore


ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
EXPORT_DIR = ROOT / "exports"
FRONTEND_DIST = ROOT / "frontend" / "dist"
STORE = TaskStore(DATA_DIR / "tasks.json")
ORCHESTRATOR = AgentOrchestrator(STORE)

EXPORT_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="BP BA Agent V2 Workbench", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/exports", StaticFiles(directory=EXPORT_DIR), name="exports")


class DesignUpdate(BaseModel):
    selected_dimensions: list[str] = []
    hypotheses: list[Hypothesis] = []


class ConfirmPayload(BaseModel):
    confirmed_by: str = "BA User"
    feedback: str = ""


class ReportUpdate(BaseModel):
    report: CEAReport


class ReportExport(BaseModel):
    format: Literal["html", "markdown", "json"] = "html"
    report: CEAReport | None = None


@app.get("/api/health")
def health() -> dict[str, str | bool]:
    return {"ok": True, "service": "bp-ba-agent-v2", "version": "0.1.0"}


@app.get("/api/tasks", response_model=TaskListResponse)
def list_tasks() -> TaskListResponse:
    tasks = STORE.all()
    stats = {
        "total": len(tasks),
        "draft": sum(1 for task in tasks if task.status == "draft"),
        "confirmed": sum(1 for task in tasks if task.status != "draft"),
        "report_ready": sum(1 for task in tasks if task.status == "report_ready"),
    }
    return TaskListResponse(tasks=tasks, stats=stats)


@app.post("/api/tasks")
def create(payload: TaskInput) -> dict:
    task = create_task(payload)
    STORE.upsert(task)
    return {"task": task, "artifacts": task.artifacts, "messages": task.messages}


@app.post("/api/chat/start", response_model=ChatResponse)
def start_chat(payload: ChatRequest) -> ChatResponse:
    return ORCHESTRATOR.start(payload)


@app.get("/api/tasks/{task_id}")
def get_task(task_id: str) -> dict:
    return {"task": _get(task_id)}


@app.post("/api/tasks/{task_id}/chat", response_model=ChatResponse)
def task_chat(task_id: str, payload: ChatRequest) -> ChatResponse:
    try:
        return ORCHESTRATOR.chat(task_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Task not found") from exc


@app.post("/api/tasks/{task_id}/chat/stream")
def task_chat_stream(task_id: str, payload: ChatRequest) -> StreamingResponse:
    try:
        response = ORCHESTRATOR.chat(task_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Task not found") from exc

    def events():
        for event in ORCHESTRATOR.stream_events(response):
            yield event_line(event)

    return StreamingResponse(events(), media_type="text/event-stream")


@app.post("/api/tasks/{task_id}/input/update")
def update_input(task_id: str, payload: TaskInput) -> dict:
    task = _get(task_id)
    task.task_name = payload.task_name
    task.business_question = payload.business_question
    task.analysis_purpose = payload.analysis_purpose
    task.time_range = payload.time_range
    task.comparison_period = payload.comparison_period
    task.data_source = payload.data_source
    task.recommended_dimensions = recommend_dimensions(payload.business_question, payload.analysis_purpose)
    task.messages.append(message("ba", "已保存任务输入草稿。", "task_creation"))
    task.messages.append(message("agent", "我已刷新 AI 追问和推荐维度，确认后会进入分析工作台。", "task_creation"))
    STORE.upsert(refresh_artifacts(task))
    return {"task": task, "followups": clarification_questions(task), "artifacts": task.artifacts}


@app.post("/api/tasks/{task_id}/input/confirm")
def confirm_input(task_id: str, payload: TaskInput) -> dict:
    update_input(task_id, payload)
    task = _get(task_id)
    task.status = "input_confirmed"
    task.current_page = "analysis_design"
    task.messages.append(message("agent", "任务输入已确认。请在分析工作台选择维度并完善假设池。", "analysis_design"))
    STORE.upsert(refresh_artifacts(task))
    return {"task": task, "artifacts": task.artifacts}


@app.post("/api/tasks/{task_id}/analysis-design/update")
def update_design(task_id: str, payload: DesignUpdate) -> dict:
    task = _get(task_id)
    task.selected_dimensions = payload.selected_dimensions
    task.hypotheses = payload.hypotheses
    task.messages.append(message("ba", "已更新分析维度和假设池。", "analysis_design"))
    STORE.upsert(refresh_artifacts(task))
    return {"task": task, "artifacts": task.artifacts}


@app.post("/api/tasks/{task_id}/analysis-design/confirm")
def confirm_design(task_id: str, payload: ConfirmPayload) -> dict:
    task = _get(task_id)
    if not task.selected_dimensions:
        task.selected_dimensions = task.recommended_dimensions
    task.status = "design_confirmed"
    task.current_page = "data_insight"
    task.messages.append(message("agent", f"分析思路已确认，开始生成数据洞察。{payload.feedback}", "data_insight"))
    STORE.upsert(refresh_artifacts(task))
    return {"task": task, "analysis": data_analysis(task), "artifacts": task.artifacts}


@app.get("/api/tasks/{task_id}/data-analysis")
def get_data_analysis(task_id: str) -> dict:
    task = _get(task_id)
    analysis = data_analysis(task)
    return analysis.model_dump(mode="json")


@app.post("/api/tasks/{task_id}/data-insight/confirm")
def confirm_insight(task_id: str, payload: ConfirmPayload) -> dict:
    task = _get(task_id)
    task.status = "insight_confirmed"
    task.current_page = "report_generation"
    task.messages.append(message("agent", f"数据洞察已确认，报告已按结论-证据-行动结构生成。{payload.feedback}", "report_generation"))
    STORE.upsert(refresh_artifacts(task))
    return {"task": task, "artifacts": task.artifacts}


@app.post("/api/tasks/{task_id}/report/update")
def update_report(task_id: str, payload: ReportUpdate) -> dict:
    task = _get(task_id)
    task.report = payload.report
    task.status = "report_ready"
    task.current_page = "report_generation"
    task.messages.append(message("ba", "已编辑报告内容。", "report_generation"))
    STORE.upsert(refresh_artifacts(task))
    return {"task": task, "artifacts": task.artifacts}


@app.post("/api/tasks/{task_id}/report/export", response_model=ReportExportResponse)
def export_report(task_id: str, payload: ReportExport) -> ReportExportResponse:
    task = _get(task_id)
    if payload.report:
        task.report = payload.report
    task.status = "report_ready"
    STORE.upsert(refresh_artifacts(task))
    file_name, url = write_report(task, EXPORT_DIR, payload.format)
    return ReportExportResponse(file_name=file_name, download_url=url, format=payload.format)


@app.get("/api/artifacts/{task_id}")
def artifacts(task_id: str) -> dict:
    task = _get(task_id)
    return {"artifacts": task.artifacts, "messages": task.messages}


@app.get("/api/catalog")
def get_catalog() -> dict:
    return catalog()


@app.get("/api/semantic-state")
def get_semantic_state() -> dict:
    return semantic_state()


@app.get("/api/data-assets")
def get_data_assets() -> dict:
    return data_assets()


def _get(task_id: str):
    try:
        return STORE.get(task_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Task not found") from exc


if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
else:
    @app.get("/")
    def missing_frontend() -> HTMLResponse:
        return HTMLResponse(
            "<!doctype html><meta charset='utf-8'><title>BP BA Agent V2</title>"
            "<body><h1>BP BA Agent V2 backend is running.</h1>"
            "<p>Build frontend with npm run build before serving the full workbench.</p></body>"
        )
