"""
pipeline_link.py — End-to-end CLI runner for the link-download pipeline.

Usage:
    python pipeline_link.py "https://www.youtube.com/shorts/..."
    python pipeline_link.py --output-dir ./out --whisper-model small "https://..."
    python pipeline_link.py          # prompts for URL interactively

Output structure per video:
    output/{video_id}/
    ├── metadata.json        technical params (ffprobe)
    ├── scenes.json
    ├── keyframes.json
    ├── frames/
    │   └── frame_NNN.jpg
    ├── audio.wav
    ├── audio.json
    ├── transcript.json
    ├── asr_info.json
    ├── ocr.json
    ├── beats.json
    ├── basic_analysis.json
    └── evidence_package.json   ← Stage 2 entry point
"""
import argparse
import json
import logging
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from math import gcd

# Allow running as a script from any working directory
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv  # type: ignore[import]

load_dotenv()

from link_input import download_from_url
from processors import analyze_video
from vlm_enricher import describe_keyframes

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _video_id_from_path(video_path: str) -> str:
    """Extract the yt-dlp video ID embedded in the downloaded filename."""
    return os.path.splitext(os.path.basename(video_path))[0]


def _get_technical_metadata(video_path: str) -> dict:
    """Extract technical video metadata via ffprobe (width, height, fps, codec, etc.)."""
    result = subprocess.run(
        [
            "ffprobe", "-v", "quiet",
            "-print_format", "json",
            "-show_streams", "-show_format",
            video_path,
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        logger.warning("ffprobe technical metadata failed: %s", result.stderr[-200:])
        return {}

    data = json.loads(result.stdout)
    fmt = data.get("format", {})
    streams = data.get("streams", [])

    video_stream = next((s for s in streams if s.get("codec_type") == "video"), {})
    has_audio = any(s.get("codec_type") == "audio" for s in streams)
    has_subtitle = any(s.get("codec_type") == "subtitle" for s in streams)

    width = video_stream.get("width")
    height = video_stream.get("height")
    aspect_ratio = None
    if width and height:
        g = gcd(int(width), int(height))
        aspect_ratio = f"{int(width) // g}:{int(height) // g}"

    fps = None
    raw_fps = video_stream.get("avg_frame_rate") or video_stream.get("r_frame_rate")
    if raw_fps and "/" in raw_fps:
        num, den = raw_fps.split("/")
        if int(den):
            fps = round(int(num) / int(den), 3)

    return {
        "duration": float(fmt.get("duration") or 0),
        "width": width,
        "height": height,
        "fps": fps,
        "codec": video_stream.get("codec_name"),
        "file_size": int(fmt.get("size") or 0),
        "has_audio": has_audio,
        "has_subtitle_track": has_subtitle,
        "bitrate": int(fmt.get("bit_rate") or 0),
        "aspect_ratio": aspect_ratio,
    }


def _write_json(path: str, data) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)


def _print_summary(evidence: dict, evidence_path: str) -> None:
    source = evidence.get("source") or {}
    social = source.get("social_metadata") or {}
    meta = evidence.get("metadata") or {}
    basic = evidence.get("basic_analysis") or {}
    beats = evidence.get("beats") or {}
    transcript = evidence.get("transcript") or []

    print()
    print("=" * 62)
    print("  ViralCut — Analysis Complete")
    print("=" * 62)
    print(f"  Title    : {social.get('title', 'N/A')}")
    print(f"  Platform : {source.get('platform', 'N/A')}")
    print(f"  Duration : {meta.get('duration', 0):.1f} s")
    print(f"  Shots    : {basic.get('shot_count', 0)}")
    print(f"  Pace     : {basic.get('estimated_pace', 'N/A')}")
    print(f"  Segments : {len(transcript)}")
    bpm = beats.get("bpm")
    print(f"  BPM      : {bpm:.1f}" if bpm is not None else "  BPM      : N/A")
    sync = beats.get("beat_sync_score")
    print(f"  Sync     : {sync:.4f}" if sync is not None else "  Sync     : N/A")
    print(f"  Output   : {evidence_path}")
    print("=" * 62)
    print()


# ---------------------------------------------------------------------------
# Core pipeline
# ---------------------------------------------------------------------------

def run_pipeline(
    url: str,
    output_dir: str,
    cookie_file: str | None = None,
    whisper_model: str = "base",
    vlm_model: str | None = None,
    vlm_base_url: str = "https://openrouter.ai/api/v1",
) -> dict:
    """
    Full link → analysis → evidence_package.json pipeline.

    1. Downloads video + social metadata via yt-dlp.
    2. Extracts technical metadata via ffprobe.
    3. Runs structural analysis (processors.analyze_video).
    4. (Optional) Describes each keyframe with a vision LLM (vlm_model).
    5. Writes per-step JSON files + evidence_package.json to output/{video_id}/.

    Returns the complete evidence_package dict.
    """
    logger.info("Pipeline start  url=%s", url)
    started_at = datetime.now(timezone.utc).isoformat()
    t0 = time.time()

    # ------------------------------------------------------------------
    # Step 1: Download
    # ------------------------------------------------------------------
    tmp_dir = os.path.join(output_dir, "temp")
    download_result = download_from_url(url, tmp_dir, cookie_file=cookie_file)
    video_path: str = download_result["video_path"]
    social_metadata: dict = download_result["metadata"]

    video_id = _video_id_from_path(video_path)
    logger.info("video_id=%s  path=%s", video_id, video_path)

    vid_dir = os.path.join(output_dir, video_id)
    os.makedirs(vid_dir, exist_ok=True)

    # ------------------------------------------------------------------
    # Step 2: Technical metadata (ffprobe)
    # ------------------------------------------------------------------
    tech_metadata = _get_technical_metadata(video_path)
    _write_json(os.path.join(vid_dir, "metadata.json"), tech_metadata)

    # ------------------------------------------------------------------
    # Step 3: Analysis — frames/ and audio.wav written inside vid_dir
    # ------------------------------------------------------------------
    analysis = analyze_video(video_path, vid_dir, whisper_model=whisper_model)

    # ------------------------------------------------------------------
    # Step 4: VLM keyframe descriptions (optional — requires API key)
    # ------------------------------------------------------------------
    if vlm_model:
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            logger.warning("VLM enrichment skipped: OPENROUTER_API_KEY not set.")
        else:
            logger.info("Running VLM keyframe descriptions with model=%s …", vlm_model)
            image_paths = [kf["path"] for kf in analysis["keyframes"]]
            vlm_descriptions = describe_keyframes(
                image_paths,
                api_key=api_key,
                model=vlm_model,
                base_url=vlm_base_url,
            )
            for kf, desc in zip(analysis["keyframes"], vlm_descriptions):
                kf["vlm_description"] = desc

    # ------------------------------------------------------------------
    # Step 5: Write per-step JSON files
    # ------------------------------------------------------------------
    audio_wav_path = os.path.join(vid_dir, "audio.wav")
    audio_info = {
        "audio_path": audio_wav_path if os.path.exists(audio_wav_path) else None,
        "has_audio": tech_metadata.get("has_audio", True),
    }

    _write_json(os.path.join(vid_dir, "scenes.json"),         analysis["scenes"])
    _write_json(os.path.join(vid_dir, "keyframes.json"),      analysis["keyframes"])
    _write_json(os.path.join(vid_dir, "transcript.json"),     analysis["transcript"] or [])
    _write_json(os.path.join(vid_dir, "asr_info.json"),       analysis["asr_info"] or {})
    _write_json(os.path.join(vid_dir, "ocr.json"),            analysis["ocr_results"])
    _write_json(os.path.join(vid_dir, "beats.json"),          analysis["beats"] or {})
    _write_json(os.path.join(vid_dir, "basic_analysis.json"), analysis["basic_analysis"])
    _write_json(os.path.join(vid_dir, "audio.json"),          audio_info)

    # ------------------------------------------------------------------
    # Step 6: Build evidence_package.json
    # ------------------------------------------------------------------
    completed_at = datetime.now(timezone.utc).isoformat()
    total_ms = int((time.time() - t0) * 1000)

    evidence: dict = {
        "video_id": video_id,
        "source": {
            "type": "link",
            "local_path": video_path,
            "original_filename": os.path.basename(video_path),
            "url": url,
            "platform": social_metadata.get("platform"),
            "social_metadata": {
                "title": social_metadata.get("title"),
                "like_count": social_metadata.get("like_count"),
                "view_count": social_metadata.get("view_count"),
                "comment_count": social_metadata.get("comment_count"),
                "upload_date": social_metadata.get("upload_date"),
                "thumbnail_url": social_metadata.get("thumbnail_url"),
            },
        },
        "metadata": tech_metadata,
        "scenes": analysis["scenes"],
        "keyframes": analysis["keyframes"],
        "transcript": analysis["transcript"],
        "asr_info": analysis["asr_info"],
        "ocr_results": analysis["ocr_results"],
        "beats": analysis["beats"],
        "basic_analysis": analysis["basic_analysis"],
        "processing_info": {
            "started_at": started_at,
            "completed_at": completed_at,
            "total_duration_ms": total_ms,
            "processors": [
                {"name": "download",      "status": "success",                                        "duration_ms": None},
                {"name": "tech_metadata", "status": "success" if tech_metadata else "failed",         "duration_ms": None},
                {"name": "scene_detect",  "status": "success" if analysis["scenes"] else "failed",    "duration_ms": None},
                {"name": "keyframes",     "status": "success" if any(kf["path"] for kf in analysis["keyframes"]) else "failed", "duration_ms": None},
                {"name": "asr",           "status": "success" if analysis["transcript"] is not None else "failed", "duration_ms": None},
                {"name": "ocr",           "status": "success",                                        "duration_ms": None},
                {"name": "audio",         "status": "success" if analysis["beats"] is not None else "failed", "duration_ms": None},
                {"name": "vlm",           "status": "success" if vlm_model and any(kf.get("vlm_description") for kf in analysis["keyframes"]) else ("skipped" if not vlm_model else "failed"), "duration_ms": None},
            ],
        },
    }

    evidence_path = os.path.join(vid_dir, "evidence_package.json")
    _write_json(evidence_path, evidence)
    logger.info("evidence_package.json saved → %s", evidence_path)
    _print_summary(evidence, evidence_path)
    return evidence


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="ViralCut — analyse a short video from a URL"
    )
    parser.add_argument(
        "url",
        nargs="?",
        help="Video URL (Douyin / TikTok / Bilibili / YouTube / Xiaohongshu)",
    )
    parser.add_argument(
        "--output-dir",
        default=os.getenv("OUTPUT_DIR", "./output"),
        help="Root output directory (default: ./output or $OUTPUT_DIR)",
    )
    parser.add_argument(
        "--cookie-file",
        default=os.getenv("COOKIE_FILE"),
        help="Netscape cookie file for yt-dlp (default: $COOKIE_FILE)",
    )
    parser.add_argument(
        "--whisper-model",
        default="base",
        choices=["tiny", "base", "small", "medium", "large"],
        help="Whisper model size (default: base)",
    )
    parser.add_argument(
        "--vlm-model",
        default=None,
        help=(
            "Vision LLM for keyframe descriptions, e.g. 'google/gemini-flash-1.5-8b'. "
            "Requires OPENROUTER_API_KEY. Skipped if omitted."
        ),
    )
    parser.add_argument(
        "--vlm-base-url",
        default="https://openrouter.ai/api/v1",
        help="API base URL for VLM (default: OpenRouter)",
    )
    args = parser.parse_args()

    url: str = args.url or ""
    if not url:
        url = input("Enter video URL: ").strip()
    if not url:
        print("Error: no URL provided.", file=sys.stderr)
        sys.exit(1)

    run_pipeline(
        url=url,
        output_dir=args.output_dir,
        cookie_file=args.cookie_file,
        whisper_model=args.whisper_model,
        vlm_model=args.vlm_model,
        vlm_base_url=args.vlm_base_url,
    )


if __name__ == "__main__":
    main()
