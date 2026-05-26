"""Processor: 关键帧抽取"""

from __future__ import annotations

import os

from src.stage1.types.evidence import Keyframe
from src.stage1.utils.ffmpeg import extract_frame
from src.stage1.utils.file_utils import write_json


def run(input_path: str, output_dir: str, context: dict) -> dict:
    scenes = context.get("scenes", [])
    if isinstance(scenes, dict):
        scenes = scenes.get("scenes", [])

    frames_dir = os.path.join(output_dir, "frames")
    os.makedirs(frames_dir, exist_ok=True)

    keyframes = []
    frame_index = 0

    for scene in scenes:
        times = _calculate_keyframe_timestamps(
            float(scene["start_time"]),
            float(scene["end_time"]),
        )
        scene.setdefault("keyframe_ids", [])
        for ts in times:
            frame_id = f"frame_{frame_index:03d}"
            frame_path = os.path.join(frames_dir, f"{frame_id}.jpg")
            extract_frame(input_path, ts, frame_path)
            keyframe = Keyframe(
                frame_id=frame_id,
                scene_id=scene["scene_id"],
                timestamp=round(ts, 3),
                path=frame_path,
            )
            keyframes.append(keyframe.__dict__)
            scene["keyframe_ids"].append(frame_id)
            frame_index += 1

    # 更新 scenes.json，写入 keyframe_ids
    write_json(os.path.join(output_dir, "scenes.json"), scenes)
    write_json(os.path.join(output_dir, "keyframes.json"), keyframes)
    return {"keyframes": keyframes, "scenes": scenes}


def _calculate_keyframe_timestamps(
    start: float,
    end: float,
    long_threshold: float = 5.0,
    interval: float = 3.0,
) -> list[float]:
    """
    计算一个镜头应该取哪些时间点的帧。
    短镜头取中点；长镜头取中点 + 每 interval 秒一帧。
    """
    duration = max(0.0, end - start)
    if duration <= 0:
        return []

    mid = start + duration / 2
    times = {round(mid, 3)}

    if duration > long_threshold:
        t = start + interval
        while t < end - 0.2:
            times.add(round(t, 3))
            t += interval

    return sorted(times)
