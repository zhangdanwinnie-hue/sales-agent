from __future__ import annotations

import json
import os
import re
import socket
import urllib.error
import urllib.request
from dataclasses import asdict, is_dataclass
from typing import Any, Protocol

from .models import DataSourceProfile


class LLMService(Protocol):
    provider_name: str

    def enhance_artifact(
        self,
        stage_id: str,
        business_problem: str,
        base_artifact: dict[str, Any],
        safe_context: dict[str, Any],
    ) -> dict[str, Any] | None:
        ...


class DisabledLLMService:
    provider_name = "disabled"
    last_error = "LLM provider is disabled or OPENAI_API_KEY is not configured."

    def enhance_artifact(
        self,
        stage_id: str,
        business_problem: str,
        base_artifact: dict[str, Any],
        safe_context: dict[str, Any],
    ) -> dict[str, Any] | None:
        return None


class OpenAIResponsesLLMService:
    provider_name = "openai_responses"

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4.1-mini",
        base_url: str = "https://api.openai.com/v1/responses",
        timeout_seconds: int = 180,
    ):
        self.api_key = _normalize_api_key(api_key)
        self.model = model
        self.base_url = base_url
        self.timeout_seconds = timeout_seconds
        self.last_error: str | None = None

    def enhance_artifact(
        self,
        stage_id: str,
        business_problem: str,
        base_artifact: dict[str, Any],
        safe_context: dict[str, Any],
    ) -> dict[str, Any] | None:
        prompt = _build_prompt(stage_id, business_problem, base_artifact, safe_context)
        key_error = _api_key_error(self.api_key)
        if key_error:
            self.last_error = key_error
            return None
        payload = {
            "model": self.model,
            "input": [
                {
                    "role": "developer",
                    "content": [
                        {
                            "type": "input_text",
                            "text": _developer_prompt(stage_id),
                        }
                    ],
                },
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": prompt}],
                },
            ],
            "text": {"format": {"type": "json_object"}},
        }
        request = urllib.request.Request(
            self.base_url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        self.last_error = None
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                response_data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            self.last_error = f"HTTP {exc.code}: {detail[:500]}"
            return None
        except (urllib.error.URLError, TimeoutError, socket.timeout, json.JSONDecodeError, UnicodeEncodeError) as exc:
            self.last_error = _request_error_text(exc)
            return None

        text = _extract_response_text(response_data)
        if not text:
            self.last_error = "OpenAI response did not include output text."
            return None
        data = parse_json_object(text)
        if not isinstance(data, dict):
            self.last_error = "OpenAI response was not a JSON object."
            return None
        return data


class OpenAICompatibleChatLLMService:
    def __init__(
        self,
        provider_name: str,
        api_key: str,
        model: str,
        base_url: str,
        timeout_seconds: int = 180,
    ):
        self.provider_name = provider_name
        self.api_key = _normalize_api_key(api_key)
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.last_error: str | None = None

    def enhance_artifact(
        self,
        stage_id: str,
        business_problem: str,
        base_artifact: dict[str, Any],
        safe_context: dict[str, Any],
    ) -> dict[str, Any] | None:
        prompt = _build_prompt(stage_id, business_problem, base_artifact, safe_context)
        key_error = _api_key_error(self.api_key)
        if key_error:
            self.last_error = key_error
            return None
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": _developer_prompt(stage_id),
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            "temperature": 0.2,
            "max_tokens": 6144,
            "max_completion_tokens": 6144,
        }
        request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        self.last_error = None
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                response_data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            self.last_error = f"HTTP {exc.code}: {detail[:500]}"
            return None
        except (urllib.error.URLError, TimeoutError, socket.timeout, json.JSONDecodeError, UnicodeEncodeError) as exc:
            self.last_error = _request_error_text(exc)
            return None

        text = _extract_chat_completion_text(response_data)
        if not text:
            self.last_error = f"{self.provider_name} response did not include message content."
            return None
        data = parse_json_object(_strip_thinking(text))
        if not isinstance(data, dict):
            data = self._retry_json_only(stage_id, prompt)
            if isinstance(data, dict):
                return data
            self.last_error = f"{self.provider_name} response was not a JSON object. Preview: {_preview_text(text)}"
            return None
        return data

    def _retry_json_only(self, stage_id: str, original_prompt: str) -> dict[str, Any] | None:
        retry_payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        _developer_prompt(stage_id)
                        + "\nReturn ONLY a valid JSON object. Do not include <think>, Markdown, explanations, or code fences."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        "Your previous answer was not valid JSON. Regenerate the answer as one valid JSON object only.\n\n"
                        + original_prompt
                    ),
                },
            ],
            "temperature": 0.0,
            "max_tokens": 6144,
            "max_completion_tokens": 6144,
        }
        request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(retry_payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                response_data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            self.last_error = f"Retry HTTP {exc.code}: {detail[:500]}"
            return None
        except (urllib.error.URLError, TimeoutError, socket.timeout, json.JSONDecodeError, UnicodeEncodeError) as exc:
            self.last_error = f"Retry failed: {_request_error_text(exc)}"
            return None
        return parse_json_object(_extract_chat_completion_text(response_data))


class AnthropicCompatibleLLMService:
    def __init__(
        self,
        provider_name: str,
        api_key: str,
        model: str,
        base_url: str,
        timeout_seconds: int = 180,
    ):
        self.provider_name = provider_name
        self.api_key = _normalize_api_key(api_key)
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.last_error: str | None = None

    def enhance_artifact(
        self,
        stage_id: str,
        business_problem: str,
        base_artifact: dict[str, Any],
        safe_context: dict[str, Any],
    ) -> dict[str, Any] | None:
        prompt = _build_prompt(stage_id, business_problem, base_artifact, safe_context)
        key_error = _api_key_error(self.api_key)
        if key_error:
            self.last_error = key_error
            return None
        payload = {
            "model": self.model,
            "max_tokens": 6144,
            "temperature": 0.2,
            "system": _developer_prompt(stage_id),
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
        }
        request = urllib.request.Request(
            f"{self.base_url}/v1/messages",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "X-Api-Key": self.api_key,
                "Content-Type": "application/json",
            },
            method="POST",
        )
        self.last_error = None
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                response_data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            self.last_error = f"HTTP {exc.code}: {detail[:500]}"
            return None
        except (urllib.error.URLError, TimeoutError, socket.timeout, json.JSONDecodeError, UnicodeEncodeError) as exc:
            self.last_error = _request_error_text(exc)
            return None

        text = _extract_anthropic_text(response_data)
        if not text:
            self.last_error = f"{self.provider_name} response did not include text content."
            return None
        data = parse_json_object(_strip_thinking(text))
        if not isinstance(data, dict):
            self.last_error = f"{self.provider_name} response was not a JSON object."
            return None
        return data


