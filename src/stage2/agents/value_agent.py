"""Value Agent: analyze value proposition and conversion strategy."""

from __future__ import annotations

from src.stage2.framework.base_agent import BaseAgent


class ValueAgent(BaseAgent):
    agent_name = "value"
    prompt_file = "value.md"
    allowed_tools = [
        "get_overview",
        "read_blackboard",
        "get_all_display_texts",
        "search_text",
        "get_segment_evidence",
    ]
    max_tool_rounds = 10

    def user_prompt(self) -> str:
        return (
            "请先调用 read_blackboard('script') 获取段落划分。"
            "再调用 get_overview 和 get_all_display_texts 判断视频的核心价值主张。"
            "必要时用 search_text 搜索关注、收藏、评论、购买、学会、教程、痛点等关键词。"
            "最后输出 value_strategy JSON。"
        )
