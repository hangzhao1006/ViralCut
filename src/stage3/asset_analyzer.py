"""Asset analyzer: understand user-uploaded materials via vision before migration.

For each uploaded video/image, extract a representative frame and use the
vision model to produce a description, scene classification, and suitability
recommendation (opening / middle / ending). This implements 真实素材适配 (Task 11).
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from typing import Any

from src.stage2.llm_client import create_llm_client

# Scene type enum the model should pick from
SCENE_TYPES = [
    "product_closeup",      # 商品特写
    "product_in_use",       # 使用过程
    "person",               # 人物
    "scene_environment",    # 场景/环境
    "text_or_title",        # 文字/标题画面
    "comparison",           # 对比
    "detail_macro",         # 细节/微距
    "wide_establishing",    # 大场景/全景
    "other",
]

VISION_PROMPT = f"""你是视频素材分析助手。请分析这张图片（来自用户上传的素材），输出JSON：

{{
  "description": "一句话描述画面内容（中文，20字以内）",
  "scene_type": "从以下选一个：{', '.join(SCENE_TYPES)}",
  "main_subject": "画面主体是什么",
  "visual_quality": "high | medium | low",
  "suitable_for": ["从 opening/middle/climax/ending 中选适合的位置，可多选"],
  "has_text": true/false
}}

只输出JSON，不要解释。"""


def _extract_mid_frame(video_path: str) -> str | None:
    """Extract the middle frame of a video to a temp jpg. Returns path or None."""
    # Get duration
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", video_path],
            capture_output=True, text=True,
        )
        duration = float(json.loads(result.stdout).get("format", {}).get("duration", 2))
    except Exception:
        duration = 2.0

    mid = duration / 2
    tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
    tmp.close()
    cmd = [
        "ffmpeg", "-y", "-ss", f"{mid:.2f}", "-i", video_path,
        "-frames:v", "1", "-q:v", "2", tmp.name,
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode == 0 and os.path.exists(tmp.name) and os.path.getsize(tmp.name) > 0:
        return tmp.name
    return None


def analyze_asset(asset_path: str, asset_type: str, asset_id: str) -> dict[str, Any]:
    """Analyze a single uploaded asset. Returns enriched metadata."""
    client = create_llm_client()

    # Get the frame to analyze
    if asset_type == "video":
        frame_path = _extract_mid_frame(asset_path)
        duration = _get_duration(asset_path)
    else:  # image
        frame_path = asset_path
        duration = None

    base = {"id": asset_id, "type": asset_type}
    if duration is not None:
        base["duration"] = round(duration, 1)

    if not frame_path:
        base.update({
            "description": "(无法提取画面)",
            "scene_type": "other",
            "suitable_for": ["middle"],
            "analyzed": False,
        })
        return base

    try:
        result_text = client.chat_with_vision(
            text_prompt=VISION_PROMPT,
            image_path=frame_path,
        )
        analysis = _parse_json(result_text)
        base.update({
            "description": analysis.get("description", ""),
            "scene_type": analysis.get("scene_type", "other"),
            "main_subject": analysis.get("main_subject", ""),
            "visual_quality": analysis.get("visual_quality", "medium"),
            "suitable_for": analysis.get("suitable_for", ["middle"]),
            "has_text": analysis.get("has_text", False),
            "analyzed": True,
        })
    except Exception as exc:  # noqa: BLE001
        base.update({
            "description": f"(分析失败: {exc})",
            "scene_type": "other",
            "suitable_for": ["middle"],
            "analyzed": False,
        })
    finally:
        # Clean up temp frame for videos
        if asset_type == "video" and frame_path and frame_path != asset_path:
            try:
                os.remove(frame_path)
            except OSError:
                pass

    return base


def analyze_assets(assets: list[dict[str, Any]]) -> dict[str, Any]:
    """Analyze a list of uploaded assets. Each item: {id, type, path}.

    Returns user_assets dict ready for Stage 3 migration.
    """
    videos = []
    images = []

    for a in assets:
        atype = a.get("type")
        analyzed = analyze_asset(a["path"], atype, a["id"])
        if atype == "video":
            videos.append(analyzed)
        elif atype == "image":
            images.append(analyzed)

    return {
        "videos": videos,
        "images": images,
        "texts": [],
        "has_bgm": False,
    }


def _get_duration(video_path: str) -> float:
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", video_path],
            capture_output=True, text=True,
        )
        return float(json.loads(result.stdout).get("format", {}).get("duration", 0))
    except Exception:
        return 0.0


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
        return {}
