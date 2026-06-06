"""Streaming version of Stage 3 migration.

Yields LLM output chunks as they arrive, so the frontend can visualize the
migration process live instead of waiting for the full result.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Iterator

import requests

from src.stage3.asset_matcher import precheck_assets

PROMPT_PATH = Path(__file__).parent / "prompts" / "migration.md"


def _config() -> dict[str, str]:
    """Read OpenAI-compatible LLM config from env (same as llm_client)."""
    provider = os.getenv("LLM_PROVIDER", "doubao").lower()
    if provider == "doubao":
        return {
            "base_url": os.getenv("DOUBAO_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3"),
            "api_key": os.getenv("DOUBAO_API_KEY", ""),
            "model": os.getenv("DOUBAO_ENDPOINT", ""),
        }
    # generic OpenAI-compatible
    return {
        "base_url": os.getenv("LLM_BASE_URL", "https://api.openai.com/v1"),
        "api_key": os.getenv("LLM_API_KEY", ""),
        "model": os.getenv("LLM_MODEL", "gpt-4o-mini"),
    }


def run_migration_stream(
    blueprint: dict[str, Any],
    new_content: dict[str, Any],
    user_assets: dict[str, Any],
) -> Iterator[str]:
    """Yield raw text chunks from the LLM as the migration plan is generated.

    The final accumulated text is a JSON object (the migration result).
    """
    cfg = _config()
    if not cfg["api_key"]:
        yield json.dumps({"_error": "No API key. Set DOUBAO_API_KEY in .env"}, ensure_ascii=False)
        return

    system_prompt = PROMPT_PATH.read_text(encoding="utf-8")
    precheck = precheck_assets(blueprint, user_assets)

    user_prompt = f"""## 样例视频的可迁移结构（transfer blueprint）
{json.dumps(blueprint, ensure_ascii=False, indent=2)}

## 用户的新内容
{json.dumps(new_content, ensure_ascii=False, indent=2)}

## 用户拥有的素材
{json.dumps(user_assets, ensure_ascii=False, indent=2)}

## 素材预检查
{json.dumps(precheck, ensure_ascii=False, indent=2)}

请把样例结构迁移到新内容，识别素材缺口并给出补全策略，只输出JSON。"""

    payload = {
        "model": cfg["model"],
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": float(os.getenv("LLM_TEMPERATURE", "0.1")),
        "stream": True,
    }
    headers = {
        "Authorization": f"Bearer {cfg['api_key']}",
        "Content-Type": "application/json",
    }

    try:
        resp = requests.post(
            f"{cfg['base_url']}/chat/completions",
            headers=headers,
            json=payload,
            stream=True,
            timeout=120,
        )
        resp.raise_for_status()

        for line in resp.iter_lines():
            if not line:
                continue
            text = line.decode("utf-8").strip()
            if not text.startswith("data:"):
                continue
            data = text[len("data:"):].strip()
            if data == "[DONE]":
                break
            try:
                obj = json.loads(data)
                delta = obj.get("choices", [{}])[0].get("delta", {})
                content = delta.get("content")
                if content:
                    yield content
            except json.JSONDecodeError:
                continue
    except Exception as exc:  # noqa: BLE001
        yield json.dumps({"_error": str(exc)}, ensure_ascii=False)


def parse_migration_json(full_text: str) -> dict[str, Any]:
    """Parse the accumulated streamed text into the migration result dict."""
    text = full_text.strip()
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
        return {"error": "parse_failed", "raw_text": full_text}
