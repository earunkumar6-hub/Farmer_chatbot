"""In-memory session store mapping a session_id to its FAISS knowledge base.

NOTE: this is intentionally simple for a learning/demo project — it lives in
process memory, so it resets on server restart and won't work correctly if
you run uvicorn with multiple worker processes (each worker would have its
own copy). Swap this for Redis or a database-backed store before using this
beyond a single local user/demo.
"""
import uuid
from typing import Dict, Optional

from langchain_community.vectorstores import FAISS

_SESSIONS: Dict[str, FAISS] = {}


def create_session(vectordb: FAISS) -> str:
    """Register a new knowledge base and return its session id."""
    session_id = str(uuid.uuid4())
    _SESSIONS[session_id] = vectordb
    return session_id


def get_session(session_id: str) -> Optional[FAISS]:
    """Look up the FAISS vector store for a session id, or None if not found."""
    return _SESSIONS.get(session_id)


def delete_session(session_id: str) -> None:
    """Remove a session's knowledge base from memory."""
    _SESSIONS.pop(session_id, None)
