"""Background tasks: Stage 1 (file OR link) + Stage 2 (main OR leo variant)."""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import sys
import traceback
from collections import deque

from backend.store.task_store import task_store

STATIC_DIR = "backend/static"
AGENT_ORDER = ["script", "rhythm", "packaging", "value", "energy", "transfer"]

# Logger names to ignore (server/library noise) when capturing pipeline progress
_NOISY_LOGGERS = ("uvicorn", "watchfiles", "httpx", "httpcore", "asyncio", "urllib3", "openai", "fastapi", "starlette")

# Stage 1 step detection (canonical order + keywords + completion markers)
_STAGE1_ORDER = ["scene", "keyframe", "ocr", "asr", "beats", "basic"]
_STAGE1_KW = {
    "scene": re.compile(r"scene|pyscenedetect|镜头|shot|分镜", re.I),
    "keyframe": re.compile(r"keyframe|关键帧|extract.?frame|代表帧", re.I),
    "ocr": re.compile(r"\bocr\b|rapidocr|easyocr|画面文字|文字识别", re.I),
    "asr": re.compile(r"whisper|\basr\b|transcri|语音|字幕", re.I),
    "beats": re.compile(r"\bbeat|\bbpm\b|librosa|节拍|tempo|卡点|audio analysis", re.I),
    "basic": re.compile(r"basic_analysis|基础分析|镜头统计", re.I),
}
_DONE_KW = re.compile(r"complete|finished|done|完成|saved|detected|extracted|分析完成", re.I)


class TaskLogHandler(logging.Handler):
    """Capture pipeline log lines into task_store so the frontend can show live progress.
    Also accumulates per-step Stage 1 progress MONOTONICALLY (never regresses → no flicker)."""

    def __init__(self, task_id: str):
        super().__init__(level=logging.INFO)
        self.task_id = task_id
        self.lines: deque[str] = deque(maxlen=10)
        self.steps: dict[str, dict] = {k: {"state": "waiting", "pct": None} for k in _STAGE1_ORDER}

    def _update_steps(self, line: str) -> None:
        # ocr/asr/beats run in PARALLEL in the link pipeline — they must NOT mark each other done.
        # Only scene & keyframe are strictly sequential-before the parallel group.
        early = {"scene", "keyframe"}
        for key in _STAGE1_ORDER:
            if not _STAGE1_KW[key].search(line):
                continue
            # When any later (non-early) step is seen, the early sequential steps are certainly done
            if key not in early:
                for k2 in ("scene", "keyframe"):
                    if self.steps[k2]["state"] != "done":
                        self.steps[k2] = {"state": "done", "pct": 100}
            cur = self.steps[key]
            if cur["state"] == "done":
                continue  # never regress
            m = re.search(r"(\d+)\s*/\s*(\d+)", line)
            pct = round(int(m.group(1)) / max(1, int(m.group(2))) * 100) if m else cur["pct"]
            if pct is not None and cur["pct"] is not None:
                pct = max(pct, cur["pct"])  # monotonic pct
            # A step turns green ONLY on its own completion log (or 100%), not because a sibling finished
            if _DONE_KW.search(line) or pct == 100:
                self.steps[key] = {"state": "done", "pct": 100}
            else:
                self.steps[key] = {"state": "active", "pct": pct}

    def mark_all_done(self) -> None:
        for k in _STAGE1_ORDER:
            self.steps[k] = {"state": "done", "pct": 100}
        task_store.update(self.task_id, stage1_steps=dict(self.steps))

    def emit(self, record: logging.LogRecord) -> None:
        try:
            if any(record.name.startswith(n) for n in _NOISY_LOGGERS):
                return
            msg = record.getMessage()
            if not msg.strip():
                return
            self.lines.append(msg)
            self._update_steps(msg)
            task_store.update(self.task_id, log_tail=list(self.lines), stage1_steps=dict(self.steps))
        except Exception:
            pass


def _attach_log_capture(task_id: str) -> TaskLogHandler:
    handler = TaskLogHandler(task_id)
    logging.getLogger().addHandler(handler)  # root — catches stage1/stage2/link loggers
    logging.getLogger().setLevel(logging.INFO)
    return handler


def _detach_log_capture(handler: TaskLogHandler) -> None:
    logging.getLogger().removeHandler(handler)


