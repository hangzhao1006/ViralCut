"""Analysis endpoints: upload video, poll status, get result."""

from __future__ import annotations

import json
import os
import shutil
import uuid

from fastapi import APIRouter, BackgroundTasks, UploadFile

from backend.store.task_store import task_store
from backend.tasks.analysis_task import run_analysis

router = APIRouter()

UPLOAD_DIR = "backend/static/uploads"
STATIC_DIR = "backend/static"


@router.post("/analyze")
async def analyze_video(video: UploadFile, background_tasks: BackgroundTasks):
    task_id = f"task_{uuid.uuid4().hex[:8]}"

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    filename = video.filename or f"{task_id}.mp4"
    upload_path = os.path.join(UPLOAD_DIR, f"{task_id}_{filename}")
    with open(upload_path, "wb") as f:
        shutil.copyfileobj(video.file, f)

    task_store.create(task_id, status="processing", message="已上传，开始分析...")
    background_tasks.add_task(run_analysis, task_id, upload_path)

    return {"task_id": task_id, "status": "processing"}


@router.get("/analyze/{task_id}/status")
async def get_status(task_id: str):
    task = task_store.get(task_id)
    # Don't leak full traceback to frontend by default
    safe = {k: v for k, v in task.items() if k != "traceback"}
    return safe


@router.get("/analyze/{task_id}/result")
async def get_result(task_id: str):
    task = task_store.get(task_id)
    if task.get("status") != "done":
        return {"error": "not_ready", "status": task.get("status")}

    video_id = task["video_id"]
    base = f"{STATIC_DIR}/{video_id}"

    with open(f"{base}/video_structure.json", encoding="utf-8") as f:
        video_structure = json.load(f)

    evidence = None
    ep_path = f"{base}/evidence_package.json"
    if os.path.exists(ep_path):
        with open(ep_path, encoding="utf-8") as f:
            evidence = json.load(f)

    ext = task.get("video_ext", ".mp4")
    return {
        "video_id": video_id,
        "video_url": f"/static/{video_id}/source{ext}",
        "video_structure": video_structure,
        "evidence_package": evidence,
    }


@router.get("/samples")
async def list_samples():
    """List pre-analyzed sample videos (fallback for demo)."""
    samples = []
    if os.path.isdir(STATIC_DIR):
        for d in os.listdir(STATIC_DIR):
            vs_path = f"{STATIC_DIR}/{d}/video_structure.json"
            if os.path.exists(vs_path):
                samples.append(d)
    return {"samples": samples}


@router.get("/samples/{video_id}")
async def get_sample(video_id: str):
    """Get a pre-analyzed sample directly."""
    base = f"{STATIC_DIR}/{video_id}"
    vs_path = f"{base}/video_structure.json"
    if not os.path.exists(vs_path):
        return {"error": "sample_not_found"}

    with open(vs_path, encoding="utf-8") as f:
        video_structure = json.load(f)

    evidence = None
    ep_path = f"{base}/evidence_package.json"
    if os.path.exists(ep_path):
        with open(ep_path, encoding="utf-8") as f:
            evidence = json.load(f)

    # Find source video extension
    ext = ".mp4"
    for e in (".mp4", ".mov", ".webm"):
        if os.path.exists(f"{base}/source{e}"):
            ext = e
            break

    return {
        "video_id": video_id,
        "video_url": f"/static/{video_id}/source{ext}",
        "video_structure": video_structure,
        "evidence_package": evidence,
    }
