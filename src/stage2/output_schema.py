"""轻量级的 Stage 2 输出 schema。

使用 dataclass 以便开发者理解，但以 JSON 作为数据交换格式。
智能体可以返回普通 dict；Summary/Evaluator 可据此 schema 进行校验。
"""

from __future__ import annotations

from dataclasses import dataclass, asdict, field
from typing import Any, Literal


SegmentFunction = Literal[
    "hook",
    "introduction",
    "instruction",
    "demonstration",
    "comparison",
    "transition",
    "climax",
    "resolution",
    "cta",
]


@dataclass
class EvidenceRef:
    type: str
    ref: str
    text: str | None = None
    desc: str | None = None


@dataclass
class ScriptSegment:
    segment_id: str
    function: str
    start_time: float
    end_time: float
    evidence: list[dict[str, Any]] = field(default_factory=list)
    reason: str = ""
    confidence: float | None = None
    core_text: str | None = None


@dataclass
class VideoStructure:
    video_id: str | None
    video_type: str
    duration: float
    script_structure: dict[str, Any]
    rhythm_structure: dict[str, Any]
    packaging_structure: dict[str, Any]
    value_strategy: dict[str, Any]
    energy_curve: dict[str, Any]
    transfer_blueprint: dict[str, Any]
    analysis_metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def basic_video_structure(video_id: str | None, duration: float) -> dict[str, Any]:
    return {
        "video_id": video_id,
        "video_type": "unknown",
        "duration": duration,
        "script_structure": {},
        "rhythm_structure": {},
        "packaging_structure": {},
        "value_strategy": {},
        "energy_curve": {},
        "transfer_blueprint": {},
        "analysis_metadata": {},
    }


def validate_video_structure_minimal(data: dict[str, Any]) -> list[str]:
    """返回错误列表。空列表表示通过最小 schema 校验。"""
    errors: list[str] = []
    required = [
        "video_id",
        "video_type",
        "duration",
        "script_structure",
        "rhythm_structure",
        "packaging_structure",
        "value_strategy",
        "energy_curve",
        "transfer_blueprint",
        "analysis_metadata",
    ]
    for key in required:
        if key not in data:
            errors.append(f"missing required key: {key}")
    if data.get("duration") is not None:
        try:
            if float(data.get("duration")) <= 0:
                errors.append("duration must be positive")
        except Exception:
            errors.append("duration must be numeric")
    return errors