def _copy_outputs(video_id: str, source_video_path: str | None) -> str:
    """Copy frames + source video to static dir. Returns video ext.
    Also clears any STALE Stage 2 results so a fresh Stage 1 run doesn't surface an old analysis."""
    dest = f"{STATIC_DIR}/{video_id}"
    os.makedirs(f"{dest}/frames", exist_ok=True)

    # Remove stale Stage 2 outputs from a previous run of the same video_id
    for stale in ("video_structure.json", "synthesis_result.json"):
        p = f"{dest}/{stale}"
        if os.path.exists(p):
            os.remove(p)

    ext = ".mp4"
    if source_video_path and os.path.exists(source_video_path):
        ext = os.path.splitext(source_video_path)[1] or ".mp4"
        shutil.copy(source_video_path, f"{dest}/source{ext}")

    frames_src = f"output/{video_id}/frames"
    if os.path.isdir(frames_src):
        for fn in os.listdir(frames_src):
            shutil.copy(f"{frames_src}/{fn}", f"{dest}/frames/{fn}")

    evidence_path = f"output/{video_id}/evidence_package.json"
    if os.path.exists(evidence_path):
        shutil.copy(evidence_path, f"{dest}/evidence_package.json")
    return ext


def _run_stage2_main(task_id: str, video_id: str, source_video_path: str | None) -> None:
    """Run the main multi-agent Stage 2 (structured, supports migration)."""
    evidence_path = f"output/{video_id}/evidence_package.json"
    task_store.update(task_id, video_id=video_id, stage="stage2", message="多Agent结构分析中...", stage2_variant="main")

    completed: list[str] = []

    def progress(agent: str, msg: str) -> None:
        task_store.update(task_id, current_step=agent, message=msg)

    def on_agent_done(agent: str) -> None:
        if agent not in completed:
            completed.append(agent)
        task_store.update(task_id, completed_agents=list(completed))

    from src.stage2.pipeline import run_full_pipeline
    try:
        result = run_full_pipeline(evidence_path, progress_callback=progress, on_agent_done=on_agent_done)
    except TypeError:
        try:
            result = run_full_pipeline(evidence_path, progress_callback=progress)
        except TypeError:
            result = run_full_pipeline(evidence_path)
        task_store.update(task_id, completed_agents=AGENT_ORDER)

    ext = _copy_outputs(video_id, source_video_path)
    dest = f"{STATIC_DIR}/{video_id}"
    with open(f"{dest}/video_structure.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2, default=str)

    task_store.update(task_id, status="done", video_ext=ext, completed_agents=AGENT_ORDER, message="分析完成")


def _run_stage2_leo(task_id: str, video_id: str, source_video_path: str | None) -> None:
    """Run the leo_variant Stage 2 (parallel lens agents → viral dimension ranking)."""
    import asyncio

    evidence_path = f"output/{video_id}/evidence_package.json"
    task_store.update(task_id, video_id=video_id, stage="stage2", message="多视角爆款维度分析中...", stage2_variant="leo")

    with open(evidence_path, encoding="utf-8") as f:
        evidence = json.load(f)

    leo_dir = os.path.abspath("src/stage2/leo_variant")
    if leo_dir not in sys.path:
        sys.path.insert(0, leo_dir)
    from orchestrator import run_viral_analysis  # type: ignore

    model = os.getenv("LEO_MODEL", "gpt-4o")
    num_agents = int(os.getenv("LEO_NUM_AGENTS", "6"))
    leo_api_key = os.getenv("LEO_API_KEY") or os.getenv("OPENAI_API_KEY") or os.getenv("OPENROUTER_API_KEY")
    leo_base_url = os.getenv("LEO_BASE_URL", "https://api.openai.com/v1")

    if not leo_api_key:
        raise ValueError("未配置 leo 的 API key（设置 LEO_API_KEY / OPENAI_API_KEY）")

    # Preflight: one tiny call so the REAL error (auth/connection/model) surfaces clearly,
    # instead of the orchestrator's generic "All agents failed".
    try:
        from openai import OpenAI
        _c = OpenAI(api_key=leo_api_key, base_url=leo_base_url)
        _c.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=1,
        )
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            f"Leo LLM 连接测试失败（base_url={leo_base_url}, model={model}）：{exc}"
        ) from exc

    synthesis = asyncio.run(run_viral_analysis(
        evidence,
        model=model,
        num_agents=num_agents,
        api_key=leo_api_key,
        base_url=leo_base_url,
    ))

    # SynthesisResult is a pydantic model → dict
    if hasattr(synthesis, "model_dump"):
        synthesis_dict = synthesis.model_dump()
    elif hasattr(synthesis, "dict"):
        synthesis_dict = synthesis.dict()
    else:
        synthesis_dict = dict(synthesis)

    ext = _copy_outputs(video_id, source_video_path)
    dest = f"{STATIC_DIR}/{video_id}"
    with open(f"{dest}/synthesis_result.json", "w", encoding="utf-8") as f:
        json.dump(synthesis_dict, f, ensure_ascii=False, indent=2, default=str)

    task_store.update(task_id, status="done", video_ext=ext, message="分析完成")


