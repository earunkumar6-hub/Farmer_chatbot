"""Pipeline stage 3: construct the OpenAI embeddings client used at indexing
and query time."""
from langchain_openai import OpenAIEmbeddings

from backend.config import settings


def get_embeddings() -> OpenAIEmbeddings:
    """Return an OpenAI embeddings client configured from settings."""
    return OpenAIEmbeddings(model=settings.embedding_model, api_key=settings.openai_api_key)
