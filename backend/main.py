"""FastAPI backend gateway for Alex, the Northwind AI Analyst.

This module is intentionally thin: it owns HTTP routing, validation, and file
responses. The agent loop lives in agent.py; demo-specific agent configs live
in backend/agents/levelN-agent.py.
"""

import asyncio
import sys
from contextlib import asynccontextmanager
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse

try:
    from .agent import stream_agent
    from .models import RunRequest
    from .settings import MODEL, BASE_URL
    from .workspace import (
        ensure_workspace_initialized,
        resolve_report_file,
        resolve_workspace_file,
        setup_workspace,
        workspace_tree,
    )
except ImportError:
    from backend.agent import stream_agent
    from backend.models import RunRequest
    from backend.settings import MODEL, BASE_URL
    from backend.workspace import (
        ensure_workspace_initialized,
        resolve_report_file,
        resolve_workspace_file,
        setup_workspace,
        workspace_tree,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    loop = asyncio.get_running_loop()
    msg = await loop.run_in_executor(None, ensure_workspace_initialized)
    print(f"Level 4 workspace startup: {msg}", flush=True)
    yield


app = FastAPI(title="Alex — Northwind AI Analyst", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/api/run")
async def api_run(req: RunRequest):
    if req.level not in (1, 2, 3, 4):
        raise HTTPException(400, "level must be 1–4")
    if not req.question.strip():
        raise HTTPException(400, "question is required")

    return StreamingResponse(
        stream_agent(req),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/setup")
async def api_setup():
    loop = asyncio.get_event_loop()
    try:
        msg = await loop.run_in_executor(None, setup_workspace)
        return {"ok": True, "message": msg}
    except Exception as exc:
        raise HTTPException(500, str(exc)) from exc


@app.get("/api/workspace/tree")
async def api_workspace_tree():
    return {"tree": workspace_tree()}


@app.get("/api/workspace/files/{file_path:path}")
async def api_workspace_file(file_path: str):
    try:
        target = resolve_workspace_file(file_path)
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    return FileResponse(str(target))


@app.get("/api/reports/{filename}")
async def api_serve_report(filename: str):
    try:
        path = resolve_report_file(filename)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    media = "application/pdf" if filename.endswith(".pdf") else "image/png"
    return FileResponse(str(path), media_type=media, filename=filename)


@app.get("/api/health")
async def api_health():
    return {"status": "ok", "model": MODEL, "base_url": BASE_URL}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
