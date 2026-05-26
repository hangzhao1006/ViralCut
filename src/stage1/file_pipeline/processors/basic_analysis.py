"""Processor: 基础统计分析"""

from __future__ import annotations

import os

from src.stage1.utils.file_utils import write_json


def run(input_path: str, output_dir: str, context: dict) -> dict:
    metadata = context.get("metadata") or {}
    duration = float(metadata.get("duration", 0) or 0)

    scenes = context.get("scenes", [])
    if isinstance(scenes, dict):
        scenes = scenes.get("scenes", [])

    transcript = context.get("transcript", [])
    if isinstance(transcript, dict):
        transcript = transcript.get("transcript", [])

    ocr_results = context.get("ocr_results", [])
    if isinstance(ocr_results, dict):
        ocr_results = ocr_results.get("ocr_results", [])

    beats = context.get("beats")
    if isinstance(beats, dict) and "beats" in beats:
        beats = beats.get("beats")

    shot_count = len(scenes)
    avg_shot_duration = duration / shot_count if shot_count and duration > 0 else 0.0
    shot_density = shot_count / duration if duration > 0 else 0.0

    transcript_segment_count = len(transcript)
    transcript_char_count = sum(len((seg.get("text") or "").strip()) for seg in transcript)

    ocr_text_count = sum(len(item.get("texts", [])) for item in ocr_results)
    ocr_text_per_second = ocr_text_count / duration if duration > 0 else 0.0

    subtitle_density = _subtitle_density(ocr_text_per_second)
    estimated_pace = _estimated_pace(avg_shot_duration)

    data = {
        "shot_count": shot_count,
        "avg_shot_duration": round(avg_shot_duration, 3),
        "shot_density": round(shot_density, 4),
        "transcript_segment_count": transcript_segment_count,
        "transcript_char_count": transcript_char_count,
        "ocr_text_count": ocr_text_count,
        "ocr_text_per_second": round(ocr_text_per_second, 4),
        "subtitle_density": subtitle_density,
        "estimated_pace": estimated_pace,
    }

    if isinstance(beats, dict) and beats.get("beat_sync_score") is not None:
        data["beat_sync_score"] = beats["beat_sync_score"]

    write_json(os.path.join(output_dir, "basic_analysis.json"), data)
    return data


def _estimated_pace(avg_shot_duration: float) -> str:
    if avg_shot_duration <= 0:
        return "unknown"
    if avg_shot_duration < 1.5:
        return "fast"
    if avg_shot_duration <= 3.0:
        return "medium"
    return "slow"


def _subtitle_density(ocr_text_per_second: float) -> str:
    if ocr_text_per_second <= 0:
        return "none"
    if ocr_text_per_second > 1.0:
        return "high"
    if ocr_text_per_second >= 0.3:
        return "medium"
    return "low"
