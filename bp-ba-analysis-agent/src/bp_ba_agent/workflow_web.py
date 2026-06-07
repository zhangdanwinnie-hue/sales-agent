"""Small web UI for the flexible, gated BP BA analysis workflow."""

from __future__ import annotations

import argparse
import html
import json
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

from .analysis_topics import list_analysis_topics
from .method_library import list_analysis_methods, list_question_types
from .multi_agent_workflow import DESIGN_STEP, INSIGHT_STEP, REPORT_STEP
from .multi_agent_workflow import MultiAgentWorkflow, workflow_contracts
from .semantic_layer import list_business_objects, list_semantic_dimensions, list_semantic_metrics


WORKFLOW = MultiAgentWorkflow()
PROJECT_ROOT = Path(__file__).resolve().parents[2]
REAL_DATA_REPORT_PATH = PROJECT_ROOT / "outputs" / "real_data_demo" / "real_data_demo_report.json"
WORKFLOW_STATE_DIR = PROJECT_ROOT / "outputs" / "workflow_state"
TASKS_STATE_PATH = WORKFLOW_STATE_DIR / "tasks.json"
EXPORT_DIR = PROJECT_ROOT / "outputs" / "exported_reports"

TASK_CREATION_PAGE = "task_creation"
ANALYSIS_DESIGN_PAGE = "analysis_design"
DATA_INSIGHT_PAGE = "data_insight"
REPORT_GENERATION_PAGE = "report_generation"

DEMO_AVAILABLE_FIELDS = [
    "register_rcid",
    "register_create_time",
    "leads_id",
    "leads_create_time",
    "oppty_id",
    "oppty_create_time",
    "visit_id",
    "visit_arrival_time",
    "td_id",
    "td_start_time",
    "order_id",
    "order_first_confirm_time",
    "order_cancel_flag",
    "region_route",
    "register_cyd_city_name_zh",
    "leads_dealer_id",
    "leads_channel_name",
    "leads_campaign_id",
    "leads_model_code_ssc",
    "order_model_code_ssc",
]

DEFAULT_TASKS: dict[str, dict[str, Any]] = {
    "task-q1-sales": {
        "task_id": "task-q1-sales",
        "name": "Q1 Sales Performance Analysis",
        "created_at": "2026/5/20",
        "updated_at": "2026/5/20",
        "status": "in_progress",
        "current_page": ANALYSIS_DESIGN_PAGE,
        "current_agent": DESIGN_STEP,
        "input_confirmed": True,
        "business_question": "为什么 4 月订单下降？请判断是渠道结构、区域经销商承接，还是转化效率的问题。",
        "analysis_purpose": "定位订单下降的主要贡献来源和可行动改进点。",
        "target_object": "全国订单表现",
        "time_range": "2026-04 vs 2026-03",
        "comparison_period": "2026-03",
        "dimensions": ["月份", "大区", "城市", "经销商", "渠道", "车型"],
        "deliverable_type": "management_report",
        "audience": "Sales BP / Management",
        "data_source": "demo_csv",
        "session_id": None,
    },
    "task-q1-dealer": {
        "task_id": "task-q1-dealer",
        "name": "Q1 Dealer Performance Review",
        "created_at": "2026/4/15",
        "updated_at": "2026/4/15",
        "status": "completed",
        "current_page": REPORT_GENERATION_PAGE,
        "current_agent": REPORT_STEP,
        "input_confirmed": True,
        "business_question": "哪些经销商承接异常？同区域同车型下，哪些经销商到店或成交显著偏低？",
        "analysis_purpose": "识别承接弱的经销商并形成复盘清单。",
        "target_object": "经销商网络",
        "time_range": "2026 Q1",
        "comparison_period": "2025 Q4",
        "dimensions": ["经销商", "大区", "城市", "车型", "经销商状态"],
        "deliverable_type": "business_review",
        "audience": "Sales BP / Dealer Operation",
        "data_source": "demo_csv",
        "session_id": None,
    },
    "task-q2-campaign": {
        "task_id": "task-q2-campaign",
        "name": "Q2 Marketing Campaign Analysis",
        "created_at": "2026/5/10",
        "updated_at": "2026/5/10",
        "status": "draft",
        "current_page": TASK_CREATION_PAGE,
        "current_agent": None,
        "input_confirmed": False,
        "business_question": "活动投放是否带来了高质量线索？哪些 campaign 带来高质量线索和订单？",
        "analysis_purpose": "评估活动线索质量和后链路转化。",
        "target_object": "Campaign 活动",
        "time_range": "2026 Q2",
        "comparison_period": "2026 Q1",
        "dimensions": ["Campaign", "活动类型", "渠道", "区域", "车型"],
        "deliverable_type": "management_report",
        "audience": "Sales BP / Marketing",
        "data_source": "demo_csv",
        "session_id": None,
    },
    "task-lead-conversion": {
        "task_id": "task-lead-conversion",
        "name": "Lead Conversion Rate Analysis",
        "created_at": "2026/5/18",
        "updated_at": "2026/5/18",
        "status": "pending",
        "current_page": TASK_CREATION_PAGE,
        "current_agent": None,
        "input_confirmed": False,
        "business_question": "近期客流下降明显，想分析是哪些渠道在下降，以及新客获取和老客回店的表现变化。",
        "analysis_purpose": "拆解客流下降原因，判断渠道、客户类型和时间因素的贡献。",
        "target_object": "客流与线索转化",
        "time_range": "2026 Q1",
        "comparison_period": "2025 Q4",
        "dimensions": ["渠道维度", "客户维度", "时间维度", "区域维度"],
        "deliverable_type": "management_report",
        "audience": "Sales BP / Management",
        "data_source": "demo_csv",
        "session_id": None,
    },
}

TASK_STORE: dict[str, dict[str, Any]] = {}
TASKS_LOADED = False


class WorkflowRequestHandler(BaseHTTPRequestHandler):
    server_version = "BPBAWorkflowDemo/0.3"

    def do_GET(self) -> None:  # noqa: N802 - stdlib API
        path = urlparse(self.path).path
        try:
            if path == "/":
                self._send_html(_index_html())
                return
            if path == "/health":
                self._send_json({"ok": True})
                return
            if path == "/api/contracts":
                self._send_json({"contracts": [contract.to_dict() for contract in workflow_contracts()]})
                return
            if path == "/api/catalog":
                self._send_json(_catalog_payload())
                return
            if path == "/api/analysis-frameworks":
                self._send_json({"frameworks": _analysis_frameworks()})
                return
            if path == "/api/tasks":
                self._send_json(_tasks_payload())
                return
            if path.startswith("/api/tasks/") and path.endswith("/data-analysis"):
                task = _get_task_or_none(path.split("/")[-2])
                if not task:
                    self._send_json({"error": "task_not_found"}, HTTPStatus.NOT_FOUND)
                    return
                self._send_json(_data_analysis_payload(task))
                return
            if path.startswith("/api/tasks/"):
                task = _get_task_or_none(path.rsplit("/", 1)[-1])
                if not task:
                    self._send_json({"error": "task_not_found"}, HTTPStatus.NOT_FOUND)
                    return
                self._send_json({"task": _task_detail(task)})
                return
            if path == "/api/real-data-report":
                self._send_json(_real_data_report())
                return
            if path == "/api/semantic-state":
                self._send_json(_semantic_state())
                return
            if path.startswith("/exports/"):
                self._send_export(path.rsplit("/", 1)[-1])
                return
            self._send_json({"error": "not_found"}, HTTPStatus.NOT_FOUND)
        except Exception as exc:  # pragma: no cover - manual UI path
            self._send_json({"error": type(exc).__name__, "message": str(exc)}, HTTPStatus.BAD_REQUEST)

    def do_POST(self) -> None:  # noqa: N802 - stdlib API
        try:
            path = urlparse(self.path).path
            payload = self._read_json()
            if path == "/api/tasks":
                self._send_json({"task": _task_detail(_create_task(payload))})
                return
            if path == "/api/start":
                session = _start_session_from_payload(payload)
                task = _upsert_task_from_session(payload, session.to_dict())
                _save_task_store()
                response = session.to_dict()
                response["task"] = _task_summary(task)
                self._send_json(response)
                return
            if path == "/api/confirm":
                session = WORKFLOW.confirm_step(
                    str(payload["session_id"]),
                    step_id=str(payload["step_id"]),
                    confirmed_by=str(payload.get("confirmed_by") or "BA"),
                    feedback=str(payload.get("feedback") or ""),
                    confirmed=bool(payload.get("confirmed", True)),
                )
                _sync_task_from_session(session.to_dict())
                _save_task_store()
                self._send_json(session.to_dict())
                return
            if path.startswith("/api/tasks/"):
                self._handle_task_post(path, payload)
                return
            self._send_json({"error": "not_found"}, HTTPStatus.NOT_FOUND)
        except Exception as exc:  # pragma: no cover - manual UI path
            self._send_json({"error": type(exc).__name__, "message": str(exc)}, HTTPStatus.BAD_REQUEST)

    def _handle_task_post(self, path: str, payload: dict[str, Any]) -> None:
        parts = [part for part in path.split("/") if part]
        if len(parts) < 3:
            self._send_json({"error": "not_found"}, HTTPStatus.NOT_FOUND)
            return
        task_id = parts[2]
        action = "/".join(parts[3:])
        task = _get_task_or_none(task_id)
        if not task:
            self._send_json({"error": "task_not_found"}, HTTPStatus.NOT_FOUND)
            return
        if action == "open":
            session = _open_task(task)
            self._send_json({"task": _task_detail(task), "session": session})
            return
        if action == "input/update":
            _update_task_input(task, payload, confirmed=False)
            _save_task_store()
            self._send_json({"task": _task_detail(task)})
            return
        if action == "input/confirm":
            _update_task_input(task, payload, confirmed=True)
            session = _start_or_restart_design(task)
            _save_task_store()
            self._send_json({"task": _task_detail(task), "session": session})
            return
        if action == "analysis-design/update":
            task["analysis_design_edits"] = payload
            task["selected_framework_id"] = payload.get("selected_framework_id", task.get("selected_framework_id"))
            if "dimensions" in payload:
                task["dimensions"] = _dimensions(payload.get("dimensions", task.get("dimensions", [])))
            if "hypotheses" in payload:
                task["hypotheses"] = payload["hypotheses"]
                task["hypotheses_manual"] = bool(payload.get("hypotheses_manual", True))
            task["updated_at"] = _today()
            _save_task_store()
            self._send_json({"task": _task_detail(task)})
            return
        if action == "analysis-design/confirm":
            session = _confirm_design(task, payload)
            _save_task_store()
            self._send_json({"task": _task_detail(task), "session": session})
            return
        if action == "hypotheses/update":
            task["hypotheses"] = payload.get("hypotheses", [])
            task["hypotheses_manual"] = True
            task["updated_at"] = _today()
            _save_task_store()
            self._send_json({"task": _task_detail(task)})
            return
        if action == "data-insight/confirm":
            session = _confirm_insight(task, payload)
            _save_task_store()
            self._send_json({"task": _task_detail(task), "session": session})
            return
        if action == "report/update":
            task["report_edits"] = payload.get("report_edits", payload)
            task["updated_at"] = _today()
            _save_task_store()
            self._send_json({"task": _task_detail(task)})
            return
        if action == "report/export":
            result = _export_report(task, payload)
            _save_task_store()
            self._send_json(result)
            return
        if action == "duplicate":
            clone = _duplicate_task(task)
            _save_task_store()
            self._send_json({"task": _task_detail(clone)})
            return
        if action == "delete":
            _ensure_task_store()
            TASK_STORE.pop(task_id, None)
            _save_task_store()
            self._send_json({"ok": True})
            return
        self._send_json({"error": "not_found"}, HTTPStatus.NOT_FOUND)

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8")
        return json.loads(raw)

    def _send_html(self, content: str, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = content.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_export(self, file_name: str) -> None:
        safe_name = Path(file_name).name
        path = EXPORT_DIR / safe_name
        if not path.exists() or path.suffix.lower() != ".html":
            self._send_json({"error": "export_not_found"}, HTTPStatus.NOT_FOUND)
            return
        self._send_html(path.read_text(encoding="utf-8"))


def run_workflow_web_demo(host: str = "127.0.0.1", port: int = 8083) -> None:
    _ensure_task_store()
    server = ThreadingHTTPServer((host, port), WorkflowRequestHandler)
    print(f"BP BA flexible workflow demo: http://{host}:{port}")
    server.serve_forever()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the BP BA flexible workflow web demo.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8083)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    run_workflow_web_demo(args.host, args.port)


def _today() -> str:
    now = datetime.now()
    return f"{now.year}/{now.month}/{now.day}"


def _ensure_task_store() -> None:
    global TASKS_LOADED, TASK_STORE
    if TASKS_LOADED:
        return
    if TASKS_STATE_PATH.exists():
        with TASKS_STATE_PATH.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        rows = data.get("tasks", []) if isinstance(data, dict) else data
        TASK_STORE = {str(task["task_id"]): _normalize_task(task) for task in rows}
    else:
        TASK_STORE = {task_id: _normalize_task(dict(task)) for task_id, task in DEFAULT_TASKS.items()}
    TASKS_LOADED = True


def _save_task_store() -> None:
    _ensure_task_store()
    WORKFLOW_STATE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "saved_at": datetime.now().isoformat(timespec="seconds"),
        "tasks": list(TASK_STORE.values()),
    }
    TASKS_STATE_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _normalize_task(task: dict[str, Any]) -> dict[str, Any]:
    task.setdefault("task_id", f"task-{uuid4().hex[:8]}")
    task.setdefault("name", task.get("task_name") or "新建分析任务")
    task.setdefault("created_at", _today())
    task.setdefault("updated_at", task["created_at"])
    task.setdefault("status", "draft")
    task.setdefault("current_page", _page_from_agent(task.get("current_agent"), str(task.get("status", "draft"))))
    task.setdefault("current_agent", None if task["current_page"] == TASK_CREATION_PAGE else task.get("current_agent"))
    task.setdefault("input_confirmed", task["current_page"] != TASK_CREATION_PAGE)
    task.setdefault("business_question", "")
    task.setdefault("analysis_purpose", "")
    task.setdefault("target_object", "")
    task.setdefault("time_range", "")
    task.setdefault("comparison_period", "")
    task.setdefault("dimensions", [])
    task["dimensions"] = _dimensions(task.get("dimensions"))
    task.setdefault("deliverable_type", "management_report")
    task.setdefault("audience", "Sales BP / Management")
    task.setdefault("data_source", "demo_csv")
    task.setdefault("selected_framework_id", "")
    task.setdefault("hypotheses", [])
    task.setdefault("hypotheses_manual", False)
    task.setdefault("ba_confirmations", {})
    task.setdefault("report_edits", {})
    task.setdefault("session_snapshot", None)
    task.setdefault("export_path", "")
    return task


def _get_task_or_none(task_id: str) -> dict[str, Any] | None:
    _ensure_task_store()
    return TASK_STORE.get(task_id)


