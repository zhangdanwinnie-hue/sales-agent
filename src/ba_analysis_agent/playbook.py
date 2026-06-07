from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path


DEFAULT_PLAYBOOK_PATH = (
    Path.home()
    / "Documents"
    / "需求整理"
    / "skills"
    / "automotive-sales-crm-analysis"
    / "references"
    / "analysis_playbook.md"
)


TOPIC_ALIASES = {
    "Sales Target Gap And Forecast": ["target", "gap", "forecast", "目标", "缺口", "预测", "达成", "订单缺口", "交付"],
    "End-To-End Funnel": ["funnel", "conversion", "注册", "线索", "商机", "到店", "试驾", "订单", "转化", "漏斗"],
    "Channel And Campaign Quality": ["channel", "campaign", "media", "渠道", "活动", "投放", "媒体", "来源"],
    "Lead Group Validation And Defeat": ["validation", "defeat", "battle", "线索组", "战败", "验证", "跟进", "拒绝"],
    "Opportunity Stock Quality": ["opportunity stock", "stale", "商机库存", "商机", "高星", "低意向", "存量"],
    "Showroom Traffic And Reception": ["showroom", "traffic", "reception", "visit", "展厅", "客流", "到店", "接待", "邀约"],
    "Test Drive Conversion": ["test drive", "td", "试驾"],
    "Dealer And Region Execution": ["dealer", "region", "经销商", "区域", "城市", "大区", "门店"],
    "Product, BEV, And Model Mix": ["product", "model", "bev", "series", "车型", "车系", "品牌", "新能源"],
    "Customer And Loyalty": ["customer", "loyalty", "客户", "忠诚", "复购", "置换"],
    "Data Quality Checks": ["data quality", "quality", "missing", "数据质量", "缺失", "重复", "口径", "合规"],
}


@dataclass(frozen=True)
class PlaybookTopic:
    title: str
    section_number: str | None
    question_examples: list[str]
    core_metrics: list[str]
    fields: list[str]
    recommended_cuts: list[str]
    analysis_approach: list[str]
    raw_excerpt: str

    def to_dict(self) -> dict[str, object]:
        return {
            "title": self.title,
            "section_number": self.section_number,
            "question_examples": self.question_examples,
            "core_metrics": self.core_metrics,
            "fields": self.fields,
            "recommended_cuts": self.recommended_cuts,
            "analysis_approach": self.analysis_approach,
        }


class AutomotiveSalesCRMPlaybook:
    def __init__(self, path: Path, text: str):
        self.path = path
        self.text = text
        self.thinking_pattern = _extract_thinking_pattern(text)
        self.topics = _parse_topics(text)

    @classmethod
    def load_default(cls) -> "AutomotiveSalesCRMPlaybook | None":
        configured = os.getenv("BA_AGENT_PLAYBOOK_PATH", "").strip()
        path = Path(configured) if configured else DEFAULT_PLAYBOOK_PATH
        if not path.exists():
            return None
        return cls(path, path.read_text(encoding="utf-8"))

    def match_topics(self, question: str, limit: int = 2) -> list[PlaybookTopic]:
        scored: list[tuple[int, int, PlaybookTopic]] = []
        normalized = question.lower()
        for index, topic in enumerate(self.topics):
            score = 0
            aliases = TOPIC_ALIASES.get(topic.title, [])
            for alias in aliases:
                if alias.lower() in normalized or alias in question:
                    score += 5
            score += _explicit_topic_boost(topic.title, question, normalized)
            for token in re.findall(r"[A-Za-z]+", topic.title.lower()):
                if len(token) > 3 and token in normalized:
                    score += 1
            for example in topic.question_examples:
                for token in re.findall(r"[A-Za-z]+", example.lower()):
                    if len(token) > 5 and token in normalized:
                        score += 1
            if score:
                scored.append((score, -index, topic))

        if not scored:
            fallback = self.topic_by_title("End-To-End Funnel")
            return [fallback] if fallback else []
        return [topic for _, _, topic in sorted(scored, reverse=True)[:limit]]

    def topic_by_title(self, title: str) -> PlaybookTopic | None:
        for topic in self.topics:
            if topic.title == title:
                return topic
        return None


