from __future__ import annotations

import hashlib
import math
import re
from pathlib import Path

try:
    from langchain_core.documents import Document
    from langchain_core.embeddings import Embeddings
    from langchain_core.vectorstores import InMemoryVectorStore
except ImportError:  # Allows the deterministic demo to run before dependencies are installed.
    Document = None
    Embeddings = object
    InMemoryVectorStore = None


class HashEmbeddings(Embeddings):
    """Deterministic local embeddings for a zero-cost prototype, not production search."""

    def __init__(self, dimensions: int = 256):
        self.dimensions = dimensions

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for token in re.findall(r"[a-z0-9]+", text.lower()):
            digest = hashlib.sha256(token.encode()).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimensions
            vector[index] += 1.0
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)


class KnowledgeRetriever:
    def __init__(self, knowledge_path: Path):
        self.documents = [path.read_text(encoding="utf-8") for path in knowledge_path.glob("*.md")]
        self.store = None
        if InMemoryVectorStore and Document:
            docs = [Document(page_content=text) for text in self.documents]
            self.store = InMemoryVectorStore.from_documents(docs, HashEmbeddings())

    def retrieve(self, query: str, k: int = 2) -> list[str]:
        if self.store:
            return [doc.page_content for doc in self.store.similarity_search(query, k=k)]
        query_words = set(re.findall(r"[a-z0-9]+", query.lower()))
        ranked = sorted(
            self.documents,
            key=lambda text: len(query_words & set(re.findall(r"[a-z0-9]+", text.lower()))),
            reverse=True,
        )
        return ranked[:k]

