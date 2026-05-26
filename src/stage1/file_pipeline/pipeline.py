"""File Pipeline 端到端编排"""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import time
import traceback

from src.stage1.file_pipeline import input as file_input
from src.stage1.file_pipeline import assembler
from src.stage1.file_pipeline.processors import (
    asr,
    audio,
    basic_analysis,
    beat,
    keyframe,
    metadata,
    ocr,
    scene_detect,
)
from src.stage1.types.evidence import EvidencePackage, ProcessorStatus
from src.stage1.utils.logger import get_logger


logger = get_logger(__name__)


def run(file_path: str) -> EvidencePackage:
    """
    MVP 阶段串行执行所有 processor。
    metadata 失败则终止；其他 processor 失败则记录错误并继续。
    """
    started = _now_iso()
    start_perf = time.perf_counter()

    prepared = file_input.validate_and_prepare(file_path)
    video_id = prepared["video_id"]
    source = prepared["source"]
    output_dir = prepared["output_dir"]

    context: dict = {
        "_output_dir": output_dir,
        "_evidence_path": f"{output_dir}/evidence_package.json",
    }
    processor_logs: list[dict] = []

    # metadata 是强依赖，失败直接抛出
    result, log = _run_processor("metadata", metadata.run, file_path, output_dir, context)
    processor_logs.append(log)
    if log["status"] != ProcessorStatus.SUCCESS.value:
        raise RuntimeError(f"metadata processor failed: {log.get('error')}")
    context["metadata"] = result

    # scene_detect
    result, log = _run_processor("scene_detect", scene_detect.run, file_path, output_dir, context)
    processor_logs.append(log)
    context["scenes"] = result.get("scenes", []) if log["status"] == "success" else []

    # audio
    result, log = _run_processor("audio", audio.run, file_path, output_dir, context)
    processor_logs.append(log)
    context["audio"] = result if log["status"] == "success" else {"audio_path": None, "has_audio": False}

    # keyframe
    result, log = _run_processor("keyframe", keyframe.run, file_path, output_dir, context)
    processor_logs.append(log)
    if log["status"] == "success":
        context["keyframes"] = result.get("keyframes", [])
        context["scenes"] = result.get("scenes", context.get("scenes", []))
    else:
        context["keyframes"] = []

    # asr
    result, log = _run_processor("asr", asr.run, file_path, output_dir, context)
    processor_logs.append(log)
    context["transcript"] = result.get("transcript", []) if log["status"] == "success" else []

    # beat
    result, log = _run_processor("beat", beat.run, file_path, output_dir, context)
    processor_logs.append(log)
    context["beats"] = result.get("beats") if log["status"] == "success" else None

    # ocr
    result, log = _run_processor("ocr", ocr.run, file_path, output_dir, context)
    processor_logs.append(log)
    context["ocr_results"] = result.get("ocr_results", []) if log["status"] == "success" else []

    # basic_analysis 应尽量成功；如果失败，用兜底空值
    result, log = _run_processor("basic_analysis", basic_analysis.run, file_path, output_dir, context)
    processor_logs.append(log)
    if log["status"] == "success":
        context["basic_analysis"] = result
    else:
        context["basic_analysis"] = {
            "shot_count": len(context.get("scenes", [])),
            "avg_shot_duration": 0.0,
            "shot_density": 0.0,
            "transcript_segment_count": len(context.get("transcript", [])),
            "transcript_char_count": 0,
            "ocr_text_count": 0,
            "ocr_text_per_second": 0.0,
            "subtitle_density": "none",
            "estimated_pace": "unknown",
        }

    completed = _now_iso()
    total_ms = int((time.perf_counter() - start_perf) * 1000)

    processing_info = {
        "started_at": started,
        "completed_at": completed,
        "total_duration_ms": total_ms,
        "processors": processor_logs,
    }

    package = assembler.assemble(
        video_id=video_id,
        source=source,
        context=context,
        processing_info=processing_info,
    )

    logger.info("Evidence package generated: %s/evidence_package.json", output_dir)
    return package


def _run_processor(name: str, fn, input_path: str, output_dir: str, context: dict) -> tuple[dict, dict]:
    logger.info("Running processor: %s", name)
    start = time.perf_counter()
    try:
        result = fn(input_path, output_dir, context)
        duration_ms = int((time.perf_counter() - start) * 1000)
        return result or {}, {
            "name": name,
            "status": ProcessorStatus.SUCCESS.value,
            "duration_ms": duration_ms,
            "error": None,
        }
    except Exception as exc:
        duration_ms = int((time.perf_counter() - start) * 1000)
        error = f"{type(exc).__name__}: {exc}"
        logger.warning("Processor %s failed: %s", name, error)
        logger.debug(traceback.format_exc())
        return {}, {
            "name": name,
            "status": ProcessorStatus.FAILED.value,
            "duration_ms": duration_ms,
            "error": error,
        }


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()