"""Rule-based evaluator for ViralCut Stage 2 outputs.

This evaluator is intentionally code-first. It does not claim to be a trained
reward model; it performs deterministic checks that catch broken schemas,
missing evidence, timeline gaps, and weak transfer blueprints.
"""

from __future__ import annotations

from typing import Any

from src.stage2.input_builder import TimelineIndex
from src.stage2.framework.blackboard import Blackboard


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _walk_values(obj: Any) -> list[Any]:
    values: list[Any] = []
    if isinstance(obj, dict):
        for v in obj.values():
            values.append(v)
            values.extend(_walk_values(v))
    elif isinstance(obj, list):
        for item in obj:
            values.append(item)
            values.extend(_walk_values(item))
    return values


def _collect_string_values(obj: Any) -> list[str]:
    strings: list[str] = []
    for v in _walk_values(obj):
        if isinstance(v, str):
            strings.append(v)
        elif isinstance(v, (int, float)):
            strings.append(str(v))
    return strings


class Stage2Evaluator:
    """Evaluate final Stage 2 blackboard/pipeline output with rule checks."""

    def __init__(self, timeline: TimelineIndex, blackboard: Blackboard):
        self.timeline = timeline
        self.blackboard = blackboard

    def evaluate(self, video_structure: dict[str, Any] | None = None) -> dict[str, Any]:
        script = self.blackboard.read("script", {}) or {}
        rhythm = self.blackboard.read("rhythm", {}) or {}
        packaging = self.blackboard.read("packaging", {}) or {}
        value = self.blackboard.read("value", {}) or {}
        energy = self.blackboard.read("energy", {}) or {}
        transfer = self.blackboard.read("transfer", {}) or {}

        checks: list[dict[str, Any]] = []
        checks.append(self._check_script_segments(script))
        checks.append(self._check_segment_evidence(script))
        checks.append(self._check_required_outputs(rhythm, packaging, value, energy, transfer))
        checks.append(self._check_transfer_blueprint(transfer))
        checks.append(self._check_important_ocr_coverage({
            "script": script,
            "rhythm": rhythm,
            "packaging": packaging,
            "value": value,
            "energy": energy,
            "transfer": transfer,
        }))
        checks.append(self._check_rhythm_consistency(rhythm))

        hard_failures = [c for c in checks if c.get("hard_fail")]
        weighted_score = sum(c.get("score", 0.0) * c.get("weight", 1.0) for c in checks)
        total_weight = sum(c.get("weight", 1.0) for c in checks) or 1.0
        score = round(weighted_score / total_weight, 4)

        if hard_failures:
            status = "fail"
        elif score >= 0.75:
            status = "pass"
        elif score >= 0.60:
            status = "warning"
        else:
            status = "fail"

        result = {
            "status": status,
            "score": score,
            "thresholds": {"pass": 0.75, "warning": 0.60},
            "checks": checks,
            "hard_failures": [c["name"] for c in hard_failures],
            "recommendations": self._recommendations(checks),
        }
        self.blackboard.write("evaluator", result, key="evaluator", summary=f"evaluation {status} score={score}")
        return result

    def _check_script_segments(self, script: dict[str, Any]) -> dict[str, Any]:
        segments = script.get("segments") or []
        duration = self.timeline.duration
        if not segments:
            return {"name": "script_segments", "score": 0.0, "weight": 1.2, "hard_fail": True, "message": "script.segments is empty"}

        sorted_segments = sorted(segments, key=lambda s: _as_float(s.get("start_time", s.get("start", 0))))
        gaps: list[list[float]] = []
        overlaps: list[list[float]] = []
        cursor = 0.0
        for seg in sorted_segments:
            start = _as_float(seg.get("start_time", seg.get("start", 0)))
            end = _as_float(seg.get("end_time", seg.get("end", start)))
            if start > cursor + 0.75:
                gaps.append([round(cursor, 3), round(start, 3)])
            if start < cursor - 0.75:
                overlaps.append([round(start, 3), round(cursor, 3)])
            cursor = max(cursor, end)
        if duration and cursor < duration - 0.75:
            gaps.append([round(cursor, 3), round(duration, 3)])

        coverage = 1.0
        if duration > 0:
            gap_len = sum(max(0.0, b - a) for a, b in gaps)
            coverage = max(0.0, 1.0 - gap_len / duration)
        score = coverage
        hard_fail = coverage < 0.90 or bool(overlaps)
        return {
            "name": "script_time_coverage",
            "score": round(score, 4),
            "weight": 1.2,
            "hard_fail": hard_fail,
            "message": f"segments={len(segments)}, coverage={coverage:.2%}",
            "gaps": gaps,
            "overlaps": overlaps,
        }

    def _check_segment_evidence(self, script: dict[str, Any]) -> dict[str, Any]:
        segments = script.get("segments") or []
        if not segments:
            return {"name": "segment_evidence", "score": 0.0, "weight": 1.0, "hard_fail": True, "message": "no segments"}
        missing = []
        for seg in segments:
            evidence = seg.get("evidence") or seg.get("evidence_refs") or []
            if not evidence:
                missing.append(seg.get("segment_id"))
        score = 1.0 - len(missing) / max(len(segments), 1)
        return {
            "name": "segment_evidence",
            "score": round(score, 4),
            "weight": 1.0,
            "hard_fail": score < 0.75,
            "message": f"{len(segments) - len(missing)}/{len(segments)} segments have evidence",
            "missing_segments": missing,
        }

    def _check_required_outputs(self, rhythm: dict[str, Any], packaging: dict[str, Any], value: dict[str, Any], energy: dict[str, Any], transfer: dict[str, Any]) -> dict[str, Any]:
        required = {
            "rhythm": rhythm,
            "packaging": packaging,
            "value": value,
            "energy": energy,
            "transfer": transfer,
        }
        missing = [name for name, obj in required.items() if not isinstance(obj, dict) or not obj]
        score = 1.0 - len(missing) / len(required)
        return {
            "name": "required_agent_outputs",
            "score": round(score, 4),
            "weight": 1.0,
            "hard_fail": bool(missing),
            "message": f"missing={missing}",
            "missing": missing,
        }

    def _check_transfer_blueprint(self, transfer: dict[str, Any]) -> dict[str, Any]:
        tb = transfer.get("transfer_blueprint") if isinstance(transfer, dict) else None
        if not isinstance(tb, dict):
            return {"name": "transfer_blueprint", "score": 0.0, "weight": 1.4, "hard_fail": True, "message": "transfer_blueprint missing"}
        slots = tb.get("structure_template") or []
        rules = tb.get("editing_rules") or []
        missing_machine_fields = []
        for slot in slots:
            if not slot.get("slot_type") or not slot.get("duration_seconds") or not slot.get("input_requirements"):
                missing_machine_fields.append(slot.get("slot_id", "unknown"))
        score = 1.0
        if not slots:
            score -= 0.5
        if not rules:
            score -= 0.25
        if missing_machine_fields:
            score -= min(0.25, 0.05 * len(missing_machine_fields))
        score = max(0.0, score)
        return {
            "name": "transfer_blueprint",
            "score": round(score, 4),
            "weight": 1.4,
            "hard_fail": score < 0.5,
            "message": f"slots={len(slots)}, rules={len(rules)}",
            "slots_missing_machine_fields": missing_machine_fields,
        }

    def _important_ocr_items(self) -> list[dict[str, Any]]:
        texts = self.timeline.get_all_display_texts()
        important: list[dict[str, Any]] = []
        keywords = ["学会", "教程", "注意", "重音", "音效", "卡点", "关注", "收藏", "评论", "购买", "不要", "技巧", "镜头", "节奏"]
        seen = set()
        for item in texts:
            text = str(item.get("display_text") or "").strip()
            if not text or text in seen:
                continue
            t = _as_float(item.get("timestamp"))
            is_important = t <= 5.0 or any(k in text for k in keywords)
            if is_important:
                important.append(item)
                seen.add(text)
        return important[:30]

    def _check_important_ocr_coverage(self, outputs: dict[str, Any]) -> dict[str, Any]:
        important = self._important_ocr_items()
        if not important:
            return {"name": "important_ocr_coverage", "score": 1.0, "weight": 0.8, "hard_fail": False, "message": "no important OCR detected"}
        haystack = "\n".join(_collect_string_values(outputs))
        covered = []
        missing = []
        for item in important:
            text = str(item.get("display_text") or "").strip()
            frame_id = str(item.get("frame_id") or "")
            # Accept either frame id reference or a short text substring reference.
            text_hit = len(text) >= 4 and text[:4] in haystack
            frame_hit = frame_id and frame_id in haystack
            if text_hit or frame_hit:
                covered.append(frame_id or text[:12])
            else:
                missing.append({"frame_id": frame_id, "text": text[:40]})
        score = len(covered) / max(len(important), 1)
        return {
            "name": "important_ocr_coverage",
            "score": round(score, 4),
            "weight": 0.8,
            "hard_fail": False,
            "message": f"{len(covered)}/{len(important)} important OCR items referenced",
            "missing_preview": missing[:8],
        }

    def _check_rhythm_consistency(self, rhythm: dict[str, Any]) -> dict[str, Any]:
        """Warn when rhythm conclusions don't match actual video metrics."""
        warnings = []
        scene_count = len(self.timeline.scenes)
        beat_sync = self.timeline.beats_info.get("beat_sync_score", 0)
        pattern = str(rhythm.get("rhythm_pattern", "")).lower()
        cutting = rhythm.get("cutting_strategy", {})
        primary_cut = str(cutting.get("primary", "")).lower() if isinstance(cutting, dict) else ""

        # Check 1: low scene_count but claims acceleration/fast
        if scene_count <= 3 and any(kw in pattern for kw in ["acceleration", "fast", "spike"]):
            warnings.append(
                f"scene_count={scene_count} but rhythm_pattern='{rhythm.get('rhythm_pattern')}'. "
                "Rhythm conclusion may be driven by short segment duration rather than real cuts."
            )

        # Check 2: beat_sync near zero but claims cut_on_beat
        if beat_sync < 0.1 and "beat" in primary_cut:
            warnings.append(
                f"beat_sync_score={beat_sync} but cutting_strategy='{primary_cut}'. "
                "Beat alignment is too low to claim cut-on-beat as primary strategy."
            )

        # Check 3: short segment marked as fast
        seg_rhythms = rhythm.get("segment_rhythm", [])
        for sr in seg_rhythms:
            tr = sr.get("time_range", [0, 0])
            dur = tr[1] - tr[0] if len(tr) == 2 else 0
            pace = str(sr.get("pace", "")).lower()
            if dur < 1.5 and pace in ("fast", "very_fast"):
                warnings.append(
                    f"{sr.get('segment_id')}: duration={dur:.1f}s marked as '{pace}'. "
                    "Very short segments inflate shot_density; may not represent real fast cutting."
                )

        score = 1.0 if not warnings else max(0.5, 1.0 - 0.15 * len(warnings))
        return {
            "name": "rhythm_consistency",
            "score": round(score, 4),
            "weight": 0.6,
            "hard_fail": False,
            "message": f"{len(warnings)} warning(s)" if warnings else "no issues",
            "warnings": warnings,
        }

    def _recommendations(self, checks: list[dict[str, Any]]) -> list[str]:
        recs: list[str] = []
        for c in checks:
            if c.get("score", 1.0) >= 0.75 and not c.get("hard_fail"):
                continue
            name = c.get("name")
            if name == "script_time_coverage":
                recs.append("Revise Script Agent: ensure segments cover the full duration without large gaps or overlaps.")
            elif name == "segment_evidence":
                recs.append("Revise Script Agent: every segment should cite at least one frame/text/metric evidence item.")
            elif name == "required_agent_outputs":
                recs.append("Run all required agents before final export: rhythm, packaging, value, energy, transfer.")
            elif name == "transfer_blueprint":
                recs.append("Revise Transfer Agent: add machine-executable slots with slot_type, duration_seconds, and input_requirements.")
            elif name == "important_ocr_coverage":
                recs.append("Improve prompts: important OCR display_texts should be referenced in script/value/packaging evidence.")
            elif name == "rhythm_consistency":
                recs.append("Rhythm Agent may have over-interpreted short segments as fast cutting. Check scene_count and segment durations.")
        return recs
