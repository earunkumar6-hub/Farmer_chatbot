"""Query-time helper: construct the chat LLM used to generate answers."""
from langchain_openai import ChatOpenAI

from backend.config import settings


def get_llm() -> ChatOpenAI:
    """Return a ChatOpenAI client configured from settings."""
    return ChatOpenAI(model=settings.chat_model, temperature=0, api_key=settings.openai_api_key)
