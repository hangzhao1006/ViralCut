"""ViralCut backend — FastAPI entry point.

Wraps Stage 1 / Stage 2 / Stage 3 as HTTP endpoints.

Run:
    uvicorn backend.main:app --reload --port 8000
"""

from __future__ import annotations

import os
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.api import analyze, assets, migrate

app = FastAPI(title="ViralCut API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs("backend/static", exist_ok=True)
app.mount("/static", StaticFiles(directory="backend/static"), name="static")

app.include_router(analyze.router, prefix="/api", tags=["analyze"])
app.include_router(migrate.router, prefix="/api", tags=["migrate"])
app.include_router(assets.router, prefix="/api", tags=["assets"])


@app.get("/api/health")
async def health():
    return {"status": "ok"}
