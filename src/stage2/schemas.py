"""
schemas.py — Pydantic models for Stage 2 viral dimension analysis.

Every agent returns an AgentFinding. The synthesis agent returns a SynthesisResult.
Structured fields (dimension_name, viral_mechanism, strength_score) are what make
findings comparable and mergeable across agents.
"""
from __future__ import annotations
from typing import Literal, Optional
from pydantic import BaseModel, Field


class EvidenceItem(BaseModel):
    """A single piece of evidence grounding an agent's claim in the raw video data."""
    source: Literal["transcript", "scene", "ocr", "audio", "metadata", "social"]
    reference: str = Field(
        description="Specific pointer: timestamp '00:05-00:12', scene ID 'scene_003', field name 'basic_analysis.shot_density'"
    )
    quote: str = Field(
        description="Exact text or value copied from the evidence package — no paraphrasing"
    )
    reasoning: str = Field(
        description="One sentence: why this evidence supports the viral dimension"
    )


class ViralDimension(BaseModel):
    """
    One viral dimension identified by an agent.

    dimension_name + viral_mechanism are the two fields used by the synthesis agent
    for semantic clustering. strength_score provides a numeric weight.
    """
    dimension_name: str = Field(
        description="2-5 word label in Chinese, e.g. '身份认同镜像', '情绪张力释放', '知识冲击'"
    )
    viral_mechanism: str = Field(
        description="1-2 sentences: the psychological/social mechanism that makes this dimension drive virality"
    )
    strength_score: float = Field(
        ge=0, le=10,
        description="How strongly this dimension is present in this specific video (0=absent, 10=defining feature)"
    )
    confidence: float = Field(
        ge=0, le=1,
        description="Agent's confidence in this analysis given the available data"
    )
    evidence: list[EvidenceItem] = Field(
        min_length=1, max_length=5,
        description="1-5 pieces of specific evidence from the video data"
    )


class AgentFinding(BaseModel):
    """Output of a single analysis agent."""
    agent_id: int
    lens_name: str
    primary_dimension: ViralDimension
    secondary_dimension: Optional[ViralDimension] = Field(
        default=None,
        description="A second notable dimension, if clearly present. Null if nothing else stands out."
    )


class ClusteredDimension(BaseModel):
    """A group of similar findings from multiple agents, merged by the synthesis agent."""
    dimension_name: str = Field(description="Canonical label for this cluster")
    viral_mechanism: str = Field(description="Synthesized explanation of the mechanism")
    agent_agreement_count: int = Field(description="How many agents independently identified this dimension")
    avg_strength_score: float = Field(description="Average strength score across contributing agents")
    supporting_agent_ids: list[int] = Field(description="IDs of agents that found this dimension")
    representative_evidence: list[EvidenceItem] = Field(
        description="1-3 best evidence items from across the contributing agents"
    )


class SynthesisResult(BaseModel):
    """Final output of the synthesis agent."""
    ranked_dimensions: list[ClusteredDimension] = Field(
        description="Dimensions ranked by (agreement_count × avg_strength_score), descending"
    )
    top_viral_reason: str = Field(
        description="One paragraph: the #1 reason this video went viral and the mechanism behind it"
    )
    analysis_note: str = Field(
        description="Notable divergences between agents, or dimensions that appeared only once but are uniquely compelling"
    )