def _run_stage2_both(task_id: str, video_id: str, source_video_path: str | None) -> None:
    """Run leo first (fast, parallel) then main (slower, sequential). Shows results as each phase completes."""
    import asyncio

    evidence_path = f"output/{video_id}/evidence_package.json"
    dest = f"{STATIC_DIR}/{video_id}"

    # Setup: copy frames/video/evidence to static dir, clear stale Stage 2 outputs
    ext = _copy_outputs(video_id, source_video_path)

    # ── Phase 1: Leo (parallel agents, fast) ─────────────────────────
    task_store.update(
        task_id,
        video_id=video_id, stage="stage2",
        message="爆款归因中（1/2）...",
        stage2_variant="both", current_phase="leo", completed_agents=[],
    )

    leo_dir = os.path.abspath("src/stage2/leo_variant")
    if leo_dir not in sys.path:
        sys.path.insert(0, leo_dir)
    from orchestrator import run_viral_analysis  # type: ignore

    model       = os.getenv("LEO_MODEL", "gpt-4o")
    num_agents  = int(os.getenv("LEO_NUM_AGENTS", "6"))
    leo_api_key = os.getenv("LEO_API_KEY") or os.getenv("OPENAI_API_KEY") or os.getenv("OPENROUTER_API_KEY")
    leo_base_url = os.getenv("LEO_BASE_URL", "https://api.openai.com/v1")

    if leo_api_key:
        # Preflight: surface auth/model errors early
        try:
            from openai import OpenAI
            _c = OpenAI(api_key=leo_api_key, base_url=leo_base_url)
            _c.chat.completions.create(model=model, messages=[{"role": "user", "content": "ping"}], max_tokens=1)
        except Exception as exc:
            task_store.update(task_id, message=f"爆款归因跳过（连接失败：{exc}），直接运行结构分析...")
        else:
            try:
                with open(evidence_path, encoding="utf-8") as f:
                    evidence = json.load(f)
                synthesis = asyncio.run(run_viral_analysis(
                    evidence, model=model, num_agents=num_agents,
                    api_key=leo_api_key, base_url=leo_base_url,
                ))
                synthesis_dict = synthesis.model_dump() if hasattr(synthesis, "model_dump") else dict(synthesis)
                with open(f"{dest}/synthesis_result.json", "w", encoding="utf-8") as f:
                    json.dump(synthesis_dict, f, ensure_ascii=False, indent=2, default=str)
            except Exception as exc:
                task_store.update(task_id, message=f"爆款归因运行失败（{exc}），跳过，继续结构分析...")
    else:
        task_store.update(task_id, message="爆款归因跳过（未配置LEO_API_KEY），直接运行结构分析...")

    # Signal: leo phase done — frontend can now fetch partial result (synthesis_result available)
    task_store.update(
        task_id,
        has_leo_result=True, current_phase="main",
        message="爆款归因完成，结构分析中（2/2）...",
        video_ext=ext, completed_agents=[],
    )

    # ── Phase 2: Main (sequential agents) ────────────────────────────
    completed: list[str] = []

    def _prog(agent: str, msg: str) -> None:
        task_store.update(task_id, current_step=agent, message=f"[结构] {msg}")

    def _done(agent: str) -> None:
        if agent not in completed:
            completed.append(agent)
        task_store.update(task_id, completed_agents=list(completed))

    from src.stage2.pipeline import run_full_pipeline
    try:
        result_main = run_full_pipeline(evidence_path, progress_callback=_prog, on_agent_done=_done)
    except TypeError:
        try:
            result_main = run_full_pipeline(evidence_path, progress_callback=_prog)
        except TypeError:
            result_main = run_full_pipeline(evidence_path)
        task_store.update(task_id, completed_agents=AGENT_ORDER)

    with open(f"{dest}/video_structure.json", "w", encoding="utf-8") as f:
        json.dump(result_main, f, ensure_ascii=False, indent=2, default=str)

    task_store.update(task_id, status="done", video_ext=ext, completed_agents=AGENT_ORDER, message="全部分析完成")


