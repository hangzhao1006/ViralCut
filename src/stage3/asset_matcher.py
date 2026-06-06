"""Asset pre-checking: compute simple stats so the LLM doesn't have to count assets."""

from __future__ import annotations

from typing import Any


def precheck_assets(blueprint: dict[str, Any], user_assets: dict[str, Any]) -> dict[str, Any]:
    """Code-level pre-check to give the LLM an initial asset-matching judgment.

    Returns per-slot likely-gap flags based on min_clip_count vs available videos.
    """
    videos = user_assets.get("videos", [])
    images = user_assets.get("images", [])
    texts = user_assets.get("texts", [])

    video_count = len(videos)
    image_count = len(images)
    text_count = len(texts)
    total_video_duration = round(sum(v.get("duration", 0) for v in videos), 1)
    has_bgm = user_assets.get("has_bgm", False)

    slot_checks = []
    for slot in blueprint.get("structure_template", []):
        ir = slot.get("input_requirements", {})
        min_clips = ir.get("min_clip_count", 0)
        needed = [str(a).lower() for a in ir.get("needed_assets", [])]

        needs_video = any("video" in a or "clip" in a for a in needed)
        needs_image = any("image" in a or "background" in a or "cover" in a for a in needed)
        needs_music = any("music" in a or "bgm" in a or "beat" in a for a in needed)

        likely_gap = False
        gap_reasons = []

        if needs_video and video_count < min_clips:
            likely_gap = True
            gap_reasons.append(f"需要{min_clips}个视频片段，用户有{video_count}个")
        if needs_music and not has_bgm:
            likely_gap = True
            gap_reasons.append("需要BGM/音乐，用户未提供")

        slot_checks.append({
            "slot_id": slot.get("slot_id"),
            "slot_type": slot.get("slot_type"),
            "min_clip_count": min_clips,
            "needs_video": needs_video,
            "needs_image": needs_image,
            "needs_music": needs_music,
            "likely_gap": likely_gap,
            "gap_reasons": gap_reasons,
        })

    return {
        "user_video_count": video_count,
        "user_image_count": image_count,
        "user_text_count": text_count,
        "total_video_duration": total_video_duration,
        "has_bgm": has_bgm,
        "slot_checks": slot_checks,
    }