class AnthropicSDKMiniMaxLLMService:
    provider_name = "minimax_anthropic_sdk"

    def __init__(
        self,
        api_key: str,
        model: str = "MiniMax-M2.7",
        base_url: str = "https://api.minimax.io/anthropic",
        timeout_seconds: int = 180,
    ):
        self.api_key = _normalize_api_key(api_key)
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.last_error: str | None = None

    def enhance_artifact(
        self,
        stage_id: str,
        business_problem: str,
        base_artifact: dict[str, Any],
        safe_context: dict[str, Any],
    ) -> dict[str, Any] | None:
        prompt = _build_prompt(stage_id, business_problem, base_artifact, safe_context)
        key_error = _api_key_error(self.api_key)
        if key_error:
            self.last_error = key_error
            return None
        try:
            from anthropic import Anthropic
        except ImportError:
            self.last_error = "anthropic package is not installed. Run: pip install anthropic"
            return None

        self.last_error = None
        try:
            client = Anthropic(
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=self.timeout_seconds,
            )
            response = client.messages.create(
                model=self.model,
                max_tokens=6144,
                temperature=0.2,
                system=_developer_prompt(stage_id),
                messages=[
                    {
                        "role": "user",
                        "content": [{"type": "text", "text": prompt}],
                    }
                ],
            )
        except Exception as exc:
            self.last_error = _sdk_error_text(exc)
            return None

        text = _extract_anthropic_sdk_text(response)
        if not text:
            self.last_error = "MiniMax Anthropic SDK response did not include text content."
            return None
        data = parse_json_object(_strip_thinking(text))
        if not isinstance(data, dict):
            self.last_error = "MiniMax Anthropic SDK response was not a JSON object."
            return None
        return data