def _parse_topics(text: str) -> list[PlaybookTopic]:
    matches = list(re.finditer(r"^##\s+(?:(\d+)\.\s+)?(.+?)\s*$", text, flags=re.MULTILINE))
    topics: list[PlaybookTopic] = []
    for index, match in enumerate(matches):
        section_number = match.group(1)
        title = match.group(2).strip()
        if section_number is None:
            continue
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        topics.append(
            PlaybookTopic(
                title=title,
                section_number=section_number,
                question_examples=_extract_bullets(body, "Question examples:") or _extract_bullets(body, "Questions:"),
                core_metrics=_extract_bullets(body, "Core metrics:") or _extract_bullets(body, "Metrics:"),
                fields=_extract_code_fields(body),
                recommended_cuts=_extract_recommended_cuts(body),
                analysis_approach=_extract_bullets(body, "Analysis approach:"),
                raw_excerpt=body[:1200],
            )
        )
    return topics


def _extract_thinking_pattern(text: str) -> list[str]:
    match = re.search(r"^##\s+Analysis Thinking Pattern\s*$", text, flags=re.MULTILINE)
    if not match:
        return []
    next_heading = re.search(r"^##\s+\d+\.", text[match.end():], flags=re.MULTILINE)
    end = match.end() + next_heading.start() if next_heading else len(text)
    section = text[match.end():end]
    lines = []
    for line in section.splitlines():
        stripped = line.strip()
        if re.match(r"^\d+\.\s+", stripped) or stripped.startswith("- "):
            lines.append(stripped)
    return lines


def _extract_bullets(section: str, heading: str) -> list[str]:
    block = _extract_block(section, heading)
    bullets = []
    for line in block.splitlines():
        stripped = line.strip()
        if stripped.startswith("- "):
            bullets.append(stripped[2:].strip())
    return bullets


def _extract_block(section: str, heading: str) -> str:
    start = section.find(heading)
    if start == -1:
        return ""
    start += len(heading)
    candidates = [
        section.find(candidate, start)
        for candidate in [
            "\nQuestion examples:",
            "\nQuestions:",
            "\nCore metrics:",
            "\nMetrics:",
            "\nFields:",
            "\nRecommended cuts:",
            "\nAnalysis approach:",
            "\nFunnel stages:",
            "\nUseful latency metrics:",
        ]
        if section.find(candidate, start) != -1
    ]
    end = min(candidates) if candidates else len(section)
    return section[start:end].strip()


def _extract_code_fields(section: str) -> list[str]:
    fields_block = _extract_block(section, "Fields:")
    if not fields_block:
        fields_block = section
    seen: set[str] = set()
    fields = []
    for field in re.findall(r"`([^`]+)`", fields_block):
        if "*" in field:
            continue
        if field not in seen:
            seen.add(field)
            fields.append(field)
    return fields


def _extract_recommended_cuts(section: str) -> list[str]:
    match = re.search(r"Recommended cuts:\s*(.+)", section)
    if not match:
        return []
    return [item.strip().rstrip(".") for item in match.group(1).split(",") if item.strip()]


def _explicit_topic_boost(title: str, question: str, normalized: str) -> int:
    boosts = {
        "Channel And Campaign Quality": ["渠道", "投放", "媒体", "campaign", "活动"],
        "Dealer And Region Execution": ["区域", "经销商", "城市", "大区", "门店"],
        "Product, BEV, And Model Mix": ["车型", "车系", "品牌", "bev", "model"],
        "Sales Target Gap And Forecast": ["目标", "缺口", "预测", "达成"],
        "Data Quality Checks": ["数据质量", "口径", "缺失", "重复", "合规"],
        "Showroom Traffic And Reception": ["到店", "接待", "展厅", "客流", "邀约"],
        "Test Drive Conversion": ["试驾", "test drive"],
    }
    return 8 if any(token.lower() in normalized or token in question for token in boosts.get(title, [])) else 0
