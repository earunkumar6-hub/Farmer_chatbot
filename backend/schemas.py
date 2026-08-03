"""Pydantic models for FastAPI request bodies and response payloads."""
from typing import List

from pydantic import BaseModel


class StageInfo(BaseModel):
    """One step of the visual pipeline (used for both indexing and query pipelines)."""
    icon: str
    name: str
    status: str  # "done" | "error"
    detail: str = ""


class BuildResponse(BaseModel):
    session_id: str
    stages: List[StageInfo]


class ChatRequest(BaseModel):
    session_id: str
    query: str


class ChatResponse(BaseModel):
    answer: str
    sources: List[str]
    stages: List[StageInfo]


class HealthResponse(BaseModel):
    status: str
    api_key_configured: bool