def create_llm_service() -> LLMService:
    provider = os.getenv("BA_AGENT_LLM_PROVIDER", "auto").strip().lower()
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if provider in {"none", "disabled", "off"}:
        return DisabledLLMService()
    if provider == "minimax":
        minimax_key = os.getenv("MINIMAX_API_KEY", "").strip() or os.getenv("BA_AGENT_MINIMAX_API_KEY", "").strip()
        if minimax_key:
            return OpenAICompatibleChatLLMService(
                provider_name="minimax",
                api_key=minimax_key,
                model=os.getenv("BA_AGENT_MINIMAX_MODEL", "MiniMax-M2.7"),
                base_url=os.getenv("BA_AGENT_MINIMAX_BASE_URL", "https://api.minimaxi.com/v1"),
                timeout_seconds=int(os.getenv("BA_AGENT_LLM_TIMEOUT_SECONDS", "180")),
            )
        return DisabledLLMService()
    if provider in {"minimax_intl", "minimax-international"}:
        minimax_key = os.getenv("MINIMAX_API_KEY", "").strip() or os.getenv("BA_AGENT_MINIMAX_API_KEY", "").strip()
        if minimax_key:
            return OpenAICompatibleChatLLMService(
                provider_name="minimax_intl",
                api_key=minimax_key,
                model=os.getenv("BA_AGENT_MINIMAX_MODEL", "MiniMax-M2.7"),
                base_url=os.getenv("BA_AGENT_MINIMAX_BASE_URL", "https://api.minimax.io/v1"),
                timeout_seconds=int(os.getenv("BA_AGENT_LLM_TIMEOUT_SECONDS", "180")),
            )
        return DisabledLLMService()
    if provider in {"minimax_anthropic", "minimax-anthropic"}:
        minimax_key = os.getenv("MINIMAX_API_KEY", "").strip() or os.getenv("BA_AGENT_MINIMAX_API_KEY", "").strip()
        if minimax_key:
            return AnthropicCompatibleLLMService(
                provider_name="minimax_anthropic",
                api_key=minimax_key,
                model=os.getenv("BA_AGENT_MINIMAX_MODEL", "MiniMax-M2.7"),
                base_url=os.getenv("BA_AGENT_MINIMAX_ANTHROPIC_BASE_URL", "https://api.minimax.io/anthropic"),
                timeout_seconds=int(os.getenv("BA_AGENT_LLM_TIMEOUT_SECONDS", "180")),
            )
        return DisabledLLMService()
    if provider in {"minimax_anthropic_sdk", "minimax-anthropic-sdk", "minimax_sdk", "minimax-sdk"}:
        minimax_key = os.getenv("MINIMAX_API_KEY", "").strip() or os.getenv("BA_AGENT_MINIMAX_API_KEY", "").strip()
        if minimax_key:
            return AnthropicSDKMiniMaxLLMService(
                api_key=minimax_key,
                model=os.getenv("BA_AGENT_MINIMAX_MODEL", "MiniMax-M2.7"),
                base_url=os.getenv("BA_AGENT_MINIMAX_ANTHROPIC_BASE_URL", "https://api.minimax.io/anthropic"),
                timeout_seconds=int(os.getenv("BA_AGENT_LLM_TIMEOUT_SECONDS", "180")),
            )
        return DisabledLLMService()
    if provider in {"auto", "openai"} and api_key:
        return OpenAIResponsesLLMService(
            api_key=api_key,
            model=os.getenv("BA_AGENT_OPENAI_MODEL", "gpt-4.1-mini"),
            base_url=os.getenv("BA_AGENT_OPENAI_RESPONSES_URL", "https://api.openai.com/v1/responses"),
            timeout_seconds=int(os.getenv("BA_AGENT_LLM_TIMEOUT_SECONDS", "180")),
        )
    return DisabledLLMService()


def _normalize_api_key(api_key: str) -> str:
    key = api_key.strip()
    if key.lower().startswith("bearer "):
        key = key[7:].strip()
    return "".join(key.split())


