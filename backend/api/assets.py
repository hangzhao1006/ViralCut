"""Asset upload endpoint — uploads + analyzes materials via vision."""

from __future__ import annotations

import os
import shutil
import uuid

from fastapi import APIRouter, UploadFile

from src.stage3.asset_analyzer import analyze_asset

router = APIRouter()

ASSETS_DIR = "backend/static/assets"

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
VIDEO_EXTS = {".mp4", ".mov", ".webm", ".mkv", ".avi"}


@router.post("/assets/upload")
async def upload_assets(files: list[UploadFile]):
    """Upload assets and analyze each via vision. Returns enriched asset metadata."""
    os.makedirs(ASSETS_DIR, exist_ok=True)
    assets = []

    for f in files:
        asset_id = f"asset_{uuid.uuid4().hex[:8]}"
        filename = f.filename or asset_id
        ext = os.path.splitext(filename)[1].lower()
        save_path = os.path.join(ASSETS_DIR, f"{asset_id}{ext}")

        with open(save_path, "wb") as out:
            shutil.copyfileobj(f.file, out)

        if ext in VIDEO_EXTS:
            atype = "video"
        elif ext in IMAGE_EXTS:
            atype = "image"
        else:
            atype = "other"

        if atype in ("video", "image"):
            analysis = analyze_asset(save_path, atype, asset_id)
        else:
            analysis = {"id": asset_id, "type": atype}

        analysis["filename"] = filename
        analysis["url"] = f"/static/assets/{asset_id}{ext}"
        assets.append(analysis)

    videos = [a for a in assets if a["type"] == "video"]
    images = [a for a in assets if a["type"] == "image"]

    return {
        "assets": assets,
        "user_assets": {
            "videos": videos,
            "images": images,
            "texts": [],
            "has_bgm": False,
        },
    }
