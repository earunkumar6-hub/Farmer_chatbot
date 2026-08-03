"""Orchestrates the indexing and query pipelines.

Two flavours of each pipeline:

* ``run_*_pipeline``          - blocking, returns everything at the end.
* ``stream_*_pipeline``       - a GENERATOR that yields one event per stage
                                boundary, so the UI can show live progress.

The streaming versions are what the Streamlit sidebar uses to light stages up
one at a time. Each yielded event is a plain dict, serialised to SSE by
``backend/main.py``.

Event shapes
------------
{"type": "stage",    "index": 0, "icon": "...", "name": "...",
 "status": "active"|"done", "detail": "..."}
{"type": "complete", "session_id": "..."}                   # indexing only
{"type": "answer",   "answer": "...", "sources": [...]}     # query only
{"type": "error",    "message": "..."}
"""
import time
from typing import Any, Dict, Generator, List, Tuple

from langchain_community.vectorstores import FAISS

from backend.document_loader import load_documents
from backend.text_splitter import split_documents
from backend.embeddings_service import get_embeddings
from backend.vector_store import build_vector_store, get_retriever
from backend.llm_service import get_llm
from backend.prompt_template import build_rag_prompt
from backend.session_manager import create_session
from backend.schemas import StageInfo
from backend.config import settings

# Stage definitions shared by the blocking and streaming variants, so the
# frontend's placeholder cards always match what the backend will emit.
INDEX_STAGES = [
    {"icon": "📂", "name": "Load Documents"},
    {"icon": "✂️", "name": "Split into Chunks"},
    {"icon": "🧬", "name": "Generate Embeddings"},
    {"icon": "🗄️", "name": "Store in Vector DB"},
]

QUERY_STAGES = [
    {"icon": "❓", "name": "User Query"},
    {"icon": "🧬", "name": "Embed Query"},
    {"icon": "🔍", "name": "Similarity Search"},
    {"icon": "📚", "name": "Assemble Context"},
    {"icon": "🤖", "name": "LLM Answer"},
]


def _stage_event(stages: List[Dict[str, str]], index: int, status: str, detail: str = "") -> Dict[str, Any]:
    return {
        "type": "stage",
        "index": index,
        "icon": stages[index]["icon"],
        "name": stages[index]["name"],
        "status": status,
        "detail": detail,
    }


# ---------------------------------------------------------------------------
# Streaming indexing pipeline
# ---------------------------------------------------------------------------
def stream_indexing_pipeline(
    file_paths: List[str], chunk_size: int, chunk_overlap: int
) -> Generator[Dict[str, Any], None, None]:
    """Yield one event per stage boundary while running Load -> Split -> Embed -> Store."""
    try:
        # Stage 0: Load
        yield _stage_event(INDEX_STAGES, 0, "active")
        t0 = time.time()
        docs = load_documents(file_paths)
        yield _stage_event(INDEX_STAGES, 0, "done", f"{len(docs)} page(s)/file(s) — {time.time() - t0:.1f}s")

        # Stage 1: Split
        yield _stage_event(INDEX_STAGES, 1, "active")
        t0 = time.time()
        chunks = split_documents(docs, chunk_size, chunk_overlap)
        yield _stage_event(INDEX_STAGES, 1, "done", f"{len(chunks)} chunks (size={chunk_size}) — {time.time() - t0:.1f}s")

        # Stage 2: Embeddings client
        yield _stage_event(INDEX_STAGES, 2, "active")
        embeddings = get_embeddings()
        yield _stage_event(INDEX_STAGES, 2, "done", settings.embedding_model)

        # Stage 3: Store (this is where the actual embedding API calls happen)
        yield _stage_event(INDEX_STAGES, 3, "active", f"embedding {len(chunks)} chunks…")
        t0 = time.time()
        vectordb = build_vector_store(chunks, embeddings)
        yield _stage_event(INDEX_STAGES, 3, "done", f"{vectordb.index.ntotal} vectors (FAISS) — {time.time() - t0:.1f}s")

        session_id = create_session(vectordb)
        yield {"type": "complete", "session_id": session_id}

    except Exception as e:  # surface the failure to the UI instead of hanging
        yield {"type": "error", "message": str(e)}


