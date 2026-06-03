"""
processors.py — Steps 2–3: shot detection, keyframe extraction, ASR, OCR, audio analysis.

All heavy analysis runs here. Each sub-step is wrapped in try/except so a
single failure fills that field with None rather than crashing the whole pipeline.
"""
import json
import logging
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_duration(video_path: str) -> float:
    """Return video duration in seconds via ffprobe."""
    result = subprocess.run(
        [
            "ffprobe", "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            video_path,
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        data = json.loads(result.stdout)
        return float(data.get("format", {}).get("duration", 0))
    return 0.0


def _detect_shots(video_path: str) -> list[dict]:
    """
    Use PySceneDetect ContentDetector to find shot boundaries.
    Falls back to a single shot covering the full video when no cuts are found.
    """
    from scenedetect import detect, ContentDetector  # type: ignore[import]

    scene_list = detect(video_path, ContentDetector())

    if not scene_list:
        duration = _get_duration(video_path)
        return [{"shot_id": 0, "start_time": 0.0, "end_time": duration, "duration": duration}]

    shots = []
    for i, (start_tc, end_tc) in enumerate(scene_list):
        start = start_tc.get_seconds()
        end = end_tc.get_seconds()
        shots.append({"shot_id": i, "start_time": start, "end_time": end, "duration": end - start})
    return shots


def _extract_keyframes(video_path: str, shots: list[dict], frames_dir: str) -> list[dict]:
    """
    Extract one frame per shot at the temporal midpoint using FFmpeg.
    Writes frame_{i:03d}.jpg to frames_dir.
    Returns list of {"path": str|None, "timestamp": float}.
    """
    os.makedirs(frames_dir, exist_ok=True)
    frames: list[dict] = []

    for shot in shots:
        shot_id = shot["shot_id"]
        mid_time = shot["start_time"] + shot["duration"] / 2.0
        out_path = os.path.join(frames_dir, f"frame_{shot_id:03d}.jpg")

        cmd = [
            "ffmpeg", "-y",
            "-ss", f"{mid_time:.3f}",
            "-i", video_path,
            "-frames:v", "1",
            "-q:v", "2",
            out_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0 and os.path.exists(out_path):
            frames.append({"path": os.path.abspath(out_path), "timestamp": mid_time})
        else:
            logger.warning(
                "Keyframe extraction failed for shot %d: %s",
                shot_id,
                result.stderr[-200:],
            )
            frames.append({"path": None, "timestamp": mid_time})

    return frames


def _run_asr(video_path: str, whisper_model: str) -> dict:
    """
    Transcribe audio with OpenAI Whisper.
    Returns {"transcript": [...], "asr_info": {...}}.
    Each segment includes confidence (avg_logprob from Whisper).
    """
    import whisper  # type: ignore[import]

    logger.info("Loading Whisper model '%s' …", whisper_model)
    model = whisper.load_model(whisper_model)
    result = model.transcribe(video_path, verbose=False)

    raw_segments = result.get("segments", [])
    segments = []
    for seg in raw_segments:
        segments.append({
            "start": float(seg["start"]),
            "end": float(seg["end"]),
            "text": seg["text"].strip(),
            "confidence": float(seg["avg_logprob"]) if seg.get("avg_logprob") is not None else None,
        })

    asr_info = {
        "language": result.get("language"),
        "language_probability": result.get("language_probability"),
        "raw_segment_count": len(raw_segments),
        "final_segment_count": len(segments),
        "mode": "normal",
        "model": whisper_model,
    }
    return {"transcript": segments, "asr_info": asr_info}


def _run_ocr(keyframe_paths: list[Optional[str]]) -> list[str]:
    """
    Run EasyOCR (Chinese simplified + English) on each keyframe.
    Uses PyTorch GPU if available, falls back to CPU automatically.
    Returns one concatenated string per frame; empty string on failure.
    """
    import easyocr  # type: ignore[import]
    import torch  # type: ignore[import]

    gpu = torch.cuda.is_available()
    logger.info("Initialising EasyOCR (gpu=%s) …", gpu)
    reader = easyocr.Reader(["ch_sim", "en"], gpu=gpu, verbose=False)
    texts: list[str] = []

    for path in keyframe_paths:
        if not path or not os.path.exists(path):
            texts.append("")
            continue
        try:
            results: list[str] = reader.readtext(path, detail=0)
            texts.append(" ".join(r.strip() for r in results if r.strip()))
        except Exception as exc:
            logger.warning("OCR failed for %s: %s", path, exc)
            texts.append("")

    return texts


def _run_audio_analysis(
    video_path: str, output_dir: str, shot_boundaries: list[float]
) -> dict:
    """
    Extract BPM, beat timestamps, and RMS energy via librosa.
    Writes audio.wav to output_dir.
    beat_sync_score: fraction of beats within 100ms of a shot boundary.
    """
    import librosa  # type: ignore[import]
    import numpy as np  # type: ignore[import]

    audio_path = os.path.join(output_dir, "audio.wav")
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-vn",
        "-acodec", "pcm_s16le",
        "-ar", "22050",
        "-ac", "1",
        audio_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg audio extraction failed: {result.stderr[-300:]}")

    logger.info("Loading audio with librosa …")
    y, sr = librosa.load(audio_path, sr=None)

    tempo_raw, beats = librosa.beat.beat_track(y=y, sr=sr)
    bpm = float(np.atleast_1d(tempo_raw)[0])
    beat_times: list[float] = librosa.frames_to_time(beats, sr=sr).tolist()

    hop_length = 512
    rms = librosa.feature.rms(y=y, hop_length=hop_length)[0]
    rms_times: list[float] = librosa.frames_to_time(
        range(len(rms)), sr=sr, hop_length=hop_length
    ).tolist()

    # Fraction of beats that land within 100ms of a shot boundary
    threshold = 0.1
    if beat_times and shot_boundaries:
        hits = sum(1 for b in beat_times if any(abs(b - s) <= threshold for s in shot_boundaries))
        beat_sync_score = round(hits / len(beat_times), 4)
    else:
        beat_sync_score = 0.0

    return {
        "bpm": bpm,
        "beat_timestamps": beat_times,
        "has_vocal": None,
        "beat_sync_score": beat_sync_score,
        "rms_energy": rms.tolist(),
        "rms_timestamps": rms_times,
    }


def _build_ocr_output(raw_keyframes: list[dict], ocr_texts: list[str]) -> list[dict]:
    """
    Build ocr.json entries from EasyOCR concatenated strings.
    Provides display_text / display_texts for Stage 2 consumption.
    bbox and confidence are omitted (OCR not upgraded to rich format).
    """
    results = []
    for i, (kf, text) in enumerate(zip(raw_keyframes, ocr_texts)):
        frame_id = f"frame_{i:03d}"
        display_texts = [{"content": text}] if text else []
        results.append({
            "frame_id": frame_id,
            "timestamp": kf["timestamp"],
            "display_texts": display_texts,
            "display_text": text,
        })
    return results


def _compute_basic_analysis(
    shots: list[dict],
    transcript: Optional[list[dict]],
    ocr_texts: list[str],
    beats: Optional[dict],
    duration: float,
) -> dict:
    """Derive summary statistics from analysis outputs."""
    shot_count = len(shots)
    avg_shot_duration = (
        sum(s["duration"] for s in shots) / shot_count if shot_count else 0.0
    )
    shot_density = shot_count / duration if duration else 0.0

    transcript_segment_count = len(transcript) if transcript else 0
    transcript_char_count = sum(len(seg["text"]) for seg in (transcript or []))

    # Word count across all OCR strings as proxy for text-block count
    # (simplified metric — no bbox-level granularity without OCR upgrade)
    ocr_text_count = sum(len(t.split()) for t in ocr_texts)
    ocr_text_per_second = ocr_text_count / duration if duration else 0.0

    if ocr_text_per_second > 1.0:
        subtitle_density = "high"
    elif ocr_text_per_second > 0.3:
        subtitle_density = "medium"
    elif ocr_text_per_second > 0.01:
        subtitle_density = "low"
    else:
        subtitle_density = "none"

    if avg_shot_duration < 1.5:
        estimated_pace = "fast"
    elif avg_shot_duration < 3.0:
        estimated_pace = "medium"
    else:
        estimated_pace = "slow"

    beat_sync_score = beats.get("beat_sync_score", 0.0) if beats else 0.0

    return {
        "shot_count": shot_count,
        "avg_shot_duration": round(avg_shot_duration, 3),
        "shot_density": round(shot_density, 4),
        "transcript_segment_count": transcript_segment_count,
        "transcript_char_count": transcript_char_count,
        "ocr_text_count": ocr_text_count,
        "ocr_text_per_second": round(ocr_text_per_second, 4),
        "subtitle_density": subtitle_density,
        "estimated_pace": estimated_pace,
        "beat_sync_score": beat_sync_score,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def analyze_video(video_path: str, output_dir: str, whisper_model: str = "base") -> dict:
    """
    Runs full structural analysis on a local video file.

    Writes to output_dir:
      frames/frame_NNN.jpg  — one keyframe per shot
      audio.wav             — extracted mono audio (22050 Hz)

    Args:
        video_path:    Absolute path to the video file.
        output_dir:    Root output directory for this video (e.g. output/{video_id}/).
        whisper_model: Whisper model size (tiny/base/small/medium/large).

    Returns:
        {
          "scenes":         [{"scene_id", "index", "start_time", "end_time",
                              "duration", "keyframe_ids"}, ...],
          "keyframes":      [{"frame_id", "scene_id", "timestamp", "path"}, ...],
          "ocr_results":    [{"frame_id", "timestamp", "display_texts",
                              "display_text"}, ...],
          "transcript":     [{"start", "end", "text", "confidence"}, ...] | None,
          "asr_info":       {"language", "language_probability", "raw_segment_count",
                             "final_segment_count", "mode", "model"} | None,
          "beats":          {"bpm", "beat_timestamps", "has_vocal", "beat_sync_score",
                             "rms_energy", "rms_timestamps"} | None,
          "basic_analysis": {"shot_count", "avg_shot_duration", "shot_density", ...},
        }
    """
    os.makedirs(output_dir, exist_ok=True)
    frames_dir = os.path.join(output_dir, "frames")

    # --- Sequential: shot detection then keyframe extraction ----------------
    shots: list[dict] = []
    try:
        shots = _detect_shots(video_path)
        logger.info("Detected %d shot(s).", len(shots))
    except Exception as exc:
        logger.error("Shot detection failed: %s", exc)

    raw_keyframes: list[dict] = [{"path": None, "timestamp": 0.0}] * len(shots)
    if shots:
        try:
            raw_keyframes = _extract_keyframes(video_path, shots, frames_dir)
            logger.info(
                "Extracted %d keyframe(s).", sum(1 for kf in raw_keyframes if kf["path"])
            )
        except Exception as exc:
            logger.error("Keyframe extraction failed: %s", exc)

    # --- Parallel: ASR | OCR | audio analysis --------------------------------
    asr_result: Optional[dict] = None
    ocr_texts: Optional[list[str]] = None
    beats_result: Optional[dict] = None

    keyframe_paths = [kf["path"] for kf in raw_keyframes]
    # All shot boundaries (start times + final end) for beat_sync_score
    shot_boundaries: list[float] = [s["start_time"] for s in shots]
    if shots:
        shot_boundaries.append(shots[-1]["end_time"])

    futures_map: dict = {}
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures_map[executor.submit(_run_asr, video_path, whisper_model)] = "asr"
        futures_map[executor.submit(_run_ocr, keyframe_paths)] = "ocr"
        futures_map[executor.submit(
            _run_audio_analysis, video_path, output_dir, shot_boundaries
        )] = "audio"

        for future in as_completed(futures_map):
            task = futures_map[future]
            try:
                value = future.result()
                if task == "asr":
                    asr_result = value
                    logger.info("ASR complete: %d segment(s).", len(value["transcript"]))
                elif task == "ocr":
                    ocr_texts = value
                    logger.info("OCR complete.")
                elif task == "audio":
                    beats_result = value
                    logger.info("Audio analysis complete: %.1f BPM.", value["bpm"])
            except Exception as exc:
                logger.error("%s analysis failed: %s", task.upper(), exc)

    transcript = asr_result["transcript"] if asr_result else None
    asr_info = asr_result["asr_info"] if asr_result else None
    if ocr_texts is None:
        ocr_texts = [""] * len(shots)

    # --- Build scenes and keyframes lists ------------------------------------
    scenes: list[dict] = []
    keyframes: list[dict] = []
    for i, shot in enumerate(shots):
        scene_id = f"scene_{i:03d}"
        frame_id = f"frame_{i:03d}"
        scenes.append({
            "scene_id": scene_id,
            "index": i,
            "start_time": shot["start_time"],
            "end_time": shot["end_time"],
            "duration": shot["duration"],
            "keyframe_ids": [frame_id],
        })
        kf = raw_keyframes[i] if i < len(raw_keyframes) else {"path": None, "timestamp": 0.0}
        keyframes.append({
            "frame_id": frame_id,
            "scene_id": scene_id,
            "timestamp": kf["timestamp"],
            "path": kf["path"],
        })

    ocr_results = _build_ocr_output(raw_keyframes, ocr_texts)

    duration = shots[-1]["end_time"] if shots else 0.0
    basic_analysis = _compute_basic_analysis(shots, transcript, ocr_texts, beats_result, duration)

    return {
        "scenes": scenes,
        "keyframes": keyframes,
        "ocr_results": ocr_results,
        "transcript": transcript,
        "asr_info": asr_info,
        "beats": beats_result,
        "basic_analysis": basic_analysis,
    }
