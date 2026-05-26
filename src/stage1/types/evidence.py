"""
证据包类型定义（Stage 1 输出 / Stage 2 输入）
两条链路共用(你可以先review一遍)
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional, Any
from enum import Enum
import json


class SourceType(str, Enum):
    FILE = "file"
    LINK = "link"


class ProcessorStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class VideoSource:
    type: SourceType
    local_path: str
    original_filename: Optional[str] = None
    url: Optional[str] = None
    platform: Optional[str] = None


@dataclass
class VideoMetadata:
    duration: float
    width: int
    height: int
    fps: float
    codec: str
    file_size: int
    has_audio: bool
    has_subtitle_track: bool
    bitrate: int
    aspect_ratio: str


@dataclass
class Scene:
    scene_id: str
    index: int
    start_time: float
    end_time: float
    duration: float
    keyframe_ids: list[str] = field(default_factory=list)


@dataclass
class Keyframe:
    frame_id: str
    scene_id: str
    timestamp: float
    path: str


@dataclass
class TranscriptSegment:
    start: float
    end: float
    text: str
    confidence: Optional[float] = None


@dataclass
class OcrTextBox:
    content: str
    bbox: list[int]
    normalized_bbox: list[float]
    confidence: float
    text_type: str = "other"

@dataclass
class OcrResult:
    frame_id: str
    timestamp: float
    texts: list[OcrTextBox] = field(default_factory=list)
    ocr_source_frame_id: Optional[str] = None
    ocr_reused: bool = False

@dataclass
class BeatInfo:
    bpm: float
    beat_timestamps: list[float] = field(default_factory=list)
    has_vocal: bool = False
    beat_sync_score: Optional[float] = None


@dataclass
class BasicAnalysis:
    shot_count: int
    avg_shot_duration: float
    shot_density: float
    transcript_segment_count: int
    transcript_char_count: int
    ocr_text_count: int
    ocr_text_per_second: float
    subtitle_density: str
    estimated_pace: str


@dataclass
class ProcessorResult:
    name: str
    status: ProcessorStatus
    duration_ms: int
    error: Optional[str] = None


@dataclass
class ProcessingInfo:
    started_at: str
    completed_at: str
    total_duration_ms: int
    processors: list[ProcessorResult] = field(default_factory=list)


@dataclass
class EvidencePackage:
    video_id: str
    source: VideoSource
    metadata: VideoMetadata
    scenes: list[Scene]
    keyframes: list[Keyframe]
    transcript: list[TranscriptSegment]
    ocr_results: list[OcrResult]
    beats: Optional[BeatInfo]
    basic_analysis: BasicAnalysis
    processing_info: ProcessingInfo

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self, *, ensure_ascii: bool = False, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=ensure_ascii, indent=indent)