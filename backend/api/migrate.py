"""Migration endpoints: blocking + streaming (SSE)."""

from __future__ import annotations

import json
import os

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src.stage3.migrate import run_migration
from src.stage3.migrate_stream import run_migration_stream

router = APIRouter()

STATIC_DIR = "backend/static"


class MigrateRequest(BaseModel):
    video_id: str
    new_content: dict
    user_assets: dict


class SlotEditRequest(BaseModel):
    video_id: str
    slot_index: int
    current_slot: dict
    new_content: dict
    user_assets: dict
    instruction: str = ""
    force_strategy: str = ""


def _load_blueprint(video_id: str):
    vs_path = f"{STATIC_DIR}/{video_id}/video_structure.json"
    if not os.path.exists(vs_path):
        return None
    with open(vs_path, encoding="utf-8") as f:
        vs = json.load(f)
    bp = vs.get("transfer_blueprint", {}).get("transfer_blueprint", {})
    return bp or vs.get("transfer_blueprint", {})


@router.post("/migrate")
async def migrate(req: MigrateRequest):
    blueprint = _load_blueprint(req.video_id)
    if blueprint is None:
        return {"error": "video_structure not found", "video_id": req.video_id}
    return run_migration(blueprint, req.new_content, req.user_assets)


@router.post("/migrate/stream")
async def migrate_stream(req: MigrateRequest):
    blueprint = _load_blueprint(req.video_id)
    if blueprint is None:
        return {"error": "video_structure not found", "video_id": req.video_id}

    def event_gen():
        full = []
        for chunk in run_migration_stream(blueprint, req.new_content, req.user_assets):
            full.append(chunk)
            # SSE: each chunk as a data event
            yield f"data: {json.dumps({'type': 'chunk', 'text': chunk}, ensure_ascii=False)}\n\n"
        # Final parsed result
        from src.stage3.migrate_stream import parse_migration_json
        result = parse_migration_json("".join(full))
        yield f"data: {json.dumps({'type': 'done', 'result': result}, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_gen(), media_type="text/event-stream")


@router.post("/migrate/slot")
async def migrate_slot(req: SlotEditRequest):
    blueprint = _load_blueprint(req.video_id)
    if blueprint is None:
        return {"error": "video_structure not found", "video_id": req.video_id}

    source_slots = blueprint.get("structure_template", [])
    source_slot = source_slots[req.slot_index] if 0 <= req.slot_index < len(source_slots) else {}

    from src.stage3.migrate_slot import regenerate_slot
    return regenerate_slot(
        source_slot=source_slot,
        current_slot=req.current_slot,
        new_content=req.new_content,
        user_assets=req.user_assets,
        instruction=req.instruction,
        force_strategy=req.force_strategy,
    )
