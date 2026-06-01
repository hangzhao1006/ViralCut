"""
文件输入与校验

职责：确保视频文件可用，返回 VideoSource 对象。
不做任何视频处理，只做校验。
"""

from __future__ import annotations

import os

from src.stage1.types.evidence import SourceType, VideoSource
from src.stage1.utils.ffmpeg import run_ffprobe
from src.stage1.utils.file_utils import (
    create_output_dir,
    generate_video_id,
    get_file_size,
    is_video_file,
)
from src.stage1.utils.logger import get_logger


logger = get_logger(__name__)


def validate_and_prepare(file_path: str) -> dict:
    """
    完整的文件校验流程，返回 video_id、VideoSource、output_dir。
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Video file not found: {file_path}")

    if not os.path.isfile(file_path):
        raise ValueError(f"Input path is not a file: {file_path}")

    if not is_video_file(file_path):
        raise ValueError(
            "Unsupported video format. Supported: .mp4 .mov .mkv .webm .avi .flv"
        )

    probe = run_ffprobe(file_path)
    duration = float(probe.get("format", {}).get("duration", 0) or 0)
    if duration < 1:
        raise ValueError(f"Video duration is too short: {duration:.2f}s")
    if duration > 600:
        logger.warning("Video duration is longer than 600s; processing may be slow.")

    file_size = get_file_size(file_path)
    if file_size > 500 * 1024 * 1024:
        logger.warning("Video file is larger than 500MB; processing may be slow.")

    video_id = generate_video_id(os.path.basename(file_path))
    output_dir = create_output_dir(video_id)

    source = VideoSource(
        type=SourceType.FILE,
        local_path=os.path.abspath(file_path),
        original_filename=os.path.basename(file_path),
    )

    return {
        "video_id": video_id,
        "source": source,
        "output_dir": output_dir,
    }
