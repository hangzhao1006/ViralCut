"""
Processor: 音频提取
"""

from __future__ import annotations

import os

from src.stage1.utils.ffmpeg import extract_audio
from src.stage1.utils.file_utils import write_json
from src.stage1.utils.logger import get_logger

logger = get_logger(__name__)


def run(input_path: str, output_dir: str, context: dict) -> dict:
    metadata = context.get("metadata") or {}
    if not metadata.get("has_audio"):
        logger.info("视频无音频轨，跳过")
        return {"audio_path": None, "has_audio": False}

    audio_path = os.path.join(output_dir, "audio.wav")
    extract_audio(input_path, audio_path)
    logger.info("音频提取完成: %s", audio_path)

    result = {"audio_path": audio_path, "has_audio": True}
    write_json(os.path.join(output_dir, "audio.json"), result)
    return result