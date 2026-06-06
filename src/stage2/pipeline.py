"""Stage 2 pipeline: evidence_package → multi-agent analysis → video_structure.

Usage:
    # Debug local tools only (no LLM calls):
    python -m src.stage2.pipeline evidence_package.json --debug

    # Run one agent with dependencies auto-run:
    python -m src.stage2.pipeline evidence_package.json --agent rhythm

    # Run all implemented agents + evaluator:
    python -m src.stage2.pipeline evidence_package.json
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from src.stage2.input_builder import build_timeline_index_from_file, TimelineIndex
from src.stage2.framework.blackboard import Blackboard
from src.stage2.framework.tools import Stage2ToolRegistry, VisionBudget
from src.stage2.framework.base_agent import AgentResult
from src.stage2.evaluator import Stage2Evaluator
from src.stage1.utils.logger import get_logger

logger = get_logger(__name__)

IMPLEMENTED_AGENTS = ["script", "rhythm", "packaging", "value", "energy", "transfer"]
AGENT_DEPENDENCIES: dict[str, list[str]] = {
    "script": [],
    # Phase 2 is logically parallel but implemented sequentially for MVP.
    # Phase 2 agents only depend on script and should not depend on each other.
    "rhythm": ["script"],
    "packaging": ["script"],
    "value": ["script"],
    # Energy synthesizes script + rhythm + packaging + value.
    "energy": ["script", "rhythm", "packaging", "value"],
    # Transfer reads overview + all upstream outputs.
    "transfer": ["script", "rhythm", "packaging", "value", "energy"],
    # Evaluator is rule-based and checks all outputs.
    "evaluator": ["script", "rhythm", "packaging", "value", "energy", "transfer"],
}


def create_stage2_context(evidence_path: str | Path) -> dict[str, Any]:
    """Build all shared infrastructure for Stage 2 agents."""
    timeline = build_timeline_index_from_file(str(evidence_path))
    blackboard = Blackboard()
    vision_budget = VisionBudget()
    tools = Stage2ToolRegistry(
        timeline=timeline,
        blackboard=blackboard,
        vision_budget=vision_budget,
    )
    return {
        "timeline": timeline,
        "blackboard": blackboard,
        "tools": tools,
        "vision_budget": vision_budget,
    }


def debug_local_tools(evidence_path: str | Path) -> dict[str, Any]:
    """Test local tools without any LLM calls."""
    ctx = create_stage2_context(evidence_path)
    timeline: TimelineIndex = ctx["timeline"]
    overview = timeline.get_overview()
    duration = overview.get("duration") or 0

    return {
        "overview": overview,
        "first_10s": timeline.query_timeline(0, min(10, duration)),
        "last_10s": timeline.query_timeline(max(0, duration - 10), duration),
        "display_texts_preview": timeline.get_all_display_texts()[:20],
        "beat_alignment_sample": timeline.get_cut_beat_alignment(0, min(30, duration)),
        "total_display_texts": len(timeline.get_all_display_texts()),
    }


def run_single_agent(
    evidence_path: str | Path,
    agent_name: str,
    feedback: str | None = None,
) -> AgentResult:
    """Run one agent for testing/debugging, auto-running dependencies first."""
    from src.stage2.llm_client import create_llm_client

    agent_name = agent_name.strip().lower()
    ctx = create_stage2_context(evidence_path)
    client = create_llm_client()
    results: dict[str, AgentResult] = {}

    start = time.perf_counter()
    _ensure_agent_completed(
        agent_name=agent_name,
        client=client,
        ctx=ctx,
        results=results,
        feedback=feedback,
    )
    elapsed = time.perf_counter() - start

    result = results[agent_name]
    logger.info(
        "%s completed in %.1fs including dependencies (%d target LLM calls, %d target tool calls)",
        agent_name, elapsed, result.llm_calls, len(result.tool_history),
    )
    return result


def run_full_pipeline(
    evidence_path,
    progress_callback=None,
    on_agent_done=None,
):
    """Run the complete Stage 2 multi-agent pipeline.

    Optional callbacks for progress reporting:
      progress_callback(agent_name, message) — called when an agent starts
      on_agent_done(agent_name) — called when an agent finishes
    """
    from src.stage2.llm_client import create_llm_client

    ctx = create_stage2_context(evidence_path)
    client = create_llm_client()
    tools = ctx["tools"]
    blackboard = ctx["blackboard"]
    timeline = ctx["timeline"]
    total_start = time.perf_counter()

    results = {}

    def _notify_start(name, msg):
        if progress_callback:
            try:
                progress_callback(name, msg)
            except Exception:
                pass

    def _notify_done(name):
        if on_agent_done:
            try:
                on_agent_done(name)
            except Exception:
                pass

    # Phase 1: Script
    logger.info("=== Phase 1: Script Agent ===")
    _notify_start("script", "正在分析脚本结构...")
    script_agent = _create_agent("script", client)
    results["script"] = script_agent.run(tools=tools, blackboard=blackboard)
    script_output = results["script"].output
    if script_output.get("segments"):
        timeline.set_segments(script_output["segments"])
        logger.info("Script Agent output %d segments", len(script_output["segments"]))
    else:
        logger.warning("Script Agent produced no segments!")
    _notify_done("script")

    # Phase 2: Rhythm + Packaging + Value (sequential, only read script)
    for agent_name in ["rhythm", "packaging", "value"]:
        logger.info("=== Phase 2: %s Agent ===", agent_name.capitalize())
        _notify_start(agent_name, f"正在分析{agent_name}...")
        agent = _create_agent(agent_name, client)
        results[agent_name] = agent.run(tools=tools, blackboard=blackboard)
        _notify_done(agent_name)

    # Phase 3: Energy
    logger.info("=== Phase 3: Energy Agent ===")
    _notify_start("energy", "正在生成能量曲线...")
    energy_agent = _create_agent("energy", client)
    results["energy"] = energy_agent.run(tools=tools, blackboard=blackboard)
    _notify_done("energy")

    # Write overview to blackboard for Transfer Agent
    blackboard.write("overview", timeline.get_overview(), key="overview")

    # Phase 4: Transfer
    logger.info("=== Phase 4: Transfer Agent ===")
    _notify_start("transfer", "正在提取迁移蓝图...")
    transfer_agent = _create_agent("transfer", client)
    results["transfer"] = transfer_agent.run(tools=tools, blackboard=blackboard)
    _notify_done("transfer")

    total_elapsed = time.perf_counter() - total_start
    total_llm_calls = sum(r.llm_calls for r in results.values())
    total_tool_calls = sum(len(r.tool_history) for r in results.values())

    logger.info(
        "Stage 2 pipeline completed in %.1fs (%d LLM calls, %d tool calls)",
        total_elapsed, total_llm_calls, total_tool_calls,
    )

    video_structure = {
        "video_id": timeline.get_overview().get("video_id"),
        "duration": timeline.duration,
        "script_structure": blackboard.read("script", {}),
        "rhythm_structure": blackboard.read("rhythm", {}),
        "packaging_structure": blackboard.read("packaging", {}),
        "value_strategy": blackboard.read("value", {}),
        "energy_curve": blackboard.read("energy", {}),
        "transfer_blueprint": blackboard.read("transfer", {}),
        "analysis_metadata": {
            "total_duration_seconds": round(total_elapsed, 1),
            "total_llm_calls": total_llm_calls,
            "total_tool_calls": total_tool_calls,
            "vision_budget": ctx["vision_budget"].status(),
            "blackboard_history": blackboard.history,
            "agent_details": {
                name: {
                    "llm_calls": r.llm_calls,
                    "tool_calls": len(r.tool_history),
                    "tool_history": r.tool_history,
                }
                for name, r in results.items()
            },
        },
    }

    # Run evaluator if available
    try:
        from src.stage2.evaluator import evaluate
        video_structure["evaluation"] = evaluate(video_structure, timeline)
    except Exception as exc:
        logger.warning("Evaluator skipped: %s", exc)

    return video_structure
    

def _ensure_agent_completed(
    agent_name: str,
    client: Any,
    ctx: dict[str, Any],
    results: dict[str, AgentResult],
    feedback: str | None = None,
) -> None:
    """Run dependencies and then the requested agent exactly once."""
    agent_name = agent_name.strip().lower()
    if agent_name in results:
        return
    if agent_name not in AGENT_DEPENDENCIES:
        raise ValueError(
            f"Unknown agent: {agent_name}. Available: {', '.join(AGENT_DEPENDENCIES.keys())}"
        )

    for dep in AGENT_DEPENDENCIES[agent_name]:
        _ensure_agent_completed(dep, client, ctx, results)

    if agent_name == "evaluator":
        video_structure = _build_video_structure(ctx=ctx, results=results, total_start=time.perf_counter())
        evaluator = Stage2Evaluator(ctx["timeline"], ctx["blackboard"])
        output = evaluator.evaluate(video_structure)
        results[agent_name] = AgentResult(agent_name, output, [], None, 0)
        return

    # Transfer should have video overview available via read_blackboard("overview").
    if agent_name == "transfer" and not ctx["blackboard"].has("overview"):
        ctx["blackboard"].write(
            "pipeline",
            ctx["timeline"].get_overview(),
            key="overview",
            summary="video overview for Transfer Agent",
        )

    agent = _create_agent(agent_name, client)
    result = agent.run(
        tools=ctx["tools"],
        blackboard=ctx["blackboard"],
        feedback=feedback,
    )
    results[agent_name] = result

    # Script output defines segments for downstream segment evidence tools.
    if agent_name == "script" and result.output.get("segments"):
        ctx["timeline"].set_segments(result.output["segments"])
        logger.info("Script Agent output %d segments", len(result.output["segments"]))


def _build_video_structure(
    ctx: dict[str, Any],
    results: dict[str, AgentResult],
    total_start: float,
) -> dict[str, Any]:
    timeline: TimelineIndex = ctx["timeline"]
    blackboard: Blackboard = ctx["blackboard"]
    total_elapsed = time.perf_counter() - total_start

    return {
        "video_id": timeline.get_overview().get("video_id"),
        "duration": timeline.duration,
        "script_structure": blackboard.read("script", {}),
        "rhythm_structure": blackboard.read("rhythm", {}),
        "packaging_structure": blackboard.read("packaging", {}),
        "value_strategy": blackboard.read("value", {}),
        "energy_curve": blackboard.read("energy", {}),
        "transfer_blueprint": blackboard.read("transfer", {}),
        "analysis_metadata": {
            "total_duration_seconds": round(total_elapsed, 1),
            "total_llm_calls": sum(r.llm_calls for r in results.values()),
            "total_tool_calls": sum(len(r.tool_history) for r in results.values()),
            "vision_budget": ctx["vision_budget"].status(),
            "blackboard_history": blackboard.history,
            "agent_details": {
                name: {
                    "llm_calls": r.llm_calls,
                    "tool_calls": len(r.tool_history),
                    "tool_history": r.tool_history,
                }
                for name, r in results.items()
            },
        },
    }


def _create_agent(name: str, client: Any) -> Any:
    """Factory for creating agents by name."""
    name = name.strip().lower()
    if name == "script":
        from src.stage2.agents.script_agent import ScriptAgent
        return ScriptAgent(llm_client=client)
    if name == "rhythm":
        from src.stage2.agents.rhythm_agent import RhythmAgent
        return RhythmAgent(llm_client=client)
    if name == "packaging":
        from src.stage2.agents.packaging_agent import PackagingAgent
        return PackagingAgent(llm_client=client)
    if name == "value":
        from src.stage2.agents.value_agent import ValueAgent
        return ValueAgent(llm_client=client)
    if name == "energy":
        from src.stage2.agents.energy_agent import EnergyAgent
        return EnergyAgent(llm_client=client)
    if name == "transfer":
        from src.stage2.agents.transfer_agent import TransferAgent
        return TransferAgent(llm_client=client)
    raise ValueError(f"Unknown agent: {name}. Available: {', '.join(IMPLEMENTED_AGENTS + ['evaluator'])}")


if __name__ == "__main__":
    import argparse
    from dotenv import load_dotenv
    load_dotenv()

    parser = argparse.ArgumentParser(description="ViralCut Stage 2 Pipeline")
    parser.add_argument("evidence_package", help="Path to evidence_package.json")
    parser.add_argument("--debug", action="store_true", help="Only test local tools, no LLM calls")
    parser.add_argument("--agent", type=str, help="Run one agent with dependencies auto-run, e.g. script/rhythm/packaging/value/energy/transfer/evaluator")
    parser.add_argument("--out", type=str, help="Output file path")
    args = parser.parse_args()

    if args.debug:
        result = debug_local_tools(args.evidence_package)
        out_path = args.out or "stage2_debug.json"
    elif args.agent:
        agent_result = run_single_agent(args.evidence_package, args.agent)
        result = {
            "agent": args.agent,
            "output": agent_result.output,
            "tool_history": agent_result.tool_history,
            "llm_calls": agent_result.llm_calls,
        }
        out_path = args.out or f"stage2_{args.agent}_result.json"
    else:
        result = run_full_pipeline(args.evidence_package)
        out_path = args.out or "video_structure.json"

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2, default=str)
    print(f"Output: {out_path}")

    # Auto-generate human-readable report
    from src.stage2.report import generate_report
    report_text = generate_report(result)
    report_path = out_path.replace(".json", "_report.md") if out_path else "video_structure_report.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_text)
    logger.info("Report saved to %s", report_path)
