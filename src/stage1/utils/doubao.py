"""
火山方舟 Doubao API 封装

用于：
- Stage 1: 多模态 OCR（把关键帧发给 Doubao，识别画面文字 + 画面内容描述）
- Stage 2: Agent 分析（脚本结构、节奏、包装等）
"""

from __future__ import annotations

import base64
import json
import os
from typing import Optional

import requests

from src.stage1.utils.logger import get_logger

logger = get_logger(__name__)


def _get_config() -> dict:
    """从环境变量读取 Doubao API 配置"""
    api_key = os.getenv("DOUBAO_API_KEY")
    endpoint = os.getenv("DOUBAO_ENDPOINT")
    model = os.getenv("DOUBAO_MODEL", "Doubao-Seed-2.0-lite")

    if not api_key or not endpoint:
        raise RuntimeError(
            "DOUBAO_API_KEY and DOUBAO_ENDPOINT must be set in .env. "
            "See .env.example for details."
        )

    return {
        "api_key": api_key,
        "endpoint": endpoint,
        "model": model,
        "base_url": "https://ark.cn-beijing.volces.com/api/v3",
    }


def call_text(prompt: str, system_prompt: Optional[str] = None) -> str:
    """
    纯文本调用 Doubao API。
    返回模型回复文本。
    """
    config = _get_config()

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    return _request(config, messages)


def call_with_image(
    prompt: str,
    image_path: str,
    system_prompt: Optional[str] = None,
) -> str:
    """
    图片 + 文本多模态调用。
    把图片编码为 base64 发送给 Doubao。
    返回模型回复文本。
    """
    config = _get_config()
    image_b64 = _encode_image(image_path)
    ext = os.path.splitext(image_path)[1].lower()
    media_type = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
    }.get(ext, "image/jpeg")

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})

    messages.append({
        "role": "user",
        "content": [
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:{media_type};base64,{image_b64}",
                },
            },
            {
                "type": "text",
                "text": prompt,
            },
        ],
    })

    return _request(config, messages)


def call_ocr(image_path: str) -> list[dict]:
    """
    用 Doubao 多模态模型做 OCR。
    返回识别到的文字列表。

    返回格式：
    [
        {
            "content": "限时优惠",
            "position": "画面下方居中",
            "type": "promotion",
            "confidence": 0.9
        }
    ]
    """
    system_prompt = """你是一个视频画面 OCR 分析专家。你的任务是识别画面中所有可见的文字信息。

对每一段文字，返回以下信息：
- content: 文字内容
- position: 在画面中的位置描述（如"顶部居中"、"底部左侧"、"画面中央"）
- type: 文字类型，从以下选择：subtitle(字幕) / title_bar(标题条) / price(价格) / selling_point(卖点) / cta(行动号召) / brand(品牌) / other(其他)
- confidence: 你对识别结果的置信度 0-1

只返回 JSON 数组，不要任何额外文字。如果画面中没有文字，返回空数组 []。"""

    prompt = "请识别这张视频截图中的所有文字信息。只返回JSON数组。"

    try:
        response = call_with_image(prompt, image_path, system_prompt)
        # 尝试解析 JSON
        text = response.strip()
        # 去掉可能的 markdown 代码块
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()
        result = json.loads(text)
        if isinstance(result, list):
            return result
        return []
    except (json.JSONDecodeError, Exception) as e:
        logger.warning("Doubao OCR JSON 解析失败: %s, 原始回复: %s", e, response[:200] if 'response' in dir() else "N/A")
        return []


def _request(config: dict, messages: list[dict]) -> str:
    """发送请求到火山方舟 API"""
    url = f"{config['base_url']}/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {config['api_key']}",
    }
    payload = {
        "model": config["endpoint"],
        "messages": messages,
        "max_tokens": 2000,
        "temperature": 0.1,
    }

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]
    except requests.exceptions.Timeout:
        raise RuntimeError("Doubao API request timed out (60s)")
    except requests.exceptions.HTTPError as e:
        raise RuntimeError(f"Doubao API HTTP error: {e.response.status_code} {e.response.text[:200]}")
    except (KeyError, IndexError) as e:
        raise RuntimeError(f"Doubao API unexpected response format: {e}")

def call_ocr_batch(image_paths: list[str]) -> dict[str, list[dict]]:
    """
    一次API调用识别多张关键帧的文字。
    每次最多传4张图。
    
    返回: {图片路径: [识别结果列表]}
    """
    config = _get_config()

    system_prompt = """你是一个视频画面 OCR 分析专家。我会给你多张视频截图，请分别识别每张图片中的所有可见文字。

对每张图片的每段文字，返回：
- content: 文字内容
- position: 位置描述（如"顶部居中"、"底部左侧"）
- type: 文字类型（subtitle/title_bar/price/selling_point/cta/brand/other）
- confidence: 置信度 0-1

返回一个JSON对象，key是"image_1"、"image_2"...，value是该图片的文字数组。
如果某张图片没有文字，对应value为空数组。
只返回JSON，不要任何额外文字。"""

    # 构建多图消息
    content = []
    for i, path in enumerate(image_paths):
        image_b64 = _encode_image(path)
        ext = os.path.splitext(path)[1].lower()
        media_type = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".webp": "image/webp",
        }.get(ext, "image/jpeg")

        content.append({
            "type": "text",
            "text": f"第{i+1}张图片：",
        })
        content.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:{media_type};base64,{image_b64}",
            },
        })

    content.append({
        "type": "text",
        "text": f"请分别识别以上{len(image_paths)}张图片中的所有文字。只返回JSON。",
    })

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": content},
    ]

    try:
        response = _request(config, messages)
        text = response.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()

        result = json.loads(text)

        # 把 image_1, image_2... 映射回文件路径
        path_results = {}
        for i, path in enumerate(image_paths):
            key = f"image_{i+1}"
            path_results[path] = result.get(key, [])

        return path_results

    except (json.JSONDecodeError, Exception) as e:
        logger.warning("Doubao 批量OCR解析失败: %s", e)
        return {path: [] for path in image_paths}

def _encode_image(image_path: str) -> str:
    """读取图片文件并编码为 base64"""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")