"""Rhythm Agent: analyze tempo, beat sync, and pacing structure."""

from __future__ import annotations

from src.stage2.framework.base_agent import BaseAgent


class RhythmAgent(BaseAgent):
    agent_name = "rhythm"
    prompt_file = "rhythm.md"
    allowed_tools = [
        "get_overview",
        "read_blackboard",
        "get_segment_evidence",
        "compute_metrics",
        "get_cut_beat_alignment",
    ]

    def user_prompt(self) -> str:
        return (
            "请先调用 read_blackboard('script') 获取段落划分，"
            "再调用 get_all_segment_metrics 一次性获取所有段落的metrics，"
            "不要逐段调用 compute_metrics。"
            "然后对关键段落调用 get_cut_beat_alignment，"
            "最后输出节奏结构 JSON。"
        )
