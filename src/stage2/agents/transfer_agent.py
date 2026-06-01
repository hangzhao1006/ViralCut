"""Transfer Agent: convert analysis results into a reusable video structure blueprint."""

from __future__ import annotations

from src.stage2.framework.base_agent import BaseAgent


class TransferAgent(BaseAgent):
    agent_name = "transfer"
    prompt_file = "transfer.md"
    allowed_tools = ["read_blackboard"]
    max_tool_rounds = 8

    def user_prompt(self) -> str:
        return (
            "请只读取 blackboard 中的 overview、script、rhythm、packaging、value、energy。"
            "不要调用其他证据工具。你的任务不是重新分析原视频，而是生成 Stage 3 可执行的迁移蓝图。"
            "请输出 transfer_blueprint JSON。"
        )
