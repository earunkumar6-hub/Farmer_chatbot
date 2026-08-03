"""Renders the indexing/query pipeline stages as vertical status cards
(designed for the sidebar), and provides helpers for applying live streamed
events onto the stage list."""
from typing import Any, Dict, List

import streamlit as st

from styles import STATUS_STYLE


def render_pipeline(stages, placeholder, title=None):
    """Draw a vertical stack of stage cards into the given st.empty() placeholder."""
    with placeholder.container():
        if title:
            st.markdown(f"**{title}**")
        for i, stage in enumerate(stages):
            style = STATUS_STYLE.get(stage["status"], STATUS_STYLE["pending"])
            st.markdown(
                f"""<div class="stage-card-v" style="background:{style['bg']};
                    border: 1px solid {style['text']}55;">
                    <div class="stage-row">
                        <div class="stage-icon-v">{stage['icon']}</div>
                        <div>
                            <div class="stage-name-v">{stage['name']}</div>
                            <div class="stage-badge-v" style="color:{style['text']};">{style['badge']}</div>
                        </div>
                    </div>
                    <div class="stage-detail-v">{stage.get('detail', '')}</div>
                </div>""",
                unsafe_allow_html=True,
            )
            if i != len(stages) - 1:
                st.markdown("<div class='arrow-v'>↓</div>", unsafe_allow_html=True)


def fresh_index_stages() -> List[Dict[str, str]]:
    """The 4 indexing-pipeline stages, all pending — shown before a build runs."""
    return [
        {"icon": "📂", "name": "Load Documents", "status": "pending", "detail": ""},
        {"icon": "✂️", "name": "Split into Chunks", "status": "pending", "detail": ""},
        {"icon": "🧬", "name": "Generate Embeddings", "status": "pending", "detail": ""},
        {"icon": "🗄️", "name": "Store in Vector DB", "status": "pending", "detail": ""},
    ]


def fresh_query_stages() -> List[Dict[str, str]]:
    """The 5 query-pipeline stages, all pending — shown before any question is asked."""
    return [
        {"icon": "❓", "name": "User Query", "status": "pending", "detail": ""},
        {"icon": "🧬", "name": "Embed Query", "status": "pending", "detail": ""},
        {"icon": "🔍", "name": "Similarity Search", "status": "pending", "detail": ""},
        {"icon": "📚", "name": "Assemble Context", "status": "pending", "detail": ""},
        {"icon": "🤖", "name": "LLM Answer", "status": "pending", "detail": ""},
    ]


def apply_stage_event(stages: List[Dict[str, str]], event: Dict[str, Any]) -> None:
    """Mutate ``stages`` in place from a streamed 'stage' event.

    The backend addresses stages by index, so the frontend's placeholder list
    and the backend's stage definitions stay in lockstep.
    """
    idx = event.get("index")
    if idx is None or not (0 <= idx < len(stages)):
        return
    stages[idx]["status"] = event.get("status", "done")
    detail = event.get("detail", "")
    # An 'active' event carries no metrics yet; don't blank out a prior detail
    # unless the backend actually supplied replacement text.
    if detail or event.get("status") == "done":
        stages[idx]["detail"] = detail


def mark_remaining_failed(stages: List[Dict[str, str]]) -> None:
    """On error, flip any still-pending/active stages to 'error' so the sidebar
    doesn't sit forever showing a spinner-ish 'RUNNING…' badge."""
    for s in stages:
        if s["status"] in ("pending", "active"):
            s["status"] = "error"


def stages_from_api(stage_dicts) -> List[Dict[str, str]]:
    """Convert a blocking-endpoint StageInfo list into render_pipeline's shape."""
    return [
        {
            "icon": s["icon"],
            "name": s["name"],
            "status": s["status"] if s["status"] in ("done", "error") else "done",
            "detail": s.get("detail", ""),
        }
        for s in stage_dicts
    ]
