"""证据包组装器"""

from __future__ import annotations

import os
from dataclasses import asdict
from typing import Any

from src.stage1.types.evidence import (
    BasicAnalysis,
    BeatInfo,
    EvidencePackage,
    Keyframe,
    OcrResult,
    OcrTextBox,
    ProcessingInfo,
    ProcessorResult,
    ProcessorStatus,
    Scene,
    TranscriptSegment,
    VideoMetadata,
    VideoSource,
)
from src.stage1.utils.file_utils import write_json


def assemble(video_id: str, source: VideoSource | dict, context: dict, processing_info: dict) -> EvidencePackage:
    """
    汇总所有 processor 的结果，组装成最终 EvidencePackage。
    """
    if isinstance(source, dict):
        source_obj = VideoSource(**source)
    else:
        source_obj = source

    metadata = VideoMetadata(**context["metadata"])
    scenes = [_to_scene(item) for item in context.get("scenes", [])]
    keyframes = [_to_keyframe(item) for item in context.get("keyframes", [])]
    transcript = [_to_transcript(item) for item in context.get("transcript", [])]
    ocr_results = [_to_ocr_result(item) for item in context.get("ocr_results", [])]

    beats_raw = context.get("beats")
    beats = BeatInfo(**beats_raw) if isinstance(beats_raw, dict) else None

    basic_analysis = BasicAnalysis(**_filter_basic_analysis(context["basic_analysis"]))

    pinfo = ProcessingInfo(
        started_at=processing_info["started_at"],
        completed_at=processing_info["completed_at"],
        total_duration_ms=int(processing_info["total_duration_ms"]),
        processors=[
            ProcessorResult(
                name=p["name"],
                status=ProcessorStatus(p["status"]),
                duration_ms=int(p["duration_ms"]),
                error=p.get("error"),
            )
            for p in processing_info.get("processors", [])
        ],
    )

    package = EvidencePackage(
        video_id=video_id,
        source=source_obj,
        metadata=metadata,
        scenes=scenes,
        keyframes=keyframes,
        transcript=transcript,
        ocr_results=ocr_results,
        beats=beats,
        basic_analysis=basic_analysis,
        processing_info=pinfo,
    )

    output_dir = os.path.dirname(context.get("_evidence_path", "")) or context.get("_output_dir", "output")
    write_json(os.path.join(output_dir, "evidence_package.json"), asdict(package))
    return package


def _to_scene(data: dict) -> Scene:
    return Scene(**data)


def _to_keyframe(data: dict) -> Keyframe:
    return Keyframe(**data)


def _to_transcript(data: dict) -> TranscriptSegment:
    return TranscriptSegment(**data)


def _to_ocr_result(data: dict) -> OcrResult:
    texts = [OcrTextBox(**box) for box in data.get("texts", [])]
    return OcrResult(
        frame_id=data["frame_id"],
        timestamp=data["timestamp"],
        texts=texts,
        ocr_source_frame_id=data.get("ocr_source_frame_id"),
        ocr_reused=data.get("ocr_reused", False),
        display_text=data.get("display_text"),
    )

def _filter_basic_analysis(data: dict[str, Any]) -> dict[str, Any]:
    allowed = {
        "shot_count",
        "avg_shot_duration",
        "shot_density",
        "transcript_segment_count",
        "transcript_char_count",
        "ocr_text_count",
        "ocr_text_per_second",
        "subtitle_density",
        "estimated_pace",
        "beat_sync_score",
    }
    return {k: v for k, v in data.items() if k in allowed}