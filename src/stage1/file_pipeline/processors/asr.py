"""Processor: ASR 语音转文字（使用 FasterWhisper）"""

from __future__ import annotations

import os

from src.stage1.utils.file_utils import write_json
from src.stage1.utils.logger import get_logger

logger = get_logger(__name__)


def run(input_path: str, output_dir: str, context: dict) -> dict:
    audio = context.get("audio") or {}
    if not audio.get("has_audio") or not audio.get("audio_path"):
        transcript = []
        write_json(os.path.join(output_dir, "transcript.json"), transcript)
        return {"transcript": transcript, "skipped": True, "reason": "no_audio"}

    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise RuntimeError(
            "faster-whisper is not installed. Run: pip install faster-whisper"
        ) from exc

    model_name = os.getenv("WHISPER_MODEL", "small")
    audio_file = audio.get("audio_path")

    logger.info("加载 FasterWhisper 模型: %s", model_name)
    model = WhisperModel(model_name, compute_type="int8")

    logger.info("开始语音识别...")
    segments, info = model.transcribe(
        audio_file,
        vad_filter=True,          # 自动跳过纯BGM段落
        vad_parameters=dict(
            min_silence_duration_ms=500,
        ),
    )

    logger.info("检测语言: %s (%.2f)", info.language, info.language_probability)

    transcript = []
    for seg in segments:
        text = seg.text.strip()
        if not text:
            continue
        transcript.append({
            "start": round(seg.start, 3),
            "end": round(seg.end, 3),
            "text": text,
            "confidence": round(seg.avg_logprob, 4) if seg.avg_logprob else None,
        })

    write_json(os.path.join(output_dir, "transcript.json"), transcript)
    logger.info("ASR 完成: %d 段", len(transcript))
    return {"transcript": transcript}