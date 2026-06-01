"""Packaging Agent: analyze visual packaging, subtitles, title cards, and emphasis style."""

from __future__ import annotations

from src.stage2.framework.base_agent import BaseAgent


class PackagingAgent(BaseAgent):
    agent_name = "packaging"
    prompt_file = "packaging.md"
    allowed_tools = [
        "get_overview",
        "read_blackboard",
        "get_segment_evidence",
        "query_timeline",
        "look_at_keyframe",
        "get_all_display_texts",
        "get_vision_budget_status",
    ]
    max_tool_rounds = 12

    def user_prompt(self) -> str:
        return (
            "请先调用 read_blackboard('script') 获取脚本段落。"
            "然后查看 get_overview 和 get_all_display_texts。"
            "对 hook、instruction card、suspected climax、ending/CTA 的代表帧，"
            "在视觉预算内调用 look_at_keyframe。"
            "最后输出 packaging_structure JSON。"
        )
