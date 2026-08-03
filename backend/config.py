"""Application configuration, loaded from environment variables / a .env file.

The API key lives only here, on the server side. The frontend never sees it —
it just talks to this backend over HTTP.
"""
import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    openai_api_key: str = os.environ.get("OPENAI_API_KEY", "").strip()
    embedding_model: str = os.environ.get("EMBEDDING_MODEL", "text-embedding-3-small")
    chat_model: str = os.environ.get("CHAT_MODEL", "gpt-4o-mini")
    default_chunk_size: int = int(os.environ.get("CHUNK_SIZE", "800"))
    default_chunk_overlap: int = int(os.environ.get("CHUNK_OVERLAP", "100"))
    retriever_k: int = int(os.environ.get("RETRIEVER_K", "4"))


settings = Settings()
