"""
pipeline_stage2.py — CLI entry point for Stage 2 viral dimension analysis.

Usage:
    python pipeline_stage2.py path/to/evidence_package.json
    python pipeline_stage2.py path/to/evidence_package.json --model anthropic/claude-opus-4-8
    python pipeline_stage2.py path/to/evidence_package.json --num-agents 8 --output results.json
    python pipeline_stage2.py path/to/evidence_package.json --base-url https://api.openai.com/v1

Requires env var OPENROUTER_API_KEY (or OPENAI_API_KEY if using --base-url with OpenAI).
"""
import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent.parent / ".env")

sys.path.insert(0, os.path.dirname(__file__))
from orchestrator import run_viral_analysis
from schemas import SynthesisResult

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def _print_results(result: SynthesisResult) -> None:
    print()
    print("=" * 66)
    print("  ViralCut Stage 2 — Viral Dimension Analysis")
    print("=" * 66)

    for i, dim in enumerate(result.ranked_dimensions, 1):
        bar = "█" * int(dim.avg_strength_score) + "░" * (10 - int(dim.avg_strength_score))
        print(f"\n  #{i}  {dim.dimension_name}")
        print(f"       共识度: {dim.agent_agreement_count} agents | 强度: {bar} {dim.avg_strength_score:.1f}/10")
        print(f"       机制: {dim.viral_mechanism}")
        if dim.representative_evidence:
            ev = dim.representative_evidence[0]
            print(f"       证据: [{ev.source}] {ev.reference} → {ev.quote[:60]}...")

    print(f"\n  核心结论\n  {'─'*60}")
    print(f"  {result.top_viral_reason}")

    if result.analysis_note:
        print(f"\n  备注\n  {'─'*60}")
        print(f"  {result.analysis_note}")

    print()
    print("=" * 66)
    print()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="ViralCut Stage 2 — Multi-agent viral dimension analysis"
    )
    parser.add_argument(
        "evidence_json",
        help="Path to evidence_package.json produced by Stage 1",
    )
    parser.add_argument(
        "--model",
        default="anthropic/claude-sonnet-4-5",
        help="OpenRouter model string (default: anthropic/claude-sonnet-4-5)",
    )
    parser.add_argument(
        "--num-agents",
        type=int,
        default=6,
        help="Number of parallel analysis agents (default: 6)",
    )
    parser.add_argument(
        "--base-url",
        default="https://openrouter.ai/api/v1",
        help="API base URL (default: OpenRouter)",
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="API key (default: reads OPENROUTER_API_KEY from environment)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Save SynthesisResult JSON to this path",
    )
    args = parser.parse_args()

    if not os.path.exists(args.evidence_json):
        print(f"Error: file not found: {args.evidence_json}", file=sys.stderr)
        sys.exit(1)

    with open(args.evidence_json, encoding="utf-8") as f:
        evidence = json.load(f)

    result = asyncio.run(
        run_viral_analysis(
            evidence,
            model=args.model,
            num_agents=args.num_agents,
            api_key=args.api_key,
            base_url=args.base_url,
        )
    )

    _print_results(result)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(result.model_dump(), f, ensure_ascii=False, indent=2)
        logger.info("Results saved → %s", args.output)


if __name__ == "__main__":
    main()
