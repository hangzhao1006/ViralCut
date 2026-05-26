"""Processor: 镜头分割"""

from __future__ import annotations

import os

from src.stage1.types.evidence import Scene
from src.stage1.utils.ffmpeg import detect_scenes
from src.stage1.utils.file_utils import write_json


def run(input_path: str, output_dir: str, context: dict) -> dict:
    metadata = context.get("metadata") or {}
    duration = float(metadata.get("duration", 0) or 0)
    if duration <= 0:
        raise RuntimeError("metadata.duration is required for scene detection.")

    cut_points = _adaptive_detect(input_path, duration)
    cut_points = _merge_short_scenes(cut_points, min_gap=0.3)

    boundaries = [0.0] + [t for t in cut_points if 0 < t < duration] + [duration]
    scenes = []
    for idx in range(len(boundaries) - 1):
        start = round(boundaries[idx], 3)
        end = round(boundaries[idx + 1], 3)
        if end <= start:
            continue
        scene = Scene(
            scene_id=f"scene_{idx:03d}",
            index=idx,
            start_time=start,
            end_time=end,
            duration=round(end - start, 3),
        )
        scenes.append(scene.__dict__)

    write_json(os.path.join(output_dir, "scenes.json"), scenes)
    return {"scenes": scenes}


def _adaptive_detect(video_path: str, duration: float) -> list[float]:
    """
    自适应镜头分割：根据结果数量自动调整阈值。
    返回切换时间点列表。
    """
    timestamps = detect_scenes(video_path, threshold=0.3)

    # 镜头过碎：短视频中每秒 2 个以上切点通常过敏
    if len(timestamps) > duration * 2:
        timestamps = detect_scenes(video_path, threshold=0.5)

    # 镜头过少：降低阈值
    if len(timestamps) < 1:
        timestamps = detect_scenes(video_path, threshold=0.15)

    # 仍然过少：固定间隔切分
    if len(timestamps) < 1 and duration > 3:
        timestamps = [round(t, 3) for t in _frange(3.0, duration, 3.0)]

    return [t for t in timestamps if 0 < t < duration]


def _merge_short_scenes(timestamps: list[float], min_gap: float = 0.3) -> list[float]:
    """
    合并间隔小于 min_gap 秒的相邻切换点。
    """
    if not timestamps:
        return []
    merged = [timestamps[0]]
    for ts in timestamps[1:]:
        if ts - merged[-1] >= min_gap:
            merged.append(ts)
    return merged


def _frange(start: float, stop: float, step: float):
    value = start
    while value < stop:
        yield value
        value += step