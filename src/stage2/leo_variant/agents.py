"""
agents.py — Single async agent: evidence_package + lens → AgentFinding.

Each agent receives the same evidence but a different soft analytical lens.
The lens is a suggestion, not a constraint — agents are free to report
whatever dimension is most strongly supported by the data.
"""
from __future__ import annotations
import asyncio
import json
import logging
import re
from openai import AsyncOpenAI
from schemas import AgentFinding, ViralDimension, EvidenceItem

logger = logging.getLogger(__name__)


def _parse_json_response(raw: str) -> dict:
    """
    Robustly parse a JSON response that may be wrapped in markdown fences
    or otherwise malformed at the tail end.
    """
    # Strip markdown code fences: ```json ... ``` or ``` ... ```
    stripped = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.IGNORECASE)
    stripped = re.sub(r"\s*```$", "", stripped.strip())

    # Try direct parse first
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass

    # Find the outermost {...} block and try to parse just that
    start = stripped.find("{")
    if start != -1:
        # Walk backwards from end to find a valid closing brace
        for end in range(len(stripped), start, -1):
            try:
                return json.loads(stripped[start:end])
            except json.JSONDecodeError:
                continue

    raise ValueError(f"Could not parse JSON from response (first 200 chars): {raw[:200]}")

# Soft analytical lenses — biases the agent's starting angle without restricting output.
# Cycle through these if num_agents > len(LENSES).
LENSES = [
    (
        "情感心理",
        "从情感和心理角度切入：恐惧、共鸣、渴望、满足感、身份认同、情绪爆发点等机制。"
        "但如果数据指向更强的其他维度，优先报告那个。",
    ),
    (
        "叙事结构",
        "从叙事和结构角度切入：钩子设计、情节反转、悬念节奏、信息披露顺序、开篇吸引力。"
        "但如果数据指向更强的其他维度，优先报告那个。",
    ),
    (
        "社会文化",
        "从社会文化角度切入：群体认同、话题性、争议性、时代共鸣、亚文化符号、社交货币。"
        "但如果数据指向更强的其他维度，优先报告那个。",
    ),
    (
        "信息认知",
        "从信息和认知角度切入：知识新颖性、信息密度、认知冲击、反常识的事实、好奇心缺口。"
        "但如果数据指向更强的其他维度，优先报告那个。",
    ),
    (
        "制作形式",
        "从制作和形式角度切入：节奏卡点、镜头节奏、视觉冲击、音乐适配、字幕密度、剪辑风格。"
        "但如果数据指向更强的其他维度，优先报告那个。",
    ),
    (
        "行为社交",
        "从行为经济学和社交动力学角度切入：分享动机、炫耀资本、从众心理、稀缺感、互动驱动、利他感。"
        "但如果数据指向更强的其他维度，优先报告那个。",
    ),
]

# JSON schema embedded in system prompt — used as the output contract.
_OUTPUT_SCHEMA = """
{
  "primary_dimension": {
    "dimension_name": "2-5字中文标签，如'情绪共鸣爆发'",
    "viral_mechanism": "1-2句话：这个维度让视频爆款的核心心理/社会机制",
    "strength_score": <0-10的小数，这个维度在视频中的体现强度>,
    "confidence": <0-1的小数，你对这个分析的置信度>,
    "evidence": [
      {
        "source": "transcript|scene|ocr|audio|metadata|social 之一",
        "reference": "具体时间戳如'00:05-00:12'，或字段名如'basic_analysis.shot_density'",
        "quote": "从数据中直接复制的原文或数值，不要改写",
        "reasoning": "一句话：这条证据如何支撑上述维度"
      }
    ]
  },
  "secondary_dimension": null
}

如果你发现了第二个明显的爆款维度，可以在 secondary_dimension 里报告，格式与 primary_dimension 相同。
"""


