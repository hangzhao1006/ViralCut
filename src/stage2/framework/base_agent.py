"""Base Agent with a lightweight tool-calling loop.

Supports any OpenAI-compatible LLM client. Prompts can be loaded from
markdown files in the prompts/ directory or hardcoded in subclasses.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from src.stage2.framework.blackboard import Blackboard
from src.stage2.framework.tools import Stage2ToolRegistry
from src.stage1.utils.logger import get_logger

logger = get_logger(__name__)

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


class LLMClientProtocol(Protocol):
    def chat(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> dict[str, Any]:
        ...


@dataclass
class AgentResult:
    agent_name: str
    output: dict[str, Any]
    tool_history: list[dict[str, Any]] = field(default_factory=list)
    raw_response: Any = None
    llm_calls: int = 0


class BaseAgent:
    agent_name: str = "base"
    prompt_file: str = ""           # e.g. "script.md", loaded from prompts/
    allowed_tools: list[str] = []
    max_tool_rounds: int = 10

    def __init__(self, llm_client: LLMClientProtocol | None = None):
        self.llm_client = llm_client

    def system_prompt(self) -> str:
        """Load prompt from file if prompt_file is set, otherwise override in subclass."""
        if self.prompt_file:
            path = PROMPTS_DIR / self.prompt_file
            if path.exists():
                return path.read_text(encoding="utf-8").strip()
            logger.warning("Prompt file not found: %s, using fallback", path)
        return f"You are the {self.agent_name} agent. Analyze the video and output JSON."

    def user_prompt(self) -> str:
        return "请根据可用工具分析视频结构，并最终输出合法JSON。"

    def run(
        self,
        tools: Stage2ToolRegistry,
        blackboard: Blackboard,
        feedback: str | None = None,
    ) -> AgentResult:
        if self.llm_client is None:
            raise RuntimeError(
                "BaseAgent requires llm_client. Pass one via constructor "
                "or use create_llm_client() from llm_client.py."
            )

        schemas = tools.schemas(self.allowed_tools or None)
        user_content = self.user_prompt()
        if feedback:
            user_content += f"\n\nEvaluator反馈（请根据反馈改进分析）：\n{feedback}"

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": self.system_prompt()},
            {"role": "user", "content": user_content},
        ]
        tool_history: list[dict[str, Any]] = []
        llm_calls = 0

        for round_idx in range(self.max_tool_rounds):
            llm_calls += 1
            response = self.llm_client.chat(messages=messages, tools=schemas)
            tool_calls = response.get("tool_calls") or []

            if not tool_calls:
                # No more tool calls → final output
                content = response.get("content") or "{}"
                output = self._parse_json_content(content)
                blackboard.write(
                    self.agent_name, output,
                    summary=f"{self.agent_name} completed in {llm_calls} LLM calls",
                )
                logger.info(
                    "%s completed: %d LLM calls, %d tool calls",
                    self.agent_name, llm_calls, len(tool_history),
                )
                return AgentResult(self.agent_name, output, tool_history, response, llm_calls)

            # Process tool calls
            messages.append({
                "role": "assistant",
                "content": response.get("content", ""),
                "tool_calls": tool_calls,
            })

            for call in tool_calls:
                fn = call.get("function", {})
                name = fn.get("name", "")
                arguments = fn.get("arguments") or {}
                if isinstance(arguments, str):
                    try:
                        arguments = json.loads(arguments)
                    except json.JSONDecodeError:
                        arguments = {}

                try:
                    result = tools.execute(name, arguments, agent_name=self.agent_name)
                except Exception as exc:
                    result = {"error": str(exc)}
                    logger.warning("%s tool %s failed: %s", self.agent_name, name, exc)

                tool_history.append({
                    "tool": name,
                    "arguments": arguments,
                    "result_preview": self._preview(result),
                })

                messages.append({
                    "role": "tool",
                    "tool_call_id": call.get("id", f"call_{round_idx}"),
                    "name": name,
                    "content": json.dumps(result, ensure_ascii=False, default=str),
                })

                logger.debug(
                    "%s called %s(%s)",
                    self.agent_name, name,
                    json.dumps(arguments, ensure_ascii=False)[:200],
                )

        # Max rounds exceeded → force final output
        logger.warning("%s hit max tool rounds (%d), forcing output", self.agent_name, self.max_tool_rounds)
        messages.append({
            "role": "user",
            "content": "工具调用轮数已达上限。请不要再调用工具，直接输出最终JSON结果。",
        })
        llm_calls += 1
        response = self.llm_client.chat(messages=messages, tools=[])
        output = self._parse_json_content(response.get("content") or "{}")
        blackboard.write(
            self.agent_name, output,
            summary=f"{self.agent_name} completed after max rounds ({llm_calls} LLM calls)",
        )
        return AgentResult(self.agent_name, output, tool_history, response, llm_calls)

    def _parse_json_content(self, content: str) -> dict[str, Any]:
        """Parse JSON from LLM response, handling markdown code blocks."""
        text = content.strip()
        # Strip markdown code block
        if text.startswith("```"):
            lines = text.split("\n")
            # Remove first line (```json) and last line (```)
            if lines[-1].strip() == "```":
                lines = lines[1:-1]
            else:
                lines = lines[1:]
            text = "\n".join(lines).strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Try to find JSON object in the text
            start = text.find("{")
            end = text.rfind("}")
            if start >= 0 and end > start:
                try:
                    return json.loads(text[start:end + 1])
                except json.JSONDecodeError:
                    pass
            logger.warning("%s response is not valid JSON, storing raw text", self.agent_name)
            return {"raw_text": content, "parse_error": "response is not valid JSON"}

    def _preview(self, value: Any, max_chars: int = 500) -> str:
        text = json.dumps(value, ensure_ascii=False, default=str)
        return text[:max_chars] + ("..." if len(text) > max_chars else "")