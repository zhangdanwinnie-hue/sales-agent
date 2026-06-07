from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, is_dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .data_source import build_profile
from .llm import (
    AnthropicCompatibleLLMService,
    AnthropicSDKMiniMaxLLMService,
    OpenAICompatibleChatLLMService,
    OpenAIResponsesLLMService,
)
from .orchestrator import BAAnalysisOrchestrator


class ChatAppState:
    def __init__(self, source: Path):
        self.source = source
        self.profile = build_profile(source)
        self.orchestrator = BAAnalysisOrchestrator(self.profile)

    def handle_message(self, message: str) -> dict[str, Any]:
        raw = message.strip()
        if not raw:
            return _reply("请输入业务问题或命令。", kind="text")

        command, _, value = raw.partition(" ")
        normalized = command.lower()

        try:
            if normalized in {"help", "帮助"}:
                return _reply(_help_text(), kind="text")
            if normalized == "llm":
                return _reply("当前 LLM 状态", self.orchestrator.llm_status())
            if normalized == "workflow":
                return _reply("当前工作流配置", self.orchestrator.workflow())
            if normalized == "profile":
                return _reply("当前数据源 profile", _profile_summary(self.profile))
            if normalized == "history":
                return _reply("执行历史", self.orchestrator.history())
            if normalized == "status":
                return _with_session(lambda: _reply("当前任务状态", self.orchestrator.status()))
            if normalized == "show":
                return _with_session(lambda: _reply("当前阶段产出", self.orchestrator.current_artifact()))
            if normalized in {"confirm", "确认", "通过", "approve"}:
                return _with_session(lambda: _reply("已确认当前阶段，进入下一阶段", self.orchestrator.confirm_current()))
            if normalized in {"revise", "修改", "调整"}:
                if not value:
                    return _reply("请在 revise 后输入修改意见，例如：revise 时间范围改为 2026-05。", kind="text")
                return _with_session(lambda: _reply("已理解修改意见并更新当前阶段", self.orchestrator.request_revision(value)))
            if normalized in {"clarify", "澄清", "补充", "回答", "answer"}:
                if not value:
                    return _reply("请在补充命令后输入内容，例如：补充 时间范围是3月，对比2月，按渠道和区域拆解。", kind="text")
                return _with_session(lambda: _reply("已理解 BA 补充并更新当前阶段", self.orchestrator.add_ba_feedback(value)))
            if normalized in {"reject", "拒绝"}:
                if not value:
                    return _reply("请在 reject 后输入拒绝原因。", kind="text")
                return _with_session(lambda: _reply("已拒绝当前阶段", self.orchestrator.reject_current(value)))
            if normalized == "new":
                if not value:
                    return _reply("请输入业务问题，例如：new 分析3月线索到订单转化率下降的原因。", kind="text")
                return _reply("已创建新分析任务", self.orchestrator.start(value))

            if self.orchestrator.session is not None:
                return _reply("已理解 BA 补充并更新当前阶段", self.orchestrator.add_ba_feedback(raw))

            # Natural-language default: start a new analysis when there is no active session.
            return _reply("已创建新分析任务", self.orchestrator.start(raw))
        except Exception as exc:
            text = str(exc)
            return {
                "ok": False,
                "title": "执行失败",
                "kind": "error",
                "text": text,
                "view": {
                    "summary": f"这次请求没有执行成功：{text}",
                    "sections": [{"title": "可以尝试", "items": ["检查当前是否已有分析任务。", "如果是阶段命令，先输入 status 或 show 查看当前状态。"]}],
                    "actions": ["需要重新开始时，直接输入新的业务问题。"],
                },
                "data": None,
            }

    def configure_openai(self, api_key: str, model: str = "gpt-4.1-mini") -> dict[str, Any]:
        return self.configure_llm("openai", api_key, model)

    def configure_llm(self, provider: str, api_key: str, model: str = "") -> dict[str, Any]:
        normalized_provider = provider.strip().lower() or "openai"
        key = _clean_api_key(api_key)
        selected_model = model.strip() or ("MiniMax-M2.7" if normalized_provider.startswith("minimax") else "gpt-4.1-mini")
        if not key:
            return {
                "ok": False,
                "title": "LLM 未启用",
                "kind": "error",
                "text": "API key 为空。",
                "view": {
                    "summary": "API key 为空，所以没有启用 LLM。",
                    "sections": [{"title": "处理方式", "items": ["在页面左侧 LLM 设置里输入 key。", "不要把 key 粘贴到聊天消息里。"]}],
                    "actions": [],
                },
                "data": None,
            }
        try:
            key.encode("ascii")
        except UnicodeEncodeError:
            return {
                "ok": False,
                "title": "LLM 未启用",
                "kind": "error",
                "text": "API key/token 包含非 ASCII 字符。",
                "view": {
                    "summary": "API key/token 里混入了中文、全角符号、空格或换行。请只粘贴 MiniMax 控制台生成的原始 token。",
                    "sections": [{"title": "处理方式", "items": ["不要带说明文字。", "如果复制内容以 Bearer 开头，可以保留，系统会自动去掉。", "重新从 MiniMax 控制台复制完整 token。"]}],
                    "actions": [],
                },
                "data": None,
            }
        if normalized_provider in {"minimax_anthropic_sdk", "minimax-anthropic-sdk", "minimax_sdk", "minimax-sdk"}:
            service = AnthropicSDKMiniMaxLLMService(
                api_key=key,
                model=selected_model,
                base_url="https://api.minimax.io/anthropic",
                timeout_seconds=180,
            )
        elif normalized_provider in {"minimax_cn", "minimax-domestic", "minimax_china"}:
            service = OpenAICompatibleChatLLMService(
                provider_name="minimax_cn",
                api_key=key,
                model=selected_model,
                base_url="https://api.minimaxi.com/v1",
                timeout_seconds=180,
            )
        elif normalized_provider in {"minimax", "minimax_openai"}:
            service = OpenAICompatibleChatLLMService(
                provider_name="minimax",
                api_key=key,
                model=selected_model,
                base_url="https://api.minimaxi.com/v1",
                timeout_seconds=180,
            )
        elif normalized_provider in {"minimax_intl", "minimax-international"}:
            service = OpenAICompatibleChatLLMService(
                provider_name="minimax_intl",
                api_key=key,
                model=selected_model,
                base_url="https://api.minimax.io/v1",
                timeout_seconds=180,
            )
        elif normalized_provider in {"minimax_anthropic", "minimax-anthropic"}:
            service = AnthropicCompatibleLLMService(
                provider_name="minimax_anthropic",
                api_key=key,
                model=selected_model,
                base_url="https://api.minimax.io/anthropic",
                timeout_seconds=180,
            )
        else:
            service = OpenAIResponsesLLMService(api_key=key, model=selected_model, timeout_seconds=180)
        self.orchestrator.llm_service = service
        for workspace_agents in self.orchestrator.agents.values():
            for stage in list(workspace_agents):
                workspace_agents[stage] = None
        return _reply("LLM 已启用", self.orchestrator.llm_status())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="BA analysis agent web chat.")
    parser.add_argument("--source", required=True, help="Path to .xlsx or .csv data source.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args(argv)

    state = ChatAppState(Path(args.source))

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/":
                _send_html(self, INDEX_HTML)
                return
            if parsed.path == "/api/state":
                first_table = state.profile.tables_or_sheets[0] if state.profile.tables_or_sheets else None
                _send_json(
                    self,
                    {
                        "source": str(state.source),
                        "source_type": state.profile.source_type,
                        "table": first_table.name if first_table else None,
                        "rows": first_table.row_count if first_table else None,
                        "columns": len(first_table.columns) if first_table else None,
                        "llm": state.orchestrator.llm_status(),
                    },
                )
                return
            _send_json(self, {"ok": False, "error": "not_found"}, status=404)

        def do_POST(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path != "/api/message":
                if parsed.path == "/api/llm/configure":
                    length = int(self.headers.get("Content-Length", "0"))
                    payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
                    response = state.configure_llm(
                        provider=str(payload.get("provider", "openai")),
                        api_key=str(payload.get("api_key", "")),
                        model=str(payload.get("model", "")),
                    )
                    _send_json(self, response, status=200 if response.get("ok") else 400)
                    return
                _send_json(self, {"ok": False, "error": "not_found"}, status=404)
                return
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
            response = state.handle_message(str(payload.get("message", "")))
            _send_json(self, response)

        def log_message(self, format: str, *args: Any) -> None:
            sys.stderr.write("%s - %s\n" % (self.address_string(), format % args))

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"BA Agent chat page: http://{args.host}:{args.port}", flush=True)
    print(f"Data source: {state.source}", flush=True)
    server.serve_forever()
    return 0


def _with_session(fn):
    try:
        return fn()
    except RuntimeError:
        return _reply("还没有分析任务。请先输入业务问题，例如：分析3月线索到订单转化率下降的原因。", kind="text")


def _clean_api_key(api_key: str) -> str:
    key = api_key.strip()
    if key.lower().startswith("bearer "):
        key = key[7:].strip()
    return "".join(key.split())


def _reply(title: str, data: Any = None, kind: str = "artifact") -> dict[str, Any]:
    jsonable = _jsonable(data)
    return {
        "ok": True,
        "title": title,
        "kind": kind,
        "text": title if data is None else "",
        "view": _build_view(title, jsonable, kind),
        "data": jsonable,
    }


def _profile_summary(profile: Any) -> dict[str, Any]:
    return {
        "source_type": profile.source_type,
        "source_name": profile.source_name,
        "business_domains": profile.business_domains,
        "tables_or_sheets": [
            {
                "name": table.name,
                "row_count": table.row_count,
                "column_count": len(table.columns),
                "sensitive_column_count": sum(1 for column in table.columns if column.is_sensitive),
            }
            for table in profile.tables_or_sheets
        ],
    }


def _help_text() -> str:
    return (
        "直接输入业务问题即可开始，例如：分析3月线索到订单转化率下降的原因。\n"
        "已有任务等待确认时，直接输入自然语言会作为当前阶段的 BA 补充。\n"
        "也支持命令：new <问题>、show、confirm、补充 <内容>、revise <意见>、reject <原因>、"
        "status、history、workflow、llm、profile。"
    )


def _build_view(title: str, data: Any, kind: str) -> dict[str, Any] | None:
    if kind == "text" or data is None:
        return None
    if isinstance(data, dict) and "payload" in data and "stage" in data:
        return _artifact_view(data)
    if isinstance(data, dict) and {"provider", "enabled", "data_boundary"} <= set(data):
        return {
            "summary": f"当前 LLM provider 是 {data.get('provider')}，{'已启用' if data.get('enabled') else '未启用'}。",
            "sections": [
                {
                    "title": "运行状态",
                    "items": [
                        f"Provider: {data.get('provider')}",
                        f"隐私边界: {data.get('data_boundary')}",
                        f"最近错误: {data.get('last_error') or '无'}",
                    ],
                }
            ],
            "actions": ["如果需要真实 LLM 增强，请用 run_agent_web.ps1 -Provider openai 启动。"],
        }
    if isinstance(data, dict) and "active_stage" in data:
        return {
            "summary": f"当前任务停在 {data.get('active_stage')}，状态为 {data.get('agent_state')}。",
            "sections": [
                {"title": "任务", "items": [str(data.get("business_question", ""))]},
                {"title": "阶段状态", "items": [f"{key}: {value}" for key, value in data.get("stages", {}).items()]},
            ],
            "actions": ["确认当前阶段可输入 confirm；需要补充口径时直接输入自然语言，或输入 revise <修改意见>。"],
        }
    if isinstance(data, dict) and "tables_or_sheets" in data:
        return {
            "summary": "当前数据源 profile 已加载，Agent 只会把字段元数据用于分析规划。",
            "sections": [
                {"title": "业务域", "items": data.get("business_domains", [])},
                {
                    "title": "表/Sheet",
                    "items": [
                        f"{item.get('name')}: {item.get('row_count')} rows, {item.get('column_count')} columns, {item.get('sensitive_column_count')} sensitive columns"
                        for item in data.get("tables_or_sheets", [])
                    ],
                },
            ],
            "actions": ["可以直接输入业务问题开始分析。"],
        }
    return {
        "summary": title,
        "sections": [],
        "actions": [],
    }


def _artifact_view(artifact: dict[str, Any]) -> dict[str, Any]:
    stage = artifact.get("stage")
    status = artifact.get("status")
    payload = artifact.get("payload", {})
    if not isinstance(payload, dict):
        return {"summary": f"{stage} 已生成。", "sections": [], "actions": []}

    if stage == "analysis_design":
        return _with_feedback_section(_analysis_design_view(status, payload), payload)
    if stage == "data_plan":
        return _with_feedback_section(_data_plan_view(status, payload), payload)
    if stage == "insight_review":
        return {
            "summary": "取数计划已确认，下一步需要 BA 补充或确认数据结果，再沉淀洞察卡片。",
            "sections": [
                {"title": "需要输入", "items": payload.get("required_input", [])},
                {"title": "洞察卡片模板", "items": _dict_items(payload.get("insight_card_template", {}))},
            ],
            "actions": ["补充数据结果后输入 confirm 进入报告产出阶段。"],
        }
    if stage == "report_plan":
        return {
            "summary": "报告结构已生成，可以检查结论摘要、PPT 故事线、Excel tabs 和 BRD 结构。",
            "sections": [
                {"title": "结论摘要", "items": [item.get("text", str(item)) for item in payload.get("executive_summary", [])]},
                {"title": "PPT 故事线", "items": payload.get("ppt_storyline", [])},
                {"title": "Excel tabs", "items": payload.get("excel_tabs", [])},
                {"title": "发布前检查", "items": payload.get("final_review_checklist", [])},
            ],
            "actions": ["确认无误输入 confirm；需要调整输入 revise <修改意见>。"],
        }
    if stage == "final_review":
        return {
            "summary": "进入发布前最终审核，重点检查口径、敏感信息和结论标注。",
            "sections": [{"title": "审核项", "items": payload.get("checklist", [])}],
            "actions": ["全部通过后输入 confirm 完成工作流。"],
        }
    return {"summary": f"{stage} 已生成，当前状态 {status}。", "sections": [], "actions": ["输入 confirm 进入下一阶段。"]}


def _analysis_design_view(status: str, payload: dict[str, Any]) -> dict[str, Any]:
    intent = payload.get("detected_intent", {})
    analysis_context = payload.get("analysis_context", {})
    playbook = payload.get("playbook_guidance", {})
    llm = payload.get("llm_enrichment", {})
    hypotheses = payload.get("business_hypotheses", [])[:6]
    metrics = payload.get("metrics_tree", [])

    purpose = payload.get("analysis_purpose") or "已生成分析设计。"
    summary = (
        f"我先把这个问题拆成一版分析设计草稿：{purpose} "
        "下面重点看 BA 需要确认的口径、可能影响问题的业务因素、指标树和分析路径。"
    )
    sections = [
        {
            "title": "当前理解",
            "items": _analysis_context_items(analysis_context),
        },
        {
            "title": "识别到的问题意图",
            "items": [
                f"时间范围: {intent.get('time_period') or '待确认'}",
                f"漏斗阶段: {_join(intent.get('mentioned_stages')) or '未指定，默认全漏斗'}",
                f"关注维度: {_join(intent.get('focus_dimensions')) or '待确认'}",
                f"问题类型: {intent.get('issue_type')}",
                f"指标焦点: {intent.get('metric_focus')}",
            ],
        },
        {"title": "需要 BA 澄清", "items": payload.get("clarification_questions", [])},
        {
            "title": "业务假设",
            "items": [
                f"{item.get('factor')}: {item.get('hypothesis')}"
                for item in hypotheses
                if isinstance(item, dict)
            ],
        },
        {
            "title": "指标树",
            "items": [
                f"{item.get('name')}: {_metric_preview(item.get('metrics'))}"
                for item in metrics
                if isinstance(item, dict)
            ],
        },
        {"title": "分析路径", "items": payload.get("analysis_path", [])[:8]},
    ]

    matched_topics = playbook.get("matched_topics", []) if isinstance(playbook, dict) else []
    if matched_topics:
        sections.insert(
            1,
            {
                "title": "匹配的 Playbook 章节",
                "items": [topic.get("title", "") for topic in matched_topics],
            },
        )

    actions = ["如果这版分析设计方向正确，输入 confirm；如果要回答澄清问题，直接输入自然语言或“补充 <内容>”；需要改稿输入 revise <修改意见>。"]
    if llm.get("status") != "applied":
        actions.append(f"LLM 未增强：{llm.get('error') or '未启用或调用失败'}")
    return {"summary": summary, "sections": sections, "actions": actions}


def _analysis_context_items(value: Any) -> list[str]:
    if not isinstance(value, dict):
        return []
    funnel = value.get("funnel_scope", {}) if isinstance(value.get("funnel_scope"), dict) else {}
    scope = "到".join([item for item in [funnel.get("start_stage"), funnel.get("end_stage")] if item])
    return [
        f"业务问题: {value.get('business_question') or '待确认'}",
        f"核心指标: {value.get('metric') or '待确认'}",
        f"时间范围: {value.get('time_range') or '待确认'}",
        f"对比基准: {value.get('comparison_baseline') or '待确认'}",
        f"漏斗范围: {scope or _join(funnel.get('mentioned_stages')) or '待确认'}",
        f"拆解维度: {_join(value.get('dimensions')) or '待确认'}",
        f"过滤口径: {_join(value.get('filters')) or '待确认'}",
        f"报告对象: {value.get('audience') or '待确认'}",
    ]


def _data_plan_view(status: str, payload: dict[str, Any]) -> dict[str, Any]:
    source_plan = payload.get("data_source_plan", {})
    sql_plan = payload.get("sql_plan", {})
    quality = payload.get("data_quality_report", {})
    insight_cards = payload.get("insight_cards", [])
    sql_queries = sql_plan.get("sql_queries", []) if isinstance(sql_plan, dict) else []
    sections = [
        {
            "title": "数据源计划",
            "items": [
                f"主表/Sheet: {source_plan.get('primary_table_or_sheet')}",
                f"隐私策略: {source_plan.get('privacy_policy')}",
                f"已映射字段数: {len(source_plan.get('mapped_fields', []))}",
                f"缺失字段数: {len(source_plan.get('unmapped_fields', []))}",
            ],
        },
        {
            "title": "取数计划",
            "items": [
                f"{item.get('name')}: {item.get('purpose')}"
                for item in sql_queries
                if isinstance(item, dict)
            ],
        },
        {"title": "需要确认的过滤条件", "items": sql_plan.get("filters_to_confirm", []) if isinstance(sql_plan, dict) else []},
        {"title": "数据校验计划", "items": quality.get("checks", []) if isinstance(quality, dict) else []},
        {
            "title": "初步洞察卡片",
            "items": [
                f"{item.get('title')}: {item.get('summary')}"
                for item in insight_cards
                if isinstance(item, dict)
            ],
        },
    ]
    return {
        "summary": "我已经把已确认的分析设计转成数据执行方案：包括数据源映射、SQL/取数计划、校验计划和第一批待验证洞察卡片。",
        "sections": sections,
        "actions": ["如果 SQL 和口径可接受，输入 confirm 进入洞察确认；需要调整输入 revise <修改意见>。"],
    }


def _with_feedback_section(view: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    feedback_items = _feedback_items(payload.get("ba_feedback", []))
    if not feedback_items:
        return view
    updated = dict(view)
    sections = list(updated.get("sections", []))
    sections.insert(1, {"title": "BA 已补充/修改", "items": feedback_items})
    updated["sections"] = sections
    return updated


def _feedback_items(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    items = []
    for item in value:
        if isinstance(item, dict):
            label = "修改意见" if item.get("type") == "revision" else "补充说明"
            text = item.get("text", "")
            if text:
                items.append(f"{label}: {text}")
        elif item:
            items.append(str(item))
    return items


def _join(value: Any) -> str:
    if isinstance(value, list):
        return "、".join(str(item) for item in value)
    return str(value or "")


def _metric_preview(value: Any) -> str:
    if isinstance(value, list):
        names = []
        for item in value[:5]:
            if isinstance(item, dict):
                names.append(str(item.get("stage") or item.get("name") or item))
            else:
                names.append(str(item))
        return "、".join(names)
    return str(value)


def _dict_items(value: Any) -> list[str]:
    if not isinstance(value, dict):
        return []
    return [f"{key}: {item}" for key, item in value.items()]


def _jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return _jsonable(asdict(value))
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    return value


def _send_json(handler: BaseHTTPRequestHandler, payload: Any, status: int = 200) -> None:
    body = json.dumps(_jsonable(payload), ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _send_html(handler: BaseHTTPRequestHandler, html: str) -> None:
    body = html.encode("utf-8")
    handler.send_response(200)
    handler.send_header("Content-Type", "text/html; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


INDEX_HTML = r"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>BA Analysis Agent</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f6f7f9;
      --panel: #ffffff;
      --ink: #1f2933;
      --muted: #667085;
      --line: #d9dee7;
      --accent: #0f766e;
      --accent-dark: #115e59;
      --soft: #e9f7f5;
      --danger: #b42318;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font-family: "Segoe UI", system-ui, -apple-system, BlinkMacSystemFont, sans-serif;
      font-size: 14px;
    }
    .app {
      height: 100vh;
      display: grid;
      grid-template-columns: 320px minmax(0, 1fr);
    }
    aside {
      border-right: 1px solid var(--line);
      background: #fbfcfe;
      padding: 18px;
      overflow: auto;
    }
    main {
      display: grid;
      grid-template-rows: auto 1fr auto;
      min-width: 0;
      height: 100vh;
    }
    header {
      background: var(--panel);
      border-bottom: 1px solid var(--line);
      padding: 16px 22px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
    }
    h1 {
      margin: 0;
      font-size: 18px;
      font-weight: 650;
    }
    .sub {
      margin-top: 4px;
      color: var(--muted);
      font-size: 13px;
    }
    .status {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      justify-content: flex-end;
    }
    .pill {
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 5px 9px;
      background: #fff;
      color: var(--muted);
      font-size: 12px;
      white-space: nowrap;
    }
    .pill.ok { color: var(--accent-dark); background: var(--soft); border-color: #b9e7df; }
    .sidebar-title {
      font-weight: 650;
      margin: 0 0 12px;
    }
    .info {
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
      padding: 12px;
      margin-bottom: 14px;
    }
    .info dl { margin: 0; }
    .info dt { color: var(--muted); font-size: 12px; margin-top: 8px; }
    .info dd { margin: 2px 0 0; word-break: break-word; }
    .quick {
      display: grid;
      gap: 8px;
    }
    .llm-settings {
      display: grid;
      gap: 8px;
      margin-bottom: 14px;
    }
    .llm-settings input {
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 9px 10px;
      font: inherit;
      background: #fff;
    }
    .llm-settings select {
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 9px 10px;
      font: inherit;
      background: #fff;
    }
    button {
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
      color: var(--ink);
      padding: 9px 10px;
      cursor: pointer;
      font: inherit;
      text-align: left;
    }
    button:hover { border-color: #9fb2c8; background: #f8fafc; }
    button.primary {
      border-color: var(--accent);
      background: var(--accent);
      color: white;
      text-align: center;
      font-weight: 600;
    }
    button.primary:hover { background: var(--accent-dark); }
    #messages {
      overflow: auto;
      padding: 22px;
      display: flex;
      flex-direction: column;
      gap: 14px;
    }
    .msg {
      max-width: min(980px, 92%);
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
      padding: 13px 14px;
      line-height: 1.55;
    }
    .msg.user {
      align-self: flex-end;
      background: #eef6ff;
      border-color: #cfe5ff;
    }
    .msg.agent { align-self: flex-start; }
    .msg.error { border-color: #f4b4ad; color: var(--danger); }
    .msg-title {
      font-weight: 650;
      margin-bottom: 8px;
    }
    .summary-text {
      margin: 0 0 12px;
      color: #273444;
    }
    .section-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
      gap: 10px;
      margin-top: 10px;
    }
    .section-card {
      border: 1px solid #e3e8ef;
      border-radius: 8px;
      background: #fbfcfe;
      padding: 11px 12px;
      min-width: 0;
    }
    .section-card h3 {
      margin: 0 0 8px;
      font-size: 13px;
      font-weight: 650;
      color: #344054;
    }
    .item-list {
      margin: 0;
      padding-left: 18px;
      color: #2f3b4a;
    }
    .item-list li {
      margin: 5px 0;
      word-break: break-word;
    }
    .actions {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 12px;
    }
    .action-chip {
      border: 1px solid #c9e8e2;
      border-radius: 999px;
      background: var(--soft);
      color: var(--accent-dark);
      padding: 5px 9px;
      font-size: 12px;
      line-height: 1.35;
    }
    pre {
      margin: 8px 0 0;
      white-space: pre-wrap;
      word-break: break-word;
      background: #111827;
      color: #e5e7eb;
      border-radius: 8px;
      padding: 12px;
      max-height: 460px;
      overflow: auto;
      font-size: 12px;
      line-height: 1.5;
    }
    details {
      margin-top: 8px;
    }
    summary {
      cursor: pointer;
      color: var(--accent-dark);
      font-weight: 600;
    }
    form {
      background: var(--panel);
      border-top: 1px solid var(--line);
      padding: 14px 18px;
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 10px;
    }
    textarea {
      min-height: 46px;
      max-height: 150px;
      resize: vertical;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 11px 12px;
      font: inherit;
      line-height: 1.45;
    }
    @media (max-width: 820px) {
      .app { grid-template-columns: 1fr; }
      aside { display: none; }
      header { align-items: flex-start; flex-direction: column; }
      .status { justify-content: flex-start; }
      form { grid-template-columns: 1fr; }
      .msg { max-width: 100%; }
    }
  </style>
</head>
<body>
  <div class="app">
    <aside>
      <p class="sidebar-title">数据源</p>
      <section class="info">
        <dl id="sourceInfo">
          <dt>状态</dt><dd>加载中...</dd>
        </dl>
      </section>
      <p class="sidebar-title">快捷操作</p>
      <div class="quick">
        <button data-send="llm">查看 LLM 状态</button>
        <button data-send="status">查看任务状态</button>
        <button data-send="show">查看当前产出</button>
        <button data-send="confirm">确认当前阶段</button>
        <button data-send="workflow">查看工作流</button>
        <button data-send="profile">查看数据源概况</button>
      </div>
      <p class="sidebar-title" style="margin-top: 18px;">LLM 设置</p>
      <section class="llm-settings">
        <select id="llmProviderInput" aria-label="LLM provider">
          <option value="openai">OpenAI</option>
          <option value="minimax_cn">MiniMax 国内版 Token Plan</option>
          <option value="minimax_anthropic_sdk">MiniMax Anthropic SDK</option>
          <option value="minimax_anthropic">MiniMax Anthropic-compatible</option>
          <option value="minimax">MiniMax OpenAI-compatible 国内版</option>
          <option value="minimax_intl">MiniMax OpenAI-compatible 国际版</option>
        </select>
        <input id="llmKeyInput" type="password" autocomplete="off" placeholder="API key / token（仅本地会话）" />
        <input id="llmModelInput" type="text" value="gpt-4.1-mini" aria-label="OpenAI model" />
        <button id="enableLlmButton" type="button">启用 LLM</button>
      </section>
    </aside>
    <main>
      <header>
        <div>
          <h1>BA Analysis Agent</h1>
          <div class="sub">输入业务问题，逐步确认分析设计、取数计划、洞察和报告结构。</div>
        </div>
        <div class="status" id="statusPills"></div>
      </header>
      <section id="messages"></section>
      <form id="chatForm">
        <textarea id="messageInput" placeholder="例如：分析3月线索到订单转化率下降的原因；等待确认时可直接回复：时间范围是3月，对比2月，按渠道拆"></textarea>
        <button class="primary" type="submit">发送</button>
      </form>
    </main>
  </div>
  <script>
    const messages = document.getElementById('messages');
    const form = document.getElementById('chatForm');
    const input = document.getElementById('messageInput');
    const sourceInfo = document.getElementById('sourceInfo');
    const statusPills = document.getElementById('statusPills');
    const llmProviderInput = document.getElementById('llmProviderInput');
    const llmKeyInput = document.getElementById('llmKeyInput');
    const llmModelInput = document.getElementById('llmModelInput');
    const enableLlmButton = document.getElementById('enableLlmButton');

    function addMessage(role, title, content, kind = 'artifact') {
      const box = document.createElement('div');
      box.className = `msg ${role} ${kind === 'error' ? 'error' : ''}`;
      const heading = document.createElement('div');
      heading.className = 'msg-title';
      heading.textContent = title;
      box.appendChild(heading);

      const hasView = content && typeof content === 'object' && content.view;
      if (hasView) {
        renderView(box, content.view);
        if (content.data) {
          renderJsonDetails(box, content.data, false);
        }
      } else if (content && typeof content === 'object' && content.text && !content.data) {
        const text = document.createElement('div');
        text.textContent = content.text;
        box.appendChild(text);
      } else if (content && typeof content === 'object') {
        renderJsonDetails(box, content, true);
      } else if (content) {
        const text = document.createElement('div');
        text.textContent = content;
        box.appendChild(text);
      }
      messages.appendChild(box);
      messages.scrollTop = messages.scrollHeight;
    }

    function renderView(box, view) {
      if (view.summary) {
        const summary = document.createElement('p');
        summary.className = 'summary-text';
        summary.textContent = view.summary;
        box.appendChild(summary);
      }

      const sections = Array.isArray(view.sections) ? view.sections.filter(Boolean) : [];
      if (sections.length) {
        const grid = document.createElement('div');
        grid.className = 'section-grid';
        sections.forEach((section) => {
          const card = document.createElement('section');
          card.className = 'section-card';
          const title = document.createElement('h3');
          title.textContent = section.title || '信息';
          card.appendChild(title);
          const items = Array.isArray(section.items) ? section.items : [];
          if (items.length) {
            const list = document.createElement('ul');
            list.className = 'item-list';
            items.forEach((item) => {
              const li = document.createElement('li');
              li.textContent = formatItem(item);
              list.appendChild(li);
            });
            card.appendChild(list);
          } else {
            const empty = document.createElement('div');
            empty.className = 'sub';
            empty.textContent = '暂无内容';
            card.appendChild(empty);
          }
          grid.appendChild(card);
        });
        box.appendChild(grid);
      }

      const actions = Array.isArray(view.actions) ? view.actions : [];
      if (actions.length) {
        const wrap = document.createElement('div');
        wrap.className = 'actions';
        actions.forEach((action) => {
          const chip = document.createElement('span');
          chip.className = 'action-chip';
          chip.textContent = action;
          wrap.appendChild(chip);
        });
        box.appendChild(wrap);
      }
    }

    function renderJsonDetails(box, data, open) {
      const details = document.createElement('details');
      details.open = open;
      const summary = document.createElement('summary');
      summary.textContent = open ? '结构化输出' : '技术详情';
      const pre = document.createElement('pre');
      pre.textContent = JSON.stringify(data, null, 2);
      details.appendChild(summary);
      details.appendChild(pre);
      box.appendChild(details);
    }

    function formatItem(item) {
      if (item === null || item === undefined) return '';
      if (typeof item === 'string') return item;
      if (typeof item === 'number' || typeof item === 'boolean') return String(item);
      return JSON.stringify(item);
    }

    async function sendMessage(message) {
      addMessage('user', message, null, 'text');
      input.value = '';
      const pending = document.createElement('div');
      pending.className = 'msg agent';
      pending.textContent = '处理中...';
      messages.appendChild(pending);
      messages.scrollTop = messages.scrollHeight;
      try {
        const res = await fetch('/api/message', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message })
        });
        const payload = await res.json();
        pending.remove();
        addMessage('agent', payload.title || 'Agent', {
          view: payload.view,
          data: payload.data,
          text: payload.text
        }, payload.kind);
      } catch (err) {
        pending.remove();
        addMessage('agent', '请求失败', String(err), 'error');
      }
    }

    form.addEventListener('submit', (event) => {
      event.preventDefault();
      const message = input.value.trim();
      if (message) sendMessage(message);
    });

    document.querySelectorAll('[data-send]').forEach((button) => {
      button.addEventListener('click', () => sendMessage(button.dataset.send));
    });

    enableLlmButton.addEventListener('click', async () => {
      const provider = llmProviderInput.value;
      const apiKey = llmKeyInput.value.trim();
      const model = llmModelInput.value.trim() || (provider.startsWith('minimax') ? 'MiniMax-M2.7' : 'gpt-4.1-mini');
      if (!apiKey) {
        addMessage('agent', 'LLM 未启用', '请在左侧输入 API key/token。不要把 key 发到聊天消息里。', 'error');
        return;
      }
      enableLlmButton.disabled = true;
      try {
        const res = await fetch('/api/llm/configure', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ provider, api_key: apiKey, model })
        });
        llmKeyInput.value = '';
        const payload = await res.json();
        addMessage('agent', payload.title || 'LLM 设置', {
          view: payload.view,
          data: payload.data,
          text: payload.text
        }, payload.kind);
        refreshState();
      } catch (err) {
        addMessage('agent', 'LLM 设置失败', String(err), 'error');
      } finally {
        enableLlmButton.disabled = false;
      }
    });

    llmProviderInput.addEventListener('change', () => {
      if (llmProviderInput.value.startsWith('minimax') && llmModelInput.value === 'gpt-4.1-mini') {
        llmModelInput.value = 'MiniMax-M2.7';
      }
      if (llmProviderInput.value === 'openai' && llmModelInput.value === 'MiniMax-M2.7') {
        llmModelInput.value = 'gpt-4.1-mini';
      }
    });

    input.addEventListener('keydown', (event) => {
      if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) {
        form.requestSubmit();
      }
    });

    async function init() {
      await refreshState();
      addMessage('agent', '已连接 BA Analysis Agent', '直接输入业务问题即可开始。也可以输入 help 查看命令。', 'text');
    }

    async function refreshState() {
      const res = await fetch('/api/state');
      const state = await res.json();
      sourceInfo.innerHTML = `
        <dt>文件</dt><dd>${escapeHtml(state.source)}</dd>
        <dt>类型</dt><dd>${state.source_type}</dd>
        <dt>Sheet/Table</dt><dd>${state.table || '-'}</dd>
        <dt>规模</dt><dd>${state.rows || 0} rows / ${state.columns || 0} columns</dd>
      `;
      statusPills.innerHTML = `
        <span class="pill ${state.llm.enabled ? 'ok' : ''}">LLM: ${state.llm.provider}</span>
        <span class="pill">Privacy: ${state.llm.data_boundary}</span>
      `;
    }

    function escapeHtml(value) {
      return String(value).replace(/[&<>"']/g, (char) => ({
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
      }[char]));
    }

    init();
  </script>
</body>
</html>
"""


if __name__ == "__main__":
    raise SystemExit(main())
