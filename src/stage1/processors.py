"""
processors.py — Steps 2–3: shot detection, keyframe extraction, ASR, OCR, audio analysis.

All heavy analysis runs here. Each sub-step is wrapped in its own try/except so a
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
        return [
            {
                "shot_id": 0,
                "start_time": 0.0,
                "end_time": duration,
                "duration": duration,
            }
        ]

    shots = []
    for i, (start_tc, end_tc) in enumerate(scene_list):
        start = start_tc.get_seconds()
        end = end_tc.get_seconds()
        shots.append(
            {
                "shot_id": i,
                "start_time": start,
                "end_time": end,
                "duration": end - start,
            }
        )
    return shots


def _extract_keyframes(
    video_path: str,
    shots: list[dict],
    keyframes_dir: str,
) -> list[Optional[str]]:
    """Extract one frame per shot at the temporal midpoint using FFmpeg."""
    os.makedirs(keyframes_dir, exist_ok=True)
    paths: list[Optional[str]] = []

    for shot in shots:
        shot_id = shot["shot_id"]
        # Sample the midpoint of each shot
        mid_time = shot["start_time"] + shot["duration"] / 2.0
        out_path = os.path.join(keyframes_dir, f"shot_{shot_id}.jpg")

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
            paths.append(os.path.abspath(out_path))
        else:
            logger.warning(
                "Keyframe extraction failed for shot %d: %s",
                shot_id,
                result.stderr[-200:],
            )
            paths.append(None)

    return paths


def _run_asr(video_path: str, whisper_model: str) -> list[dict]:
    """Transcribe audio with OpenAI Whisper. Returns timestamped segments."""
    import whisper  # type: ignore[import]

    logger.info("Loading Whisper model '%s' …", whisper_model)
    model = whisper.load_model(whisper_model)
    result = model.transcribe(video_path, verbose=False)
    segments = []
    for seg in result.get("segments", []):
        segments.append(
            {
                "start": float(seg["start"]),
                "end": float(seg["end"]),
                "text": seg["text"].strip(),
            }
        )
    return segments


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


def _run_audio_analysis(video_path: str, output_dir: str) -> dict:
    """
    Extract BPM, beat timestamps, and RMS energy envelope via librosa.
    Audio is first stripped to a temporary WAV file with FFmpeg.
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
    # librosa 0.10+ returns a 1-element array; earlier versions return a scalar
    bpm = float(np.atleast_1d(tempo_raw)[0])
    beat_times: list[float] = librosa.frames_to_time(beats, sr=sr).tolist()

    hop_length = 512
    rms = librosa.feature.rms(y=y, hop_length=hop_length)[0]
    rms_times: list[float] = librosa.frames_to_time(
        range(len(rms)), sr=sr, hop_length=hop_length
    ).tolist()

    return {
        "bpm": bpm,
        "beat_timestamps": beat_times,
        "rms_energy": rms.tolist(),
        "rms_timestamps": rms_times,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def analyze_video(
    video_path: str,
    output_dir: str,
    whisper_model: str = "base",
) -> dict:
    """
    Runs full structural analysis on a local mp4 file.

    Args:
        video_path:    Absolute path to the mp4 file.
        output_dir:    Directory where keyframes and audio.wav are saved.
        whisper_model: Whisper model size (tiny/base/small/medium/large).

    Returns:
        {
          "shots": [{"shot_id", "start_time", "end_time", "duration",
                     "keyframe_path", "ocr_text"}, ...],
          "transcript": [{"start", "end", "text"}, ...] | None,
          "audio": {"bpm", "beat_timestamps", "rms_energy", "rms_timestamps"} | None,
        }
    """
    os.makedirs(output_dir, exist_ok=True)

    # --- Sequential: shot detection then keyframe extraction ----------------
    shots: list[dict] = []
    try:
        shots = _detect_shots(video_path)
        logger.info("Detected %d shot(s).", len(shots))
    except Exception as exc:
        logger.error("Shot detection failed: %s", exc)

    keyframe_paths: list[Optional[str]] = [None] * len(shots)
    if shots:
        try:
            keyframe_paths = _extract_keyframes(video_path, shots, output_dir)
            logger.info("Extracted %d keyframe(s).", sum(1 for p in keyframe_paths if p))
        except Exception as exc:
            logger.error("Keyframe extraction failed: %s", exc)

    # --- Parallel: ASR | OCR | audio analysis --------------------------------
    transcript: Optional[list[dict]] = None
    ocr_texts: Optional[list[str]] = None
    audio_result: Optional[dict] = None

    futures_map: dict = {}
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures_map[executor.submit(_run_asr, video_path, whisper_model)] = "asr"
        futures_map[executor.submit(_run_ocr, keyframe_paths)] = "ocr"
        futures_map[executor.submit(_run_audio_analysis, video_path, output_dir)] = "audio"

        for future in as_completed(futures_map):
            task = futures_map[future]
            try:
                value = future.result()
                if task == "asr":
                    transcript = value
                    logger.info("ASR complete: %d segment(s).", len(value))
                elif task == "ocr":
                    ocr_texts = value
                    logger.info("OCR complete.")
                elif task == "audio":
                    audio_result = value
                    logger.info("Audio analysis complete: %.1f BPM.", value["bpm"])
            except Exception as exc:
                logger.error("%s analysis failed: %s", task.upper(), exc)

    # --- Merge keyframe paths + OCR text into shot records -------------------
    enriched_shots: list[dict] = []
    for i, shot in enumerate(shots):
        enriched_shots.append(
            {
                "shot_id": shot["shot_id"],
                "start_time": shot["start_time"],
                "end_time": shot["end_time"],
                "duration": shot["duration"],
                "keyframe_path": keyframe_paths[i] if i < len(keyframe_paths) else None,
                "ocr_text": ocr_texts[i] if ocr_texts and i < len(ocr_texts) else "",
            }
        )

    return {
        "shots": enriched_shots,
        "transcript": transcript,
        "audio": audio_result,
    }