def _api_key_error(api_key: str) -> str | None:
    if not api_key:
        return "API key/token is empty."
    try:
        api_key.encode("ascii")
    except UnicodeEncodeError:
        return "API key/token contains non-ASCII characters. Please paste the raw token only, without Chinese text, full-width punctuation, spaces, or line breaks."
    return None


def safe_context_from_profile(data_source: DataSourceProfile) -> dict[str, Any]:
    tables = []
    for table in data_source.tables_or_sheets:
        tables.append(
            {
                "name": table.name,
                "row_count": table.row_count,
                "columns": [
                    {
                        "name": column.name,
                        "dtype": column.dtype,
                        "business_domain": column.business_domain,
                        "is_sensitive": column.is_sensitive,
                        "sample_allowed": False,
                    }
                    for column in table.columns
                ],
            }
        )
    return {
        "source_type": data_source.source_type,
        "source_name": data_source.source_name,
        "privacy_policy": data_source.privacy_policy,
        "business_domains": data_source.business_domains,
        "tables_or_sheets": tables,
        "privacy_boundary": (
            "Only metadata is allowed. Do not transmit row-level samples, phone numbers, VINs, "
            "customer IDs, order details, or any raw customer-level records."
        ),
    }


def apply_llm_enhancement(
    base_artifact: dict[str, Any],
    enhanced: dict[str, Any] | None,
    provider_name: str,
    error: str | None = None,
) -> dict[str, Any]:
    if not enhanced:
        result = dict(base_artifact)
        result["llm_enrichment"] = {
            "enabled": False,
            "provider": provider_name,
            "status": "not_used_or_failed",
            "error": error,
        }
        return result

    protected_keys = {"analysis_agent", "skill", "ba_confirmation_required"}
    result = dict(base_artifact)
    for key, value in enhanced.items():
        if key not in protected_keys:
            result[key] = value
    result["llm_enrichment"] = {
        "enabled": provider_name != "disabled",
        "provider": provider_name,
        "status": "applied",
        "error": None,
    }
    return result


def parse_json_object(text: str) -> dict[str, Any] | None:
    text = _strip_thinking(_strip_code_fence(text)).strip()
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        pass

    for candidate in reversed(_json_object_candidates(text)):
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


def _compact_safe_context_for_prompt(
    safe_context: dict[str, Any],
    business_problem: str,
    base_artifact: dict[str, Any],
    max_columns: int = 180,
) -> dict[str, Any]:
    """Keep LLM prompts fast while preserving metadata-only privacy boundaries."""
    problem_blob = f"{business_problem}\n{json.dumps(_jsonable(base_artifact), ensure_ascii=False)}".lower()
    priority_fragments = _priority_column_fragments(problem_blob)
    compact_tables: list[dict[str, Any]] = []

    for table in safe_context.get("tables_or_sheets", []):
        columns = table.get("columns", []) if isinstance(table, dict) else []
        scored_columns: list[tuple[int, int, dict[str, Any]]] = []
        for index, column in enumerate(columns):
            if not isinstance(column, dict):
                continue
            name = str(column.get("name", ""))
            domain = str(column.get("business_domain", ""))
            haystack = f"{name} {domain}".lower()
            score = 0
            for rank, fragment in enumerate(priority_fragments):
                if fragment and fragment in haystack:
                    score += max(1, 50 - rank)
            if str(column.get("is_sensitive", "")).lower() == "true":
                score -= 5
            if score > 0:
                scored_columns.append((score, -index, _compact_column(column)))

        if len(scored_columns) < min(max_columns, 80):
            for index, column in enumerate(columns):
                if not isinstance(column, dict):
                    continue
                compact = _compact_column(column)
                if any(existing[2]["name"] == compact["name"] for existing in scored_columns):
                    continue
                scored_columns.append((0, -index, compact))

        selected = [item[2] for item in sorted(scored_columns, reverse=True)[:max_columns]]
        compact_tables.append(
            {
                "name": table.get("name"),
                "row_count": table.get("row_count"),
                "column_count": len(columns),
                "relevant_columns": selected,
                "omitted_column_count": max(0, len(columns) - len(selected)),
            }
        )

    return {
        "source_type": safe_context.get("source_type"),
        "source_name": safe_context.get("source_name"),
        "privacy_policy": safe_context.get("privacy_policy"),
        "business_domains": safe_context.get("business_domains", []),
        "tables_or_sheets": compact_tables,
        "column_selection_note": (
            "The prompt includes a metadata-only relevant column subset to reduce latency. "
            "Use only relevant_columns for field_requirements; put other desired fields in missing_recommended_fields."
        ),
        "privacy_boundary": safe_context.get("privacy_boundary"),
    }


