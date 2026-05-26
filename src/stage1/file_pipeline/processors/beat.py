"""Processor: BGM 节拍检测"""

from __future__ import annotations

import os
from bisect import bisect_left

from src.stage1.utils.file_utils import write_json


def run(input_path: str, output_dir: str, context: dict) -> dict:
    audio = context.get("audio") or {}
    if not audio.get("has_audio") or not audio.get("audio_path"):
        data = None
        write_json(os.path.join(output_dir, "beats.json"), data)
        return {"beats": data, "skipped": True, "reason": "no_audio"}

    try:
        import librosa  # type: ignore
    except Exception as exc:
        raise RuntimeError("librosa is not installed. Install librosa or skip beat.") from exc

    y, sr = librosa.load(audio["audio_path"], sr=None)
    tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
    beat_times = librosa.frames_to_time(beat_frames, sr=sr).tolist()

    scenes = context.get("scenes", [])
    if isinstance(scenes, dict):
        scenes = scenes.get("scenes", [])
    scene_cuts = [float(s["start_time"]) for s in scenes if float(s.get("start_time", 0)) > 0]

    score = _calculate_beat_sync_score(scene_cuts, beat_times) if beat_times else None

    bpm = float(tempo[0]) if hasattr(tempo, "__len__") else float(tempo)
    data = {
        "bpm": round(bpm, 3),
        "beat_timestamps": [round(float(t), 3) for t in beat_times],
        "has_vocal": False,
        "beat_sync_score": score,
    }
    write_json(os.path.join(output_dir, "beats.json"), data)
    return {"beats": data}


def _calculate_beat_sync_score(
    scene_cuts: list[float],
    beat_timestamps: list[float],
    tolerance: float = 0.1,
) -> float:
    """
    计算镜头切换与节拍的对齐度。
    对每个镜头切换点，找最近的节拍，如果距离 < tolerance 秒则算卡点。
    """
    if not scene_cuts or not beat_timestamps:
        return 0.0

    beats = sorted(beat_timestamps)
    matched = 0
    for cut in scene_cuts:
        idx = bisect_left(beats, cut)
        candidates = []
        if idx < len(beats):
            candidates.append(abs(beats[idx] - cut))
        if idx > 0:
            candidates.append(abs(beats[idx - 1] - cut))
        if candidates and min(candidates) <= tolerance:
            matched += 1

    return round(matched / len(scene_cuts), 4)