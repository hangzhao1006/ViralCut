"""Generic OpenAI-compatible LLM client for Stage 2 agents.

Supports any OpenAI-compatible API: Doubao (Volcano Ark), OpenAI, DeepSeek,
Moonshot, Qwen, etc. Just change base_url and api_key in .env.

Usage:
    client = create_llm_client()               # reads from .env
    client = create_llm_client(provider="openai")  # explicit provider
"""

from __future__ import annotations

import json
import os
import base64
from typing import Any

import requests

from src.stage1.utils.logger import get_logger

logger = get_logger(__name__)

# Provider presets: name -> (base_url, env_key_name, default_model)
PROVIDER_PRESETS = {
    "doubao": (
        "https://ark.cn-beijing.volces.com/api/v3",
        "DOUBAO_API_KEY",
        None,  # uses DOUBAO_ENDPOINT as model
    ),
    "openai": (
        "https://api.openai.com/v1",
        "OPENAI_API_KEY",
        "gpt-4o",
    ),
    "deepseek": (
        "https://api.deepseek.com",
        "DEEPSEEK_API_KEY",
        "deepseek-chat",
    ),
    "moonshot": (
        "https://api.moonshot.cn/v1",
        "MOONSHOT_API_KEY",
        "moonshot-v1-8k",
    ),
}


class LLMClient:
    """OpenAI-compatible chat completion client with tool calling support."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        timeout: int = 120,
        temperature: float = 0.1,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.temperature = temperature
        self._call_count = 0

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Send a chat completion request. Returns a normalized response dict.

        Response format:
            {"content": "...", "tool_calls": [...] or None}

        tool_calls item format:
            {"id": "...", "function": {"name": "...", "arguments": {...}}}
        """
        self._call_count += 1
        url = f"{self.base_url}/chat/completions"

        body: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
        }
        if tools:
            body["tools"] = tools
            # body["tool_choice"] = "auto"

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        logger.debug(
            "LLM call #%d: model=%s, messages=%d, tools=%d",
            self._call_count,
            self.model,
            len(messages),
            len(tools or []),
        )

        resp = None
        try:
            resp = requests.post(
                url, json=body, headers=headers, timeout=self.timeout
            )
            resp.raise_for_status()
            data = resp.json()
        except requests.exceptions.RequestException as exc:
            body_text = ""
            if resp is not None:
                body_text = resp.text[:500]
            logger.error("LLM request failed: %s", exc)
            logger.error("Response body: %s", body_text or "no response body")
            raise RuntimeError(f"LLM API request failed: {exc}") from exc

        return self._normalize_response(data)

    def chat_with_vision(
        self,
        text_prompt: str,
        image_path: str,
        system_prompt: str | None = None,
    ) -> str:
        """Send a multimodal request with one image. Returns text content."""
        with open(image_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode("utf-8")

        # Detect media type
        ext = os.path.splitext(image_path)[1].lower()
        media_type = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".webp": "image/webp",
        }.get(ext, "image/jpeg")

        messages: list[dict[str, Any]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        messages.append({
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{media_type};base64,{image_data}",
                    },
                },
                {"type": "text", "text": text_prompt},
            ],
        })

        result = self.chat(messages=messages, tools=None)
        return result.get("content", "")

    def _normalize_response(self, data: dict[str, Any]) -> dict[str, Any]:
        """Normalize API response to a stable format."""
        choices = data.get("choices", [])
        if not choices:
            return {"content": "", "tool_calls": None}

        message = choices[0].get("message", {})
        content = message.get("content") or ""
        raw_tool_calls = message.get("tool_calls")

        tool_calls = None
        if raw_tool_calls:
            tool_calls = []
            for tc in raw_tool_calls:
                fn = tc.get("function", {})
                args = fn.get("arguments", "{}")
                # Keep as string for API compatibility
                if not isinstance(args, str):
                    args = json.dumps(args, ensure_ascii=False)
                    
                tool_calls.append({
                    "id": tc.get("id", ""),
                    "type": "function",
                    "function": {
                        "name": fn.get("name", ""),
                        "arguments": args,
                    },
                })

        return {"content": content, "tool_calls": tool_calls}

    @property
    def call_count(self) -> int:
        return self._call_count


def create_llm_client(provider: str | None = None) -> LLMClient:
    """Create an LLM client from .env configuration.

    .env variables:
        LLM_PROVIDER=doubao          # doubao / openai / deepseek / moonshot
        LLM_BASE_URL=               # override base_url (optional)
        LLM_API_KEY=                # override api_key (optional)
        LLM_MODEL=                  # override model (optional)
        LLM_TEMPERATURE=0.1
        LLM_TIMEOUT=120

        # Provider-specific (used if LLM_API_KEY not set):
        DOUBAO_API_KEY=ark-xxx
        DOUBAO_ENDPOINT=ep-xxx      # Doubao uses endpoint as model name
        OPENAI_API_KEY=sk-xxx
        DEEPSEEK_API_KEY=sk-xxx
    """
    provider = (provider or os.getenv("LLM_PROVIDER", "doubao")).lower().strip()

    # Get preset defaults
    preset = PROVIDER_PRESETS.get(provider)
    if preset:
        default_base_url, default_key_env, default_model = preset
    else:
        default_base_url = ""
        default_key_env = "LLM_API_KEY"
        default_model = ""

    # Resolve base_url
    base_url = os.getenv("LLM_BASE_URL") or default_base_url
    if not base_url:
        raise ValueError(
            f"No base_url for provider '{provider}'. "
            f"Set LLM_BASE_URL in .env or use a known provider: {list(PROVIDER_PRESETS.keys())}"
        )

    # Resolve api_key
    api_key = os.getenv("LLM_API_KEY") or os.getenv(default_key_env, "")
    if not api_key:
        raise ValueError(
            f"No API key found. Set LLM_API_KEY or {default_key_env} in .env"
        )

    # Resolve model
    model = os.getenv("LLM_MODEL", "")
    if not model:
        if provider == "doubao":
            model = os.getenv("DOUBAO_ENDPOINT", "")
        else:
            model = default_model or ""
    if not model:
        raise ValueError(
            f"No model specified. Set LLM_MODEL in .env"
        )

    temperature = float(os.getenv("LLM_TEMPERATURE", "0.1"))
    timeout = int(os.getenv("LLM_TIMEOUT", "120"))

    logger.info(
        "LLM client: provider=%s, base_url=%s, model=%s",
        provider, base_url, model,
    )

    return LLMClient(
        base_url=base_url,
        api_key=api_key,
        model=model,
        timeout=timeout,
        temperature=temperature,
    )