def _compact_column(column: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": column.get("name"),
        "dtype": column.get("dtype"),
        "business_domain": column.get("business_domain"),
        "is_sensitive": column.get("is_sensitive"),
        "sample_allowed": False,
    }


def _priority_column_fragments(text: str) -> list[str]:
    fragments = [
        "create_time",
        "_time",
        "date",
        "month",
        "channel",
        "media",
        "campaign",
        "source",
        "leads",
        "lead",
        "visit",
        "arrival",
        "order",
        "confirm",
        "first_flag",
        "_id",
        "dealer",
        "region",
        "province",
        "city",
        "area",
        "brand",
        "series",
        "model",
        "product",
    ]
    topic_fragments = {
        ("douyin", "抖音", "渠道", "channel", "投放", "媒体", "campaign"): [
            "douyin",
            "channel",
            "media",
            "campaign",
            "source",
            "leads",
            "visit",
        ],
        ("客流", "到店", "visit", "流量"): ["visit", "arrival", "dealer", "city", "region"],
        ("转化", "conversion", "订单", "成交", "order"): ["leads", "oppty", "visit", "td", "order", "first_flag"],
        ("区域", "城市", "经销商", "dealer", "region"): ["dealer", "region", "province", "city", "area"],
        ("车型", "车系", "品牌", "product", "brand"): ["brand", "series", "model", "product"],
    }
    prioritized: list[str] = []
    for triggers, additions in topic_fragments.items():
        if any(trigger in text for trigger in triggers):
            prioritized.extend(additions)
    prioritized.extend(fragments)
    deduped: list[str] = []
    for fragment in prioritized:
        if fragment not in deduped:
            deduped.append(fragment)
    return deduped


def _build_prompt(
    stage_id: str,
    business_problem: str,
    base_artifact: dict[str, Any],
    safe_context: dict[str, Any],
) -> str:
    prompt_context = _compact_safe_context_for_prompt(safe_context, business_problem, base_artifact)
    if stage_id == "intent_understanding":
        return _build_intent_prompt(business_problem, base_artifact, prompt_context)
    if stage_id == "analysis_design_llm_first":
        return _build_analysis_design_llm_first_prompt(business_problem, base_artifact, prompt_context)
    return json.dumps(
        {
            "task": f"Enhance the {stage_id} artifact for a BA analytics workflow.",
            "business_problem": business_problem,
            "rules": [
                "Return one JSON object only.",
                "Materially adapt the artifact to the exact business_problem; do not return generic funnel boilerplate.",
                "Keep the existing top-level structure where possible, but rewrite content that is too generic.",
                "Use only fields present in safe_context.tables_or_sheets.columns.",
                "Do not include raw data samples or customer-level records.",
                "Mark unverified conclusions as 待验证 or 待业务确认.",
                "For analysis_design, business_hypotheses must be factor-based causal hypotheses, not default口径 assumptions.",
                "For channel, region, dealer, product, volume, conversion, or cycle questions, prioritize the matching dimensions and metrics.",
            ],
            "safe_context": prompt_context,
            "base_artifact": _jsonable(base_artifact),
        },
        ensure_ascii=False,
        indent=2,
    )


def _developer_prompt(stage_id: str) -> str:
    if stage_id == "analysis_design_llm_first":
        return (
            "你是一个严谨的 BA 数据分析设计 Agent。只能基于用户问题、analysis_context 和字段元数据"
            "生成结构化 JSON。不要参考或复述任何 skill/playbook 模板，不要编造不存在的字段，"
            "不要要求或输出客户级明细、手机号、VIN、客户 ID 或订单明细样本。"
            "你的回复必须是一个可被 json.loads 直接解析的 JSON object，不要输出 Markdown、代码块、解释文字或 <think> 思考过程。"
        )
    if stage_id == "intent_understanding":
        return (
            "你是一个严谨的 BA 需求理解 Agent。只能基于用户问题、BA 补充和字段元数据理解分析上下文。"
            "不要编造不存在的字段，不要要求或输出客户级明细、手机号、VIN、客户 ID 或订单明细样本。"
            "你的回复必须是一个可被 json.loads 直接解析的 JSON object，不要输出 Markdown、代码块、解释文字或 <think> 思考过程。"
        )
    return (
        "你是一个严谨的 BA 数据分析 Agent。只能基于用户问题、字段元数据、"
        "skill 草稿和已确认上下文生成结构化 JSON。不要编造不存在的字段，"
        "不要要求或输出客户级明细、手机号、VIN、客户 ID 或订单明细样本。"
    )


