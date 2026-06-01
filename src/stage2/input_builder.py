"""Stage 2 输入构建器：evidence_package.json -> TimelineIndex。

本模块为纯 Python 实现，不调用任何 LLM。它将 Stage 1 的输出规范化为
可供 Stage 2 智能体查询的时间线证据。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional
import bisect
import json
import math
import os


Number = int | float


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _get_time(item: dict[str, Any]) -> float:
    """Return the best timestamp for scenes/keyframes/ocr/transcript/beats."""
    for key in ("timestamp", "time", "start", "start_time"):
        if key in item:
            return _as_float(item.get(key))
    return 0.0


def _get_end_time(item: dict[str, Any]) -> float:
    for key in ("end", "end_time"):
        if key in item:
            return _as_float(item.get(key))
    start = _get_time(item)
    duration = _as_float(item.get("duration"), 0.0)
    return start + duration


def _in_range(item: dict[str, Any], start: float, end: float) -> bool:
    t0 = _get_time(item)
    t1 = _get_end_time(item)
    # Treat point events as inside if timestamp is inside range.
    if abs(t1 - t0) < 1e-6:
        return start <= t0 < end
    return t1 > start and t0 < end


def _safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _normalize_text(text: Any) -> str:
    return str(text or "").strip()


@dataclass
class TimelineIndex:
    """Queryable index over Stage 1 evidence package.

    The class intentionally accepts flexible Stage 1 field names, because the
    earlier pipeline has evolved several times. Stage 2 should not crash if a
    field is missing; it should return empty evidence and let the Evaluator flag
    quality issues later.
    """

    evidence_package: dict[str, Any]
    scenes: list[dict[str, Any]] = field(init=False)
    keyframes: list[dict[str, Any]] = field(init=False)
    ocr_results: list[dict[str, Any]] = field(init=False)
    transcript: list[dict[str, Any]] = field(init=False)
    beats: list[dict[str, Any] | float] = field(init=False)
    metadata: dict[str, Any] = field(init=False)
    basic_analysis: dict[str, Any] = field(init=False)
    segments: list[dict[str, Any]] = field(default_factory=list)

    _keyframe_by_id: dict[str, dict[str, Any]] = field(init=False, default_factory=dict)
    _ocr_by_frame_id: dict[str, dict[str, Any]] = field(init=False, default_factory=dict)

    def __post_init__(self) -> None:
        ep = self.evidence_package
        self.scenes = _safe_list(ep.get("scenes"))
        self.keyframes = _safe_list(ep.get("keyframes"))
        self.ocr_results = _safe_list(ep.get("ocr_results") or ep.get("ocr") or ep.get("ocr_frames"))
        self.transcript = _safe_list(ep.get("transcript"))
        _beats_raw = ep.get("beats") or {}
        if isinstance(_beats_raw, dict):
            self.beats = _beats_raw.get("beat_timestamps", [])
            self.beats_info = _beats_raw
        else:
            self.beats = _safe_list(_beats_raw)
            self.beats_info = {}
        self.metadata = ep.get("metadata") or ep.get("video_metadata") or {}
        self.basic_analysis = ep.get("basic_analysis") or ep.get("analysis") or {}

        self.scenes.sort(key=_get_time)
        self.keyframes.sort(key=_get_time)
        self.ocr_results.sort(key=_get_time)
        self.transcript.sort(key=_get_time)

        self._keyframe_by_id = {
            str(k.get("frame_id") or k.get("id")): k
            for k in self.keyframes
            if k.get("frame_id") or k.get("id")
        }
        self._ocr_by_frame_id = {
            str(o.get("frame_id")): o
            for o in self.ocr_results
            if o.get("frame_id")
        }

    @classmethod
    def from_file(cls, path: str) -> "TimelineIndex":
        with open(path, "r", encoding="utf-8") as f:
            return cls(json.load(f))

    @property
    def duration(self) -> float:
        return _as_float(
            self.metadata.get("duration")
            or self.evidence_package.get("duration")
            or self.basic_analysis.get("duration"),
            0.0,
        )

    def set_segments(self, segments: list[dict[str, Any]]) -> None:
        """Inject Script Agent output so later tools can query by segment_id."""
        normalized: list[dict[str, Any]] = []
        for i, seg in enumerate(segments or []):
            item = dict(seg)
            item.setdefault("segment_id", f"seg_{i + 1:03d}")
            item["start_time"] = _as_float(item.get("start_time", item.get("start", 0.0)))
            item["end_time"] = _as_float(item.get("end_time", item.get("end", self.duration)))
            normalized.append(item)
        self.segments = sorted(normalized, key=lambda x: x.get("start_time", 0.0))

    def get_overview(self) -> dict[str, Any]:
        resolution = self.metadata.get("resolution")
        if not resolution:
            w = self.metadata.get("width") or self.evidence_package.get("width")
            h = self.metadata.get("height") or self.evidence_package.get("height")
            resolution = f"{w}x{h}" if w and h else None

        return {
            "video_id": self.evidence_package.get("video_id") or self.metadata.get("video_id"),
            "duration": self.duration,
            "resolution": resolution,
            "fps": self.metadata.get("fps") or self.evidence_package.get("fps"),
            "scene_count": len(self.scenes),
            "keyframe_count": len(self.keyframes),
            "transcript_segment_count": len(self.transcript),
            "ocr_frame_count": sum(1 for x in self.ocr_results if _normalize_text(x.get("display_text"))),
            "beat_count": len(self.beats),
            "beat_sync_score": self.beats_info.get("beat_sync_score"),
            "bpm": self.beats_info.get("bpm"),
            "estimated_pace": self.basic_analysis.get("estimated_pace"),
            "subtitle_density": self.basic_analysis.get("subtitle_density"),
            "avg_shot_duration": self.basic_analysis.get("avg_shot_duration"),
            "shot_density": self.basic_analysis.get("shot_density"),
            "has_speech": len(self.transcript) > 0,
        }

    def _scene_id_for_time(self, timestamp: float) -> Optional[str]:
        for scene in self.scenes:
            if _get_time(scene) <= timestamp < _get_end_time(scene):
                return str(scene.get("scene_id") or scene.get("id"))
        return None

    def _enrich_keyframe(self, kf: dict[str, Any]) -> dict[str, Any]:
        frame_id = str(kf.get("frame_id") or kf.get("id") or "")
        ocr = self._ocr_by_frame_id.get(frame_id, {})
        t = _get_time(kf)
        return {
            "frame_id": frame_id,
            "timestamp": t,
            "path": kf.get("path") or kf.get("image_path"),
            "scene_id": kf.get("scene_id") or self._scene_id_for_time(t),
            "display_text": _normalize_text(ocr.get("display_text")),
            "display_texts": ocr.get("display_texts") or [],
            "ocr_source": ocr.get("ocr_source"),
        }

    def _beat_time(self, beat: dict[str, Any] | float) -> float:
        if isinstance(beat, (int, float)):
            return float(beat)
        return _get_time(beat)

    def query_timeline(self, start_time: Number, end_time: Number) -> dict[str, Any]:
        start = max(0.0, _as_float(start_time))
        end = max(start, _as_float(end_time, self.duration))
        scenes = [s for s in self.scenes if _in_range(s, start, end)]
        keyframes = [self._enrich_keyframe(k) for k in self.keyframes if start <= _get_time(k) < end]
        transcript = [t for t in self.transcript if _in_range(t, start, end)]
        beats = [b for b in self.beats if start <= self._beat_time(b) < end]
        return {
            "time_range": [round(start, 3), round(end, 3)],
            "scenes": scenes,
            "keyframes": keyframes,
            "transcript": transcript,
            "beat_count": len(beats),
            "beats": beats[:80],  # avoid returning huge arrays to LLM tools
            "metrics": self.compute_metrics(start, end),
        }

    def compute_metrics(self, start_time: Number, end_time: Number) -> dict[str, Any]:
        start = max(0.0, _as_float(start_time))
        end = max(start, _as_float(end_time, self.duration))
        span = max(end - start, 1e-6)
        scenes = [s for s in self.scenes if _in_range(s, start, end)]
        keyframes = [self._enrich_keyframe(k) for k in self.keyframes if start <= _get_time(k) < end]
        text_frames = [k for k in keyframes if k.get("display_text")]
        beats = [b for b in self.beats if start <= self._beat_time(b) < end]

        shot_durations = []
        for s in scenes:
            dur = _get_end_time(s) - _get_time(s)
            if dur > 0:
                shot_durations.append(dur)

        # Scene cuts that START inside this range (not just overlap)
        scene_cut_count = sum(1 for s in self.scenes if start < _get_time(s) < end)

        # OCR change: count consecutive keyframes with different display_text
        sorted_text_frames = sorted(text_frames, key=lambda k: k.get("timestamp", 0))
        ocr_change_count = 0
        for i in range(1, len(sorted_text_frames)):
            prev_text = sorted_text_frames[i-1].get("display_text", "")
            curr_text = sorted_text_frames[i].get("display_text", "")
            if prev_text != curr_text:
                ocr_change_count += 1

        return {
            "time_range": [round(start, 3), round(end, 3)],
            "duration": round(span, 3),
            "shot_count": len(scenes),
            "scene_cut_count": scene_cut_count,
            "avg_shot_duration": round(sum(shot_durations) / len(shot_durations), 3) if shot_durations else None,
            "shot_density": round(len(scenes) / span, 4),
            "keyframe_count": len(keyframes),
            "keyframes_per_second": round(len(keyframes) / span, 4),
            "beat_count": len(beats),
            "beats_per_second": round(len(beats) / span, 4),
            "text_frame_count": len(text_frames),
            "unique_text_count": len({k.get("display_text") for k in text_frames if k.get("display_text")}),
            "ocr_change_count": ocr_change_count,
            "transcript_count": len([t for t in self.transcript if _in_range(t, start, end)]),
            "short_segment_warning": span < 1.5 and len(scenes) > 0,
        }

    def search_text(self, keyword: str) -> list[dict[str, Any]]:
        kw = _normalize_text(keyword).lower()
        if not kw:
            return []
        results = []
        for kf in self.keyframes:
            item = self._enrich_keyframe(kf)
            text = _normalize_text(item.get("display_text"))
            if kw in text.lower():
                results.append(item)
        return results

    def get_all_display_texts(self) -> list[dict[str, Any]]:
        items = []
        for kf in self.keyframes:
            item = self._enrich_keyframe(kf)
            if item.get("display_text"):
                items.append({
                    "frame_id": item["frame_id"],
                    "timestamp": item["timestamp"],
                    "scene_id": item.get("scene_id"),
                    "display_text": item["display_text"],
                })
        return items

    def get_segment_evidence(self, segment_id: str) -> dict[str, Any]:
        seg = next((s for s in self.segments if s.get("segment_id") == segment_id), None)
        if not seg:
            return {"error": f"segment not found: {segment_id}", "segment_id": segment_id}
        data = self.query_timeline(seg["start_time"], seg["end_time"])
        data["segment"] = seg
        return data

    def get_cut_beat_alignment(self, start_time: Number, end_time: Number, tolerance: float = 0.12) -> dict[str, Any]:
        """Estimate how often scene cuts are close to beat timestamps.

        cut times are approximated by scene start times, excluding the first scene
        if it begins exactly at the query start.
        """
        start = max(0.0, _as_float(start_time))
        end = max(start, _as_float(end_time, self.duration))
        cut_times = [
            _get_time(s)
            for s in self.scenes
            if start < _get_time(s) < end
        ]
        beat_times = sorted(self._beat_time(b) for b in self.beats if start <= self._beat_time(b) < end)

        aligned: list[float] = []
        for cut in cut_times:
            i = bisect.bisect_left(beat_times, cut)
            candidates = []
            if i < len(beat_times):
                candidates.append(abs(beat_times[i] - cut))
            if i > 0:
                candidates.append(abs(beat_times[i - 1] - cut))
            if candidates and min(candidates) <= tolerance:
                aligned.append(round(cut, 3))

        cut_count = len(cut_times)
        aligned_count = len(aligned)
        score = aligned_count / cut_count if cut_count else 0.0
        return {
            "time_range": [round(start, 3), round(end, 3)],
            "cut_count": cut_count,
            "beat_count": len(beat_times),
            "aligned_cut_count": aligned_count,
            "alignment_score": round(score, 4),
            "strong_alignment_times": aligned[:30],
            "tolerance_seconds": tolerance,
        }


def build_timeline_index(evidence_package: dict[str, Any]) -> TimelineIndex:
    return TimelineIndex(evidence_package)


def build_timeline_index_from_file(path: str) -> TimelineIndex:
    return TimelineIndex.from_file(path)

def get_all_segment_metrics(self) -> list[dict[str, Any]]:
    """一次性返回所有segment的metrics，避免逐段调用。"""
    if not self.segments:
        return []
    return [
        {
            "segment_id": seg.get("segment_id"),
            **self.compute_metrics(seg["start_time"], seg["end_time"])
        }
        for seg in self.segments
    ]