# ---------------------------------------------------------------------------
# Streaming query pipeline
# ---------------------------------------------------------------------------
def stream_query_pipeline(vectordb: FAISS, query: str) -> Generator[Dict[str, Any], None, None]:
    """Yield one event per stage boundary while answering a question."""
    try:
        short_q = query if len(query) <= 28 else query[:28] + "…"
        yield _stage_event(QUERY_STAGES, 0, "done", short_q)

        # Stage 1: build retriever / embed query
        yield _stage_event(QUERY_STAGES, 1, "active")
        retriever = get_retriever(vectordb, k=settings.retriever_k)
        yield _stage_event(QUERY_STAGES, 1, "done", "query vector ready")

        # Stage 2: similarity search
        yield _stage_event(QUERY_STAGES, 2, "active")
        t0 = time.time()
        retrieved_docs = retriever.invoke(query)
        yield _stage_event(QUERY_STAGES, 2, "done", f"top {len(retrieved_docs)} chunks — {time.time() - t0:.1f}s")

        # Stage 3: assemble context
        yield _stage_event(QUERY_STAGES, 3, "active")
        context_text = "\n\n".join(d.page_content for d in retrieved_docs)
        yield _stage_event(QUERY_STAGES, 3, "done", f"{len(context_text)} chars")

        # Stage 4: LLM answer
        yield _stage_event(QUERY_STAGES, 4, "active", f"{settings.chat_model} thinking…")
        t0 = time.time()
        llm = get_llm()
        prompt = build_rag_prompt()
        prompt_messages = prompt.invoke({"context": context_text, "input": query})
        response = llm.invoke(prompt_messages)
        yield _stage_event(QUERY_STAGES, 4, "done", f"{settings.chat_model} — {time.time() - t0:.1f}s")

        sources = sorted(set(d.metadata.get("source", "unknown") for d in retrieved_docs))
        yield {"type": "answer", "answer": response.content, "sources": sources}

    except Exception as e:
        yield {"type": "error", "message": str(e)}


# ---------------------------------------------------------------------------
# Blocking variants (kept for the non-streaming endpoints / programmatic use)
# ---------------------------------------------------------------------------
def run_indexing_pipeline(
    file_paths: List[str], chunk_size: int, chunk_overlap: int
) -> Tuple[FAISS, List[StageInfo]]:
    """Run the indexing pipeline to completion. Returns (vector_store, stages)."""
    stages: List[StageInfo] = []

    t0 = time.time()
    docs = load_documents(file_paths)
    stages.append(StageInfo(icon="📂", name="Load Documents", status="done",
                            detail=f"{len(docs)} page(s)/file(s) — {time.time() - t0:.1f}s"))

    t0 = time.time()
    chunks = split_documents(docs, chunk_size, chunk_overlap)
    stages.append(StageInfo(icon="✂️", name="Split into Chunks", status="done",
                            detail=f"{len(chunks)} chunks (size={chunk_size}) — {time.time() - t0:.1f}s"))

    embeddings = get_embeddings()
    stages.append(StageInfo(icon="🧬", name="Generate Embeddings", status="done",
                            detail=settings.embedding_model))

    t0 = time.time()
    vectordb = build_vector_store(chunks, embeddings)
    stages.append(StageInfo(icon="🗄️", name="Store in Vector DB", status="done",
                            detail=f"{vectordb.index.ntotal} vectors (FAISS) — {time.time() - t0:.1f}s"))

    return vectordb, stages


def run_query_pipeline(vectordb: FAISS, query: str) -> Tuple[str, List[str], List[StageInfo]]:
    """Run the query pipeline to completion. Returns (answer, sources, stages)."""
    stages: List[StageInfo] = []
    short_q = query if len(query) <= 28 else query[:28] + "…"
    stages.append(StageInfo(icon="❓", name="User Query", status="done", detail=short_q))

    retriever = get_retriever(vectordb, k=settings.retriever_k)
    stages.append(StageInfo(icon="🧬", name="Embed Query", status="done", detail="query vector ready"))

    t0 = time.time()
    retrieved_docs = retriever.invoke(query)
    stages.append(StageInfo(icon="🔍", name="Similarity Search", status="done",
                            detail=f"top {len(retrieved_docs)} chunks — {time.time() - t0:.1f}s"))

    context_text = "\n\n".join(d.page_content for d in retrieved_docs)
    stages.append(StageInfo(icon="📚", name="Assemble Context", status="done",
                            detail=f"{len(context_text)} chars"))

    t0 = time.time()
    llm = get_llm()
    prompt = build_rag_prompt()
    prompt_messages = prompt.invoke({"context": context_text, "input": query})
    response = llm.invoke(prompt_messages)
    stages.append(StageInfo(icon="🤖", name="LLM Answer", status="done",
                            detail=f"{settings.chat_model} — {time.time() - t0:.1f}s"))

    sources = sorted(set(d.metadata.get("source", "unknown") for d in retrieved_docs))
    return response.content, sources, stages
