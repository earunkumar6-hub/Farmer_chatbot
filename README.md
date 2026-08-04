# 🌾Farmer's Chatbot

A Retrieval-Augmented Generation (RAG) chatbot for farmers, now split into a proper
**FastAPI backend** (the actual LangChain/OpenAI pipeline) and a **Streamlit chat
frontend** that talks to it over HTTP. Every pipeline stage — document loading, text
splitting, embedding, vector storage, retrieval, and generation — lives in its own
single-purpose file.

---

## Architecture

```
┌─────────────────────────┐        HTTP / JSON        ┌──────────────────────────────┐
│  Streamlit Frontend      │  ────────────────────────▶ │  FastAPI Backend             │
│  (frontend/app.py)       │  ◀──────────────────────── │  (backend/main.py)           │
│  - chat UI (st.chat_*)   │                            │  - /health                   │
│  - sidebar controls      │                            │  - /documents/build          │
│  - live pipeline cards   │                            │  - /chat                     │
│  - never sees OpenAI key │                            │  - /session/{id}  (DELETE)   │
└─────────────────────────┘                            └──────────────────────────────┘
                                                                       │
                                                                       ▼
                                                    ┌──────────────────────────────────┐
                                                    │ RAG pipeline (backend/*.py)       │
                                                    │ document_loader → text_splitter   │
                                                    │ → embeddings_service → vector_store│
                                                    │ (query time: vector_store →       │
                                                    │  llm_service → prompt_template)   │
                                                    └──────────────────────────────────┘
```

The frontend **only ever calls HTTP endpoints** — it never imports LangChain or OpenAI,
and never sees your API key. All of that lives server-side in the backend, which is
the correct place for it (the previous single-file Streamlit version had the LLM calls
running inside the browser-facing process).

---

## Project structure

```
farmer_agri_rag_app_v2/
├── backend/
│   ├── __init__.py
│   ├── main.py                  # FastAPI app + routes
│   ├── config.py                # settings, loads .env
│   ├── schemas.py                # Pydantic request/response models
│   ├── document_loader.py        # Stage 1: load_documents()
│   ├── text_splitter.py          # Stage 2: split_documents()
│   ├── embeddings_service.py     # Stage 3: get_embeddings()
│   ├── vector_store.py           # Stage 4: build_vector_store(), get_retriever()
│   ├── llm_service.py            # get_llm() (query-time)
│   ├── prompt_template.py        # build_rag_prompt() — the grounded, bilingual prompt
│   ├── session_manager.py        # in-memory session_id -> FAISS store
│   └── rag_pipeline.py           # orchestrates the stages above, records timings
├── frontend/
│   ├── __init__.py
│   ├── app.py                   # Streamlit chatbot (chat UI + sidebar)
│   ├── api_client.py             # HTTP client wrapping calls to the backend
│   ├── pipeline_visual.py        # renders the live pipeline stage cards
│   └── styles.py                 # color palette + CSS
├── sample_docs/                 # 4 ready-to-use demo documents (English + Tamil)
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

---

## Setup

1. **Create a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate      # Windows: venv\Scripts\activate
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set your OpenAI API key**
   ```bash
   cp .env.example .env
   ```
   Edit `.env` and paste your real key:
   ```
   OPENAI_API_KEY=sk-...
   ```
   This file must sit in the **project root** — the backend loads it from there
   regardless of which folder you launch it from.

4. **Run the backend** (terminal 1, from the project root)
   ```bash
   python -m uvicorn backend.main:app --reload --port 8000
   ```
   > **Important:** use `python -m uvicorn ...`, not a bare `uvicorn ...`. The bare
   > console-script entry point does not reliably add the project root to Python's
   > import path, so it can fail with `ModuleNotFoundError: No module named 'backend'`.
   > `python -m` fixes this by construction. This was tested directly — the bare form
   > failed in exactly this way during development.

   Visit `http://127.0.0.1:8000/docs` to see the interactive Swagger UI for all
   endpoints.

5. **Run the frontend** (terminal 2, also from the project root)
   ```bash
   streamlit run frontend/app.py
   ```

6. **In the browser tab that opens:**
   - Upload the sample files from `sample_docs/` (or your own PDFs/TXT — English,
     Tamil, or a mix).
   - Click **🚀 Build Knowledge Base** in the sidebar and watch the indexing pipeline
     appear below it.
   - Use the chat box at the bottom to ask questions — in English or Tamil, the
     assistant replies in whichever language you asked in. Try
     *"How do I control stem borer in paddy?"* or
     *"நிலக்கடலையில் இலைப்புள்ளி நோயை எப்படி கட்டுப்படுத்துவது?"*.

If the sidebar shows a red error about not reaching the backend, it means step 4
hasn't been done yet (or crashed) — check that terminal.

