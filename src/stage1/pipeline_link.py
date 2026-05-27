"""
pipeline_link.py — End-to-end CLI runner for the link-download pipeline.

Usage:
    python pipeline_link.py "https://www.youtube.com/shorts/..."
    python pipeline_link.py --output-dir ./out --whisper-model small "https://..."
    python pipeline_link.py          # prompts for URL interactively
"""
import argparse
import json
import logging
import os
import sys

# Allow running as a script from any working directory
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv  # type: ignore[import]

load_dotenv()

from link_input import download_from_url
from processors import analyze_video

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


def _print_summary(result: dict, json_path: str) -> None:
    metadata = result.get("metadata") or {}
    shots = result.get("shots") or []
    transcript = result.get("transcript") or []
    audio = result.get("audio") or {}

    print()
    print("=" * 62)
    print("  ViralCut — Analysis Complete")
    print("=" * 62)
    print(f"  Title    : {metadata.get('title', 'N/A')}")
    print(f"  Platform : {metadata.get('platform', 'N/A')}")
    print(f"  Duration : {metadata.get('duration', 0):.1f} s")
    print(f"  Shots    : {len(shots)}")
    print(f"  Segments : {len(transcript)}")
    bpm = audio.get("bpm")
    print(f"  BPM      : {bpm:.1f}" if bpm is not None else "  BPM      : N/A")
    print(f"  Output   : {json_path}")
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
) -> dict:
    """
    Full link → analysis → JSON pipeline.

    1. Downloads video + metadata via yt-dlp (link_input.download_from_url).
    2. Runs structural analysis (processors.analyze_video).
    3. Merges results into the canonical output schema and writes JSON.

    Returns the complete result dict.
    """
    logger.info("Pipeline start  url=%s", url)

    # ------------------------------------------------------------------
    # Step 1: Download
    # ------------------------------------------------------------------
    tmp_dir = os.path.join(output_dir, "temp")
    download_result = download_from_url(url, tmp_dir, cookie_file=cookie_file)
    video_path: str = download_result["video_path"]
    metadata: dict = download_result["metadata"]

    video_id = _video_id_from_path(video_path)
    logger.info("video_id=%s  path=%s", video_id, video_path)

    # ------------------------------------------------------------------
    # Step 2: Analysis — keyframes saved to output/keyframes/{video_id}/
    # ------------------------------------------------------------------
    keyframes_dir = os.path.join(output_dir, "keyframes", video_id)
    analysis = analyze_video(video_path, keyframes_dir, whisper_model=whisper_model)

    # ------------------------------------------------------------------
    # Step 3: Merge into final schema
    # ------------------------------------------------------------------
    result: dict = {
        "source": "link",
        "video_path": video_path,
        "metadata": metadata,
        "shots": analysis["shots"],
        "transcript": analysis["transcript"],
        "audio": analysis["audio"],
    }

    # Save JSON → output/results/{video_id}.json
    results_dir = os.path.join(output_dir, "results")
    os.makedirs(results_dir, exist_ok=True)
    json_path = os.path.join(results_dir, f"{video_id}.json")

    with open(json_path, "w", encoding="utf-8") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=2)

    logger.info("JSON saved → %s", json_path)
    _print_summary(result, json_path)
    return result


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
    )


if __name__ == "__main__":
    main()
