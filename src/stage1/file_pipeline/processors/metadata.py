"""Processor: 视频元信息提取"""

from __future__ import annotations

import os
from fractions import Fraction

from src.stage1.types.evidence import VideoMetadata
from src.stage1.utils.ffmpeg import run_ffprobe
from src.stage1.utils.file_utils import write_json


def _parse_fps(value: str | None) -> float:
    if not value or value == "0/0":
        return 0.0
    try:
        return float(Fraction(value))
    except Exception:
        try:
            return float(value)
        except Exception:
            return 0.0


def _aspect_ratio(width: int, height: int) -> str:
    if width <= 0 or height <= 0:
        return "unknown"
    # common social-video ratios
    ratio = width / height
    if abs(ratio - 9 / 16) < 0.03:
        return "9:16"
    if abs(ratio - 16 / 9) < 0.03:
        return "16:9"
    if abs(ratio - 1) < 0.03:
        return "1:1"
    return f"{width}:{height}"


def run(input_path: str, output_dir: str, context: dict) -> dict:
    probe = run_ffprobe(input_path)
    streams = probe.get("streams", [])
    fmt = probe.get("format", {})

    video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
    if not video_stream:
        raise RuntimeError("No video stream found.")

    audio_streams = [s for s in streams if s.get("codec_type") == "audio"]
    subtitle_streams = [s for s in streams if s.get("codec_type") == "subtitle"]

    width = int(video_stream.get("width", 0) or 0)
    height = int(video_stream.get("height", 0) or 0)
    fps = _parse_fps(video_stream.get("avg_frame_rate") or video_stream.get("r_frame_rate"))

    metadata = VideoMetadata(
        duration=round(float(fmt.get("duration", 0) or 0), 3),
        width=width,
        height=height,
        fps=round(fps, 3),
        codec=str(video_stream.get("codec_name", "unknown")),
        file_size=int(fmt.get("size", os.path.getsize(input_path)) or 0),
        has_audio=len(audio_streams) > 0,
        has_subtitle_track=len(subtitle_streams) > 0,
        bitrate=int(float(fmt.get("bit_rate", 0) or 0)),
        aspect_ratio=_aspect_ratio(width, height),
    )

    data = metadata.__dict__
    write_json(os.path.join(output_dir, "metadata.json"), data)
    return data