---

## Troubleshooting

**`ModuleNotFoundError: No module named 'frontend'`** — the files inside `frontend/`
import each other directly (e.g. `from styles import CUSTOM_CSS`, not
`from frontend.styles import ...`), specifically so this works no matter what your
current directory is when you launch Streamlit. If you still hit this, you're likely
running an older copy of `app.py` — re-download and replace the whole `frontend/`
folder.

**`ModuleNotFoundError: No module named 'backend'`** when starting the API — you used
a bare `uvicorn` command instead of `python -m uvicorn`. See step 4 above.

---

## API endpoints

| Method | Path                        | Purpose                                              |
|--------|-----------------------------|-------------------------------------------------------|
| GET    | `/health`                   | Check the backend is up and has an API key configured |
| POST   | `/documents/build/stream`   | **(used by the UI)** Indexing pipeline, streamed stage by stage as SSE |
| POST   | `/chat/stream`              | **(used by the UI)** Query pipeline, streamed stage by stage as SSE |
| POST   | `/documents/build`          | Same indexing pipeline, one blocking JSON response    |
| POST   | `/chat`                     | Same query pipeline, one blocking JSON response       |
| DELETE | `/session/{id}`             | Discard a session's knowledge base from memory        |

`POST /documents/build` takes multipart form data: `files` (one or more), plus
`chunk_size` and `chunk_overlap` form fields. `POST /chat` takes JSON:
`{"session_id": "...", "query": "..."}`.

---

## How the pipeline visualization works

The sidebar updates **live, stage by stage**, via Server-Sent Events (SSE).

- `backend/rag_pipeline.py` exposes generator functions (`stream_indexing_pipeline`,
  `stream_query_pipeline`) that `yield` an event at each stage boundary — one when a
  stage starts (`status: "active"`) and one when it finishes (`status: "done"`, with
  real metrics like chunk counts and elapsed seconds).
- `backend/main.py` serialises those events to SSE on `/documents/build/stream` and
  `/chat/stream`, with `X-Accel-Buffering: no` so nothing buffers them.
- `frontend/api_client.py` consumes the stream with `requests(stream=True)` and yields
  parsed event dicts as they arrive.
- `frontend/app.py` applies each event to its stage list and re-renders the sidebar
  placeholder immediately, so you watch cards go gray → amber (RUNNING…) → green.

The slow stages are genuinely visible: "Store in Vector DB" sits in amber for the whole
time the embedding API calls are running, then flips green with the vector count.

If a stage fails, the error event flips any still-pending stages to a red ERROR state
rather than leaving them stuck showing "RUNNING…".

The blocking endpoints (`/documents/build`, `/chat`) are still available for scripted
or non-SSE API consumers — they return everything in one JSON response.

---

## Session management — a deliberate limitation

`session_manager.py` stores each knowledge base in a plain Python dictionary in the
backend process's memory. That's intentional for a learning/demo project, but it means:

- Restarting the backend loses all knowledge bases (the frontend will show "Session
  not found" and you'll need to rebuild).
- Running `uvicorn` with multiple worker processes (`--workers 4`, for example) will
  **not** work correctly, since each worker has its own separate memory and its own
  copy of `_SESSIONS` — a request could land on a worker that never built the session.
- For anything beyond local/single-user use, swap `session_manager.py` for a
  Redis-backed or database-backed store.

---

## A note on LangChain's fast-moving API (carried over from the single-file version)

1. **`RetrievalQA` and even `create_retrieval_chain` have moved.** LangChain 1.0
   slimmed the main `langchain` package down to agents/tools/chat models, and moved
   prebuilt chain helpers into a separate `langchain-classic` package. This project
   avoids that dependency entirely by building the retrieval step with LCEL primitives
   directly (`ChatPromptTemplate` + `ChatOpenAI.invoke`) in `rag_pipeline.py`.
2. **`langchain-community` is being sunset.** It still supplies `PyPDFLoader`,
   `TextLoader`, and `FAISS` here and works fine as of this writing — just expect a
   deprecation notice on import, and consider `langchain-chroma` as an eventual
   replacement for the vector store.

---

## Extending this project

- **Streaming pipeline progress**: add an SSE endpoint (`/documents/build/stream`) that
  yields one `StageInfo` event per stage as it completes, so the sidebar animates live
  again instead of showing the final result all at once.
- **Persistent vector store**: swap FAISS for `Chroma` with on-disk persistence, or
  a hosted store like Pinecone, so knowledge bases survive backend restarts.
- **Multi-user auth**: add an API key / login layer in front of the FastAPI routes if
  this ever leaves your own machine.
- **Dockerize**: a `docker-compose.yml` running the backend and frontend as two
  services is a natural next step once you're happy with the local setup.
