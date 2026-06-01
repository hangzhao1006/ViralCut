"""Script Agent: segment the video into functional sections."""

from __future__ import annotations

from src.stage2.framework.base_agent import BaseAgent


class ScriptAgent(BaseAgent):
    agent_name = "script"
    prompt_file = "script.md"
    allowed_tools = [
        "get_overview",
        "get_all_display_texts",
        "query_timeline",
        "compute_metrics",
        "look_at_keyframe",
    ]

    def user_prompt(self) -> str:
        return (
            "请先调用 get_overview 了解视频概况，"
            "再调用 get_all_display_texts 查看所有画面文字，"
            "然后按需要用 query_timeline / compute_metrics / look_at_keyframe 深入分析，"
            "最后输出脚本结构 JSON。"
        )