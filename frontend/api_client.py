"""Thin HTTP client wrapping calls to the FastAPI backend.

Kept in one file so the Streamlit UI never talks to LangChain/OpenAI directly.

The ``stream_*`` functions are generators that yield parsed event dicts as
they arrive over Server-Sent Events, letting the sidebar update stage by
stage instead of all at once.
"""
import json
import os
from typing import Any, Dict, Generator

import requests

API_BASE_URL = os.environ.get("KISAN_MITRA_API_URL", "http://127.0.0.1:8000")


def check_health() -> dict:
    """Ping the backend; returns {'status': 'unreachable', ...} if it's down."""
    try:
        r = requests.get(f"{API_BASE_URL}/health", timeout=5)
        r.raise_for_status()
        return r.json()
    except requests.RequestException as e:
        return {"status": "unreachable", "error": str(e)}


def _iter_sse(response: requests.Response) -> Generator[Dict[str, Any], None, None]:
    """Parse an SSE response body into a stream of event dicts."""
    for raw_line in response.iter_lines(decode_unicode=True):
        if not raw_line:
            continue
        if raw_line.startswith("data:"):
            payload = raw_line[len("data:"):].strip()
            if payload:
                try:
                    yield json.loads(payload)
                except json.JSONDecodeError:
                    # Ignore malformed frames rather than killing the whole stream
                    continue


def stream_build_knowledge_base(
    files, chunk_size: int, chunk_overlap: int
) -> Generator[Dict[str, Any], None, None]:
    """Yield stage/complete/error events while the backend builds the index.

    ``files`` is a list of Streamlit UploadedFile objects.
    """
    file_payload = [("files", (f.name, f.getvalue())) for f in files]
    data = {"chunk_size": chunk_size, "chunk_overlap": chunk_overlap}
    with requests.post(
        f"{API_BASE_URL}/documents/build/stream",
        files=file_payload,
        data=data,
        stream=True,
        timeout=600,
    ) as r:
        if r.status_code != 200:
            detail = r.text
            try:
                detail = r.json().get("detail", detail)
            except Exception:
                pass
            yield {"type": "error", "message": f"HTTP {r.status_code}: {detail}"}
            return
        yield from _iter_sse(r)


def stream_ask_question(session_id: str, query: str) -> Generator[Dict[str, Any], None, None]:
    """Yield stage/answer/error events while the backend answers a question."""
    with requests.post(
        f"{API_BASE_URL}/chat/stream",
        json={"session_id": session_id, "query": query},
        stream=True,
        timeout=180,
    ) as r:
        if r.status_code != 200:
            detail = r.text
            try:
                detail = r.json().get("detail", detail)
            except Exception:
                pass
            yield {"type": "error", "message": f"HTTP {r.status_code}: {detail}"}
            return
        yield from _iter_sse(r)


# --- Blocking variants, kept as a fallback / for scripted use ---------------
def build_knowledge_base(files, chunk_size: int, chunk_overlap: int) -> dict:
    file_payload = [("files", (f.name, f.getvalue())) for f in files]
    data = {"chunk_size": chunk_size, "chunk_overlap": chunk_overlap}
    r = requests.post(f"{API_BASE_URL}/documents/build", files=file_payload, data=data, timeout=600)
    r.raise_for_status()
    return r.json()


def ask_question(session_id: str, query: str) -> dict:
    r = requests.post(
        f"{API_BASE_URL}/chat",
        json={"session_id": session_id, "query": query},
        timeout=180,
    )
    r.raise_for_status()
    return r.json()


def reset_session(session_id: str) -> None:
    """Best-effort cleanup — ignore failures since the frontend is resetting anyway."""
    try:
        requests.delete(f"{API_BASE_URL}/session/{session_id}", timeout=5)
    except requests.RequestException:
        pass
