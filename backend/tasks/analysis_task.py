"""Background task: run Stage 1 + Stage 2 on an uploaded video."""

from __future__ import annotations

import json
import os
import shutil
import traceback

from backend.store.task_store import task_store

STATIC_DIR = "backend/static"

AGENT_ORDER = ["script", "rhythm", "packaging", "value", "energy", "transfer"]


def run_analysis(task_id: str, video_path: str) -> None:
    """Run the full Stage 1 + Stage 2 pipeline. Updates task_store with progress."""
    try:
        # ── Stage 1 ──
        task_store.update(task_id, stage="stage1", message="提取视频证据中（OCR/ASR/节拍）...", completed_agents=[])
        from src.stage1.file_pipeline.pipeline import run as run_stage1

        package = run_stage1(video_path)
        # EvidencePackage 是对象不是dict，用属性访问
        video_id = getattr(package, "video_id", None)
        if video_id is None and isinstance(package, dict):
            video_id = package.get("video_id")
            
        task_store.update(task_id, video_id=video_id)

        evidence_path = f"output/{video_id}/evidence_package.json"

        # ── Stage 2 ──
        task_store.update(task_id, stage="stage2", message="多Agent结构分析中...")

        completed: list[str] = []

        def progress(agent: str, msg: str) -> None:
            # When an agent starts, mark it as current
            task_store.update(task_id, current_step=agent, message=msg)

        def on_agent_done(agent: str) -> None:
            if agent not in completed:
                completed.append(agent)
            task_store.update(task_id, completed_agents=list(completed))

        from src.stage2.pipeline import run_full_pipeline

        # Try with progress callbacks; fall back if not supported
        try:
            result = run_full_pipeline(
                evidence_path,
                progress_callback=progress,
                on_agent_done=on_agent_done,
            )
        except TypeError:
            try:
                result = run_full_pipeline(evidence_path, progress_callback=progress)
            except TypeError:
                result = run_full_pipeline(evidence_path)
            task_store.update(task_id, completed_agents=AGENT_ORDER)

        # ── Save outputs to static dir ──
        dest = f"{STATIC_DIR}/{video_id}"
        os.makedirs(f"{dest}/frames", exist_ok=True)

        ext = os.path.splitext(video_path)[1] or ".mp4"
        shutil.copy(video_path, f"{dest}/source{ext}")

        frames_src = f"output/{video_id}/frames"
        if os.path.isdir(frames_src):
            for fn in os.listdir(frames_src):
                shutil.copy(f"{frames_src}/{fn}", f"{dest}/frames/{fn}")

        if os.path.exists(evidence_path):
            shutil.copy(evidence_path, f"{dest}/evidence_package.json")
        with open(f"{dest}/video_structure.json", "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2, default=str)

        task_store.update(
            task_id, status="done", video_ext=ext,
            completed_agents=AGENT_ORDER, message="分析完成",
        )
    except Exception as exc:  # noqa: BLE001
        task_store.update(
            task_id, status="failed", message=str(exc),
            traceback=traceback.format_exc(),
        )
