"""FastAPI application exposing the RAG pipeline as HTTP endpoints.

Both pipelines are available in two forms:

* blocking JSON  (``/documents/build``, ``/chat``)
* SSE streaming  (``/documents/build/stream``, ``/chat/stream``)

The Streamlit frontend uses the STREAMING endpoints so the sidebar can light
up each pipeline stage as it actually happens, rather than all at once when
the whole request finishes.

Run with:
    python -m uvicorn backend.main:app --reload --port 8000
"""
import json
import os
import shutil
import tempfile
from typing import Any, Dict, Generator, List

from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from backend.config import settings
from backend.rag_pipeline import (
    run_indexing_pipeline,
    run_query_pipeline,
    stream_indexing_pipeline,
    stream_query_pipeline,
)
from backend.session_manager import create_session, get_session, delete_session
from backend.schemas import BuildResponse, ChatRequest, ChatResponse, HealthResponse

app = FastAPI(title="Kisan Mitra AI — RAG API", version="1.1.0")

# Demo/local setup only — restrict allow_origins before deploying this anywhere public.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Headers that stop intermediate layers (and nginx, if you add one later) from
# buffering the SSE stream, which would defeat the whole point of streaming.
SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


def _sse(event: Dict[str, Any]) -> str:
    """Serialise one event dict into Server-Sent Events wire format."""
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


def _save_uploads(files: List[UploadFile]) -> str:
    """Persist uploads to a temp dir and return that dir's path.

    Done BEFORE streaming starts, because UploadFile objects are tied to the
    request lifecycle and can't be read reliably from inside a sync generator.
    """
    tmp_dir = tempfile.mkdtemp(prefix="kisan_mitra_")
    for f in files:
        dest = os.path.join(tmp_dir, os.path.basename(f.filename))
        with open(dest, "wb") as out:
            shutil.copyfileobj(f.file, out)
    return tmp_dir


@app.get("/health", response_model=HealthResponse)
def health():
    """Lets the frontend confirm the backend is reachable and configured."""
    return HealthResponse(status="ok", api_key_configured=bool(settings.openai_api_key))


# ---------------------------------------------------------------------------
# Streaming endpoints (used by the Streamlit frontend)
# ---------------------------------------------------------------------------
@app.post("/documents/build/stream")
async def build_documents_stream(
    files: List[UploadFile] = File(...),
    chunk_size: int = Form(settings.default_chunk_size),
    chunk_overlap: int = Form(settings.default_chunk_overlap),
):
    """Stream the indexing pipeline stage by stage as Server-Sent Events."""
    if not settings.openai_api_key:
        raise HTTPException(status_code=400, detail="No OpenAI API key configured on the server (.env).")
    if not files:
        raise HTTPException(status_code=400, detail="Please upload at least one document.")

    tmp_dir = _save_uploads(files)
    file_paths = [os.path.join(tmp_dir, n) for n in sorted(os.listdir(tmp_dir))]

    def event_generator() -> Generator[str, None, None]:
        try:
            for event in stream_indexing_pipeline(file_paths, chunk_size, chunk_overlap):
                yield _sse(event)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    return StreamingResponse(event_generator(), media_type="text/event-stream", headers=SSE_HEADERS)


@app.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """Stream the query pipeline stage by stage as Server-Sent Events."""
    if not settings.openai_api_key:
        raise HTTPException(status_code=400, detail="No OpenAI API key configured on the server (.env).")

    vectordb = get_session(request.session_id)
    if vectordb is None:
        raise HTTPException(status_code=404, detail="Session not found. Build a knowledge base first.")

    def event_generator() -> Generator[str, None, None]:
        for event in stream_query_pipeline(vectordb, request.query):
            yield _sse(event)

    return StreamingResponse(event_generator(), media_type="text/event-stream", headers=SSE_HEADERS)


# ---------------------------------------------------------------------------
# Blocking endpoints (kept for API consumers that don't want SSE)
# ---------------------------------------------------------------------------
@app.post("/documents/build", response_model=BuildResponse)
async def build_documents(
    files: List[UploadFile] = File(...),
    chunk_size: int = Form(settings.default_chunk_size),
    chunk_overlap: int = Form(settings.default_chunk_overlap),
):
    """Run the full indexing pipeline and return once everything is finished."""
    if not settings.openai_api_key:
        raise HTTPException(status_code=400, detail="No OpenAI API key configured on the server (.env).")
    if not files:
        raise HTTPException(status_code=400, detail="Please upload at least one document.")

    tmp_dir = _save_uploads(files)
    try:
        file_paths = [os.path.join(tmp_dir, n) for n in sorted(os.listdir(tmp_dir))]
        vectordb, stages = run_indexing_pipeline(file_paths, chunk_size, chunk_overlap)
        session_id = create_session(vectordb)
        return BuildResponse(session_id=session_id, stages=stages)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Indexing failed: {e}")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Answer a question against a previously built knowledge base."""
    if not settings.openai_api_key:
        raise HTTPException(status_code=400, detail="No OpenAI API key configured on the server (.env).")

    vectordb = get_session(request.session_id)
    if vectordb is None:
        raise HTTPException(status_code=404, detail="Session not found. Build a knowledge base first.")

    try:
        answer, sources, stages = run_query_pipeline(vectordb, request.query)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query failed: {e}")

    return ChatResponse(answer=answer, sources=sources, stages=stages)


@app.delete("/session/{session_id}")
async def reset_session(session_id: str):
    """Discard a knowledge base session from server memory."""
    delete_session(session_id)
    return {"status": "deleted"}
