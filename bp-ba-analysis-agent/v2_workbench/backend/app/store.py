from __future__ import annotations

import json
from pathlib import Path

from .mock_agent import sample_task
from .models import Task, now_iso


class TaskStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def all(self) -> list[Task]:
        if not self.path.exists():
            tasks = [sample_task()]
            self.save_all(tasks)
            return tasks
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        return [Task.model_validate(item) for item in raw.get("tasks", [])]

    def save_all(self, tasks: list[Task]) -> None:
        payload = {"tasks": [task.model_dump(mode="json") for task in tasks]}
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def get(self, task_id: str) -> Task:
        for task in self.all():
            if task.task_id == task_id:
                return task
        raise KeyError(task_id)

    def upsert(self, task: Task) -> Task:
        tasks = self.all()
        task.updated_at = now_iso()
        for index, existing in enumerate(tasks):
            if existing.task_id == task.task_id:
                tasks[index] = task
                self.save_all(tasks)
                return task
        tasks.insert(0, task)
        self.save_all(tasks)
        return task
