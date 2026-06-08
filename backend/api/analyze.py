"""Analysis endpoints: upload/link video, poll status, get result."""

from __future__ import annotations

import json
import os
import shutil
import uuid

from fastapi import APIRouter, BackgroundTasks, Form, UploadFile
from pydantic import BaseModel

from backend.store.task_store import task_store
from backend.tasks.analysis_task import run_analysis, run_analysis_link, run_restage2

router = APIRouter()

UPLOAD_DIR = "backend/static/uploads"
STATIC_DIR = "backend/static"


class LinkRequest(BaseModel):
    url: str
    stage2_variant: str = "main"
    pause_after_stage1: bool = False


class ReStage2Request(BaseModel):
    video_id: str
    stage2_variant: str = "main"


@router.post("/analyze")
async def analyze_video(
    background_tasks: BackgroundTasks,
    video: UploadFile,
    stage2_variant: str = Form("main"),
    pause_after_stage1: bool = Form(False),
):
    task_id = f"task_{uuid.uuid4().hex[:8]}"

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    filename = video.filename or f"{task_id}.mp4"
    upload_path = os.path.join(UPLOAD_DIR, f"{task_id}_{filename}")
    with open(upload_path, "wb") as f:
        shutil.copyfileobj(video.file, f)

    task_store.create(task_id, status="processing", message="已上传，开始分析...")
    background_tasks.add_task(run_analysis, task_id, upload_path, stage2_variant, pause_after_stage1)

    return {"task_id": task_id, "status": "processing"}


@router.post("/analyze/link")
async def analyze_link(req: LinkRequest, background_tasks: BackgroundTasks):
    task_id = f"task_{uuid.uuid4().hex[:8]}"
    task_store.create(task_id, status="processing", message="开始下载并解析链接...")
    background_tasks.add_task(run_analysis_link, task_id, req.url, req.stage2_variant, req.pause_after_stage1)
    return {"task_id": task_id, "status": "processing"}


@router.post("/analyze/restage2")
async def restage2(req: ReStage2Request, background_tasks: BackgroundTasks):
    """Re-run only Stage 2 with a different variant, reusing the cached Stage 1 evidence."""
    task_id = f"task_{uuid.uuid4().hex[:8]}"
    task_store.create(task_id, status="processing", message="复用Stage1，切换Stage2模式...")
    background_tasks.add_task(run_restage2, task_id, req.video_id, req.stage2_variant)
    return {"task_id": task_id, "status": "processing"}


@router.get("/analyze/{task_id}/status")
async def get_status(task_id: str):
    task = task_store.get(task_id)
    safe = {k: v for k, v in task.items() if k != "traceback"}
    return safe


def _load_result(video_id: str, video_ext: str = ".mp4") -> dict:
    base = f"{STATIC_DIR}/{video_id}"

    # Determine source ext if not given
    ext = video_ext
    for e in (".mp4", ".mov", ".webm"):
        if os.path.exists(f"{base}/source{e}"):
            ext = e
            break

    evidence = None
    ep_path = f"{base}/evidence_package.json"
    if os.path.exists(ep_path):
        with open(ep_path, encoding="utf-8") as f:
            evidence = json.load(f)

    result = {
        "video_id": video_id,
        "video_url": f"/static/{video_id}/source{ext}",
        "evidence_package": evidence,
    }

    vs_path  = f"{base}/video_structure.json"
    syn_path = f"{base}/synthesis_result.json"
    has_vs  = os.path.exists(vs_path)
    has_syn = os.path.exists(syn_path)

    if has_vs:
        with open(vs_path, encoding="utf-8") as f:
            result["video_structure"] = json.load(f)
    if has_syn:
        with open(syn_path, encoding="utf-8") as f:
            result["synthesis_result"] = json.load(f)

    if has_vs and has_syn:
        result["stage2_variant"] = "both"
    elif has_vs:
        result["stage2_variant"] = "main"
    elif has_syn:
        result["stage2_variant"] = "leo"

    return result


@router.get("/analyze/{task_id}/result")
async def get_result(task_id: str):
    task = task_store.get(task_id)
    status = task.get("status")
    if status == "done":
        return _load_result(task["video_id"], task.get("video_ext", ".mp4"))
    # Both mode: leo done, main still running — return partial result so frontend can show leo immediately
    if status == "processing" and task.get("has_leo_result") and task.get("video_id"):
        res = _load_result(task["video_id"], task.get("video_ext", ".mp4"))
        res["main_loading"] = True
        return res
    # Stage 1 finished and awaiting confirmation to run Stage 2
    if status == "stage1_done" and task.get("video_id"):
        res = _load_result(task["video_id"], task.get("video_ext", ".mp4"))
        res["stage1_only"] = True
        res["pending_variant"] = task.get("stage2_variant", "main")
        return res
    # Stage 2 failed but Stage 1 succeeded — return the partial (evidence-only) result
    if status == "failed" and task.get("stage1_available") and task.get("video_id"):
        res = _load_result(task["video_id"], task.get("video_ext", ".mp4"))
        res["stage2_failed"] = True
        res["error"] = task.get("message")
        return res
    return {"error": "not_ready", "status": status}


@router.get("/samples")
async def list_samples():
    samples = []
    if os.path.isdir(STATIC_DIR):
        for d in os.listdir(STATIC_DIR):
            base = f"{STATIC_DIR}/{d}"
            if os.path.exists(f"{base}/video_structure.json") or os.path.exists(f"{base}/synthesis_result.json"):
                samples.append(d)
    return {"samples": samples}


@router.get("/samples/{video_id}")
async def get_sample(video_id: str):
    base = f"{STATIC_DIR}/{video_id}"
    if not (os.path.exists(f"{base}/video_structure.json") or os.path.exists(f"{base}/synthesis_result.json")):
        return {"error": "sample_not_found"}
    return _load_result(video_id)