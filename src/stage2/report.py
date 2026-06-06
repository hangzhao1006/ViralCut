"""Generate a human-readable analysis report from video_structure.json.

Usage:
    python -m src.stage2.report video_structure.json
    python -m src.stage2.report video_structure.json --out report.md
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def generate_report(data: dict) -> str:
    """Convert video_structure.json to a human-readable markdown report."""
    lines: list[str] = []

    # ── Header ──
    video_id = data.get("video_id", "unknown")
    duration = data.get("duration", 0)
    ev = data.get("evaluation", {})
    meta = data.get("analysis_metadata", {})

    lines.append(f"# 视频结构分析报告")
    lines.append(f"")
    lines.append(f"视频ID: `{video_id}`  |  时长: {duration:.1f}秒 ({duration/60:.1f}分钟)  |  评分: {ev.get('score', 'N/A')} ({ev.get('status', 'N/A')})")
    lines.append(f"")

    # ── 一句话总结 ──
    script = data.get("script_structure", {})
    transfer = data.get("transfer_blueprint", {}).get("transfer_blueprint", {})
    value = data.get("value_strategy", {}).get("value_strategy", {})
    rhythm = data.get("rhythm_structure", {})
    energy = data.get("energy_curve", {})
    packaging = data.get("packaging_structure", {}).get("packaging_structure", {})

    pattern = script.get("structure_pattern", "")
    video_type = transfer.get("source_video_type", value.get("video_category", "unknown"))
    value_type = value.get("value_type", "")
    primary_value = value.get("primary_value", "")

    lines.append(f"## 一句话总结")
    lines.append(f"")
    lines.append(f"这是一个 **{video_type}** 类型的视频，核心价值是「{primary_value}」。")
    lines.append(f"")
    lines.append(f"结构模式: `{pattern}`")
    lines.append(f"")

    # ── 脚本结构 ──
    segments = script.get("segments", [])
    lines.append(f"## 脚本结构（{len(segments)} 段）")
    lines.append(f"")

    for seg in segments:
        sid = seg.get("segment_id", "")
        func = seg.get("function", "")
        start = seg.get("start_time", 0)
        end = seg.get("end_time", 0)
        dur = end - start
        core = seg.get("core_text", "")
        conf = seg.get("confidence", 0)
        reason = seg.get("reason", "")

        emoji = {
            "hook": "🎯", "introduction": "📖", "instruction": "📝",
            "demonstration": "🎬", "comparison": "⚖️", "transition": "🔄",
            "climax": "🔥", "resolution": "✅", "cta": "📢",
        }.get(func, "▪️")

        lines.append(f"{emoji} **{sid}** `{func}` ({start:.1f}-{end:.1f}s, {dur:.1f}秒)")
        lines.append(f"   {core}")
        if reason:
            lines.append(f"   → {reason}")
        lines.append(f"")

    # ── 节奏分析 ──
    lines.append(f"## 节奏分析")
    lines.append(f"")

    overall = rhythm.get("overall_rhythm", {})
    lines.append(f"整体节奏: **{overall.get('pace', 'N/A')}**  |  BPM: {overall.get('bpm', 'N/A')}  |  卡点同步: {overall.get('beat_sync_score', 'N/A')}")
    lines.append(f"")
    lines.append(f"节奏模式: `{rhythm.get('rhythm_pattern', 'N/A')}`")
    lines.append(f"")

    # Rhythm per segment - simplified
    seg_rhythms = rhythm.get("segment_rhythm", [])
    if seg_rhythms:
        lines.append(f"| 段落 | 节奏 | 镜头密度 | 卡点对齐 | 节奏驱动 |")
        lines.append(f"|------|------|---------|---------|---------|")
        for sr in seg_rhythms:
            sid = sr.get("segment_id", "")
            pace = sr.get("pace", "?")
            sps = sr.get("shots_per_second", 0)
            cba = sr.get("cut_beat_alignment", 0)
            driver = sr.get("rhythm_driver", "N/A")
            lines.append(f"| {sid} | {pace} | {sps:.2f}/s | {cba:.2f} | {driver} |")
        lines.append(f"")

    # Climax
    climax = rhythm.get("climax_analysis", {})
    if climax:
        confirmed = "✅ 已确认" if climax.get("confirmed") else "⚠️ 未确认"
        crange = climax.get("confirmed_range", [])
        lines.append(f"高潮位置: {confirmed}  范围: {crange}")
        if climax.get("reason"):
            lines.append(f"原因: {climax['reason']}")
        lines.append(f"")

    # ── 包装分析 ──
    lines.append(f"## 包装分析")
    lines.append(f"")
    lines.append(f"字幕密度: {packaging.get('subtitle_density', 'N/A')}  |  字幕样式: {packaging.get('subtitle_style', 'N/A')}")
    lines.append(f"标题卡: {'有' if packaging.get('title_card_usage') else '无'}  |  主要布局: {packaging.get('dominant_text_layout', 'N/A')}")
    lines.append(f"")

    uncertain = packaging.get("uncertain_elements", []) or data.get("packaging_structure", {}).get("uncertain_elements", [])
    if uncertain:
        lines.append(f"不确定的元素: {', '.join(uncertain)}")
        lines.append(f"")

    # ── 价值分析 ──
    lines.append(f"## 价值分析")
    lines.append(f"")
    lines.append(f"价值类型: **{value_type}**")
    lines.append(f"核心价值: {primary_value}")
    lines.append(f"目标受众: {value.get('target_audience', 'N/A')}")
    lines.append(f"转化目标: {value.get('conversion_goal', 'N/A')}")
    lines.append(f"")

    # CTA
    cta_creator = value.get("creator_cta")
    cta_platform = value.get("platform_cta")
    if cta_creator:
        lines.append(f"创作者CTA: {cta_creator}")
    if cta_platform:
        lines.append(f"平台CTA: {cta_platform}")
    if cta_creator or cta_platform:
        lines.append(f"")

    # ── 能量曲线 ──
    lines.append(f"## 能量曲线")
    lines.append(f"")
    lines.append(f"能量模式: `{energy.get('energy_pattern', 'N/A')}`")
    lines.append(f"")

    energy_curve = energy.get("energy_curve", [])
    if energy_curve:
        # Simple visual bar
        level_map = {"low": "▓░░░░", "low-medium": "▓▓░░░", "medium": "▓▓▓░░",
                     "medium-high": "▓▓▓▓░", "high": "▓▓▓▓▓", "peak": "█████"}
        for e in energy_curve:
            sid = e.get("segment_id", "")
            level = e.get("energy_level", "medium")
            bar = level_map.get(level, "▓▓▓░░")
            role = e.get("role", "")
            lines.append(f"`{bar}` {sid} ({level}) — {role}")
        lines.append(f"")

    # ── 迁移蓝图 ──
    lines.append(f"## 迁移蓝图（Transfer Blueprint）")
    lines.append(f"")

    slots = transfer.get("structure_template", [])
    if slots:
        lines.append(f"### 结构模板（{len(slots)} 个 slot）")
        lines.append(f"")
        for slot in slots:
            sid = slot.get("slot_id", "")
            stype = slot.get("slot_type", "")
            dur = slot.get("duration_seconds", 0)
            ratio = slot.get("duration_ratio", 0)
            purpose = slot.get("purpose", "")
            template = slot.get("template", "")
            priority = slot.get("priority", "")

            lines.append(f"**{sid}: {stype}** ({dur:.1f}秒, {ratio*100:.0f}%) — 优先级: {priority}")
            lines.append(f"  目的: {purpose}")
            if template:
                lines.append(f"  模板: `{template}`")

            ir = slot.get("input_requirements", {})
            if ir:
                assets = ir.get("needed_assets", [])
                if assets:
                    lines.append(f"  需要素材: {', '.join(assets)}")

            replaceable = slot.get("replaceable_elements", [])
            if replaceable:
                lines.append(f"  可替换: {', '.join(replaceable)}")
            lines.append(f"")

    # Editing rules
    rules = transfer.get("editing_rules", [])
    if rules:
        lines.append(f"### 剪辑规则（{len(rules)} 条）")
        lines.append(f"")
        for rule in rules:
            name = rule.get("rule_name", rule.get("rule", ""))
            desc = rule.get("description", "")
            pri = rule.get("priority", "")
            lines.append(f"- **{name}** ({pri}): {desc}")
        lines.append(f"")

    # Adaptation guidance
    adapt = transfer.get("adaptation_guidance", {})
    if adapt:
        lines.append(f"### 迁移指导")
        lines.append(f"")
        for k, v in adapt.items():
            lines.append(f"- **{k}**: {v}")
        lines.append(f"")

    # ── 分析元数据 ──
    lines.append(f"---")
    lines.append(f"")
    lines.append(f"**分析统计**: {meta.get('total_llm_calls', 'N/A')} 次LLM调用, {meta.get('total_tool_calls', 'N/A')} 次工具调用, 耗时 {meta.get('total_duration_seconds', 'N/A')}秒")
    vision = meta.get("vision_budget", {})
    if vision:
        lines.append(f"**视觉预算**: 已用 {vision.get('total_used', 0)}/{vision.get('max_total', 16)}")

    # Evaluator warnings
    checks = ev.get("checks", [])
    warnings = []
    for c in checks:
        for w in c.get("warnings", []):
            warnings.append(w)
    if warnings:
        lines.append(f"")
        lines.append(f"**⚠️ 警告**:")
        for w in warnings:
            lines.append(f"- {w}")

    return "\n".join(lines)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Generate human-readable report from video_structure.json")
    parser.add_argument("input", help="Path to video_structure.json")
    parser.add_argument("--out", help="Output markdown file path")
    args = parser.parse_args()

    with open(args.input, "r", encoding="utf-8") as f:
        data = json.load(f)

    report = generate_report(data)

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"Report saved to {args.out}")
    else:
        print(report)