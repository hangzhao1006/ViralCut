"""Regenerate a single migrated slot, optionally with a natural-language instruction.

Supports 人工可调 (Task 12) and 自然语言改片 (bonus): the user can adjust one slot
without re-running the whole migration.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.stage2.llm_client import create_llm_client

PROMPT_PATH = Path(__file__).parent / "prompts" / "slot_edit.md"


def regenerate_slot(
    source_slot: dict[str, Any],
    current_slot: dict[str, Any],
    new_content: dict[str, Any],
    user_assets: dict[str, Any],
    instruction: str = "",
    force_strategy: str = "",
) -> dict[str, Any]:
    """Regenerate one migrated slot.

    Args:
        source_slot: the original blueprint slot (the skeleton template)
        current_slot: the current migrated slot (to be adjusted)
        new_content: topic / selling_points / target_type
        user_assets: available assets
        instruction: optional natural-language instruction, e.g. "开头更抓人"
        force_strategy: optional forced fill strategy (restructure/text_fill/packaging/aigc/asset_reuse)
    """
    client = create_llm_client()
    system_prompt = PROMPT_PATH.read_text(encoding="utf-8")

    user_prompt = f"""## 这个slot在爆款骨架里的模板
{json.dumps(source_slot, ensure_ascii=False, indent=2)}

## 当前迁移结果（需要调整）
{json.dumps(current_slot, ensure_ascii=False, indent=2)}

## 新内容
{json.dumps(new_content, ensure_ascii=False, indent=2)}

## 用户素材
{json.dumps(user_assets, ensure_ascii=False, indent=2)}

## 用户调整指令
{instruction or "（无特定指令，请优化这个slot的迁移质量）"}

{f"## 强制使用补全策略: {force_strategy}" if force_strategy else ""}

请只输出调整后的这一个slot的JSON对象（不要数组，不要其他slot）。"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    response = client.chat(messages=messages, tools=None)
    content = response.get("content", "{}")
    return _parse_json(content)


def _parse_json(content: str) -> dict[str, Any]:
    text = content.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:]).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                pass
        return {"error": "parse_failed", "raw_text": content}