def _build_analysis_design_llm_first_prompt(
    business_problem: str,
    base_artifact: dict[str, Any],
    safe_context: dict[str, Any],
) -> str:
    return json.dumps(
        {
            "task": "Generate the analysis design artifact from scratch for a BA analytics workflow.",
            "business_problem": business_problem,
            "rules": [
                "Return one JSON object only.",
                "Do not use skill/playbook/template content. Generate the analysis thinking, dimensions, metrics, hypotheses, and path directly from analysis_context and field metadata.",
                "Use only fields present in safe_context.tables_or_sheets.columns for field_requirements.",
                "Do not invent unavailable fields. If a useful field is unavailable, put it in missing_recommended_fields.",
                "Business hypotheses must be factor-based causal hypotheses related to the user's problem, not口径 defaults.",
                "Metrics tree must include business metrics, metric definitions, dimensions/cuts, and suggested calculation logic.",
                "Keep the answer concise: up to 5 hypotheses, 4 metric groups, and 8 analysis steps.",
                "Clarification questions should ask only for genuinely missing BA decisions.",
                "Mark unverified assumptions as 待验证 or 待业务确认.",
                "Do not include raw data samples or customer-level records.",
                "Keep the output directly usable by the Data Analysis Agent.",
            ],
            "required_output_shape": {
                "analysis_purpose": "",
                "business_context": {
                    "purpose": "",
                    "business_background": "",
                    "core_problems": [],
                    "related_departments": [],
                    "key_metrics": [],
                    "urgency": "",
                    "confidence": 0.0,
                },
                "clarification_questions": [],
                "business_hypotheses": [
                    {
                        "factor": "",
                        "hypothesis": "",
                        "why_it_matters": "",
                        "validation_approach": "",
                        "related_fields": [],
                        "evidence_status": "待验证",
                    }
                ],
                "metrics_tree": [
                    {
                        "name": "",
                        "description": "",
                        "metrics": [],
                    }
                ],
                "field_requirements": {
                    "funnel_time_fields": [],
                    "funnel_id_fields": [],
                    "first_flag_fields": [],
                    "dimension_fields": [],
                    "metric_fields": [],
                    "missing_recommended_fields": [],
                },
                "analysis_path": [],
                "confidence_score": 0.0,
            },
            "safe_context": safe_context,
            "analysis_design_skeleton": _jsonable(base_artifact),
        },
        ensure_ascii=False,
        indent=2,
    )


def _build_intent_prompt(
    business_problem: str,
    base_artifact: dict[str, Any],
    safe_context: dict[str, Any],
) -> str:
    return json.dumps(
        {
            "task": "Understand the BA analytics request and update analysis_context.",
            "business_problem": business_problem,
            "rules": [
                "Return one JSON object only.",
                "Prefer the user's latest clarification over older assumptions.",
                "Use semantic understanding, not only keyword matching.",
                "Keep fields within this schema: business_question, latest_user_message, feedback_type, time_range, comparison_baseline, metric_focus, metric, issue_type, funnel_scope, dimensions, filters, audience, open_questions, confidence, understanding_summary.",
                "Allowed funnel stages: 注册, 线索, 商机, 到店, 试驾, 订单.",
                "Allowed dimensions: 渠道, 区域, 经销商, 产品, 时间.",
                "If the user negates a dimension, such as 不看车型 or 不按经销商, do not include that dimension.",
                "Do not invent unavailable data fields. This stage should understand intent only.",
                "Do not include raw data samples or customer-level records.",
                "Ask only missing questions in open_questions; do not ask for information already provided.",
                "Keep the answer concise and avoid long prose.",
            ],
            "expected_json_shape": {
                "time_range": "e.g. 2026-03 or 3月, or null",
                "comparison_baseline": "e.g. 2026-02, 2月, 上月, 去年同期, 目标, or null",
                "metric_focus": "转化率 | 规模 | 耗时 | 综合",
                "metric": "business metric in Chinese",
                "issue_type": "下降 | 提升 | 异常波动 | 差异 | 变化",
                "funnel_scope": {
                    "start_stage": "注册 | 线索 | 商机 | 到店 | 试驾 | 订单 | null",
                    "end_stage": "注册 | 线索 | 商机 | 到店 | 试驾 | 订单 | null",
                    "mentioned_stages": [],
                },
                "dimensions": [],
                "filters": [],
                "audience": None,
                "open_questions": [],
                "confidence": 0.0,
                "understanding_summary": "",
            },
            "safe_context": safe_context,
            "rule_context_draft": _jsonable(base_artifact),
        },
        ensure_ascii=False,
        indent=2,
    )