def _optional(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _dimensions(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [item.strip() for item in value.replace("，", ",").split(",") if item.strip()]
    return []


def _catalog_payload() -> dict[str, Any]:
    return {
        "question_types": list_question_types(),
        "analysis_methods": list_analysis_methods(),
        "business_objects": list_business_objects(),
        "semantic_metrics": list_semantic_metrics(),
        "semantic_dimensions": list_semantic_dimensions(),
        "analysis_topics": list_analysis_topics(),
        "demo_available_fields": DEMO_AVAILABLE_FIELDS,
    }


def _analysis_frameworks() -> list[dict[str, Any]]:
    topics = list_analysis_topics()
    base = [
        ("traffic_decline", "客流下降分析框架", "用于拆解自然到店、邀约到店、线上预约到店、新客和老客回店变化。"),
        ("sales_funnel", "销售漏斗转化框架", "用于定位 register、lead、oppty、visit、td、order 链路掉点。"),
        ("channel_quality", "渠道质量分析框架", "用于比较渠道获客量、留资质量、到店率和订单转化。"),
        ("dealer_performance", "经销商表现框架", "用于在区域、城市、车型可比前提下识别承接异常经销商。"),
        ("campaign_review", "营销活动复盘框架", "用于评估 campaign 从投放、线索、客流到订单的贡献。"),
    ]
    frameworks: list[dict[str, Any]] = []
    for index, (key, name, desc) in enumerate(base):
        topic = topics[index % len(topics)] if topics else {}
        frameworks.append(
            {
                "id": key,
                "name": name,
                "description": desc,
                "dimensions": topic.get("default_dimensions", ["时间", "区域", "渠道", "车型"]),
                "metric_templates": topic.get("core_metrics", ["到店量", "订单量", "转化率"]),
                "data_requirements": {
                    "required_fields": topic.get("required_fields", [])[:8],
                    "optional_fields": topic.get("optional_fields", [])[:6],
                    "extra_data": ["竞品/市场容量", "节假日/活动日历"] if index == 0 else ["目标值", "预算或线索成本"],
                },
                "analysis_path": [
                    "确认业务问题和时间口径",
                    "拆解核心指标及上期对比",
                    "按维度识别贡献和异常",
                    "验证关键假设",
                    "输出行动建议和复盘材料",
                ],
            }
        )
    return frameworks


def _tasks_payload() -> dict[str, Any]:
    _ensure_task_store()
    tasks = [_task_summary(task) for task in TASK_STORE.values()]
    status_order = {"in_progress": 0, "pending": 1, "draft": 2, "completed": 3}
    tasks.sort(key=lambda item: (status_order.get(str(item["status"]), 9), str(item["created_at"])))
    counts = {
        "total": len(tasks),
        "in_progress": sum(1 for task in tasks if task["status"] == "in_progress"),
        "completed": sum(1 for task in tasks if task["status"] == "completed"),
        "pending": sum(1 for task in tasks if task["status"] == "pending"),
        "draft": sum(1 for task in tasks if task["status"] == "draft"),
    }
    return {"tasks": tasks, "stats": counts}


def _task_summary(task: dict[str, Any]) -> dict[str, Any]:
    current_page = str(task.get("current_page") or _page_from_agent(task.get("current_agent"), str(task.get("status"))))
    return {
        "task_id": task["task_id"],
        "name": task["name"],
        "created_at": task["created_at"],
        "updated_at": task.get("updated_at", task["created_at"]),
        "status": task["status"],
        "status_text": _task_status_text(str(task["status"])),
        "node": _page_label(current_page),
        "step": _page_step(current_page),
        "current_page": current_page,
        "current_agent": task.get("current_agent"),
        "session_id": task.get("session_id"),
        "business_question": task.get("business_question", ""),
        "data_source": task.get("data_source", "demo_csv"),
        "input_confirmed": bool(task.get("input_confirmed")),
    }


def _task_detail(task: dict[str, Any]) -> dict[str, Any]:
    detail = _task_summary(task)
    detail.update(
        {
            "analysis_purpose": task.get("analysis_purpose", ""),
            "target_object": task.get("target_object", ""),
            "time_range": task.get("time_range", ""),
            "comparison_period": task.get("comparison_period", ""),
            "dimensions": task.get("dimensions", []),
            "deliverable_type": task.get("deliverable_type", "management_report"),
            "audience": task.get("audience", "Sales BP / Management"),
            "selected_framework_id": task.get("selected_framework_id", ""),
            "hypotheses": task.get("hypotheses", []),
            "hypotheses_manual": bool(task.get("hypotheses_manual")),
            "ba_confirmations": task.get("ba_confirmations", {}),
            "analysis_design_edits": task.get("analysis_design_edits", {}),
            "report_edits": task.get("report_edits", {}),
            "export_path": task.get("export_path", ""),
        }
    )
    return detail


def _task_status_text(status: str) -> str:
    return {"draft": "草稿", "pending": "待确认", "in_progress": "进行中", "completed": "已完成"}.get(status, status)


def _page_from_agent(agent_id: Any, status: str) -> str:
    if status == "draft" or not agent_id:
        return TASK_CREATION_PAGE
    if agent_id == INSIGHT_STEP:
        return DATA_INSIGHT_PAGE
    if agent_id == REPORT_STEP or status == "completed":
        return REPORT_GENERATION_PAGE
    return ANALYSIS_DESIGN_PAGE


def _page_label(page: str) -> str:
    return {
        TASK_CREATION_PAGE: "创建任务",
        ANALYSIS_DESIGN_PAGE: "分析思路",
        DATA_INSIGHT_PAGE: "数据分析",
        REPORT_GENERATION_PAGE: "报告生成",
    }.get(page, page)


def _page_step(page: str) -> int:
    return {TASK_CREATION_PAGE: 1, ANALYSIS_DESIGN_PAGE: 2, DATA_INSIGHT_PAGE: 3, REPORT_GENERATION_PAGE: 4}.get(page, 1)


def _create_task(payload: dict[str, Any]) -> dict[str, Any]:
    _ensure_task_store()
    task_id = str(payload.get("task_id") or f"task-{uuid4().hex[:8]}")
    task = _normalize_task(
        {
            "task_id": task_id,
            "name": str(payload.get("task_name") or payload.get("name") or "新建分析任务"),
            "created_at": _today(),
            "updated_at": _today(),
            "status": "draft",
            "current_page": TASK_CREATION_PAGE,
            "current_agent": None,
            "input_confirmed": False,
        }
    )
    _update_task_input(task, payload, confirmed=False)
    TASK_STORE[task_id] = task
    _save_task_store()
    return task


def _duplicate_task(task: dict[str, Any]) -> dict[str, Any]:
    clone = json.loads(json.dumps(task, ensure_ascii=False))
    clone["task_id"] = f"task-{uuid4().hex[:8]}"
    clone["name"] = f"{task.get('name', '分析任务')} Copy"
    clone["created_at"] = _today()
    clone["updated_at"] = _today()
    clone["status"] = "draft"
    clone["current_page"] = TASK_CREATION_PAGE
    clone["current_agent"] = None
    clone["input_confirmed"] = False
    clone["session_id"] = None
    clone["session_snapshot"] = None
    clone["export_path"] = ""
    TASK_STORE[clone["task_id"]] = clone
    return clone


def _update_task_input(task: dict[str, Any], payload: dict[str, Any], *, confirmed: bool) -> None:
    name = str(payload.get("task_name") or payload.get("name") or task.get("name") or "").strip()
    question = str(payload.get("business_question") or task.get("business_question") or "").strip()
    if not name and question:
        name = question[:28] + ("..." if len(question) > 28 else "")
    task.update(
        {
            "name": name or "新建分析任务",
            "business_question": question,
            "analysis_purpose": payload.get("analysis_purpose", task.get("analysis_purpose", "")),
            "target_object": payload.get("target_object", task.get("target_object", "")),
            "time_range": payload.get("time_range", task.get("time_range", "")),
            "comparison_period": payload.get("comparison_period", task.get("comparison_period", "")),
            "dimensions": _dimensions(payload.get("dimensions", task.get("dimensions", []))),
            "deliverable_type": payload.get("deliverable_type", task.get("deliverable_type", "management_report")),
            "audience": payload.get("audience", task.get("audience", "Sales BP / Management")),
            "data_source": payload.get("data_source", task.get("data_source", "demo_csv")),
            "updated_at": _today(),
        }
    )
    if confirmed:
        task["input_confirmed"] = True
        task["input_dirty"] = False
        task["hypotheses"] = []
        task["hypotheses_manual"] = False
    elif task.get("input_confirmed"):
        task["input_dirty"] = True


def _task_payload(task: dict[str, Any]) -> dict[str, Any]:
    return {
        "business_question": task.get("business_question", ""),
        "scenario": task.get("scenario"),
        "analysis_purpose": task.get("analysis_purpose"),
        "target_object": task.get("target_object"),
        "time_range": task.get("time_range"),
        "dimensions": task.get("dimensions", []),
        "deliverable_type": task.get("deliverable_type", "management_report"),
        "audience": task.get("audience", "Sales BP / Management"),
        "available_fields": DEMO_AVAILABLE_FIELDS,
    }


def _start_session_from_payload(payload: dict[str, Any]):
    available_fields = DEMO_AVAILABLE_FIELDS if bool(payload.get("use_demo_fields", True)) else None
    return WORKFLOW.start(
        business_question=str(payload.get("business_question") or "").strip(),
        scenario=_optional(payload.get("scenario")),
        analysis_purpose=_optional(payload.get("analysis_purpose")),
        target_object=_optional(payload.get("target_object")),
        time_range=_optional(payload.get("time_range")),
        dimensions=_dimensions(payload.get("dimensions")),
        deliverable_type=str(payload.get("deliverable_type") or "management_report"),
        audience=str(payload.get("audience") or "Sales BP / Management"),
        available_fields=available_fields,
    )


def _start_or_restart_design(task: dict[str, Any]) -> dict[str, Any]:
    session = WORKFLOW.start(**_task_payload(task))
    task["session_id"] = session.session_id
    task["session_snapshot"] = session.to_dict()
    task["current_page"] = ANALYSIS_DESIGN_PAGE
    task["current_agent"] = DESIGN_STEP
    task["status"] = "in_progress"
    task["updated_at"] = _today()
    output = session.to_dict()["results"][DESIGN_STEP]["output_payload"]
    task["hypotheses"] = _topic_hypotheses(task, output)
    task["hypotheses_manual"] = False
    return session.to_dict()


def _ensure_session(task: dict[str, Any]) -> dict[str, Any] | None:
    if not task.get("input_confirmed") and task.get("current_page") == TASK_CREATION_PAGE:
        return None
    session_id = task.get("session_id")
    if session_id:
        try:
            return WORKFLOW.get_session(str(session_id)).to_dict()
        except KeyError:
            pass
    session = WORKFLOW.start(**_task_payload(task))
    task["session_id"] = session.session_id
    target_page = str(task.get("current_page") or ANALYSIS_DESIGN_PAGE)
    if target_page in {DATA_INSIGHT_PAGE, REPORT_GENERATION_PAGE} or task.get("ba_confirmations", {}).get(DESIGN_STEP):
        session = WORKFLOW.confirm_step(
            session.session_id,
            step_id=DESIGN_STEP,
            confirmed_by="BA User",
            feedback="服务重启后根据任务状态恢复：分析思路已确认。",
            confirmed=True,
        )
    if target_page == REPORT_GENERATION_PAGE or task.get("ba_confirmations", {}).get(INSIGHT_STEP):
        session = WORKFLOW.confirm_step(
            session.session_id,
            step_id=INSIGHT_STEP,
            confirmed_by="BA User",
            feedback="服务重启后根据任务状态恢复：数据分析已确认。",
            confirmed=True,
        )
    if task.get("status") == "completed" and task.get("ba_confirmations", {}).get(REPORT_STEP):
        session = WORKFLOW.confirm_step(
            session.session_id,
            step_id=REPORT_STEP,
            confirmed_by="BA User",
            feedback="服务重启后根据任务状态恢复：报告已确认。",
            confirmed=True,
        )
    task["session_snapshot"] = session.to_dict()
    return session.to_dict()


def _open_task(task: dict[str, Any]) -> dict[str, Any] | None:
    session = _ensure_session(task)
    if session:
        task["current_agent"] = None if session["current_step"] == "completed" else session["current_step"]
        task["status"] = "completed" if session["status"] == "completed" else "in_progress"
    return session


def _confirm_design(task: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    session = _ensure_session(task) or _start_or_restart_design(task)
    if not session.get("confirmations", {}).get(DESIGN_STEP):
        session_obj = WORKFLOW.confirm_step(
            session["session_id"],
            step_id=DESIGN_STEP,
            confirmed_by=str(payload.get("confirmed_by") or "BA User"),
            feedback=str(payload.get("feedback") or "确认分析思路配置。"),
            confirmed=bool(payload.get("confirmed", True)),
        )
        session = session_obj.to_dict()
    if bool(payload.get("confirmed", True)):
        task["current_page"] = DATA_INSIGHT_PAGE
        task["current_agent"] = INSIGHT_STEP
        task["status"] = "in_progress"
    task.setdefault("ba_confirmations", {})[DESIGN_STEP] = {
        "confirmed_by": str(payload.get("confirmed_by") or "BA User"),
        "feedback": str(payload.get("feedback") or "确认分析思路配置。"),
        "confirmed": bool(payload.get("confirmed", True)),
        "confirmed_at": datetime.now().isoformat(timespec="seconds"),
    }
    task["session_snapshot"] = session
    task["updated_at"] = _today()
    return session


def _confirm_insight(task: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    session = _ensure_session(task) or _start_or_restart_design(task)
    if not session.get("confirmations", {}).get(DESIGN_STEP):
        session = _confirm_design(task, {"confirmed_by": "BA User", "feedback": "自动补齐：分析思路已确认。"})
    if not session.get("confirmations", {}).get(INSIGHT_STEP):
        session_obj = WORKFLOW.confirm_step(
            session["session_id"],
            step_id=INSIGHT_STEP,
            confirmed_by=str(payload.get("confirmed_by") or "BA User"),
            feedback=str(payload.get("feedback") or "确认数据分析结果和假设验证。"),
            confirmed=bool(payload.get("confirmed", True)),
        )
        session = session_obj.to_dict()
    if bool(payload.get("confirmed", True)):
        task["current_page"] = REPORT_GENERATION_PAGE
        task["current_agent"] = REPORT_STEP
        task["status"] = "in_progress"
    task.setdefault("ba_confirmations", {})[INSIGHT_STEP] = {
        "confirmed_by": str(payload.get("confirmed_by") or "BA User"),
        "feedback": str(payload.get("feedback") or "确认数据分析结果和假设验证。"),
        "confirmed": bool(payload.get("confirmed", True)),
        "confirmed_at": datetime.now().isoformat(timespec="seconds"),
    }
    task["session_snapshot"] = session
    task["updated_at"] = _today()
    return session


def _upsert_task_from_session(payload: dict[str, Any], session: dict[str, Any]) -> dict[str, Any]:
    task_id = str(payload.get("task_id") or f"task-{uuid4().hex[:8]}")
    task = TASK_STORE.get(task_id) or _normalize_task({"task_id": task_id, "created_at": _today()})
    _update_task_input(task, payload, confirmed=True)
    task.update(
        {
            "status": "in_progress",
            "current_page": ANALYSIS_DESIGN_PAGE,
            "current_agent": session["current_step"],
            "session_id": session["session_id"],
            "session_snapshot": session,
        }
    )
    TASK_STORE[task_id] = task
    return task


def _sync_task_from_session(session: dict[str, Any]) -> None:
    for task in TASK_STORE.values():
        if task.get("session_id") == session.get("session_id"):
            current = session.get("current_step")
            task["current_agent"] = None if current == "completed" else current
            task["current_page"] = _page_from_agent(task["current_agent"], "completed" if session.get("status") == "completed" else "in_progress")
            task["status"] = "completed" if session.get("status") == "completed" else "in_progress"
            task["session_snapshot"] = session
            task["updated_at"] = _today()
            return


def _task_topic(task: dict[str, Any]) -> str:
    text = f"{task.get('business_question', '')} {task.get('analysis_purpose', '')}".lower()
    if any(key in text for key in ["客流", "到店", "回店", "自然", "邀约", "预约"]):
        return "traffic"
    if any(key in text for key in ["订单", "成交", "转化", "漏斗"]):
        return "order"
    if any(key in text for key in ["渠道", "线索", "投放", "归因"]):
        return "channel"
    if any(key in text for key in ["经销商", "门店", "区域", "城市"]):
        return "dealer"
    if any(key in text for key in ["活动", "campaign", "营销"]):
        return "campaign"
    return "generic"


def _make_hypothesis(index: int, title: str, metrics: list[str], *, core: bool = False) -> dict[str, Any]:
    return {
        "id": f"hyp-{index + 1}",
        "title": title,
        "type": "核心假设" if core else "次要假设",
        "status": "待验证",
        "metrics": metrics,
    }


def _topic_hypotheses(task: dict[str, Any], design_output: dict[str, Any]) -> list[dict[str, Any]]:
    topic = _task_topic(task)
    templates: dict[str, list[tuple[str, list[str], bool]]] = {
        "traffic": [
            ("主要原因是自然获客能力下降", ["自然到店客流", "自然到店占比"], True),
            ("线上渠道获客效率下降是重要因素", ["线上预约客流", "线上占比"], False),
            ("邀约策略效果减弱", ["邀约到店客流", "邀约成功率"], False),
            ("新客获取能力下降是核心问题", ["新客客流", "新客占比"], True),
            ("季节性/节假日因素影响", ["工作日客流", "周末客流"], False),
        ],
        "order": [
            ("订单下降主要来自上游线索或客流不足", ["线索量", "客流总量", "订单量"], True),
            ("到店到订单转化率下降造成成交缺口", ["到店到订单转化率", "成交率"], True),
            ("部分渠道带来高量低质线索", ["渠道线索量", "渠道订单转化率"], False),
            ("区域/经销商承接能力差异拖累整体", ["经销商客流", "经销商成交率"], False),
            ("车型结构变化影响订单转化", ["车型客流", "车型订单量"], False),
        ],
        "channel": [
            ("投放效率下降来自低质渠道占比提升", ["渠道线索量", "渠道订单转化率"], True),
            ("自然/付费渠道结构变化影响整体获客成本", ["自然到店客流", "线上预约客流"], False),
            ("重点渠道的留资到到店链路存在掉点", ["留资量", "客流总量"], True),
            ("渠道归因口径差异影响贡献判断", ["渠道占比", "订单量"], False),
        ],
        "dealer": [
            ("少数经销商承接下滑拖累整体表现", ["经销商客流", "经销商成交率"], True),
            ("区域市场容量或竞品动作造成局部异常", ["区域客流", "订单量"], False),
            ("高意向客户分配与跟进效率不足", ["高意向客户占比", "成交量"], True),
            ("门店活动执行差异影响到店和成交", ["客流总量", "成交量"], False),
        ],
        "campaign": [
            ("活动带来的新增线索质量不足", ["线索量", "留资转化率"], True),
            ("活动客流集中但成交承接不足", ["客流总量", "成交量"], True),
            ("活动覆盖人群与目标车型不匹配", ["车型客流", "车型订单量"], False),
            ("活动周期或触达节奏造成转化滞后", ["工作日客流", "周末客流"], False),
        ],
    }
    if topic in templates:
        return [_make_hypothesis(i, title, metrics, core=core) for i, (title, metrics, core) in enumerate(templates[topic])]
    return _default_hypotheses(design_output)


def _default_hypotheses(design_output: dict[str, Any]) -> list[dict[str, Any]]:
    raw = design_output.get("hypotheses") or [
        "核心指标变化来自渠道结构或转化效率变化。",
        "区域、经销商或车型维度存在集中贡献。",
        "数据口径或链路字段缺失可能影响结论强度。",
    ]
    statuses = ["待验证", "待验证", "待验证", "待验证", "待验证"]
    return [
        {
            "id": f"hyp-{index + 1}",
            "title": str(item),
            "type": "核心假设" if index == 0 else "次要假设",
            "status": statuses[index % len(statuses)],
            "metrics": [],
        }
        for index, item in enumerate(raw[:5])
    ]


def _data_analysis_payload(task: dict[str, Any]) -> dict[str, Any]:
    session = _ensure_session(task)
    insight = (session or {}).get("results", {}).get(INSIGHT_STEP, {}).get("output_payload", {})
    design = (session or {}).get("results", {}).get(DESIGN_STEP, {}).get("output_payload", {})
    report = _real_data_report()
    metrics = _metric_rows(task, design, report)
    hypotheses = (task.get("hypotheses") or _topic_hypotheses(task, design)) if task.get("hypotheses_manual") else _topic_hypotheses(task, design)
    return {
        "task": _task_detail(task),
        "tabs": ["overview", "dimension_table", "hypothesis_validation", "sql_logic"],
        "metrics": metrics,
        "dimension_rows": _dimension_rows(metrics),
        "hypotheses": _validated_hypotheses(hypotheses, metrics),
        "sql_logic": _sql_logic_rows(insight, metrics),
        "insight_cards": insight.get("insight_cards", []),
        "data_quality": {
            "coverage": "99.75%",
            "completeness": "98.5%",
            "exceptions": 3,
        },
    }


def _metric_rows(task: dict[str, Any], design: dict[str, Any], report: dict[str, Any]) -> list[dict[str, Any]]:
    stages = report.get("stage_counts", {}) if report.get("available") else {}
    rates = report.get("conversion_rates", {}) if report.get("available") else {}
    rows = [
        ("渠道维度", "客流总量", stages.get("visit", 3856), 4234, "visit_id", "COUNT(DISTINCT visit_id)"),
        ("渠道维度", "自然到店客流", 1234, 1567, "visit_type", 'COUNT(DISTINCT visit_id) WHERE visit_type = "自然到店"'),
        ("渠道维度", "邀约到店客流", 2120, 1989, "invite_consultant_id", 'COUNT(DISTINCT visit_id) WHERE invite_flag = "Y"'),
        ("渠道维度", "线上预约客流", 502, 678, "source_channel", 'COUNT(DISTINCT visit_id) WHERE source_channel = "线上预约"'),
        ("渠道维度", "自然到店占比", 32.0, 37.0, "visit_type", '自然到店客流 / 客流总量'),
        ("客户维度", "新客客流", 1456, 1789, "first_visit_flag", 'COUNT(DISTINCT customer_id) WHERE first_visit_flag = "Y"'),
        ("客户维度", "回店客流", 2400, 2445, "first_visit_flag", 'COUNT(DISTINCT customer_id) WHERE first_visit_flag = "N"'),
        ("客户维度", "高意向客户占比", 28.5, 30.2, "intent_level", '高意向客户数 / 客户数'),
        ("时间维度", "工作日客流", 2456, 2689, "visit_arrival_time", 'COUNT(DISTINCT visit_id) WHERE day_type = "工作日"'),
        ("时间维度", "周末客流", 1400, 1545, "visit_arrival_time", 'COUNT(DISTINCT visit_id) WHERE day_type = "周末"'),
        ("品牌维度", "BMW 客流", 2456, 2698, "brand", 'COUNT(DISTINCT visit_id) WHERE brand = "BMW"'),
        ("品牌维度", "MINI 客流", 892, 956, "brand", 'COUNT(DISTINCT visit_id) WHERE brand = "MINI"'),
        ("品牌维度", "MOTO 客流", 508, 580, "brand", 'COUNT(DISTINCT visit_id) WHERE brand = "MOTO"'),
        ("漏斗维度", "订单量", stages.get("order", 456), 512, "order_id", "COUNT(DISTINCT order_id)"),
        ("漏斗维度", "留资量", 2634, 2896, "leads_id", "COUNT(DISTINCT leads_id)"),
        ("漏斗维度", "留资转化率", 68.3, 68.4, "leads_id/visit_id", "COUNT(DISTINCT visit_id)/COUNT(DISTINCT leads_id)"),
        ("漏斗维度", "成交量", 456, 512, "order_id", "COUNT(DISTINCT order_id) WHERE order_cancel_flag = 0"),
        ("漏斗维度", "订单/线索转化率", round((rates.get("order_per_leads", 0.0683) or 0.0683) * 100, 1), 68.4, "leads_id/order_id", "COUNT(DISTINCT order_id)/COUNT(DISTINCT leads_id)"),
    ]
    wanted = set(task.get("dimensions") or [])
    output: list[dict[str, Any]] = []
    for dim, name, current, previous, field, formula in rows:
        change = _change(current, previous)
        output.append(
            {
                "dimension": dim,
                "name": name,
                "current": current,
                "previous": previous,
                "change": change,
                "trend": "up" if change > 0 else "down" if change < 0 else "flat",
                "field": field,
                "formula": formula,
                "selected": not wanted or dim in wanted or name in wanted,
            }
        )
    if design.get("metric_tree"):
        for metric in design.get("metric_tree", [])[:4]:
            if not any(row["name"] == metric.get("name") for row in output):
                output.append(
                    {
                        "dimension": "Agent 指标",
                        "name": metric.get("name", "指标"),
                        "current": "待取数",
                        "previous": "待取数",
                        "change": 0,
                        "trend": "flat",
                        "field": ", ".join(metric.get("source_tables", [])),
                        "formula": metric.get("formula", "待 BA 确认"),
                        "selected": True,
                    }
                )
    return output


def _change(current: Any, previous: Any) -> float:
    try:
        prev = float(previous)
        cur = float(current)
    except (TypeError, ValueError):
        return 0.0
    if prev == 0:
        return 0.0
    return round((cur - prev) / prev * 100, 1)


def _dimension_rows(metrics: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return metrics


def _validated_hypotheses(hypotheses: list[dict[str, Any]], metrics: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for index, hyp in enumerate(hypotheses):
        used: set[str] = set()
        related = []
        for name in hyp.get("metrics", []):
            found = next((row for row in metrics if row["name"] not in used and row["name"] == name), None)
            if not found:
                short_name = str(name).replace("占比", "")
                found = next((row for row in metrics if row["name"] not in used and (short_name in row["name"] or row["name"] in str(name))), None)
            if found:
                used.add(found["name"])
                related.append(found)
        if not related:
            related = [row for row in metrics if row["name"] not in used][index : index + 3] or metrics[:2]
        status = hyp.get("status")
        if not status or status == "待验证":
            status = "已验证" if any(row.get("trend") == "down" for row in related) else "待验证"
        result.append({**hyp, "status": status, "related_metrics": related})
    return result


def _sql_logic_rows(insight: dict[str, Any], metrics: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sql_plan = insight.get("sql_plan") or []
    rows = []
    for metric in metrics[:12]:
        rows.append(
            {
                "metric": metric["name"],
                "fields": metric["field"],
                "formula": metric["formula"],
                "sql": f"SELECT {metric['formula']} AS value FROM sales_wide_table WHERE period BETWEEN :start AND :end",
                "business_explanation": _sql_business_explanation(metric),
            }
        )
    for item in sql_plan[:4]:
        rows.append(
            {
                "metric": item.get("metric", "Agent SQL"),
                "fields": ", ".join(item.get("source_tables", [])),
                "formula": item.get("purpose", ""),
                "sql": item.get("sql", ""),
                "business_explanation": item.get("purpose", "用于复核 Agent 自动生成的数据口径和取数字段。"),
            }
        )
    return rows


def _sql_business_explanation(metric: dict[str, Any]) -> str:
    name = str(metric.get("name", "该指标"))
    dimension = str(metric.get("dimension", "业务维度"))
    formula = str(metric.get("formula", ""))
    if "占比" in name or "转化率" in name or "/" in formula:
        return f"按当前时间范围计算{name}，用于判断{dimension}下结构或效率是否发生变化。BA 需要确认分母、去重键和过滤条件。"
    if "客流" in name or "到店" in name:
        return f"统计当前周期内的去重到店/客流记录，用于判断{dimension}是否是核心变化来源。"
    if "订单" in name or "成交" in name:
        return f"统计当前周期内的去重订单或成交结果，用于评估最终业务结果和上游链路影响。"
    return f"按当前任务口径计算{name}，用于支撑假设验证和报告证据链。"


def _export_report(task: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    session = _ensure_session(task)
    if not session or REPORT_STEP not in session.get("results", {}):
        session = _confirm_insight(task, {"confirmed_by": "BA User", "feedback": "导出前自动生成报告内容。"})
    edits = task.get("report_edits") or payload.get("report_edits") or {}
    report_output = session.get("results", {}).get(REPORT_STEP, {}).get("output_payload", {})
    sections = _report_sections(task, report_output, edits)
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    file_name = f"{task['task_id']}.html"
    export_path = EXPORT_DIR / file_name
    export_path.write_text(_report_html(task, sections), encoding="utf-8")
    task["export_path"] = str(export_path)
    task["updated_at"] = _today()
    return {"ok": True, "file_name": file_name, "download_url": f"/exports/{file_name}"}


def _report_sections(task: dict[str, Any], report_output: dict[str, Any], edits: dict[str, Any]) -> dict[str, str]:
    summary = "\n".join(report_output.get("executive_summary") or ["本分析围绕业务问题完成思路设计、数据洞察和报告生成。"])
    findings = "\n".join(report_output.get("ppt_storyline") or report_output.get("brd_sections") or [])
    return {
        "executive_summary": edits.get("executive_summary") or summary,
        "background": edits.get("background") or f"业务问题：{task.get('business_question', '')}\n时间范围：{task.get('time_range', '')}",
        "data_scope": edits.get("data_scope") or f"数据源：{task.get('data_source', 'demo_csv')}；维度：{' / '.join(task.get('dimensions', []))}",
        "key_findings": edits.get("key_findings") or findings,
        "recommendations": edits.get("recommendations") or "建议 BA 结合区域、渠道、经销商和车型下钻结果，确认短期跟进动作和中长期机制优化。",
        "conclusion": edits.get("conclusion") or edits.get("key_findings") or findings,
        "evidence": edits.get("evidence") or edits.get("data_scope") or f"数据源：{task.get('data_source', 'demo_csv')}；维度：{' / '.join(task.get('dimensions', []))}",
        "action": edits.get("action") or edits.get("recommendations") or "建议 BA 结合区域、渠道、经销商和车型下钻结果，确认短期跟进动作和中长期机制优化。",
    }


def _report_html(task: dict[str, Any], sections: dict[str, str]) -> str:
    title = html.escape(str(task.get("name") or "Sales BP 分析报告"))
    body = "\n".join(
        f"<section><h2>{html.escape(label)}</h2><pre>{html.escape(value)}</pre></section>"
        for label, value in [
            ("结论", sections.get("conclusion") or sections["key_findings"]),
            ("证据", sections.get("evidence") or sections["data_scope"]),
            ("行动", sections.get("action") or sections["recommendations"]),
            ("背景与口径", f"{sections['background']}\n{sections['data_scope']}"),
        ]
    )
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><title>{title}</title>
<style>body{{font-family:Segoe UI,Microsoft YaHei,Arial,sans-serif;margin:40px;background:#f7f8fb;color:#0f172a}}main{{max-width:960px;margin:auto;background:white;border:1px solid #e2e8f0;border-radius:12px;padding:32px}}h1{{font-size:28px}}section{{border-top:1px solid #e2e8f0;padding-top:20px;margin-top:20px}}pre{{white-space:pre-wrap;font:inherit;line-height:1.7}}</style>
</head><body><main><h1>{title}</h1><p>由 Sales BP 三 Agent 分析流程导出，导出时间：{datetime.now().isoformat(timespec="seconds")}</p>{body}</main></body></html>"""


def _real_data_report() -> dict[str, Any]:
    if not REAL_DATA_REPORT_PATH.exists():
        return {"available": False, "path": str(REAL_DATA_REPORT_PATH)}
    with REAL_DATA_REPORT_PATH.open("r", encoding="utf-8") as handle:
        report = json.load(handle)
    return {
        "available": True,
        "path": str(REAL_DATA_REPORT_PATH),
        "total_rows": report.get("total_rows"),
        "column_count": report.get("column_count"),
        "files": report.get("files", []),
        "stage_counts": report.get("stage_counts", {}),
        "conversion_rates": report.get("conversion_rates", {}),
        "top_dimensions": report.get("top_dimensions", {}),
        "data_quality": report.get("data_quality", {}),
        "executive_summary": report.get("executive_summary", []),
        "privacy_notes": report.get("privacy_notes", []),
    }


def _semantic_state() -> dict[str, Any]:
    return {
        "ok": True,
        "source": "bp_ba_workflow_service",
        "semantic_config": {
            "ontology_config": _local_ontology_config(),
            "field_aliases": _local_field_aliases(),
        },
    }


def _local_ontology_config() -> dict[str, Any]:
    entities = [
        {
            "key": item["key"],
            "title": item["title"],
            "description": item["description"],
            "grain": "业务对象",
            "id_fields": item.get("id_candidates", []),
            "time_fields": item.get("time_candidates", []),
            "metrics": item.get("metric_names", []),
            "dimensions": item.get("dimension_names", []),
        }
        for item in list_business_objects()
    ]
    metrics = [
        {
            "key": item["key"],
            "title": item["title"],
            "entity": item["business_object"],
            "business_definition": item["definition"],
            "formula": item["default_aggregation"],
            "physical_fields": item.get("physical_field_candidates", []),
            "owner": "Sales BP BA",
        }
        for item in list_semantic_metrics()
    ]
    return {
        "entities": entities,
        "events": [
            {"key": "register_created", "title": "注册创建", "entity": "lead", "description": "用户注册或留资入口形成。", "time_field": "register_create_time", "flag_field": "register_rcid"},
            {"key": "lead_created", "title": "线索创建", "entity": "lead", "description": "销售线索进入跟进链路。", "time_field": "leads_create_time", "flag_field": "leads_id"},
            {"key": "opportunity_created", "title": "机会创建", "entity": "opportunity", "description": "线索转为销售机会。", "time_field": "oppty_create_time", "flag_field": "oppty_id"},
            {"key": "visit_arrived", "title": "到店发生", "entity": "visit", "description": "客户到店或形成有效客流。", "time_field": "visit_arrival_time", "flag_field": "visit_id"},
            {"key": "test_drive_started", "title": "试驾执行", "entity": "test_drive", "description": "客户完成试驾。", "time_field": "td_start_time", "flag_field": "td_id"},
            {"key": "order_created", "title": "订单创建", "entity": "order", "description": "客户创建有效订单。", "time_field": "order_create_time", "flag_field": "order_id"},
        ],
        "relationships": [
            {"from": "customer", "to": "lead", "type": "creates", "join_keys": ["customer_id", "leads_mobile_phone_number"], "description": "客户产生注册或线索。"},
            {"from": "lead", "to": "opportunity", "type": "converts_to", "join_keys": ["leads_id", "leads_opportunity_id"], "description": "线索转化为销售机会。"},
            {"from": "lead", "to": "visit", "type": "drives", "join_keys": ["leads_id", "visit_id"], "description": "线索驱动到店或客流。"},
            {"from": "visit", "to": "test_drive", "type": "leads_to", "join_keys": ["visit_id", "td_id"], "description": "到店后发生试驾。"},
            {"from": "test_drive", "to": "order", "type": "leads_to", "join_keys": ["td_id", "order_id"], "description": "试驾后形成订单。"},
            {"from": "dealer", "to": "lead", "type": "owns", "join_keys": ["leads_dealer_id", "dealer_id"], "description": "经销商承接线索。"},
        ],
        "metrics": metrics,
        "policies": {
            "default_permission_rule": "按 Sales BP 区域、经销商和项目角色授权，默认只展示聚合结果。",
            "pii_fields": ["customer_id", "leads_mobile_phone_number"],
            "audit_required": True,
        },
    }


def _local_field_aliases() -> dict[str, list[str]]:
    return {
        "register_id": ["register_rcid"],
        "register_time": ["register_create_time"],
        "lead_id": ["leads_id"],
        "lead_time": ["leads_create_time"],
        "opportunity_id": ["oppty_id", "leads_opportunity_id"],
        "opportunity_time": ["oppty_create_time"],
        "visit_id": ["visit_id"],
        "visit_time": ["visit_arrival_time", "visit_create_time"],
        "test_drive_id": ["td_id"],
        "test_drive_time": ["td_start_time"],
        "order_id": ["order_id", "order_so_no"],
        "order_time": ["order_create_time"],
        "region": ["region_route", "register_cyd_region_name_zh"],
        "city": ["register_cyd_city_name_zh", "city_name_zh"],
        "dealer_id": ["leads_dealer_id", "visit_dealer_id", "order_dealer_id", "dealer_id"],
        "channel": ["leads_channel_name", "register_first_channel_name"],
        "campaign_id": ["leads_campaign_id", "register_campaign_id"],
        "model": ["register_model", "leads_model_code_ssc", "order_model_code_ssc"],
    }


def _index_html() -> str:
    return r"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Sales BP 分析平台</title>
  <style>
    :root{--bg:#f5f7fb;--panel:#fff;--ink:#0f172a;--muted:#64748b;--line:#e5e7eb;--line2:#dbe3ef;--blue:#2563eb;--blue2:#eaf2ff;--green:#16a34a;--green2:#eafaf0;--amber:#b45309;--amber2:#fff7e6;--red:#dc2626;--red2:#fff1f1;--purple:#7c3aed;--purple2:#f5efff;--shadow:0 10px 28px rgba(15,23,42,.06)}
    *{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font-family:"Segoe UI","Microsoft YaHei",Arial,sans-serif}.app{display:grid;grid-template-columns:248px 1fr;min-height:100vh}.side{background:#fff;border-right:1px solid var(--line);padding:20px 16px;position:sticky;top:0;height:100vh;overflow:auto}.brand{display:flex;gap:10px;align-items:center;margin-bottom:22px}.logo{width:38px;height:38px;border-radius:9px;background:linear-gradient(145deg,#2563eb,#1d4ed8);color:white;display:grid;place-items:center;font-weight:900}.brand h1{font-size:18px;margin:0}.brand p{font-size:12px;color:var(--muted);margin:2px 0 0}.nav-title{font-size:12px;color:var(--muted);font-weight:800;margin:18px 0 8px}.nav{display:grid;gap:6px}.nav button{border:0;background:transparent;text-align:left;padding:10px 12px;border-radius:8px;color:#334155;cursor:pointer;font-weight:700}.nav button.active{background:var(--blue2);color:var(--blue)}.main{padding:22px 28px 48px}.top{display:flex;justify-content:space-between;align-items:center;margin-bottom:18px}.top h2{margin:0;font-size:24px}.user{color:var(--muted);font-size:14px}.panel{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:20px;margin-bottom:18px;box-shadow:var(--shadow)}.subtle-panel{background:#fff;border:1px solid var(--line);border-radius:10px;padding:16px}.page{display:none}.page.active{display:block}.hero-row{display:flex;justify-content:space-between;gap:16px;align-items:center}.hero-title{display:flex;gap:14px;align-items:center}.icon{width:44px;height:44px;border-radius:10px;background:var(--blue2);color:var(--blue);display:grid;place-items:center;font-weight:900}.muted{color:var(--muted)}.btn{border:0;border-radius:8px;padding:10px 14px;font-weight:800;cursor:pointer;background:var(--blue);color:#fff}.btn.secondary{background:#f1f5f9;color:#334155}.btn.green{background:var(--green)}.btn.warn{background:var(--amber)}.btn.ghost{background:#fff;color:var(--blue);border:1px solid #bfdbfe}.btn:disabled{opacity:.45;cursor:not-allowed}.toolbar{display:flex;gap:10px;align-items:center;flex-wrap:wrap}.searchbar{display:grid;grid-template-columns:1fr 170px;gap:12px}.input,textarea,select{width:100%;border:1px solid var(--line2);border-radius:8px;background:#fff;padding:11px 12px;font:inherit}textarea{min-height:96px;resize:vertical}label{display:block;font-size:13px;font-weight:800;margin:14px 0 7px}.grid2{display:grid;grid-template-columns:1fr 1fr;gap:18px}.grid3{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}.grid4{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}.card{border:1px solid var(--line);border-radius:10px;background:#fff;padding:14px}.card h3{margin:0 0 6px;font-size:16px}.pill{display:inline-flex;align-items:center;border-radius:999px;padding:4px 8px;font-size:12px;font-weight:800;background:#f1f5f9;color:#475569}.pill.blue{background:var(--blue2);color:var(--blue)}.pill.green{background:var(--green2);color:var(--green)}.pill.amber{background:var(--amber2);color:var(--amber)}.pill.red{background:var(--red2);color:var(--red)}.task-shell{display:grid;grid-template-columns:1fr auto;gap:16px;align-items:center}.task-shell h3{font-size:20px;margin:0}.task-facts{display:flex;gap:8px;flex-wrap:wrap;margin-top:8px}.stepper{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;align-items:center}.step{display:flex;gap:10px;align-items:center;border:1px solid var(--line);border-radius:12px;padding:12px;background:#fff}.step .dot{width:34px;height:34px;border-radius:50%;display:grid;place-items:center;background:#f1f5f9;color:#94a3b8;font-weight:900}.step.done .dot{background:var(--green);color:white}.step.active{border-color:#93c5fd;background:#eff6ff}.step.active .dot{background:var(--blue);color:white}.task-row{display:grid;grid-template-columns:1fr auto;gap:16px;align-items:center;border-top:1px solid var(--line);padding:18px 0}.task-row:first-child{border-top:0}.task-title{display:flex;gap:10px;align-items:center;margin-bottom:8px}.task-title strong{font-size:18px}.task-meta{display:flex;gap:12px;color:var(--muted);font-size:13px;flex-wrap:wrap}.mini-flow{display:flex;gap:7px;align-items:center;margin-top:10px}.mini-flow span{width:26px;height:26px;border-radius:50%;display:grid;place-items:center;background:#f1f5f9;color:#94a3b8;font-size:12px;font-weight:900}.mini-flow span.done{background:var(--blue2);color:var(--blue)}.tabs{display:flex;gap:8px;border-bottom:1px solid var(--line);margin-bottom:16px}.tabs button{border:0;background:transparent;padding:11px 12px;cursor:pointer;font-weight:800;color:#64748b}.tabs button.active{color:var(--blue);border-bottom:2px solid var(--blue)}.confirm{background:#f0fdf4;border-color:#bbf7d0}.confirm.purple{background:#faf5ff;border-color:#d8b4fe}.confirm.blue{background:#eff6ff;border-color:#bfdbfe}.table{width:100%;border-collapse:collapse;border:1px solid var(--line);border-radius:8px;overflow:hidden}.table th,.table td{text-align:left;border-bottom:1px solid var(--line);padding:10px;font-size:13px}.table th{background:#f8fafc;color:#475569}.metric-card{border:1px solid var(--line);border-radius:10px;padding:14px;background:#fff}.metric-card.down{border-color:#fecaca;background:#fff7f7}.metric-card.up{border-color:#bbf7d0;background:#f7fff9}.metric-card.flat{background:#f8fafc}.metric-card strong{display:block;font-size:22px;margin:6px 0}.metric-card small{color:var(--muted)}.data-layout{display:grid;grid-template-columns:1fr 320px;gap:16px}.report-layout{display:grid;grid-template-columns:minmax(0,1fr) 300px;gap:16px}.report-grid{display:grid;grid-template-columns:1fr 1fr;gap:14px}.code{background:#111827;color:#d1fae5;border-radius:8px;padding:12px;white-space:pre-wrap;overflow:auto}.empty{border:1px dashed var(--line);border-radius:10px;padding:24px;text-align:center;color:var(--muted);background:#fff}.hint{background:#eff6ff;border:1px solid #bfdbfe;border-radius:10px;padding:14px;color:#1d4ed8}.warning-box{background:#fff7ed;border:1px solid #fed7aa;border-radius:10px;padding:12px;color:#9a3412}.data-source-card,.dimension-card{border:1px solid var(--line);border-radius:10px;background:#fff;padding:13px;cursor:pointer}.data-source-card.active,.dimension-card.active{border-color:#60a5fa;background:#eff6ff;box-shadow:0 0 0 2px rgba(37,99,235,.08)}.ai-followups{margin-top:12px;border:1px solid #bfdbfe;background:#f8fbff;border-radius:10px;padding:14px}.ai-followups h3,.dimension-review h3{margin:0 0 8px}.followup-row{display:grid;grid-template-columns:22px 1fr;gap:8px;margin:8px 0;color:#1e3a8a}.dimension-review{border:1px solid var(--line);border-radius:10px;background:#fff;padding:14px;margin:16px 0}.hyp-card{display:grid;grid-template-columns:1fr auto;gap:12px;align-items:center;border:1px solid var(--line);border-radius:10px;padding:14px;background:#fff;margin-top:10px}.hyp-card.core{border-color:#93c5fd;background:#f8fbff}.hyp-card input{border:0;border-bottom:1px solid transparent;font-weight:800;font-size:15px}.hyp-card input:focus{border-bottom-color:var(--blue);outline:0}.hyp-actions{display:grid;grid-template-columns:150px 130px 90px;gap:8px}.north-tree{display:grid;gap:10px}.tree-node{border:1px solid var(--line);border-radius:10px;background:#fff;padding:12px}.tree-node.root{border-color:#93c5fd;background:#eff6ff}.tree-children{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-top:10px}.evidence-card{border:1px solid var(--line);border-radius:10px;background:#fff;padding:14px;margin-bottom:12px}.evidence-meta{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin:12px 0}.business-explain{margin:0 14px 12px;border-left:4px solid #93c5fd;background:#eff6ff;border-radius:6px;padding:10px;color:#1e3a8a}.report-section{border:1px solid var(--line);border-radius:10px;background:#fff;padding:14px;margin-bottom:12px}.report-section textarea{min-height:120px}.ai-section-title{display:flex;gap:8px;align-items:center;font-size:16px;font-weight:900;margin:18px 0 10px}.ai-objectives{border:1px solid var(--line);border-radius:10px;background:#fff;padding:14px}.ai-objectives div{display:grid;grid-template-columns:28px 1fr;gap:10px;align-items:center;margin:8px 0}.ai-objectives b{width:28px;height:28px;border-radius:50%;display:grid;place-items:center;background:var(--purple2);color:var(--purple)}.factor-tree{border:1px solid var(--line);border-radius:10px;background:#fff;padding:14px}.factor-group{margin:10px 0 16px}.factor-group h4{margin:0 0 8px;color:var(--purple);font-size:16px}.factor-item{display:grid;grid-template-columns:18px 160px 1fr 240px;gap:10px;align-items:center;padding:10px 12px;border-radius:8px}.factor-item:hover,.factor-item.focus{background:#f8fafc}.factor-item .arrow{color:#94a3b8}.factor-item small{color:var(--muted)}.path-card{border:1px solid var(--line);border-radius:10px;background:#fff;padding:14px}.path-card h4{margin:0 0 8px}.path-card ul{margin:8px 0 0;padding-left:18px;color:var(--muted)}.sql-item{border:1px solid var(--line);border-radius:10px;background:#fff;margin-bottom:10px;overflow:hidden}.sql-item summary{cursor:pointer;padding:14px;font-weight:900}.sql-item .sql-meta{display:flex;gap:8px;flex-wrap:wrap;padding:0 14px 10px}.chartbar{display:grid;gap:9px}.chartbar div{display:grid;grid-template-columns:110px 1fr 64px;gap:8px;align-items:center}.bar{height:12px;background:#e2e8f0;border-radius:99px;overflow:hidden}.bar span{display:block;height:100%;background:var(--blue);border-radius:99px}.preview-doc{background:#fff;border:1px solid var(--line);border-radius:10px;padding:18px;line-height:1.7}.preview-doc h3{margin-top:0}.config-section{margin-bottom:18px}.config-section h3{margin-bottom:10px}@media(max-width:1100px){.data-layout,.report-layout,.report-grid{grid-template-columns:1fr}.factor-item{grid-template-columns:18px 1fr}.factor-item small,.factor-item .pill{grid-column:2}.tree-children,.evidence-meta{grid-template-columns:1fr}}@media(max-width:1000px){.app{grid-template-columns:1fr}.side{position:relative;height:auto}.grid2,.grid3,.grid4,.searchbar,.stepper,.task-shell{grid-template-columns:1fr}.main{padding:16px}.task-row{grid-template-columns:1fr}.hyp-actions{grid-template-columns:1fr}}
  </style>
</head>
<body>
<div class="app">
  <aside class="side">
    <div class="brand"><div class="logo">BP</div><div><h1>Sales BP 分析平台</h1><p>智能数据分析与报告生成</p></div></div>
    <div class="nav-title">工作流程</div>
    <div class="nav">
      <button data-page="workbench" class="active">任务管理</button>
      <button data-page="task_creation">创建分析任务</button>
      <button data-page="analysis_design">分析思路设计</button>
      <button data-page="data_insight">数据分析与洞察</button>
      <button data-page="report_generation">报告生成</button>
    </div>
    <div class="nav-title">基础能力与配置</div>
    <div class="nav">
      <button data-page="catalog">能力目录</button>
      <button data-page="ontology">Ontology 语义维护</button>
      <button data-page="realdata">数据资产预览</button>
    </div>
  </aside>
  <main class="main">
    <div class="top"><h2 id="pageTitle">任务管理</h2><div class="user">当前用户：<b>BA User</b> · <span id="health">checking</span></div></div>
    <section id="stepPanel" class="panel" style="display:none"></section>

    <section id="workbench" class="page active">
      <div class="panel hero-row">
        <div class="hero-title"><div class="icon">□</div><div><h2>任务管理</h2><p class="muted">查看和管理所有分析任务。每个任务内包含创建输入、分析思路、数据洞察和报告生成四个页面节点。</p></div></div>
        <button class="btn" onclick="newTask()">+ 新建任务</button>
      </div>
      <div class="panel searchbar"><input id="taskSearch" class="input" placeholder="搜索任务名称或业务问题..." oninput="renderTasks()"><select id="taskFilter" onchange="renderTasks()"><option value="all">全部状态</option><option value="in_progress">进行中</option><option value="completed">已完成</option><option value="pending">待确认</option><option value="draft">草稿</option></select></div>
      <div class="panel"><div id="taskList"></div></div>
      <div class="grid4" id="taskStats"></div>
    </section>

    <section id="task_creation" class="page">
      <div class="panel">
        <div class="hero-title"><div class="icon">+</div><div><h2>创建分析任务</h2><p class="muted">这一步只是分析思路 Agent 的输入准备页，不调用 Agent。BA 确认后才进入分析思路 Agent。</p></div></div>
        <div class="grid2">
          <div>
            <label>业务问题描述 *</label><textarea id="inQuestion">近期客流下降明显，想分析是哪些渠道在下降，以及新客获取和老客回店的表现变化。</textarea>
            <div id="aiFollowups" class="ai-followups"></div>
            <label>任务名称 *</label><input id="inName" class="input" value="客流下降原因分析">
            <label>分析目标描述</label><textarea id="inPurpose">分析某经销店 Q1 客流下降的主要原因，从渠道、客户、内部因素等多维度拆解。</textarea>
            <label>数据源 *</label><input id="inDataSource" type="hidden" value="demo_csv"><div class="grid3" id="dataSourcePicker"></div>
            <div id="inputDirtyWarning" class="warning-box" style="display:none;margin-top:12px">当前任务已进入后续节点，修改输入后需要重新生成分析思路。</div>
          </div>
          <div>
            <label>分析时间范围</label><div class="grid2"><input id="inStart" class="input" value="2026/01/01"><input id="inEnd" class="input" value="2026/03/31"></div>
            <label>对比基期</label><select id="inCompare"><option>Q4 2025</option><option>Q1 2025</option><option>上月</option><option>去年同期</option></select>
            <div class="hint" style="margin-top:18px"><b>填写提示</b><br>创建任务页只保留问题、目标、数据源和时间口径。分析维度会在下一步由 AI 推荐，BA 再确认或调整。</div>
            <div class="subtle-panel" style="margin-top:12px"><h3>下一步由 AI 补齐</h3><p class="muted">Agent 会根据业务问题推荐分析维度、假设、指标口径和数据缺口，避免 BA 在任务创建阶段提前填大量参数。</p></div>
          </div>
        </div>
      </div>
      <div class="panel confirm">
        <h3>BA 确认环节</h3><p>请确认以上输入是否符合分析需求。修改已进入后续节点的任务后，需要重新生成分析思路。</p>
        <label><input id="inputConfirmed" type="checkbox"> 确认配置正确</label>
        <div class="toolbar"><button class="btn secondary" onclick="saveTaskDraft()">保存草稿</button><button class="btn green" onclick="confirmTaskInput()">确认并继续</button><button class="btn secondary" onclick="setPage('workbench')">返回任务列表</button></div>
      </div>
    </section>

    <section id="analysis_design" class="page">
      <div class="panel">
        <div class="hero-row"><div class="hero-title"><div class="icon" style="background:var(--purple2);color:var(--purple)">↳</div><div><h2>分析思路设计</h2><p class="muted">分析思路 Agent 输出：目标、归因框架、假设和成熟框架配置。</p></div></div><span id="designStatus" class="pill amber">待 BA 确认</span></div>
        <div class="tabs"><button id="tabDesignBusiness" onclick="designTab='business';renderDesign()">分析思路拓展</button><button id="tabDesignFramework" onclick="designTab='framework';renderDesign()">成熟分析框架</button></div>
        <div id="designBody"></div>
      </div>
      <div class="panel confirm purple"><h3>BA 确认环节</h3><p>确认归因框架、绑定维度、指标模板和分析假设后，进入数据分析 Agent。</p><label><input id="designConfirmed" type="checkbox"> 确认分析思路</label><div class="toolbar"><button class="btn secondary" onclick="saveAnalysisDesign()">保存修改</button><button class="btn green" onclick="confirmDesign()">确认并继续</button><button class="btn secondary" onclick="setPage('task_creation')">上一步</button></div></div>
    </section>

    <section id="data_insight" class="page">
      <div class="panel">
        <div class="hero-row"><div class="hero-title"><div class="icon" style="background:var(--green2);color:var(--green)">▥</div><div><h2>数据分析与洞察</h2><p class="muted">数据分析 Agent 输出：指标、维度表、假设验证和计算逻辑。</p></div></div><button class="btn secondary" onclick="loadDataAnalysis(true)">重新计算</button></div>
        <div class="tabs"><button onclick="insightTab='overview';renderInsight()">指标概览</button><button onclick="insightTab='dimension_table';renderInsight()">维度指标表</button><button onclick="insightTab='hypothesis_validation';renderInsight()">假设验证</button><button onclick="insightTab='sql_logic';renderInsight()">计算逻辑(SQL)</button></div>
        <div id="insightBody"></div>
      </div>
      <div class="panel confirm"><h3>BA 确认环节</h3><p>确认指标结果、维度表和假设验证逻辑后，进入报告生成 Agent。</p><label><input id="insightConfirmed" type="checkbox"> 确认分析结果</label><div class="toolbar"><button class="btn green" onclick="confirmInsight()">确认并继续</button><button class="btn secondary" onclick="setPage('analysis_design')">上一步</button></div></div>
    </section>

    <section id="report_generation" class="page">
      <div class="panel">
        <div class="hero-title"><div class="icon" style="background:var(--purple2);color:var(--purple)">R</div><div><h2>报告生成</h2><p class="muted">报告生成 Agent 输出：左侧可编辑内容、图表预览和右侧导出入口。本期真实导出 HTML。</p></div></div>
        <div class="report-layout" style="margin-top:16px"><div id="reportEditor"></div><aside class="card"><h3>导出格式</h3><button class="btn secondary" style="width:100%;margin:6px 0" disabled>PowerPoint（后续）</button><button class="btn secondary" style="width:100%;margin:6px 0" disabled>PDF（后续）</button><button class="btn secondary" style="width:100%;margin:6px 0" disabled>Word（后续）</button><button class="btn green" style="width:100%;margin:6px 0" onclick="exportReport()">导出 HTML</button><div id="exportResult" class="muted" style="margin-top:10px"></div></aside></div>
      </div>
      <div class="panel confirm purple"><h3>BA 确认环节</h3><p>确认报告内容、图表和发布范围。</p><div class="toolbar"><button class="btn secondary" onclick="saveReport()">保存报告内容</button><button class="btn secondary" onclick="setPage('data_insight')">上一步</button></div></div>
    </section>

    <section id="catalog" class="page"><div class="panel hero-row"><div><h2>能力目录</h2><p class="muted">可维护的问题类型、分析方法、指标模板和数据要求。它是能力基础，不是每个任务的必经路径。</p></div><button class="btn secondary" onclick="addLocalCapability()">+ 新增能力</button></div><div class="panel" id="catalogBody"></div></section>
    <section id="ontology" class="page"><div class="panel"><h2>Ontology 语义维护</h2><p class="muted">业务对象、业务事件、对象关系、指标口径和字段映射由 8091 本服务提供。</p></div><div class="grid4" id="ontologyStats"></div><div class="panel" id="ontologyBody"></div></section>
    <section id="realdata" class="page"><div class="panel"><h2>数据资产预览</h2><p class="muted">当前 CSV 聚合结果，用于生成真实可查看的分析案例。</p></div><div class="panel" id="realDataBody"></div></section>
  </main>
</div>
<script>
let tasks=[], stats={}, currentTask=null, session=null, frameworks=[], catalog=null, semanticState=null, realReport=null, dataAnalysis=null, abilityState=[], ontologyState=[];
let designTab="business", insightTab="overview";
const pages={workbench:"任务管理",task_creation:"创建分析任务",analysis_design:"分析思路设计",data_insight:"数据分析与洞察",report_generation:"报告生成",catalog:"能力目录",ontology:"Ontology 语义维护",realdata:"数据资产预览"};
const dims=["渠道维度","客户维度","时间维度","区域维度","经销商","品牌维度","产品维度","顾问维度","漏斗维度"];
async function api(path, body){const opt=body?{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)}:{};const res=await fetch(path,opt);const data=await res.json();if(!res.ok)throw new Error(data.message||data.error||"API error");return data}
function esc(v){return String(v??"").replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;").replaceAll('"',"&quot;")}
function summaryText(text,len=72){const s=String(text||"");return s.length>len?s.slice(0,len)+"...":s}
function statusClass(status){return status==="completed"?"green":status==="draft"?"amber":status==="pending"?"amber":"blue"}
function sourceLabel(id){return{id:"数据源",demo_csv:"Sales 宽表 Demo",semantic_model:"企业语义模型",new_csv:"上传 CSV"}[id]||id||"未选数据源"}
function setPage(id){document.querySelectorAll(".page").forEach(p=>p.classList.toggle("active",p.id===id));document.querySelectorAll(".nav button").forEach(b=>b.classList.toggle("active",b.dataset.page===id));document.getElementById("pageTitle").textContent=pages[id]||id;renderStepper(id);if(id==="analysis_design")renderDesign();if(id==="data_insight"){insightTab="overview";loadDataAnalysis()}if(id==="report_generation")renderReport();if(id==="catalog")renderCatalog();if(id==="ontology")renderOntology();if(id==="realdata")renderRealData()}
function renderStepper(page){const box=document.getElementById("stepPanel");if(!["task_creation","analysis_design","data_insight","report_generation"].includes(page)||!currentTask){box.style.display="none";return}box.style.display="block";const nodes=[["task_creation","1. 创建任务","输入配置"],["analysis_design","2. 分析思路","Agent 输出"],["data_insight","3. 数据分析","指标/假设/SQL"],["report_generation","4. 报告生成","编辑/导出"]];const active=nodes.findIndex(x=>x[0]===page);box.innerHTML=`<div class="task-shell"><div><h3>${esc(currentTask.name||"未命名任务")} <span class="pill ${statusClass(currentTask.status)}">${esc(currentTask.status_text||currentTask.status)}</span></h3><div class="task-facts"><span class="pill">ID ${esc(currentTask.task_id)}</span><span class="pill blue">${esc(currentTask.node||"创建任务")}</span><span class="pill">${esc(currentTask.time_range||"未设置时间")}</span><span class="pill">${sourceLabel(currentTask.data_source)}</span></div></div><button class="btn secondary" onclick="setPage('workbench')">返回任务列表</button></div><div class="stepper" style="margin-top:16px">${nodes.map((n,i)=>`<div class="step ${i<active?"done":i===active?"active":""}"><div class="dot">${i<active?"✓":i+1}</div><div><b>${n[1]}</b><br><span class="muted">${n[2]}</span></div></div>`).join("")}</div>`}
async function loadTasks(){const data=await api("/api/tasks");tasks=data.tasks;stats=data.stats;renderTasks()}
function renderTasks(){const q=(document.getElementById("taskSearch")?.value||"").toLowerCase(),f=document.getElementById("taskFilter")?.value||"all";const rows=tasks.filter(t=>(f==="all"||t.status===f)&&(!q||`${t.name} ${t.business_question}`.toLowerCase().includes(q)));document.getElementById("taskList").innerHTML=rows.map(t=>`<div class="task-row"><div><div class="task-title"><strong>${esc(t.name)}</strong><span class="pill ${statusClass(t.status)}">${esc(t.status_text)}</span><span class="pill blue">${esc(t.node)}</span></div><div class="task-meta"><span>${esc(t.created_at)}</span><span>${sourceLabel(t.data_source)}</span><span>${esc(summaryText(t.business_question,74))}</span></div><div class="mini-flow">${[1,2,3,4].map(i=>`<span class="${i<=t.step?"done":""}">${i}</span>`).join("")}</div></div><div class="toolbar"><button class="btn" onclick="openTask('${t.task_id}')">打开</button><button class="btn secondary" onclick="duplicateTask('${t.task_id}')">复制</button><button class="btn secondary" onclick="deleteTask('${t.task_id}')">删除</button></div></div>`).join("")||`<div class="empty">没有匹配任务。</div>`;document.getElementById("taskStats").innerHTML=[["总任务数",stats.total||0,""],["进行中",stats.in_progress||0,"blue"],["已完成",stats.completed||0,"green"],["待确认/草稿",(stats.pending||0)+(stats.draft||0),"amber"]].map(([t,n,c])=>`<div class="card"><span class="muted">${t}</span><h2 style="margin:6px 0 0;color:${c?`var(--${c})`:"var(--ink)"}">${n}</h2></div>`).join("")}
async function newTask(){const data=await api("/api/tasks",{task_name:"客流下降原因分析",business_question:"近期客流下降明显，想分析是哪些渠道在下降，以及新客获取和老客回店的表现变化。",analysis_purpose:"分析客流下降主要原因。",time_range:"2026/01/01 - 2026/03/31",comparison_period:"Q4 2025",dimensions:["渠道维度","客户维度","时间维度"],data_source:"demo_csv"});currentTask=data.task;session=null;dataAnalysis=null;insightTab="overview";fillTaskForm(currentTask);await loadTasks();setPage("task_creation")}
async function openTask(id){const data=await api(`/api/tasks/${id}/open`,{});currentTask=data.task;session=data.session;dataAnalysis=null;insightTab="overview";fillTaskForm(currentTask);await loadTasks();setPage(currentTask.current_page||"task_creation")}
async function duplicateTask(id){const data=await api(`/api/tasks/${id}/duplicate`,{});currentTask=data.task;fillTaskForm(currentTask);await loadTasks();setPage("task_creation")}
async function deleteTask(id){if(!confirm("确认删除该任务？"))return;await api(`/api/tasks/${id}/delete`,{});if(currentTask?.task_id===id){currentTask=null;session=null}await loadTasks();setPage("workbench")}
function renderDataSourcePicker(selected="demo_csv"){const items=[["demo_csv","Sales 宽表 Demo","已加载 CSV，可直接生成真实分析案例"],["semantic_model","企业语义模型","复用 Ontology、指标口径和权限规则"],["new_csv","上传其他 CSV","保留入口，后续做字段识别与映射"]];document.getElementById("dataSourcePicker").innerHTML=items.map(([id,t,b])=>`<div class="data-source-card ${selected===id?"active":""}" onclick="selectDataSource('${id}')"><b>${esc(t)}</b><p class="muted">${esc(b)}</p>${selected===id?'<span class="pill green">已选择</span>':'<span class="pill">可选</span>'}</div>`).join("")}
function selectDataSource(id){document.getElementById("inDataSource").value=id;renderDataSourcePicker(id)}
function recommendedDimensions(){const q=`${document.getElementById("inQuestion")?.value||currentTask?.business_question||""} ${document.getElementById("inPurpose")?.value||currentTask?.analysis_purpose||""}`;const selected=new Set();if(/渠道|客流|自然|邀约|预约|投放|线索/.test(q)){["渠道维度","客户维度","时间维度","漏斗维度"].forEach(x=>selected.add(x))}if(/经销商|门店|区域|城市|大区/.test(q)){["区域维度","经销商"].forEach(x=>selected.add(x))}if(/车型|车系|品牌|产品|BMW|MINI/.test(q)){["品牌维度","产品维度"].forEach(x=>selected.add(x))}if(!selected.size){["渠道维度","客户维度","时间维度"].forEach(x=>selected.add(x))}return [...selected]}
function renderFollowups(){const q=document.getElementById("inQuestion")?.value||"";const questions=["本次分析的核心北极星指标是客流、订单，还是线索到订单转化率？","对比基期使用上月、去年同期，还是目标差距？","是否需要排除节假日、营业日差异或数据口径变更？","如果结论要给业务方看，是否需要同时输出行动建议和证据链？"];if(/渠道|投放/.test(q))questions.splice(2,0,"渠道层级按一级渠道、媒体平台还是 Campaign 颗粒度拆？");if(/经销商|门店/.test(q))questions.splice(2,0,"是否需要按经销商、城市或大区先做贡献度排序？");document.getElementById("aiFollowups").innerHTML=`<h3>AI 追问区</h3><p class="muted">这些问题由 AI 根据当前业务描述自动生成，BA 可在进入分析思路页后继续细化。</p>${questions.slice(0,5).map((x,i)=>`<div class="followup-row"><b>${i+1}</b><span>${esc(x)}</span></div>`).join("")}`}
function renderDimensionPicker(selected=[]){const target=document.getElementById("dimensionPicker");if(!target)return;const values=selected.length?selected:recommendedDimensions();target.innerHTML=dims.map(d=>`<label class="dimension-card ${values.includes(d)?"active":""}" style="margin:0"><input type="checkbox" value="${esc(d)}" ${values.includes(d)?"checked":""} onchange="this.closest('.dimension-card').classList.toggle('active',this.checked)"> <b>${esc(d)}</b><br><span class="muted">${values.includes(d)?"AI 推荐，BA 可取消":"可补充加入分析路径"}</span></label>`).join("")}
function fillTaskForm(t){renderDataSourcePicker(t?.data_source||"demo_csv");document.getElementById("inQuestion").value=t?.business_question||"";document.getElementById("inName").value=t?.name||"";document.getElementById("inPurpose").value=t?.analysis_purpose||"";document.getElementById("inDataSource").value=t?.data_source||"demo_csv";document.getElementById("inCompare").value=t?.comparison_period||"Q4 2025";const range=String(t?.time_range||"2026/01/01 - 2026/03/31").split(/\s+-\s+/);document.getElementById("inStart").value=range[0]||"";document.getElementById("inEnd").value=range[1]||"";document.getElementById("inputConfirmed").checked=!!t?.input_confirmed;document.getElementById("inputDirtyWarning").style.display=t?.input_confirmed&&t?.current_page!=="task_creation"?"block":"none";renderFollowups()}
function currentDesignDimensions(){const picked=[...document.querySelectorAll("#dimensionPicker input:checked")].map(x=>x.value);return picked.length?picked:(currentTask?.dimensions?.length?currentTask.dimensions:recommendedDimensions())}
function inputPayload(){return{task_name:document.getElementById("inName").value,business_question:document.getElementById("inQuestion").value,analysis_purpose:document.getElementById("inPurpose").value,data_source:document.getElementById("inDataSource").value,time_range:`${document.getElementById("inStart").value} - ${document.getElementById("inEnd").value}`,comparison_period:document.getElementById("inCompare").value,dimensions:currentTask?.dimensions?.length?currentTask.dimensions:recommendedDimensions(),deliverable_type:"management_report",audience:"Sales BP / Management"}}
async function saveTaskDraft(){if(!currentTask){await newTask()}const data=await api(`/api/tasks/${currentTask.task_id}/input/update`,inputPayload());currentTask=data.task;await loadTasks();alert("草稿已保存，未启动 Agent。")}
async function confirmTaskInput(){if(!document.getElementById("inputConfirmed").checked){alert("请先勾选 BA 确认。");return}if(!currentTask){await newTask()}const data=await api(`/api/tasks/${currentTask.task_id}/input/confirm`,inputPayload());currentTask=data.task;session=data.session;dataAnalysis=null;insightTab="overview";await loadTasks();setPage("analysis_design")}
function designOutput(){return session?.results?.analysis_design?.output_payload||{}}
function hypotheses(){const saved=currentTask?.hypotheses||[];if(currentTask?.hypotheses_manual&&saved.length)return saved;return topicHypotheses()}
function topicType(){const q=`${currentTask?.business_question||""} ${currentTask?.analysis_purpose||""}`.toLowerCase();if(/客流|到店|回店|自然|邀约|预约/.test(q))return"traffic";if(/订单|成交|转化|漏斗/.test(q))return"order";if(/渠道|线索|投放|归因/.test(q))return"channel";if(/经销商|门店|区域|城市/.test(q))return"dealer";if(/活动|campaign|营销/.test(q))return"campaign";return"generic"}
function topicHypotheses(){const topic=topicType();if(topic==="traffic")return[
  {id:"traffic-h1",title:"主要原因是自然获客能力下降",type:"核心假设",status:"待验证",metrics:["自然到店客流","自然到店占比"]},
  {id:"traffic-h2",title:"线上渠道获客效率下降是重要因素",type:"次要假设",status:"待验证",metrics:["线上预约客流","线上占比"]},
  {id:"traffic-h3",title:"邀约策略效果减弱",type:"次要假设",status:"待验证",metrics:["邀约到店客流","邀约成功率"]},
  {id:"traffic-h4",title:"新客获取能力下降是核心问题",type:"核心假设",status:"待验证",metrics:["新客客流","新客占比"]},
  {id:"traffic-h5",title:"季节性/节假日因素影响",type:"备选假设",status:"待验证",metrics:["节假日客流变化","工作日/周末客流"]}
];if(topic==="order")return[
  {id:"order-h1",title:"订单下降主要来自上游线索或客流不足",type:"核心假设",status:"待验证",metrics:["线索量","客流量","订单量"]},
  {id:"order-h2",title:"到店到订单转化率下降造成成交缺口",type:"核心假设",status:"待验证",metrics:["到店到订单转化率","成交率"]},
  {id:"order-h3",title:"部分渠道带来高量低质线索",type:"次要假设",status:"待验证",metrics:["渠道线索量","渠道订单转化率"]},
  {id:"order-h4",title:"区域/经销商承接能力差异拖累整体",type:"次要假设",status:"待验证",metrics:["经销商客流","经销商成交率"]},
  {id:"order-h5",title:"车型结构变化影响订单转化",type:"备选假设",status:"待验证",metrics:["车型客流","车型订单量"]}
];if(topic==="channel")return[
  {id:"channel-h1",title:"投放效率下降来自低质渠道占比提升",type:"核心假设",status:"待验证",metrics:["渠道线索量","渠道订单转化率"]},
  {id:"channel-h2",title:"自然/付费渠道结构变化影响整体获客效率",type:"次要假设",status:"待验证",metrics:["自然到店客流","线上预约客流"]},
  {id:"channel-h3",title:"重点渠道的留资到到店链路存在掉点",type:"核心假设",status:"待验证",metrics:["留资量","客流总量"]},
  {id:"channel-h4",title:"渠道归因口径差异影响贡献判断",type:"备选假设",status:"待验证",metrics:["渠道占比","订单量"]}
];if(topic==="dealer")return[
  {id:"dealer-h1",title:"少数经销商承接下滑拖累整体表现",type:"核心假设",status:"待验证",metrics:["经销商客流","经销商成交率"]},
  {id:"dealer-h2",title:"区域市场容量或竞品动作造成局部异常",type:"次要假设",status:"待验证",metrics:["区域客流","订单量"]},
  {id:"dealer-h3",title:"高意向客户分配与跟进效率不足",type:"核心假设",status:"待验证",metrics:["高意向客户占比","成交量"]},
  {id:"dealer-h4",title:"门店活动执行差异影响到店和成交",type:"备选假设",status:"待验证",metrics:["客流总量","成交量"]}
];if(topic==="campaign")return[
  {id:"campaign-h1",title:"活动带来的新增线索质量不足",type:"核心假设",status:"待验证",metrics:["线索量","留资转化率"]},
  {id:"campaign-h2",title:"活动客流集中但成交承接不足",type:"核心假设",status:"待验证",metrics:["客流总量","成交量"]},
  {id:"campaign-h3",title:"活动覆盖人群与目标车型不匹配",type:"次要假设",status:"待验证",metrics:["车型客流","车型订单量"]},
  {id:"campaign-h4",title:"活动周期或触达节奏造成转化滞后",type:"备选假设",status:"待验证",metrics:["工作日客流","周末客流"]}
];return(designOutput().hypotheses||["目标指标变化来自关键维度结构变化","局部对象异常拖累整体表现","数据口径或字段缺失影响结论强度"]).map((x,i)=>({id:`hyp-${i+1}`,title:x,type:i===0?"核心假设":"次要假设",status:"待验证",metrics:[]}))}
function renderDesign(){if(!currentTask){document.getElementById("designBody").innerHTML=`<div class="empty">请先打开或创建任务。</div>`;return}document.getElementById("tabDesignBusiness").classList.toggle("active",designTab==="business");document.getElementById("tabDesignFramework").classList.toggle("active",designTab==="framework");const out=designOutput();document.getElementById("designStatus").textContent=session?.confirmations?.analysis_design?"已确认":"待 BA 确认";if(!session){document.getElementById("designBody").innerHTML=`<div class="empty">创建任务页 BA 确认后，才会调用分析思路 Agent。</div>`;return}if(designTab==="framework"){renderFrameworkTab(out);return}const hs=hypotheses();const thinking=analysisThinking(out);document.getElementById("designBody").innerHTML=`${renderAnalysisThinking(thinking)}${renderDesignDimensionReview()}<div class="subtle-panel" style="margin-top:16px"><div class="hero-row"><div><h3>分析假设</h3><p class="muted">BA 可以像带电子实习生一样编辑、删除、补充假设，并把真正关键的假设标为核心。</p></div><button class="btn secondary" onclick="addHypothesis()">+ 添加假设</button></div><div id="hypList">${hs.map(renderHyp).join("")}</div></div>`;renderDimensionPicker(currentTask.dimensions||recommendedDimensions())}
function renderDesignDimensionReview(){return`<div class="dimension-review"><div class="hero-row"><div><h3>AI 推荐分析维度</h3><p class="muted">维度选择已从创建任务页移到这里。AI 先推荐，BA 在确认分析思路前调整。</p></div><span class="pill blue">BA 确认后进入数据分析</span></div><div class="grid3" id="dimensionPicker" style="margin-top:12px"></div></div>`}
function analysisThinking(out){const q=`${currentTask?.business_question||""} ${out?.analysis_purpose||""}`;const isTraffic=/客流|到店|回店|自然|邀约|预约/.test(q);if(isTraffic){return{goals:["定位客流下降的主要来源：自然到店、邀约到店、线上预约或回店客流。","识别关键影响因素：渠道获客、客户结构、时间周期、区域/经销商承接。","输出可执行建议：短期修复获客与邀约，中期优化渠道和客户运营策略。"],summary:"AI 判断这是一个客流下降归因问题，优先按外部因素、内部运营因素和结构性因素拆解，再用渠道/客户/时间/区域维度验证。",paths:[{title:"先确认下降是否真实",items:["对比本期与基期客流总量、自然到店、邀约到店、线上预约。","排除门店营业日、节假日、数据缺失和口径变化。"]},{title:"再定位下降发生在哪里",items:["按渠道来源拆：自然、邀约、线上预约、活动渠道。","按客户类型拆：新客获取、老客回店、高意向客户占比。","按时间拆：工作日/周末、周内趋势、节假日前后。"]},{title:"最后转成业务动作",items:["若自然到店下降，检查市场环境、品牌曝光、竞品活动。","若邀约到店下降，检查顾问跟进、邀约策略和线索质量。","若回店下降，检查保客运营、复访触达和门店活动。"]}],factors:[{group:"外部因素",desc:"市场、竞品、季节等外部环境因素",items:[["市场环境","当地市场整体客流/容量变化","需外部数据"],["竞品影响","竞品活动、新店开业、价格政策变化","需外部数据"],["季节性因素","春节/假期/天气造成周期性波动","可用日历数据验证"]]},{group:"内部因素",desc:"门店、团队、策略等内部运营因素",items:[["获客能力","自然到店、线上获客、活动引流是否下降","自然到店客流 / 线上预约客流"],["转化能力","到店后的留资、试驾、成交承接是否变化","到店-订单转化 / 成交率"],["留存能力","老客回店和再次到店是否下降","回店客流 / 老客占比"],["邀约能力","顾问邀约效率和邀约成功率是否下降","邀约到店客流 / 邀约成功率"]]},{group:"结构因素",desc:"品牌、渠道、时段等结构性因素",items:[["渠道结构","高客流渠道占比是否下降","渠道占比 / 渠道客流"],["客户结构","新客、老客、高意向客户结构是否变化","新客占比 / 高意向客户占比"],["时间结构","下降是否集中在工作日、周末或特定周","日/周/月趋势"],["区域/经销商结构","是否由少数门店或区域拖累整体","区域客流 / 经销商客流"]]}]}}return{goals:["明确业务问题的目标指标和对比口径。","按时间、区域、渠道、产品和组织维度拆解差异。","形成可验证假设，并输出可行动建议。"],summary:"AI 将该问题识别为经营指标变化归因问题，先确认变化真实性，再按贡献维度定位原因，最后沉淀成建议和报告。",paths:[{title:"确认问题边界",items:["明确目标指标、时间范围、对比基期和适用对象。","识别数据是否足以支撑分析。"]},{title:"拆解变化来源",items:["按核心维度计算贡献和异常。","识别最大贡献项与异常对象。"]},{title:"验证业务解释",items:["将候选原因转成假设。","用数据验证假设并形成建议。"]}],factors:[{group:"外部因素",desc:"市场、竞品、政策等外部因素",items:[["市场变化","整体需求或容量变化","需外部数据"],["竞品影响","竞品活动或价格变化","需外部数据"]]},{group:"内部因素",desc:"运营、流程、团队等内部因素",items:[["获客/供给","上游输入是否下降","核心输入指标"],["转化/承接","链路效率是否下降","转化率指标"]]},{group:"结构因素",desc:"渠道、区域、产品和时间结构",items:[["渠道结构","渠道占比变化","渠道维度"],["区域结构","区域贡献变化","区域维度"],["产品结构","产品组合变化","产品维度"]]}]}}
function renderAnalysisThinking(plan){return`<div class="ai-section-title">◎ 分析目标</div><div class="ai-objectives">${plan.goals.map((x,i)=>`<div><b>${i+1}</b><span>${esc(x)}</span></div>`).join("")}</div><div class="ai-section-title">↳ AI 对问题的理解</div><div class="hint">${esc(plan.summary)}</div><div class="ai-section-title">⌁ 分析路径</div><div class="grid3">${plan.paths.map(p=>`<div class="path-card"><h4>${esc(p.title)}</h4><ul>${p.items.map(x=>`<li>${esc(x)}</li>`).join("")}</ul></div>`).join("")}</div><div class="ai-section-title">⌘ 归因分析框架 <span class="muted">（点击展开查看详情）</span></div><div class="factor-tree">${plan.factors.map((g,gi)=>`<div class="factor-group"><h4>${gi<2?"⌄":"›"} ${esc(g.group)} <small class="muted">（${esc(g.desc)}）</small></h4>${g.items.map((item,ii)=>`<div class="factor-item ${gi===0&&ii===2?"focus":""}"><span class="arrow">→</span><strong>${esc(item[0])}</strong><small>${esc(item[1])}</small><span class="pill blue">${esc(item[2])}</span></div>`).join("")}</div>`).join("")}</div>`}
function renderFrameworkTab(out){const selected=currentTask.selected_framework_id||frameworks[0]?.id||"";const fw=frameworks.find(x=>x.id===selected)||frameworks[0]||{};document.getElementById("designBody").innerHTML=`<div class="toolbar"><select id="frameworkSelect" onchange="currentTask.selected_framework_id=this.value;renderDesign()">${frameworks.map(f=>`<option value="${f.id}" ${f.id===selected?"selected":""}>${esc(f.name)}</option>`).join("")}</select><button class="btn ghost" onclick="recommendFramework()">智能推荐</button></div><div class="subtle-panel" style="margin-top:16px"><h3>${esc(fw.name||"暂无框架")}</h3><p class="muted">${esc(fw.description||"")}</p><h3>绑定维度</h3><div class="toolbar">${(fw.dimensions||[]).map(x=>`<span class="pill blue">${esc(x)}</span>`).join("")}</div><h3>指标模板</h3><div class="grid3">${(fw.metric_templates||[]).map(x=>statCard(x,"指标模板","blue")).join("")}</div><h3>数据要求</h3><div class="grid3">${statCard("必要字段",(fw.data_requirements?.required_fields||[]).length,"red")}${statCard("可选字段",(fw.data_requirements?.optional_fields||[]).length,"amber")}${statCard("需外部数据",(fw.data_requirements?.extra_data||[]).join(" / "),"blue")}</div></div>`}
function renderHyp(h){const cls=h.status==="已验证"?"green":h.status==="已否定"?"red":"amber",isCore=h.type==="核心假设";return`<div class="hyp-card ${isCore?"core":""}" data-id="${esc(h.id)}"><div><div class="toolbar"><span class="pill ${cls}">${esc(h.status)}</span><span class="pill ${isCore?"blue":""}">${esc(h.type||"假设")}</span><span class="pill blue">${esc((h.metrics||[]).join(" / ")||"待绑定指标")}</span></div><input class="hyp-title" data-id="${esc(h.id)}" value="${esc(h.title)}"></div><div class="hyp-actions"><select class="hyp-type" onchange="this.closest('.hyp-card').classList.toggle('core',this.value==='核心假设')"><option ${h.type==="核心假设"?"selected":""}>核心假设</option><option ${h.type==="次要假设"?"selected":""}>次要假设</option><option ${h.type==="备选假设"?"selected":""}>备选假设</option></select><select class="hyp-status"><option ${h.status==="待验证"?"selected":""}>待验证</option><option ${h.status==="已验证"?"selected":""}>已验证</option><option ${h.status==="已否定"?"selected":""}>已否定</option></select><button class="btn secondary" onclick="deleteHypothesis('${esc(h.id)}')">删除</button></div></div>`}
function collectHypotheses(){const prior=hypotheses();return[...document.querySelectorAll("#hypList .hyp-card")].map((el,i)=>{const id=el.querySelector(".hyp-title").dataset.id||`hyp-${i+1}`,old=prior.find(h=>h.id===id)||prior[i]||{};return{id,title:el.querySelector(".hyp-title").value,type:el.querySelector(".hyp-type").value,status:el.querySelector(".hyp-status").value,metrics:old.metrics||[]}})}
function addHypothesis(){currentTask.hypotheses=collectHypotheses();currentTask.hypotheses.push({id:`hyp-${Date.now()}`,title:"新增待验证假设",type:"备选假设",status:"待验证",metrics:[]});renderDesign()}
function deleteHypothesis(id){currentTask.hypotheses=collectHypotheses().filter(h=>h.id!==id);currentTask.hypotheses_manual=true;renderDesign()}
async function saveAnalysisDesign(silent=false){if(designTab==="business"){currentTask.hypotheses=collectHypotheses();currentTask.hypotheses_manual=true;currentTask.dimensions=currentDesignDimensions()}await api(`/api/tasks/${currentTask.task_id}/analysis-design/update`,{selected_framework_id:currentTask.selected_framework_id||document.getElementById("frameworkSelect")?.value||"",dimensions:currentDesignDimensions(),hypotheses:currentTask.hypotheses||hypotheses(),hypotheses_manual:!!currentTask.hypotheses_manual});await loadTasks();if(!silent)alert("分析思路修改已保存。")}
async function confirmDesign(){if(!document.getElementById("designConfirmed").checked){alert("请先勾选 BA 确认。");return}await saveAnalysisDesign(true);const data=await api(`/api/tasks/${currentTask.task_id}/analysis-design/confirm`,{confirmed_by:"BA User",feedback:"确认分析思路配置。"});currentTask=data.task;session=data.session;dataAnalysis=null;insightTab="overview";await loadTasks();setPage("data_insight")}
function recommendFramework(){const q=(currentTask.business_question||"").toLowerCase();currentTask.selected_framework_id=q.includes("渠道")?"channel_quality":q.includes("经销商")?"dealer_performance":q.includes("活动")||q.includes("campaign")?"campaign_review":q.includes("漏斗")?"sales_funnel":"traffic_decline";renderDesign()}
async function loadDataAnalysis(force=false){if(!currentTask){document.getElementById("insightBody").innerHTML=`<div class="empty">请先打开任务。</div>`;return}if(!dataAnalysis||force){dataAnalysis=await api(`/api/tasks/${currentTask.task_id}/data-analysis`)}renderInsight()}
function renderInsight(){if(!dataAnalysis){return}document.querySelectorAll("#data_insight .tabs button").forEach((b,i)=>b.classList.toggle("active",["overview","dimension_table","hypothesis_validation","sql_logic"][i]===insightTab));const body=document.getElementById("insightBody");if(insightTab==="overview"){body.innerHTML=renderInsightOverview();return}if(insightTab==="dimension_table"){body.innerHTML=`<div class="config-section"><h3>维度指标明细</h3>${table(["维度","指标名称","本期值","上期值","变化率","趋势"],dataAnalysis.dimension_rows.map(r=>[r.dimension,r.name,formatValue(r.current),formatValue(r.previous),formatChange(r),trendText(r.trend)]))}</div><div class="config-section"><h3>贡献度表格</h3>${contributionTable()}</div>`;return}if(insightTab==="hypothesis_validation"){body.innerHTML=validatedHypotheses().map(renderHypothesisEvidence).join("");return}body.innerHTML=`<p class="muted">计算逻辑用于 BA 或数据同事复核口径，每条 SQL 下方补充业务语言解释，便于非技术用户理解。</p>${dataAnalysis.sql_logic.map((r,i)=>`<details class="sql-item" ${i===0?"open":""}><summary>${esc(r.metric)}</summary><div class="sql-meta"><span class="pill blue">${esc(r.fields)}</span><span class="pill">${esc(r.formula||"待确认公式")}</span><button class="btn secondary" onclick="copySql(${i})">复制 SQL</button></div><div class="business-explain"><b>业务解释：</b>${esc(r.business_explanation||sqlExplain(r))}</div><div class="code">${esc(r.sql)}</div></details>`).join("")}`}
function renderInsightOverview(){const groups=metricGroups(),risks=riskPoints();return`<div class="config-section">${northStarTree()}</div><div class="config-section"><h3>贡献度表格</h3>${contributionTable()}</div><div class="data-layout"><div>${groups.map(g=>`<div class="config-section"><h3>${esc(g.title)}</h3><div class="grid4">${g.items.map(metricCard).join("")}</div></div>`).join("")}<div class="config-section"><h3>可视化图表</h3>${insightCharts()}</div></div><aside class="subtle-panel"><h3>风险识别点</h3>${risks.map(riskCard).join("")}</aside></div>`}
function northStarTree(){const rows=dataAnalysis.metrics||[],root=rows.find(r=>r.name==="客流总量")||rows.find(r=>r.name==="订单量")||rows[0],drivers=contributionRows().slice(0,6);return`<h3>北极星指标归因树</h3><div class="north-tree"><div class="tree-node root"><div class="hero-row"><div><b>${esc(root?.name||"核心指标")}</b><p class="muted">本期 ${formatValue(root?.current)}，较上期 ${formatChange(root||{})}</p></div><span class="pill ${root?.trend==="down"?"red":"green"}">${trendText(root?.trend)}</span></div></div><div class="tree-children">${drivers.map(d=>`<div class="tree-node"><span class="pill ${d.direction==="拖累"?"red":"green"}">${esc(d.direction)}</span><h3>${esc(d.dimension)} · ${esc(d.metric)}</h3><p class="muted">贡献度 ${d.contribution}%；变化 ${d.change}%</p></div>`).join("")}</div></div>`}
function contributionRows(){return(dataAnalysis.metrics||[]).filter(r=>Number.isFinite(Number(r.change))).map(r=>{const impact=Math.abs(Number(r.change)||0)*(Number(r.previous)||1);return{dimension:r.dimension,metric:r.name,current:formatValue(r.current),previous:formatValue(r.previous),change:Number(r.change||0).toFixed(1),direction:Number(r.change)<0?"拖累":"拉动",impact}}).sort((a,b)=>b.impact-a.impact).slice(0,10).map((r,i,arr)=>({...r,contribution:(arr.reduce((s,x)=>s+x.impact,0)?(r.impact/arr.reduce((s,x)=>s+x.impact,0)*100):0).toFixed(1)}))}
function contributionTable(){const rows=contributionRows();return table(["排名","维度","指标","本期","上期","变化","方向","贡献度"],rows.map((r,i)=>[i+1,r.dimension,r.metric,r.current,r.previous,`${r.change}%`,r.direction,`${r.contribution}%`]))}
function renderHypothesisEvidence(h){const strength=evidenceStrength(h),missing=missingDataForHypothesis(h),statusClass=h.status==="已验证"?"green":h.status==="已否定"?"red":"amber";return`<div class="evidence-card"><div class="hero-row"><div><h3>${esc(h.title)}</h3><div class="toolbar"><span class="pill ${statusClass}">${esc(h.status)}</span><span class="pill ${strength.cls}">证据强度：${strength.label}</span></div></div><button class="btn secondary" onclick="insightTab='sql_logic';renderInsight()">查看 SQL</button></div><div class="evidence-meta"><div class="hint"><b>验证结论</b><br>${esc(hypothesisConclusion(h))}</div><div class="warning-box"><b>待补数据</b><br>${esc(missing)}</div><div class="subtle-panel"><b>BA 处理建议</b><br><span class="muted">${h.status==="已验证"?"可进入报告，但需保留口径说明。":"继续补充数据或调整假设。"}</span></div></div><div class="grid3">${(h.related_metrics||[]).map(metricCard).join("")}</div></div>`}
function evidenceStrength(h){const related=h.related_metrics||[],strong=related.filter(m=>Math.abs(Number(m.change)||0)>=15).length;if(strong>=2)return{label:"强",cls:"green"};if(strong===1)return{label:"中",cls:"amber"};return{label:"弱",cls:"red"}}
function missingDataForHypothesis(h){const title=h.title||"";if(/市场|竞品|季节|节假日/.test(title))return"需要市场大盘、竞品活动、节假日日历或天气数据。";if(/渠道|线上|投放/.test(title))return"需要媒体成本、Campaign、CPL/CPA 或渠道归因口径。";if(/邀约|承接|顾问/.test(title))return"需要顾问排班、跟进记录、邀约成功率和门店运营动作。";return"当前 CSV 可初步验证，仍需 BA 确认指标口径和去重规则。"}
function hypothesisConclusion(h){const related=h.related_metrics||[];if(!related.length)return"当前缺少可绑定指标，需要 BA 补充验证口径。";const worst=[...related].sort((a,b)=>Math.abs(Number(b.change)||0)-Math.abs(Number(a.change)||0))[0];return`${worst.name} 本期 ${formatValue(worst.current)}，较上期 ${formatChange(worst)}，支撑该假设的当前判断。`}
function sqlExplain(r){if(String(r.metric||"").includes("转化率"))return"用分子指标除以分母指标，判断链路效率是否变化，BA 需确认分母是否排除无效记录。";if(String(r.metric||"").includes("客流"))return"统计去重到店或访问记录，用于判断客流来源和结构变化。";return"用于复核该指标的字段、过滤条件和计算口径。"}
function metricGroups(){const rows=dataAnalysis.metrics||[];const by=(names)=>names.map(n=>rows.find(r=>r.name===n)).filter(Boolean);return[{title:"渠道维度指标",items:by(["客流总量","自然到店客流","邀约到店客流","线上预约客流","自然到店占比"])},{title:"客户维度指标",items:by(["新客客流","回店客流","高意向客户占比"])},{title:"时间维度指标",items:by(["工作日客流","周末客流"])},{title:"品牌维度指标",items:by(["BMW 客流","MINI 客流","MOTO 客流"])},{title:"漏斗维度指标",items:by(["订单量","留资量","留资转化率","成交量"]).concat(rows.filter(r=>["漏斗维度"].includes(r.dimension)&&!["订单量"].includes(r.name)).slice(0,3))}].filter(g=>g.items.length)}
function riskPoints(){const rows=(dataAnalysis.metrics||[]).filter(m=>m.trend==="down").sort((a,b)=>Math.abs(Number(b.change)||0)-Math.abs(Number(a.change)||0)).slice(0,6);return rows.map(m=>({title:`${m.name}${Number(m.change)<0?"下降":"变化"}${Math.abs(Number(m.change)||0).toFixed(1)}%`,detail:`${m.name}本期为${formatValue(m.current)}，较上期${formatValue(m.previous)}有明显变化`,level:Math.abs(Number(m.change)||0)>=18?"高影响":"中影响",metric:m}))}
function riskCard(r){const cls=r.level==="高影响"?"red":"amber";return`<div class="card" style="margin-bottom:10px;background:${r.level==="高影响"?"var(--red2)":"var(--amber2)"}"><div class="hero-row"><h3>${esc(r.title)}</h3><span class="pill ${cls}">${esc(r.level)}</span></div><p class="muted">${esc(r.detail)}</p></div>`}
function insightCharts(){const rows=dataAnalysis.metrics||[],channel=["自然到店客流","邀约到店客流","线上预约客流"].map(n=>rows.find(r=>r.name===n)).filter(Boolean),customer=["新客客流","回店客流"].map(n=>rows.find(r=>r.name===n)).filter(Boolean),brand=["BMW 客流","MINI 客流","MOTO 客流"].map(n=>rows.find(r=>r.name===n)).filter(Boolean);return`<div class="grid2"><div class="card"><h3>各渠道客流对比</h3>${miniBars(channel)}</div><div class="card"><h3>新客 vs 老客客流</h3>${miniBars(customer)}</div><div class="card"><h3>各品牌客流占比</h3>${donutLegend(brand)}</div><div class="card"><h3>漏斗转化</h3>${funnelBars()}</div></div>`}
function miniBars(items){const max=Math.max(...items.map(x=>Number(x.previous)||0,0),1);return`<div class="chartbar">${items.map(x=>`<div><span>${esc(x.name.replace("客流",""))}</span><div class="bar"><span style="width:${Math.max(6,(Number(x.current)||0)/max*100)}%"></span></div><b>${formatValue(x.current)}</b></div><div><span class="muted">上期</span><div class="bar"><span style="width:${Math.max(6,(Number(x.previous)||0)/max*100)}%;background:#cbd5e1"></span></div><b class="muted">${formatValue(x.previous)}</b></div>`).join("")}</div>`}
function donutLegend(items){const sum=items.reduce((s,x)=>s+(Number(x.current)||0),0)||1;return`<div class="toolbar">${items.map((x,i)=>`<span class="pill ${i===0?"blue":i===1?"green":"amber"}">${esc(x.name.replace(" 客流",""))} ${((Number(x.current)||0)/sum*100).toFixed(1)}%</span>`).join("")}</div>`}
function funnelBars(){const rows=dataAnalysis.metrics||[],items=["客流总量","订单量"].map(n=>rows.find(r=>r.name===n)).filter(Boolean);return miniBars(items)}
function validatedHypotheses(){const rows=dataAnalysis?.metrics||[];return hypotheses().map((h,i)=>{const used=new Set();const related=(h.metrics||[]).map(name=>{let found=rows.find(r=>!used.has(r.name)&&r.name===name);if(!found)found=rows.find(r=>!used.has(r.name)&&(r.name.includes(name.replace("占比",""))||name.includes(r.name)));if(found)used.add(found.name);return found}).filter(Boolean);const fallback=rows.filter(r=>!used.has(r.name)).slice(i,i+3);const evidence=related.length?related:fallback;const down=evidence.some(m=>m.trend==="down");return{...h,status:h.status&&h.status!=="待验证"?h.status:(down?"已验证":"待验证"),related_metrics:evidence}})}
function copySql(index){const sql=dataAnalysis?.sql_logic?.[index]?.sql||"";navigator.clipboard?.writeText(sql)}
async function confirmInsight(){if(!document.getElementById("insightConfirmed").checked){alert("请先勾选 BA 确认。");return}const data=await api(`/api/tasks/${currentTask.task_id}/data-insight/confirm`,{confirmed_by:"BA User",feedback:"确认数据分析结果和假设验证。"});currentTask=data.task;session=data.session;await loadTasks();setPage("report_generation")}
function reportOutput(){return session?.results?.report_generation?.output_payload||{}}
function reportDefaults(){const out=reportOutput(),top=contributionRows()[0],verified=validatedHypotheses().filter(h=>h.status==="已验证").slice(0,2);return{conclusion:(out.ppt_storyline||out.brd_sections||[]).slice(0,2).join("\n")||`${currentTask?.name||"本次分析"}的主要结论需要围绕北极星指标变化、贡献度最高维度和已验证假设展开。`,evidence:verified.map(h=>`${h.title}：${hypothesisConclusion(h)}`).join("\n")||`数据源：${currentTask?.data_source||""}；维度：${(currentTask?.dimensions||[]).join(" / ")}；最大贡献项：${top?`${top.dimension}-${top.metric}`:"待确认"}。`,action:"短期：优先处理贡献度最高的拖累维度。\n中期：复核指标口径和缺失数据。\n长期：将本次分析路径保存为可复用 Playbook。",background:`业务问题：${currentTask?.business_question||""}\n时间范围：${currentTask?.time_range||""}`,executive_summary:(out.executive_summary||["本分析已完成任务输入、分析思路、数据洞察和报告生成。"]).join("\n"),data_scope:`数据源：${currentTask?.data_source||""}\n维度：${(currentTask?.dimensions||[]).join(" / ")}`,key_findings:(out.ppt_storyline||out.brd_sections||["关键发现待 BA 基于图表确认。"]).join("\n"),recommendations:"建议按短期、中期、长期拆解跟进行动，并沉淀为可复用分析框架。"}}
function renderReport(){if(!currentTask){document.getElementById("reportEditor").innerHTML=`<div class="empty">请先打开任务。</div>`;return}const d={...reportDefaults(),...(currentTask.report_edits||{})};document.getElementById("reportEditor").innerHTML=`<div class="report-grid"><div><div class="report-section"><h3>结论</h3><p class="muted">面向老板和业务方的先行判断，可由 BA 直接改写。</p><textarea id="rep_conclusion">${esc(d.conclusion)}</textarea></div><div class="report-section"><h3>证据</h3><p class="muted">保留指标、假设、贡献度和数据限制，确保结论可追溯。</p><textarea id="rep_evidence">${esc(d.evidence)}</textarea></div><div class="report-section"><h3>行动</h3><p class="muted">拆成短期修复、中期验证、长期沉淀，便于业务落地。</p><textarea id="rep_action">${esc(d.action)}</textarea></div><details class="subtle-panel"><summary><b>补充背景与口径</b></summary><label>背景</label><textarea id="rep_background">${esc(d.background)}</textarea><label>数据口径</label><textarea id="rep_data_scope">${esc(d.data_scope)}</textarea></details></div><div><div class="subtle-panel"><h3>报告预览</h3>${reportPreviewDoc(d)}</div><div class="subtle-panel" style="margin-top:14px"><h3>图表预览</h3>${chartPreview()}</div></div></div>`}
function chartPreview(){const rows=(dataAnalysis?.metrics||[]).slice(0,5);return`<div class="chartbar">${rows.map(r=>`<div><span>${esc(r.name)}</span><div class="bar"><span style="width:${barWidth(r)}%"></span></div><b>${formatChange(r)}</b></div>`).join("")}</div><p class="muted">数值型指标按变化率展示，百分比指标保留百分点/百分比表达。</p>`}
function reportPreviewDoc(d){return`<div class="preview-doc"><h3>${esc(currentTask?.name||"分析报告")}</h3><p><b>结论：</b>${esc(summaryText(d.conclusion,180))}</p><p><b>证据：</b>${esc(summaryText(d.evidence,220))}</p><p><b>行动：</b>${esc(summaryText(d.action,180))}</p></div>`}
function collectReport(){const keys=["conclusion","evidence","action","background","data_scope"];const report=Object.fromEntries(keys.map(k=>[k,document.getElementById(`rep_${k}`)?.value||""]));return{...report,executive_summary:report.conclusion,key_findings:report.evidence,recommendations:report.action}}
async function saveReport(silent=false){const data=await api(`/api/tasks/${currentTask.task_id}/report/update`,{report_edits:collectReport()});currentTask=data.task;if(!silent)alert("报告内容已保存。")}
async function exportReport(){await saveReport(true);const data=await api(`/api/tasks/${currentTask.task_id}/report/export`,{format:"html",report_edits:collectReport()});document.getElementById("exportResult").innerHTML=`已导出：<a href="${data.download_url}" target="_blank">${esc(data.file_name)}</a>`}
function initAbilityState(){const saved=localStorage.getItem("bpba_ability_catalog");if(saved){abilityState=JSON.parse(saved);return}abilityState=[...(catalog.question_types||[]).map(x=>({type:"问题类型",name:x.title,description:`识别业务问题类型，触发分析方法：${(x.default_methods||[]).join(" / ")}`,tags:x.default_methods||[],status:"启用",owner:"Sales BP BA"})),...(catalog.analysis_methods||[]).map(x=>({type:"分析方法",name:x.title,description:x.purpose||"",tags:[...(x.useful_metrics||[]),...(x.useful_dimensions||[])].slice(0,6),status:"启用",owner:"Sales BP BA"})),...(catalog.analysis_topics||[]).map(x=>({type:"Playbook",name:x.title,description:`指标：${(x.core_metrics||[]).slice(0,4).join(" / ")}；维度：${(x.default_dimensions||[]).slice(0,4).join(" / ")}`,tags:[...(x.core_metrics||[]).slice(0,3),...(x.default_dimensions||[]).slice(0,3)],status:"启用",owner:"Sales BP BA"}))]}
function renderCatalog(){if(!catalog)return;const q=(document.getElementById("capSearch")?.value||"").toLowerCase(),f=document.getElementById("capFilter")?.value||"全部能力";const rows=abilityState.filter(x=>(f==="全部能力"||x.type===f)&&(!q||`${x.name} ${x.description} ${(x.tags||[]).join(" ")}`.toLowerCase().includes(q)));const counts=["问题类型","分析方法","Playbook"].map(t=>[t,abilityState.filter(x=>x.type===t).length]);document.getElementById("catalogBody").innerHTML=`<div class="toolbar" style="justify-content:space-between;margin-bottom:14px"><div class="toolbar"><button class="btn" onclick="addLocalCapability()">+ 新增能力</button><button class="btn secondary" onclick="saveAbilityCatalog()">保存能力目录</button><button class="btn secondary" onclick="resetAbilityCatalog()">从系统目录重载</button></div><span class="pill blue">本地可维护</span></div><div class="searchbar"><input id="capSearch" class="input" value="${esc(document.getElementById("capSearch")?.value||"")}" placeholder="搜索能力名称、说明、标签..." oninput="renderCatalog()"><select id="capFilter" onchange="renderCatalog()">${["全部能力","问题类型","分析方法","Playbook"].map(x=>`<option ${f===x?"selected":""}>${x}</option>`).join("")}</select></div><div class="grid4" style="margin:14px 0">${[["能力总数",abilityState.length],...counts].map(([t,n])=>`<div class="card"><span class="muted">${t}</span><h2 style="margin:6px 0">${n}</h2></div>`).join("")}</div>${rows.map((x,i)=>capabilityRow(x,abilityState.indexOf(x))).join("")||'<div class="empty">没有匹配的能力配置。</div>'}`}
function capabilityRow(x,i){return`<div class="card" style="margin-bottom:10px"><div class="hero-row"><div><div class="toolbar"><h3>${esc(x.name)}</h3><span class="pill blue">${esc(x.type)}</span><span class="pill green">${esc(x.status)}</span></div><p class="muted">${esc(x.description)}</p><div class="toolbar">${(x.tags||[]).map(t=>`<span class="pill">${esc(t)}</span>`).join("")}<span class="pill">Owner: ${esc(x.owner||"Sales BP BA")}</span></div></div><button class="btn secondary" onclick="deleteCapability(${i})">删除</button></div><details class="subtle-panel" style="margin-top:12px"><summary><b>维护内容</b></summary><div class="grid2"><label>名称<input class="input" value="${esc(x.name)}" onchange="updateCapability(${i},'name',this.value)"></label><label>类型<select onchange="updateCapability(${i},'type',this.value)">${["问题类型","分析方法","Playbook"].map(t=>`<option ${x.type===t?"selected":""}>${t}</option>`).join("")}</select></label><label>状态<select onchange="updateCapability(${i},'status',this.value)">${["启用","草稿","停用"].map(t=>`<option ${x.status===t?"selected":""}>${t}</option>`).join("")}</select></label><label>Owner<input class="input" value="${esc(x.owner||"")}" onchange="updateCapability(${i},'owner',this.value)"></label></div><label>说明<textarea onchange="updateCapability(${i},'description',this.value)">${esc(x.description)}</textarea></label><label>标签，逗号分隔<input class="input" value="${esc((x.tags||[]).join(","))}" onchange="updateCapability(${i},'tags',this.value.split(',').map(v=>v.trim()).filter(Boolean))"></label></details></div>`}
function addLocalCapability(){abilityState.unshift({type:"分析方法",name:"新增分析能力",description:"描述该能力适用的问题、输入数据和输出结果。",tags:["custom"],status:"草稿",owner:"Sales BP BA"});renderCatalog()}
function updateCapability(i,k,v){abilityState[i][k]=v}
function deleteCapability(i){abilityState.splice(i,1);renderCatalog()}
function saveAbilityCatalog(){localStorage.setItem("bpba_ability_catalog",JSON.stringify(abilityState));alert("能力目录已保存到浏览器本地。")}
function resetAbilityCatalog(){localStorage.removeItem("bpba_ability_catalog");initAbilityState();renderCatalog()}
function initOntologyState(){const saved=localStorage.getItem("bpba_ontology_config");if(saved){ontologyState=JSON.parse(saved);return}const o=semanticState?.semantic_config?.ontology_config||{};ontologyState=[...(o.entities||[]).map(x=>({type:"业务对象",name:x.title,description:x.description,meta:[x.key,...(x.id_fields||[]),...(x.metrics||[])].filter(Boolean),status:"本服务"})),...(o.events||[]).map(x=>({type:"业务事件",name:x.title,description:x.description,meta:[x.key,x.entity,x.time_field,x.flag_field].filter(Boolean),status:"本服务"})),...(o.relationships||[]).map(x=>({type:"对象关系",name:`${x.from} -> ${x.to}`,description:x.description,meta:[x.type,...(x.join_keys||[])].filter(Boolean),status:"本服务"})),...(o.metrics||[]).map(x=>({type:"指标口径",name:x.title,description:x.business_definition,meta:[x.key,x.entity,x.formula].filter(Boolean),status:"本服务"}))]}
function renderOntology(){const q=(document.getElementById("ontoSearch")?.value||"").toLowerCase(),f=document.getElementById("ontoFilter")?.value||"全部配置";const rows=ontologyState.filter(x=>(f==="全部配置"||x.type===f)&&(!q||`${x.name} ${x.description} ${(x.meta||[]).join(" ")}`.toLowerCase().includes(q)));document.getElementById("ontologyStats").innerHTML=["业务对象","业务事件","对象关系","指标口径"].map((t,idx)=>`<div class="card"><span class="muted">${t}</span><h2 style="margin:6px 0;color:var(--${["blue","green","amber","blue"][idx]})">${ontologyState.filter(x=>x.type===t).length}</h2></div>`).join("");document.getElementById("ontologyBody").innerHTML=`<div class="toolbar" style="justify-content:space-between;margin-bottom:14px"><div class="toolbar"><button class="btn" onclick="addOntologyItem()">+ 新增配置</button><button class="btn secondary" onclick="saveOntologyConfig()">保存语义配置</button><button class="btn secondary" onclick="resetOntologyConfig()">从本服务重载</button></div><span class="pill green">8091 本服务提供</span></div><div class="searchbar"><input id="ontoSearch" class="input" value="${esc(document.getElementById("ontoSearch")?.value||"")}" placeholder="搜索对象、指标、字段..." oninput="renderOntology()"><select id="ontoFilter" onchange="renderOntology()">${["全部配置","业务对象","业务事件","对象关系","指标口径"].map(x=>`<option ${f===x?"selected":""}>${x}</option>`).join("")}</select></div><div style="margin-top:14px">${rows.map((x,i)=>ontologyRow(x,ontologyState.indexOf(x))).join("")||'<div class="empty">没有匹配的语义配置。</div>'}</div>`}
function ontologyRow(x,i){return`<div class="card" style="margin-bottom:10px"><div class="hero-row"><div><div class="toolbar"><h3>${esc(x.name)}</h3><span class="pill blue">${esc(x.type)}</span><span class="pill green">${esc(x.status)}</span></div><p class="muted">${esc(x.description)}</p><div class="toolbar">${(x.meta||[]).slice(0,10).map(t=>`<span class="pill">${esc(t)}</span>`).join("")}</div></div><button class="btn secondary" onclick="deleteOntologyItem(${i})">删除</button></div><details class="subtle-panel" style="margin-top:12px"><summary><b>维护内容</b></summary><div class="grid2"><label>名称<input class="input" value="${esc(x.name)}" onchange="updateOntologyItem(${i},'name',this.value)"></label><label>类型<select onchange="updateOntologyItem(${i},'type',this.value)">${["业务对象","业务事件","对象关系","指标口径"].map(t=>`<option ${x.type===t?"selected":""}>${t}</option>`).join("")}</select></label></div><label>说明<textarea onchange="updateOntologyItem(${i},'description',this.value)">${esc(x.description)}</textarea></label><label>字段/关系/口径，逗号分隔<input class="input" value="${esc((x.meta||[]).join(","))}" onchange="updateOntologyItem(${i},'meta',this.value.split(',').map(v=>v.trim()).filter(Boolean))"></label></details></div>`}
function addOntologyItem(){ontologyState.unshift({type:"业务对象",name:"新增语义对象",description:"描述业务对象、事件、关系或指标口径。",meta:["custom_field"],status:"草稿"});renderOntology()}
function updateOntologyItem(i,k,v){ontologyState[i][k]=v}
function deleteOntologyItem(i){ontologyState.splice(i,1);renderOntology()}
function saveOntologyConfig(){localStorage.setItem("bpba_ontology_config",JSON.stringify(ontologyState));alert("Ontology 语义配置已保存到浏览器本地。")}
function resetOntologyConfig(){localStorage.removeItem("bpba_ontology_config");initOntologyState();renderOntology()}
function renderRealData(){if(!realReport?.available){document.getElementById("realDataBody").innerHTML=`<div class="empty">真实 CSV 聚合报告未加载。</div>`;return}const s=realReport.stage_counts||{},r=realReport.conversion_rates||{};document.getElementById("realDataBody").innerHTML=`<div class="grid4">${card("样本行数",Number(realReport.total_rows||0).toLocaleString("zh-CN"),"blue")}${card("字段数",realReport.column_count,"green")}${card("Leads",s.leads||0,"blue")}${card("Order/Leads",(((r.order_per_leads||0)*100).toFixed(1))+"%","amber")}</div><h3>执行摘要</h3>${list(realReport.executive_summary||[])}`}
function statCard(t,b,c){return`<div class="card"><h3>${esc(t)}</h3><p class="muted">${esc(b)}</p></div>`}
function card(t,b,c){return statCard(t,b,c)}
function metricCard(m){const cls=m.trend==="up"?"up":m.trend==="down"?"down":"flat";const pill=m.trend==="up"?"green":m.trend==="down"?"red":"";return`<div class="metric-card ${cls}"><small>${esc(m.dimension||"指标")}</small><span>${esc(m.name)}</span><strong>${formatValue(m.current)}</strong><span class="pill ${pill}">${formatChange(m)} vs 上期</span></div>`}
function formatValue(v){if(typeof v==="number")return Math.abs(v)>=1000?v.toLocaleString("zh-CN"):String(v);return esc(v)}
function formatChange(m){const c=Number(m.change);if(!Number.isFinite(c))return "-";if(Math.abs(c)>300)return c>0?"大幅上升":"大幅下降";const sign=c>0?"+":"";return `${sign}${c.toFixed(Math.abs(c)<10?1:0)}%`}
function barWidth(r){const raw=Math.abs(Number(r.change)||0);return Math.min(100,Math.max(8,(raw>300?80:raw*2+18)))}
function trendText(t){return t==="up"?"上升":t==="down"?"下降":"稳定"}
function frameworkHint(text){if(String(text).includes("假设"))return"把业务解释转成可验证假设。";if(String(text).includes("维度"))return"按渠道、客户、时间、区域等维度拆解贡献。";if(String(text).includes("取数"))return"生成数据口径、SQL 和校验计划。";return"明确边界，避免分析发散。"}
function list(items){return`<ol>${(items||[]).map(x=>`<li>${esc(x)}</li>`).join("")}</ol>`}
function table(headers,rows){return`<table class="table"><thead><tr>${headers.map(h=>`<th>${esc(h)}</th>`).join("")}</tr></thead><tbody>${rows.map(r=>`<tr>${r.map(c=>`<td>${esc(c)}</td>`).join("")}</tr>`).join("")}</tbody></table>`}
function availabilityTable(items){if(!items.length)return"";return`<h3>数据可用性</h3>${table(["需求","状态","说明"],items.map(x=>[x.requirement||x.name||"",x.status||"",x.note||((x.missing_fields||[]).join(" / "))]))}`}
document.querySelectorAll(".nav button").forEach(b=>b.addEventListener("click",()=>setPage(b.dataset.page)));
(async function init(){document.getElementById("health").textContent=(await api("/health")).ok?"service ready":"service unavailable";[catalog,semanticState,realReport]=await Promise.all([api("/api/catalog"),api("/api/semantic-state"),api("/api/real-data-report")]);frameworks=(await api("/api/analysis-frameworks")).frameworks;initAbilityState();initOntologyState();renderDataSourcePicker("demo_csv");document.getElementById("inQuestion")?.addEventListener("input",renderFollowups);document.getElementById("inPurpose")?.addEventListener("input",renderFollowups);renderFollowups();await loadTasks();renderCatalog();renderOntology();renderRealData()})().catch(err=>{document.getElementById("health").textContent=err.message});
</script>
</body>
</html>"""


if __name__ == "__main__":
    main()
