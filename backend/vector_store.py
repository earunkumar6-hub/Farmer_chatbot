"""Pipeline stage 4 (index build) plus the query-time retriever helper."""
from typing import List

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_community.vectorstores import FAISS


def build_vector_store(chunks: List[Document], embeddings: Embeddings) -> FAISS:
    """Embed chunks and store them in an in-memory FAISS index."""
    return FAISS.from_documents(chunks, embeddings)


def get_retriever(vectordb: FAISS, k: int = 4):
    """Return a retriever that returns the top-k most similar chunks for a query."""
    return vectordb.as_retriever(search_kwargs={"k": k})