def _extract_response_text(response_data: dict[str, Any]) -> str:
    output_text = response_data.get("output_text")
    if isinstance(output_text, str):
        return output_text

    chunks: list[str] = []
    for item in response_data.get("output", []):
        if not isinstance(item, dict):
            continue
        for content in item.get("content", []):
            if isinstance(content, dict) and content.get("type") in {"output_text", "text"}:
                text = content.get("text")
                if isinstance(text, str):
                    chunks.append(text)
    return "\n".join(chunks)


def _extract_chat_completion_text(response_data: dict[str, Any]) -> str:
    choices = response_data.get("choices", [])
    if not isinstance(choices, list) or not choices:
        return ""
    first = choices[0]
    if not isinstance(first, dict):
        return ""
    message = first.get("message", {})
    if not isinstance(message, dict):
        return ""
    content = message.get("content")
    return content if isinstance(content, str) else ""


def _extract_anthropic_text(response_data: dict[str, Any]) -> str:
    chunks: list[str] = []
    content = response_data.get("content", [])
    if isinstance(content, list):
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text" and isinstance(item.get("text"), str):
                chunks.append(item["text"])
    return "\n".join(chunks)


def _extract_anthropic_sdk_text(response: Any) -> str:
    chunks: list[str] = []
    for item in getattr(response, "content", []) or []:
        text = getattr(item, "text", None)
        if isinstance(text, str):
            chunks.append(text)
        elif isinstance(item, dict) and isinstance(item.get("text"), str):
            chunks.append(item["text"])
    return "\n".join(chunks)


def _sdk_error_text(exc: Exception) -> str:
    status_code = getattr(exc, "status_code", None)
    response = getattr(exc, "response", None)
    detail = ""
    if response is not None:
        try:
            detail = response.text
        except Exception:
            detail = ""
    prefix = f"HTTP {status_code}: " if status_code else ""
    return f"{prefix}{detail or str(exc)}"


def _request_error_text(exc: Exception) -> str:
    message = str(exc) or exc.__class__.__name__
    if isinstance(exc, (TimeoutError, socket.timeout)) or "timed out" in message.lower():
        return "request timed out while waiting for the LLM response. Try again, or use a smaller/faster model."
    return message


def _strip_thinking(text: str) -> str:
    stripped = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    if "<think>" in stripped:
        json_start = stripped.find("{")
        if json_start >= 0:
            return stripped[json_start:].strip()
    return stripped


def _strip_code_fence(text: str) -> str:
    stripped = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", stripped, flags=re.DOTALL | re.IGNORECASE)
    if fence:
        return fence.group(1).strip()
    return stripped


def _json_object_candidates(text: str) -> list[str]:
    candidates: list[str] = []
    start: int | None = None
    depth = 0
    in_string = False
    escape = False
    for index, char in enumerate(text):
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
            continue
        if char == "{":
            if depth == 0:
                start = index
            depth += 1
        elif char == "}" and depth:
            depth -= 1
            if depth == 0 and start is not None:
                candidates.append(text[start : index + 1])
                start = None
    return candidates


def _preview_text(text: str, limit: int = 200) -> str:
    compact = " ".join(text.strip().split())
    return compact[:limit]


def _jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return _jsonable(asdict(value))
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    return value
