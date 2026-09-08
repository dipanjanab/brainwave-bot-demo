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
        stop_words = {
            "a", "an", "and", "are", "can", "does", "how", "is", "of", "the", "what",
        }
        query_words = {
            word
            for word in re.findall(r"[a-z0-9]+", query.lower())
            if word not in stop_words
        }
        lexical_scores = [
            len(query_words & set(re.findall(r"[a-z0-9]+", text.lower())))
            for text in self.documents
        ]
        if lexical_scores and max(lexical_scores) > 0:
            ranked = sorted(
                zip(lexical_scores, self.documents),
                key=lambda item: item[0],
                reverse=True,
            )
            return [text for _, text in ranked[:k]]
        return []

