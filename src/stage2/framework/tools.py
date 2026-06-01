"""Tool registry for Stage 2 agents.

Local tools wrap TimelineIndex + Blackboard. The only expensive tool is
look_at_keyframe(), which is budgeted globally and per agent.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable
import os

from src.stage2.input_builder import TimelineIndex
from src.stage2.framework.blackboard import Blackboard


@dataclass
class VisionBudget:
    max_total: int = field(default_factory=lambda: int(os.getenv("STAGE2_VISION_MAX_CALLS_TOTAL", "16")))
    max_per_agent: int = field(default_factory=lambda: int(os.getenv("STAGE2_VISION_MAX_CALLS_PER_AGENT", "4")))
    total_used: int = 0
    used_by_agent: dict[str, int] = field(default_factory=dict)

    def consume(self, agent_name: str) -> None:
        used = self.used_by_agent.get(agent_name, 0)
        if self.total_used >= self.max_total:
            raise RuntimeError(f"Global vision budget exhausted: {self.total_used}/{self.max_total}")
        if used >= self.max_per_agent:
            raise RuntimeError(f"Vision budget exhausted for {agent_name}: {used}/{self.max_per_agent}")
        self.total_used += 1
        self.used_by_agent[agent_name] = used + 1

    def status(self) -> dict[str, Any]:
        return {
            "total_used": self.total_used,
            "max_total": self.max_total,
            "max_per_agent": self.max_per_agent,
            "used_by_agent": dict(self.used_by_agent),
        }


class Stage2ToolRegistry:
    def __init__(self, timeline: TimelineIndex, blackboard: Blackboard, vision_budget: VisionBudget | None = None):
        self.timeline = timeline
        self.blackboard = blackboard
        self.vision_budget = vision_budget or VisionBudget()

    def schemas(self, allowed_tools: list[str] | None = None) -> list[dict[str, Any]]:
        all_schemas = self._all_schemas()
        if allowed_tools is None:
            return all_schemas
        allowed = set(allowed_tools)
        return [s for s in all_schemas if s["function"]["name"] in allowed]

    def execute(self, tool_name: str, arguments: dict[str, Any], agent_name: str = "unknown") -> Any:
        arguments = arguments or {}
        if tool_name == "get_overview":
            return self.timeline.get_overview()
        if tool_name == "query_timeline":
            return self.timeline.query_timeline(arguments["start_time"], arguments["end_time"])
        if tool_name == "compute_metrics":
            return self.timeline.compute_metrics(arguments["start_time"], arguments["end_time"])
        if tool_name == "search_text":
            return self.timeline.search_text(arguments["keyword"])
        if tool_name == "read_blackboard":
            return self.blackboard.read(arguments["agent_name"], default={"error": "not_available"})
        if tool_name == "get_all_display_texts":
            return self.timeline.get_all_display_texts()
        if tool_name == "get_segment_evidence":
            return self.timeline.get_segment_evidence(arguments["segment_id"])
        if tool_name == "get_cut_beat_alignment":
            return self.timeline.get_cut_beat_alignment(arguments["start_time"], arguments["end_time"])
        if tool_name == "look_at_keyframe":
            return self.look_at_keyframe(arguments["frame_id"], agent_name=agent_name)
        if tool_name == "get_vision_budget_status":
            return self.vision_budget.status()
        raise ValueError(f"Unknown Stage2 tool: {tool_name}")

    def look_at_keyframe(self, frame_id: str, agent_name: str) -> dict[str, Any]:
        """Budgeted vision tool placeholder.

        Real Doubao vision can be plugged here later. For now it returns the
        keyframe path and OCR text, so agents can be tested without vision API.
        """
        self.vision_budget.consume(agent_name)
        keyframe = self.timeline._keyframe_by_id.get(frame_id)
        if not keyframe:
            return {"error": f"keyframe not found: {frame_id}", "frame_id": frame_id}
        enriched = self.timeline._enrich_keyframe(keyframe)
        # TODO: replace with Doubao multimodal call when API wrapper is ready.
        return {
            "frame_id": frame_id,
            "timestamp": enriched.get("timestamp"),
            "path": enriched.get("path"),
            "display_text": enriched.get("display_text"),
            "vision_description": "Vision API placeholder: use display_text/path for now.",
            "budget": self.vision_budget.status(),
        }

    def _all_schemas(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "get_overview",
                    "description": "获取视频整体概况：时长、分辨率、镜头数、节奏、字幕密度等",
                    "parameters": {"type": "object", "properties": {}},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "query_timeline",
                    "description": "查询指定时间段内的镜头、关键帧、画面文字、语音内容和节拍数",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "start_time": {"type": "number"},
                            "end_time": {"type": "number"},
                        },
                        "required": ["start_time", "end_time"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "compute_metrics",
                    "description": "计算指定时间段的镜头密度、平均镜头时长、节拍密度等指标",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "start_time": {"type": "number"},
                            "end_time": {"type": "number"},
                        },
                        "required": ["start_time", "end_time"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "search_text",
                    "description": "搜索画面中包含指定关键词的所有帧",
                    "parameters": {
                        "type": "object",
                        "properties": {"keyword": {"type": "string"}},
                        "required": ["keyword"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "look_at_keyframe",
                    "description": "查看指定关键帧实际画面。受视觉预算限制，请优先查看hook帧、段落边界帧和高潮帧。",
                    "parameters": {
                        "type": "object",
                        "properties": {"frame_id": {"type": "string"}},
                        "required": ["frame_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "read_blackboard",
                    "description": "读取其他Agent已完成的分析结果。Phase 2只应读取script。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "agent_name": {
                                "type": "string",
                                "enum": ["overview", "script", "rhythm", "packaging", "value", "energy", "transfer", "summary", "evaluator"],
                            }
                        },
                        "required": ["agent_name"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_all_display_texts",
                    "description": "获取所有关键帧的画面文字，按时间排列",
                    "parameters": {"type": "object", "properties": {}},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_segment_evidence",
                    "description": "获取指定段落内的所有证据：镜头、关键帧、文字、语音、节拍、指标",
                    "parameters": {
                        "type": "object",
                        "properties": {"segment_id": {"type": "string"}},
                        "required": ["segment_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_cut_beat_alignment",
                    "description": "分析指定时间段内镜头切换与音乐节拍的对齐程度",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "start_time": {"type": "number"},
                            "end_time": {"type": "number"},
                        },
                        "required": ["start_time", "end_time"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_vision_budget_status",
                    "description": "查看 Stage 2 多模态视觉工具的全局和单 Agent 调用预算使用情况",
                    "parameters": {"type": "object", "properties": {}},
                },
            },
        ]
