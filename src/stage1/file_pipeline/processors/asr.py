"""Processor: ASR 语音转文字（使用 FasterWhisper）"""

from __future__ import annotations

import os
import re

from src.stage1.utils.file_utils import write_json
from src.stage1.utils.logger import get_logger

logger = get_logger(__name__)


def run(input_path: str, output_dir: str, context: dict) -> dict:
    audio = context.get("audio") or {}
    if not audio.get("has_audio") or not audio.get("audio_path"):
        transcript = []
        write_json(os.path.join(output_dir, "transcript.json"), transcript)
        write_json(os.path.join(output_dir, "asr_info.json"), {"skipped": True, "reason": "no_audio"})
        return {"transcript": transcript, "skipped": True, "reason": "no_audio"}

    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise RuntimeError("faster-whisper is not installed. Run: pip install faster-whisper") from exc

    model_name = os.getenv("WHISPER_MODEL", "small")
    audio_file = audio.get("audio_path")

    logger.info("加载 FasterWhisper 模型: %s", model_name)
    model = WhisperModel(model_name, compute_type=os.getenv("WHISPER_COMPUTE_TYPE", "int8"))

    logger.info("开始语音识别...")
    segments, info = model.transcribe(
        audio_file,
        language=_get_language_option(),
        vad_filter=True,
        vad_parameters=dict(
            min_silence_duration_ms=int(os.getenv("ASR_VAD_MIN_SILENCE_MS", "500")),
            speech_pad_ms=int(os.getenv("ASR_VAD_SPEECH_PAD_MS", "250")),
        ),
        beam_size=int(os.getenv("ASR_BEAM_SIZE", "5")),
        best_of=int(os.getenv("ASR_BEST_OF", "5")),
        temperature=0,
        condition_on_previous_text=False,
        compression_ratio_threshold=float(os.getenv("ASR_COMPRESSION_RATIO_THRESHOLD", "2.4")),
        log_prob_threshold=float(os.getenv("ASR_LOG_PROB_THRESHOLD", "-1.0")),
        no_speech_threshold=float(os.getenv("ASR_NO_SPEECH_THRESHOLD", "0.65")),
        word_timestamps=False,
    )

    logger.info("检测语言: %s (%.2f)", info.language, info.language_probability)

    raw_segments = list(segments)
    transcript = _filter_segments(raw_segments)
    transcript = _global_quality_guard(transcript, info)

    asr_info = {
        "language": getattr(info, "language", None),
        "language_probability": round(float(getattr(info, "language_probability", 0.0)), 4),
        "raw_segment_count": len(raw_segments),
        "final_segment_count": len(transcript),
        "mode": os.getenv("ASR_MODE", "safe"),
        "model": model_name,
    }

    write_json(os.path.join(output_dir, "transcript.json"), transcript)
    write_json(os.path.join(output_dir, "asr_info.json"), asr_info)

    logger.info("ASR 完成: %d/%d 段保留", len(transcript), len(raw_segments))
    return {"transcript": transcript, "asr_info": asr_info}


def _get_language_option():
    lang = os.getenv("ASR_LANGUAGE", "auto").lower().strip()
    if lang in ("auto", "none", ""):
        return None
    return lang


def _filter_segments(segments):
    min_avg_logprob = float(os.getenv("ASR_MIN_AVG_LOGPROB", "-1.0"))
    max_no_speech_prob = float(os.getenv("ASR_MAX_NO_SPEECH_PROB", "0.65"))
    min_duration = float(os.getenv("ASR_MIN_SEGMENT_DURATION", "0.35"))
    max_duration = float(os.getenv("ASR_MAX_SEGMENT_DURATION", "15"))

    transcript = []
    for seg in segments:
        text = seg.text.strip()
        if not text:
            continue

        duration = seg.end - seg.start
        if duration < min_duration:
            continue
        # if duration > max_duration and len(text) < 8:
        #     continue
        if duration > max_duration:
            continue

        avg_logprob = getattr(seg, "avg_logprob", None)
        no_speech_prob = getattr(seg, "no_speech_prob", None)

        if avg_logprob is not None and avg_logprob < min_avg_logprob:
            continue
        if no_speech_prob is not None and no_speech_prob > max_no_speech_prob:
            continue
        if _is_probable_hallucination(text):
            continue

        transcript.append({
            "start": round(float(seg.start), 3),
            "end": round(float(seg.end), 3),
            "text": text,
            "confidence": round(float(avg_logprob), 4) if avg_logprob is not None else None,
        })

    return transcript


def _global_quality_guard(transcript, info):
    if not transcript:
        return []

    language_probability = getattr(info, "language_probability", None)
    min_language_probability = float(os.getenv("ASR_MIN_LANGUAGE_PROBABILITY", "0.45"))

    total_text = "".join(item["text"] for item in transcript)

    if language_probability is not None:
        if language_probability < min_language_probability and len(total_text) < 20:
            logger.info("ASR 质量保护：语言置信度低且内容少，清空 transcript")
            return []

    # if len(transcript) == 1 and len(total_text) < 5:
    if len(transcript) == 1 and len(total_text) < 3:
        logger.info("ASR 质量保护：仅一段且内容极短，清空 transcript")
        return []

    return transcript


def _is_probable_hallucination(text: str) -> bool:
    if not text:
        return True

    cleaned = text.strip()
    lower = cleaned.lower()

    hallucination_phrases = [
        "thank you for watching",
        "thanks for watching",
        "like and subscribe",
        "subscribe",
        "music",
        "applause",
        "♪", "♫",
        "字幕", "字幕组",
    ]

    for phrase in hallucination_phrases:
        if phrase in lower:
            return True

    if re.search(r"(.)\1{5,}", cleaned):
        return True

    letters = re.findall(r"[A-Za-z]", cleaned)
    if len(letters) >= 12:
        words = re.findall(r"[A-Za-z]+", cleaned)
        if words:
            avg_word_len = sum(len(w) for w in words) / len(words)
            vowels = sum(1 for ch in letters if ch.lower() in "aeiou")
            vowel_ratio = vowels / len(letters)
            if avg_word_len > 12 or vowel_ratio < 0.15:
                return True

    return False