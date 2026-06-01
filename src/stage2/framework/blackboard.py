"""Shared blackboard for Stage 2 agents."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
import copy


@dataclass
class BlackboardEvent:
    timestamp: str
    action: str
    agent_name: str
    key: str
    summary: str = ""


@dataclass
class Blackboard:
    """A tiny shared memory layer for multi-agent collaboration.

    It stores each agent's latest output under a stable key and keeps a write
    history so the UI / Evaluator can explain how the final structure was built.
    """

    data: dict[str, Any] = field(default_factory=dict)
    history: list[dict[str, Any]] = field(default_factory=list)

    def write(self, agent_name: str, value: Any, key: str | None = None, summary: str = "") -> None:
        store_key = key or agent_name
        self.data[store_key] = copy.deepcopy(value)
        self.history.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": "write",
            "agent_name": agent_name,
            "key": store_key,
            "summary": summary or self._auto_summary(value),
        })

    def read(self, key: str, default: Any = None) -> Any:
        return copy.deepcopy(self.data.get(key, default))

    def has(self, key: str) -> bool:
        return key in self.data

    def snapshot(self) -> dict[str, Any]:
        return {
            "data": copy.deepcopy(self.data),
            "history": copy.deepcopy(self.history),
        }

    def _auto_summary(self, value: Any) -> str:
        if isinstance(value, dict):
            keys = list(value.keys())[:8]
            return f"dict keys={keys}"
        if isinstance(value, list):
            return f"list len={len(value)}"
        return type(value).__name__
