"""Pipeline stage 1: load documents from disk into LangChain Document objects."""
import os
from typing import List

from langchain_core.documents import Document
from langchain_community.document_loaders import PyPDFLoader, TextLoader


def load_documents(file_paths: List[str]) -> List[Document]:
    """Load PDF or TXT files from the given paths.

    Each resulting Document is tagged with metadata["source"] = the original
    filename, so answers can later be traced back to which file they came from.
    """
    docs: List[Document] = []
    for path in file_paths:
        suffix = os.path.splitext(path)[1].lower()
        loader = PyPDFLoader(path) if suffix == ".pdf" else TextLoader(path, encoding="utf-8")
        loaded = loader.load()
        for d in loaded:
            d.metadata["source"] = os.path.basename(path)
        docs.extend(loaded)
    return docs