def _prepare_evidence(package: dict) -> str:
    """
    Distill evidence_package into agent-consumable JSON.
    Strips local file paths and heavy numeric arrays (rms_energy etc.)
    Truncates transcript/OCR if unusually long.
    """
    social = (package.get("source") or {}).get("social_metadata", {})

    beats_raw = dict(package.get("beats") or {})
    beats_raw.pop("rms_energy", None)
    beats_raw.pop("rms_timestamps", None)
    bt = beats_raw.get("beat_timestamps", [])
    if len(bt) > 20:
        beats_raw["beat_timestamps"] = bt[:10] + ["...(truncated)..."] + bt[-5:]

    transcript = package.get("transcript") or []
    if len(transcript) > 60:
        transcript = transcript[:25] + [{"text": "...(truncated)..."}] + transcript[-10:]

    scenes = package.get("scenes") or []
    for s in scenes:
        s.pop("keyframe_ids", None)

    # Build a compact per-shot view merging keyframe metadata + OCR + VLM description.
    # Strips local file paths; preserves vlm_description when present.
    ocr_map = {r["frame_id"]: r.get("display_text", "") for r in (package.get("ocr_results") or [])}
    raw_keyframes = package.get("keyframes") or []
    if len(raw_keyframes) > 30:
        raw_keyframes = raw_keyframes[:20] + [{"frame_id": "...(truncated)..."}] + raw_keyframes[-5:]
    shots_view = []
    for kf in raw_keyframes:
        fid = kf.get("frame_id", "")
        entry: dict = {"frame_id": fid, "timestamp": kf.get("timestamp"), "ocr_text": ocr_map.get(fid, "")}
        if kf.get("vlm_description"):
            entry["vlm_description"] = kf["vlm_description"]
        shots_view.append(entry)

    return json.dumps(
        {
            "social_metadata": social,
            "technical_metadata": package.get("metadata", {}),
            "basic_analysis": package.get("basic_analysis", {}),
            "asr_info": package.get("asr_info", {}),
            "beats": beats_raw,
            "scenes": scenes,
            "transcript": transcript,
            "keyframes": shots_view,
        },
        ensure_ascii=False,
        indent=2,
    )


def _build_system_prompt(lens_name: str, lens_instruction: str) -> str:
    return f"""你是一位专业的爆款短视频分析师。

当前分析视角（软引导，不是限制）：{lens_instruction}

你的任务：基于下方的视频结构化数据，找出这个视频成为爆款的最核心维度。

输出规则：
1. 必须输出严格合法的 JSON，结构如下：
{_OUTPUT_SCHEMA}
2. evidence 里的 quote 必须原文复制自数据，不得编造或改写
3. strength_score 要客观，不要虚高，没有强力证据不超过 7
4. 如果数据不足以支撑某维度，不要强行套用
5. dimension_name 要精炼有力，2-5个中文字即可"""


async def run_agent(
    agent_id: int,
    evidence_package: dict,
    client: AsyncOpenAI,
    model: str,
    temperature: float = 0.75,
) -> AgentFinding:
    """
    Run one analysis agent and return its structured finding.
    Retries up to 2 times on JSON parse or validation failure.
    """
    lens_name, lens_instruction = LENSES[agent_id % len(LENSES)]
    evidence_str = _prepare_evidence(evidence_package)

    messages = [
        {"role": "system", "content": _build_system_prompt(lens_name, lens_instruction)},
        {
            "role": "user",
            "content": f"以下是视频分析数据，请找出爆款核心维度并输出JSON：\n\n{evidence_str}",
        },
    ]

    last_error: Exception | None = None
    for attempt in range(3):
        try:
            response = await client.chat.completions.create(
                model=model,
                messages=messages,
                response_format={"type": "json_object"},
                temperature=temperature,
                max_tokens=4000,
            )
            raw = response.choices[0].message.content
            try:
                data = _parse_json_response(raw)
            except (json.JSONDecodeError, ValueError) as parse_err:
                logger.debug("Agent %d raw response (first 500): %s", agent_id, raw[:500])
                raise parse_err

            primary = ViralDimension(
                dimension_name=data["primary_dimension"]["dimension_name"],
                viral_mechanism=data["primary_dimension"]["viral_mechanism"],
                strength_score=float(data["primary_dimension"]["strength_score"]),
                confidence=float(data["primary_dimension"]["confidence"]),
                evidence=[EvidenceItem(**e) for e in data["primary_dimension"]["evidence"]],
            )

            secondary = None
            if data.get("secondary_dimension"):
                sd = data["secondary_dimension"]
                secondary = ViralDimension(
                    dimension_name=sd["dimension_name"],
                    viral_mechanism=sd["viral_mechanism"],
                    strength_score=float(sd["strength_score"]),
                    confidence=float(sd["confidence"]),
                    evidence=[EvidenceItem(**e) for e in sd["evidence"]],
                )

            finding = AgentFinding(
                agent_id=agent_id,
                lens_name=lens_name,
                primary_dimension=primary,
                secondary_dimension=secondary,
            )
            logger.info(
                "Agent %d [%s] → '%s' strength=%.1f conf=%.2f",
                agent_id,
                lens_name,
                primary.dimension_name,
                primary.strength_score,
                primary.confidence,
            )
            return finding

        except Exception as exc:
            last_error = exc
            if attempt < 2:
                logger.warning("Agent %d attempt %d failed (%s) — retrying", agent_id, attempt + 1, exc)
                await asyncio.sleep(1.5 * (attempt + 1))

    raise RuntimeError(f"Agent {agent_id} failed after 3 attempts: {last_error}") from last_error
