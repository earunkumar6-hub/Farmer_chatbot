"""Farmer chatbot — Streamlit chatbot frontend.

Talks HTTP-only to the FastAPI backend (see backend/main.py) — never imports
LangChain or OpenAI directly. Uses the backend's SSE streaming endpoints so
the sidebar pipeline lights up stage by stage, live.

Run alongside the backend, both from the project root:

    python -m uvicorn backend.main:app --reload --port 8000   # terminal 1
    streamlit run frontend/app.py                              # terminal 2
"""
import streamlit as st

from styles import CUSTOM_CSS
from pipeline_visual import (
    render_pipeline,
    fresh_index_stages,
    fresh_query_stages,
    apply_stage_event,
    mark_remaining_failed,
)
import api_client

st.set_page_config(
    page_title="Farmer Chatbot — Farm Knowledge Assistant",
    page_icon="🌾",
    layout="wide",
)
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------
if "session_id" not in st.session_state:
    st.session_state.session_id = None
if "messages" not in st.session_state:
    st.session_state.messages = []  # [{"role", "content", "sources"}]
if "index_stages" not in st.session_state:
    st.session_state.index_stages = fresh_index_stages()
if "query_stages" not in st.session_state:
    st.session_state.query_stages = fresh_query_stages()

# ---------------------------------------------------------------------------
# Sidebar — controls + live pipeline visuals
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("### 📚 Knowledge Base")

    health = api_client.check_health()
    if health.get("status") != "ok":
        st.error(
            f"Can't reach the API backend at `{api_client.API_BASE_URL}`.\n\n"
            "Start it with:\n\n`python -m uvicorn backend.main:app --reload --port 8000`"
        )
    elif not health.get("api_key_configured"):
        st.error("Backend has no OpenAI API key configured — add one to the project root `.env`.")

    uploaded_files = st.file_uploader(
        "Upload farm documents (PDF or TXT)",
        type=["pdf", "txt"],
        accept_multiple_files=True,
    )
    st.caption("No files handy? Use the sample docs in `sample_docs/` — PM-KISAN scheme, "
               "paddy pest management, organic farming basics, and a Tamil groundnut guide.")
    chunk_size = st.slider("Chunk size", 200, 2000, 800, step=100)
    chunk_overlap = st.slider("Chunk overlap", 0, 400, 100, step=50)
    build_clicked = st.button("🚀 Build Knowledge Base", use_container_width=True, type="primary")

    if st.session_state.session_id is not None:
        st.success("Knowledge base ready ✅")
        if st.button("🗑️ Reset Everything", use_container_width=True):
            api_client.reset_session(st.session_state.session_id)
            st.session_state.session_id = None
            st.session_state.messages = []
            st.session_state.index_stages = fresh_index_stages()
            st.session_state.query_stages = fresh_query_stages()
            st.rerun()

    st.markdown("---")
    index_placeholder = st.empty()
    render_pipeline(st.session_state.index_stages, index_placeholder, title="📊 Indexing Pipeline")

    st.markdown("---")
    query_placeholder = st.empty()
    render_pipeline(st.session_state.query_stages, query_placeholder, title="💬 Query Pipeline")

# ---------------------------------------------------------------------------
# Hero
# ---------------------------------------------------------------------------
st.markdown(
    """<div class="hero-banner">
    <h1 style="color:white; margin:0;">🌾 Farmer chatbot</h1>
    <p>Ask questions about crops, government schemes, pests and soil health —
    answered strictly from your uploaded farm documents, never guessed.</p>
    </div>""",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Build knowledge base — streams stage events into the sidebar live
# ---------------------------------------------------------------------------
if build_clicked:
    if not uploaded_files:
        st.error("Please upload at least one document (or add the sample_docs files).")
    else:
        stages = fresh_index_stages()
        st.session_state.index_stages = stages
        render_pipeline(stages, index_placeholder, title="📊 Indexing Pipeline")

        status_slot = st.empty()
        build_error = None
        new_session_id = None

        for event in api_client.stream_build_knowledge_base(uploaded_files, chunk_size, chunk_overlap):
            etype = event.get("type")
            if etype == "stage":
                apply_stage_event(stages, event)
                render_pipeline(stages, index_placeholder, title="📊 Indexing Pipeline")
            elif etype == "complete":
                new_session_id = event.get("session_id")
            elif etype == "error":
                build_error = event.get("message", "Unknown error")
                mark_remaining_failed(stages)
                render_pipeline(stages, index_placeholder, title="📊 Indexing Pipeline")
                break

        if build_error:
            status_slot.error(f"Failed to build knowledge base: {build_error}")
        elif new_session_id:
            st.session_state.session_id = new_session_id
            status_slot.success("✅ Knowledge base built! Ask a question below.")
        else:
            status_slot.error("Build finished but no session was returned — check the backend logs.")

# ---------------------------------------------------------------------------
# Chat UI — streams stage events into the sidebar live
# ---------------------------------------------------------------------------
st.markdown("## 💬 Chat with Farmer chatbot")

if st.session_state.session_id is None:
    st.info("👆 Build your knowledge base in the sidebar first.")
else:
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("sources"):
                st.markdown(
                    "".join(f"<span class='source-chip'>📄 {s}</span>" for s in msg["sources"]),
                    unsafe_allow_html=True,
                )

    user_query = st.chat_input("Ask about crops, schemes, pests… (English or Tamil)")
    if user_query:
        st.session_state.messages.append({"role": "user", "content": user_query, "sources": []})
        with st.chat_message("user"):
            st.markdown(user_query)

        qstages = fresh_query_stages()
        st.session_state.query_stages = qstages
        render_pipeline(qstages, query_placeholder, title="💬 Query Pipeline")

        with st.chat_message("assistant"):
            answer_slot = st.empty()
            answer_slot.markdown("_Retrieving…_")

            answer_text = None
            sources = []
            chat_error = None

            for event in api_client.stream_ask_question(st.session_state.session_id, user_query):
                etype = event.get("type")
                if etype == "stage":
                    apply_stage_event(qstages, event)
                    render_pipeline(qstages, query_placeholder, title="💬 Query Pipeline")
                elif etype == "answer":
                    answer_text = event.get("answer", "")
                    sources = event.get("sources", [])
                elif etype == "error":
                    chat_error = event.get("message", "Unknown error")
                    mark_remaining_failed(qstages)
                    render_pipeline(qstages, query_placeholder, title="💬 Query Pipeline")
                    break

            if chat_error:
                text = f"Something went wrong talking to the backend: {chat_error}"
                answer_slot.error(text)
                st.session_state.messages.append({"role": "assistant", "content": text, "sources": []})
            elif answer_text is not None:
                answer_slot.markdown(answer_text)
                if sources:
                    st.markdown(
                        "".join(f"<span class='source-chip'>📄 {s}</span>" for s in sources),
                        unsafe_allow_html=True,
                    )
                st.session_state.messages.append(
                    {"role": "assistant", "content": answer_text, "sources": sources}
                )
            else:
                text = "The backend finished without returning an answer — check its logs."
                answer_slot.error(text)
                st.session_state.messages.append({"role": "assistant", "content": text, "sources": []})
