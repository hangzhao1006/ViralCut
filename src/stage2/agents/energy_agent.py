"""Energy Agent: synthesize script, rhythm, packaging, and value into an energy curve."""

from __future__ import annotations

from src.stage2.framework.base_agent import BaseAgent


class EnergyAgent(BaseAgent):
    agent_name = "energy"
    prompt_file = "energy.md"
    allowed_tools = [
        "get_overview",
        "read_blackboard",
        "get_segment_evidence",
        "compute_metrics",
    ]
    max_tool_rounds = 10

    def user_prompt(self) -> str:
        return (
            "请读取 read_blackboard('script')、read_blackboard('rhythm')、"
            "read_blackboard('packaging')、read_blackboard('value')。"
            "必要时对关键段落调用 compute_metrics 或 get_segment_evidence。"
            "请基于数据综合输出情绪/能量曲线 JSON，不要凭感觉判断复杂心理情绪。"
        )
