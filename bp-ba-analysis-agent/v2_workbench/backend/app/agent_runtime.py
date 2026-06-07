from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass

from .agent_tools import apply_rule_actions, build_rule_reply
from .mock_agent import create_task, message, refresh_artifacts
from .models import AgentAction, ChatRequest, ChatResponse, ConversationMessage, Stage, Task, TaskInput
from .store import TaskStore


@dataclass
class AgentResult:
    task: Task
    assistant_text: str
    actions: list[AgentAction]
    next_page: Stage | None


class RuleAgent:
    def run(self, task: Task, request: ChatRequest) -> AgentResult:
        task, actions, next_page = apply_rule_actions(task, request.message, request.active_page)
        assistant_text = build_rule_reply(task, request.message, actions)
        return AgentResult(task=task, assistant_text=assistant_text, actions=actions, next_page=next_page)


class LLMAgent:
    def __init__(self) -> None:
        self.base_url = os.getenv("BPBA_LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
        self.api_key = os.getenv("BPBA_LLM_API_KEY", "")
        self.model = os.getenv("BPBA_LLM_MODEL", "gpt-4.1-mini")

    def available(self) -> bool:
        return bool(self.api_key)

    def run(self, task: Task, request: ChatRequest) -> AgentResult:
        rule_task, actions, next_page = apply_rule_actions(task, request.message, request.active_page)
        prompt = self._prompt(rule_task, request.message, actions)
        try:
            assistant_text = self._chat_completion(prompt)
        except Exception:
            assistant_text = build_rule_reply(rule_task, request.message, actions)
            actions.append(AgentAction(type="llm_fallback", title="LLM 降级", detail="模型调用失败，已使用本地规则 Agent 完成处理。"))
        return AgentResult(task=rule_task, assistant_text=assistant_text, actions=actions, next_page=next_page)

    def _prompt(self, task: Task, user_message: str, actions: list[AgentAction]) -> str:
        return (
            "你是销售 BP BA 分析 Agent，回复要简洁、具体、说明你已经执行了什么。"
            "不要编造未执行的系统动作。\n"
            f"当前任务：{task.task_name}\n业务问题：{task.business_question}\n"
            f"已执行动作：{'; '.join(action.detail for action in actions) or '暂无'}\n"
            f"用户消息：{user_message}"
        )

    def _chat_completion(self, prompt: str) -> str:
        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "你是一个懂销售分析和 BI 项目交付的 BP BA Agent。"},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=20) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise RuntimeError(exc.read().decode("utf-8", errors="ignore")) from exc
        return data["choices"][0]["message"]["content"].strip()


class AgentOrchestrator:
    def __init__(self, store: TaskStore) -> None:
        self.store = store
        self.rule_agent = RuleAgent()
        self.llm_agent = LLMAgent()

    def start(self, request: ChatRequest) -> ChatResponse:
        task = create_task(
            TaskInput(
                task_name="自然语言创建的分析任务",
                business_question=request.message,
                analysis_purpose="根据 BA 自然语言输入自动创建并完善分析任务。",
            )
        )
        self.store.upsert(task)
        return self.chat(task.task_id, request)

    def chat(self, task_id: str, request: ChatRequest) -> ChatResponse:
        task = self.store.get(task_id)
        task.messages.append(message("ba", request.message, request.active_page))
        agent = self._select_agent()
        result = agent.run(task, request)
        assistant = message("agent", result.assistant_text, result.next_page or request.active_page)
        result.task.messages.append(assistant)
        refresh_artifacts(result.task)
        self.store.upsert(result.task)
        return ChatResponse(
            assistant_message=assistant,
            actions=result.actions,
            task=result.task,
            artifacts=result.task.artifacts,
            next_page=result.next_page,
        )

    def stream_events(self, response: ChatResponse):
        text = response.assistant_message.content
        for chunk in _chunks(text):
            yield {"type": "delta", "content": chunk}
        yield {
            "type": "final",
            "response": response.model_dump(mode="json"),
        }

    def _select_agent(self):
        mode = os.getenv("BPBA_LLM_MODE", "auto").lower()
        if mode == "rule":
            return self.rule_agent
        if mode == "llm":
            return self.llm_agent
        return self.llm_agent if self.llm_agent.available() else self.rule_agent


def event_line(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _chunks(text: str, size: int = 12):
    for index in range(0, len(text), size):
        yield text[index : index + size]