def _dispatch_stage2(task_id: str, video_id: str, source_video_path: str | None, variant: str) -> None:
    if variant == "leo":
        _run_stage2_leo(task_id, video_id, source_video_path)
    elif variant == "both":
        _run_stage2_both(task_id, video_id, source_video_path)
    else:
        _run_stage2_main(task_id, video_id, source_video_path)


def run_restage2(task_id: str, video_id: str, stage2_variant: str = "main") -> None:
    """Re-run ONLY Stage 2 on already-extracted evidence (reuse Stage 1)."""
    log_handler = _attach_log_capture(task_id)
    try:
        out_ev = f"output/{video_id}/evidence_package.json"
        static_ev = f"{STATIC_DIR}/{video_id}/evidence_package.json"
        if not os.path.exists(out_ev) and os.path.exists(static_ev):
            os.makedirs(f"output/{video_id}", exist_ok=True)
            shutil.copy(static_ev, out_ev)
        if not os.path.exists(out_ev):
            raise ValueError("找不到已提取的Stage1证据，无法只重跑Stage2，请重新完整分析")
        task_store.update(task_id, video_id=video_id, stage="stage2", message="复用Stage1，重新运行Stage2...")
        _dispatch_stage2(task_id, video_id, None, stage2_variant)
    except Exception as exc:  # noqa: BLE001
        task_store.update(task_id, status="failed", message=str(exc), traceback=traceback.format_exc())
    finally:
        _detach_log_capture(log_handler)


def run_analysis(task_id: str, video_path: str, stage2_variant: str = "main", pause_after_stage1: bool = True) -> None:
    """File upload: Stage 1 only. Stage 2 ALWAYS requires explicit user confirmation (via /analyze/restage2)."""
    log_handler = _attach_log_capture(task_id)
    try:
        task_store.update(task_id, stage="stage1", message="提取视频证据中（OCR/ASR/节拍）...", completed_agents=[])
        from src.stage1.file_pipeline.pipeline import run as run_stage1
        package = run_stage1(video_path)
        video_id = getattr(package, "video_id", None)
        if video_id is None and isinstance(package, dict):
            video_id = package.get("video_id")
        _copy_outputs(video_id, video_path)
        log_handler.mark_all_done()
        # Always stop after Stage 1 — user must confirm before Stage 2
        task_store.update(task_id, video_id=video_id, stage1_available=True, stage2_variant=stage2_variant,
                          status="stage1_done", stage="stage1_done",
                          message="Stage 1 完成，等待确认是否继续 Stage 2")
    except Exception as exc:  # noqa: BLE001
        task_store.update(task_id, status="failed", message=f"Stage 1 失败：{exc}", traceback=traceback.format_exc())
    finally:
        _detach_log_capture(log_handler)


def run_analysis_link(task_id: str, url: str, stage2_variant: str = "main", pause_after_stage1: bool = True) -> None:
    """Link: Stage 1 only. Stage 2 ALWAYS requires explicit user confirmation (via /analyze/restage2)."""
    log_handler = _attach_log_capture(task_id)
    try:
        task_store.update(task_id, stage="stage1", message="下载并解析链接视频中...", completed_agents=[])

        link_dir = os.path.abspath("src/stage1/link_pipeline")
        if link_dir not in sys.path:
            sys.path.insert(0, link_dir)
        from pipeline_link import run_pipeline  # type: ignore

        cookie_file = os.getenv("COOKIE_FILE") or None
        evidence = run_pipeline(url, "output", cookie_file=cookie_file)

        video_id = evidence.get("video_id") if isinstance(evidence, dict) else None
        if not video_id:
            raise ValueError("link_pipeline 未返回 video_id")

        source_path = None
        if isinstance(evidence, dict):
            source_path = (evidence.get("source") or {}).get("local_path")

        _copy_outputs(video_id, source_path)
        log_handler.mark_all_done()
        # Always stop after Stage 1 — user must confirm before Stage 2
        task_store.update(task_id, video_id=video_id, stage1_available=True, stage2_variant=stage2_variant,
                          status="stage1_done", stage="stage1_done",
                          message="Stage 1 完成，等待确认是否继续 Stage 2")
    except Exception as exc:  # noqa: BLE001
        task_store.update(task_id, status="failed", message=f"Stage 1 失败：{exc}", traceback=traceback.format_exc())
    finally:
        _detach_log_capture(log_handler)