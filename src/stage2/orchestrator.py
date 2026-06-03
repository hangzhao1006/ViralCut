"""
orchestrator.py — Parallel fan-out across N agents, then synthesis.

Flow:
  evidence_package
      ↓  (asyncio.gather — all agents in parallel)
  [AgentFinding × N]
      ↓  (synthesis agent)
  SynthesisResult
"""
from __future__ import annotations
import asyncio
import json
import logging
import os
from openai import AsyncOpenAI
from schemas import AgentFinding, SynthesisResult, ClusteredDimension, EvidenceItem
from agents import run_agent, _parse_json_response

logger = logging.getLogger(__name__)

_SYNTHESIS_SCHEMA = """
{
  "ranked_dimensions": [
    {
      "dimension_name": "这个cluster的规范标签，2-5字中文",
      "viral_mechanism": "综合各agent的发现，1-2句话阐述核心机制",
      "agent_agreement_count": <多少个agent（主+次维度都算）发现了这个维度，整数>,
      "avg_strength_score": <贡献此维度的agent的平均strength_score，保留1位小数>,
      "supporting_agent_ids": [<agent_id列表>],
      "representative_evidence": [<最有代表性的1-3条EvidenceItem，原样保留或择优合并>]
    }
  ],
  "top_viral_reason": "一段话（3-5句）：这个视频最核心的爆款原因和背后机制",
  "analysis_note": "值得注意的分歧、仅被1个agent发现但独特有价值的维度，或数据局限说明"
}
"""


async def _run_synthesis(
    findings: list[AgentFinding],
    client: AsyncOpenAI,
    model: str,
) -> SynthesisResult:
    """
    Synthesis agent: semantically cluster findings from all worker agents,
    rank by (agreement_count × avg_strength_score), return SynthesisResult.
    """
    findings_payload = json.dumps(
        [f.model_dump() for f in findings],
        ensure_ascii=False,
        indent=2,
    )

    system_prompt = f"""你是爆款视频分析的主分析师，负责汇总来自 {len(findings)} 个不同视角agent的分析结果。

任务：
1. 把语义相似的维度归并为同一个 cluster（标签不同但机制相近即可合并）
2. 同时考虑 primary_dimension 和 secondary_dimension（如果存在）
3. 按照"共识度 × 平均强度"降序排列：多个agent独立发现同一维度，说明该维度是更可靠的爆款原因
4. 识别有价值的独特发现（仅1个agent发现但 strength_score ≥ 7）

输出严格合法的 JSON，格式：
{_SYNTHESIS_SCHEMA}"""

    response = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": f"以下是各agent的分析结果，请归并排序输出最终分析：\n\n{findings_payload}",
            },
        ],
        response_format={"type": "json_object"},
        temperature=0.2,
        max_tokens=6000,
    )

    raw = response.choices[0].message.content
    try:
        data = _parse_json_response(raw)
    except (json.JSONDecodeError, ValueError) as e:
        logger.debug("Synthesis raw response (first 500): %s", raw[:500])
        raise

    ranked = []
    for d in data.get("ranked_dimensions", []):
        evidence = [EvidenceItem(**e) for e in d.get("representative_evidence", [])]
        ranked.append(
            ClusteredDimension(
                dimension_name=d["dimension_name"],
                viral_mechanism=d["viral_mechanism"],
                agent_agreement_count=int(d["agent_agreement_count"]),
                avg_strength_score=float(d["avg_strength_score"]),
                supporting_agent_ids=d.get("supporting_agent_ids", []),
                representative_evidence=evidence,
            )
        )

    return SynthesisResult(
        ranked_dimensions=ranked,
        top_viral_reason=data.get("top_viral_reason", ""),
        analysis_note=data.get("analysis_note", ""),
    )


async def run_viral_analysis(
    evidence_package: dict,
    *,
    model: str = "anthropic/claude-sonnet-4-5",
    num_agents: int = 6,
    api_key: str | None = None,
    base_url: str = "https://openrouter.ai/api/v1",
) -> SynthesisResult:
    """
    Main entry point for Stage 2.

    Spawns `num_agents` agents in parallel (each with a different soft analytical lens),
    collects their AgentFinding objects, then runs a synthesis agent that clusters
    similar findings and ranks dimensions by agent agreement × strength.

    Args:
        evidence_package: The dict from evidence_package.json (Stage 1 output).
        model:            OpenRouter model string, e.g. 'anthropic/claude-sonnet-4-5'.
        num_agents:       Number of parallel analysis agents (default 6, one per lens).
        api_key:          OpenRouter API key; falls back to OPENROUTER_API_KEY env var.
        base_url:         API base URL; override for non-OpenRouter endpoints.

    Returns:
        SynthesisResult with ranked viral dimensions.
    """
    resolved_key = api_key or os.getenv("OPENROUTER_API_KEY")
    if not resolved_key:
        raise ValueError("OpenRouter API key not found. Set OPENROUTER_API_KEY or pass api_key=")

    client = AsyncOpenAI(api_key=resolved_key, base_url=base_url)

    logger.info("Starting parallel viral analysis: %d agents, model=%s", num_agents, model)

    tasks = [run_agent(i, evidence_package, client, model) for i in range(num_agents)]
    raw_results = await asyncio.gather(*tasks, return_exceptions=True)

    valid: list[AgentFinding] = []
    for i, result in enumerate(raw_results):
        if isinstance(result, Exception):
            logger.error("Agent %d failed: %s", i, result)
        else:
            valid.append(result)

    if not valid:
        raise RuntimeError("All agents failed — cannot run synthesis.")

    logger.info("%d/%d agents succeeded. Running synthesis...", len(valid), num_agents)
    synthesis = await _run_synthesis(valid, client, model)

    logger.info(
        "Synthesis complete: %d dimensions identified. Top: '%s' (agreement=%d)",
        len(synthesis.ranked_dimensions),
        synthesis.ranked_dimensions[0].dimension_name if synthesis.ranked_dimensions else "N/A",
        synthesis.ranked_dimensions[0].agent_agreement_count if synthesis.ranked_dimensions else 0,
    )
    return synthesis
