"""
viralcut.py — Unified CLI: Stage 1 (download + analysis) → Stage 2 (viral dimension analysis).

Usage:
    # Full pipeline (Stage 1 + Stage 2)
    python viralcut.py "https://www.youtube.com/shorts/..."
    python viralcut.py "https://..." --vlm-model google/gemini-3.5-flash
    python viralcut.py "https://..." --vlm-model google/gemini-3.5-flash --agents 8

    # Stage 2 only (if Stage 1 already ran)
    python viralcut.py --analyze stage1/output/VIDEO_ID/evidence_package.json
"""
import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from datetime import datetime

from dotenv import load_dotenv
# This file lives at src/stage2/leo_variant/ — repo root is three levels up.
load_dotenv(Path(__file__).parent.parent.parent.parent / ".env")

# Stage 1 link pipeline lives at src/stage1/link_pipeline/;
# this variant's Stage 2 modules sit in the same dir as this file.
_SRC = Path(__file__).parent.parent.parent  # src/
sys.path.insert(0, str(_SRC / "stage1" / "link_pipeline"))
sys.path.insert(0, str(Path(__file__).parent))

from pipeline_link import run_pipeline
from orchestrator import run_viral_analysis
from pipeline_stage2 import _print_results

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="ViralCut — full pipeline: download → analyse → viral dimensions"
    )

    # Mutually exclusive: URL (full pipeline) vs --analyze (stage 2 only)
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("url", nargs="?", help="Video URL to process (Stage 1 + Stage 2)")
    input_group.add_argument(
        "--analyze",
        metavar="EVIDENCE_JSON",
        help="Skip Stage 1, run Stage 2 only on an existing evidence_package.json",
    )

    # Stage 1 options
    parser.add_argument("--output-dir", default=os.getenv("OUTPUT_DIR", "./stage1/output"))
    parser.add_argument("--cookie-file", default=os.getenv("COOKIE_FILE"))
    parser.add_argument("--whisper-model", default="base",
                        choices=["tiny", "base", "small", "medium", "large"])
    parser.add_argument("--vlm-model", default=None,
                        help="Vision LLM for keyframe descriptions, e.g. google/gemini-3.5-flash")
    parser.add_argument("--vlm-base-url", default="https://openrouter.ai/api/v1")

    # Stage 2 options
    parser.add_argument("--model", default="anthropic/claude-sonnet-4-5",
                        help="LLM for viral analysis agents (default: claude-sonnet-4-5)")
    parser.add_argument("--agents", type=int, default=6,
                        help="Number of parallel analysis agents (default: 6)")
    parser.add_argument("--base-url", default="https://openrouter.ai/api/v1")
    parser.add_argument("--output", default=None,
                        help="Save Stage 2 results to this JSON path")

    args = parser.parse_args()

    # ------------------------------------------------------------------
    # Stage 1 (skip if --analyze)
    # ------------------------------------------------------------------
    if args.analyze:
        evidence_path = args.analyze
        with open(evidence_path, encoding="utf-8") as f:
            evidence = json.load(f)
        logger.info("Skipping Stage 1 — loaded %s", evidence_path)
    else:
        evidence = run_pipeline(
            url=args.url,
            output_dir=args.output_dir,
            cookie_file=args.cookie_file,
            whisper_model=args.whisper_model,
            vlm_model=args.vlm_model,
            vlm_base_url=args.vlm_base_url,
        )

    # ------------------------------------------------------------------
    # Stage 2
    # ------------------------------------------------------------------
    result = asyncio.run(
        run_viral_analysis(
            evidence,
            model=args.model,
            num_agents=args.agents,
            base_url=args.base_url,
        )
    )

    _print_results(result)

    # Determine output path: explicit --output, or auto-save to output/viral_analysis_{video_id}.json
    if args.output:
        out_path = args.output
    else:
        video_id = evidence.get("video_id", "unknown")
        out_dir = Path(args.analyze).parent.parent if args.analyze else Path(args.output_dir)
        out_path = str(out_dir / f"viral_analysis_{video_id}.json")

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result.model_dump(), f, ensure_ascii=False, indent=2)
    logger.info("Viral analysis saved → %s", out_path)


if __name__ == "__main__":
    main()
