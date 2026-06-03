"""
vlm_enricher.py — Parallel VLM description of keyframe images.

Sends each keyframe as a base64-encoded image to a vision-capable LLM
(via OpenRouter or any OpenAI-compatible API) and returns natural-language
descriptions that can be embedded in the evidence package for Stage 2.

Designed to be called from pipeline_link.py after keyframe extraction.
"""
from __future__ import annotations
import asyncio
import base64
import logging
import os

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

_DESCRIBE_PROMPT = (
    "请用2-4句话描述这个视频关键帧的内容，依次关注："
    "①画面主体（人物表情/动作、场景环境、核心物体）；"
    "②镜头构图和视觉风格（景别、角度、色调）；"
    "③情绪氛围或戏剧张力；"
    "④任何可见的文字、字幕、特效或品牌元素。"
    "用连续的中文段落描述，不要分点列举。"
)


def _to_data_url(image_path: str) -> str:
    ext = os.path.splitext(image_path)[1].lower().lstrip(".")
    mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}.get(ext, "image/jpeg")
    with open(image_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    return f"data:{mime};base64,{b64}"


async def _describe_one(
    image_path: str | None,
    client: AsyncOpenAI,
    model: str,
    semaphore: asyncio.Semaphore,
) -> str | None:
    if not image_path or not os.path.exists(image_path):
        return None

    async with semaphore:
        try:
            data_url = _to_data_url(image_path)
            response = await client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "image_url", "image_url": {"url": data_url}},
                            {"type": "text", "text": _DESCRIBE_PROMPT},
                        ],
                    }
                ],
                max_tokens=300,
            )
            description = response.choices[0].message.content.strip()
            logger.info("VLM [%s] %s → %s…", model, os.path.basename(image_path), description[:60])
            return description
        except Exception as exc:
            logger.warning("VLM failed for %s: %s", image_path, exc)
            return None


async def describe_keyframes_async(
    image_paths: list[str | None],
    *,
    api_key: str,
    model: str,
    base_url: str = "https://openrouter.ai/api/v1",
    max_concurrent: int = 4,
) -> list[str | None]:
    """
    Describe a batch of keyframe images in parallel using a vision LLM.

    Args:
        image_paths:    List of absolute paths (None entries are skipped → None returned).
        api_key:        API key for OpenRouter (or other OpenAI-compatible provider).
        model:          Vision-capable model string, e.g. 'google/gemini-flash-1.5-8b'.
        base_url:       API base URL.
        max_concurrent: Max simultaneous requests (keep ≤5 to avoid rate limits).

    Returns:
        List of description strings, same length as image_paths.
        None for images that are missing or fail VLM processing.
    """
    client = AsyncOpenAI(api_key=api_key, base_url=base_url)
    semaphore = asyncio.Semaphore(max_concurrent)
    tasks = [_describe_one(p, client, model, semaphore) for p in image_paths]
    results = await asyncio.gather(*tasks)
    success = sum(1 for r in results if r is not None)
    logger.info("VLM enrichment: %d/%d keyframes described.", success, len(image_paths))
    return list(results)


def describe_keyframes(
    image_paths: list[str | None],
    *,
    api_key: str,
    model: str,
    base_url: str = "https://openrouter.ai/api/v1",
    max_concurrent: int = 4,
) -> list[str | None]:
    """Synchronous wrapper around describe_keyframes_async for use in sync pipelines."""
    return asyncio.run(
        describe_keyframes_async(
            image_paths,
            api_key=api_key,
            model=model,
            base_url=base_url,
            max_concurrent=max_concurrent,
        )
    )
