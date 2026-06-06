"""Simple in-memory task store for tracking async analysis jobs.

For demo this is fine. For production, swap with Redis.
"""

from __future__ import annotations

import threading
from typing import Any


class TaskStore:
    def __init__(self) -> None:
        self._tasks: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()

    def create(self, task_id: str, **kwargs: Any) -> None:
        with self._lock:
            self._tasks[task_id] = {"task_id": task_id, "status": "processing", **kwargs}

    def update(self, task_id: str, **kwargs: Any) -> None:
        with self._lock:
            if task_id in self._tasks:
                self._tasks[task_id].update(kwargs)

    def get(self, task_id: str) -> dict[str, Any]:
        with self._lock:
            return self._tasks.get(task_id, {"status": "not_found", "task_id": task_id})


task_store = TaskStore()
