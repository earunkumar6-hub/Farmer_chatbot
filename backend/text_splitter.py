"""Pipeline stage 2: split loaded documents into retrievable chunks."""
from typing import List

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter


def split_documents(docs: List[Document], chunk_size: int, chunk_overlap: int) -> List[Document]:
    """Split documents into overlapping chunks sized for embedding and retrieval."""
    splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    return splitter.split_documents(docs)
