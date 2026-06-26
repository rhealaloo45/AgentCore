"""Knowledge memory — RAG-style retrieval into context.

Wraps a retriever and pulls the most relevant documents for a query, filtered by a
similarity threshold and capped at ``top_k``. Any LangChain retriever plugs in via
the constructor (Azure AI Search, FAISS, Chroma, ...). For local/dev and tests,
``from_texts`` builds a dependency-free keyword retriever — pass an ``embeddings``
object to build a real vector store instead.
"""

from __future__ import annotations

import re
from typing import Any

from langchain_core.documents import Document


class KnowledgeMemory:
    """Retrieves relevant documents for a query."""

    def __init__(
        self,
        retriever: Any,
        top_k: int = 3,
        score_threshold: float = 0.0,
    ) -> None:
        self._retriever = retriever
        self.top_k = top_k
        self.score_threshold = score_threshold

    @classmethod
    def from_texts(
        cls,
        texts: list[str],
        embeddings: Any | None = None,
        top_k: int = 3,
        score_threshold: float = 0.0,
        metadatas: list[dict[str, Any]] | None = None,
        **vector_kwargs: Any,
    ) -> "KnowledgeMemory":
        """Build from raw texts.

        With ``embeddings`` -> a FAISS vector store. Without -> a keyword retriever
        (no ML deps), suitable for local dev and tests. ``metadatas`` (e.g. a per-text
        ``{"source": "policy.pdf"}``) is carried onto the documents so callers can cite
        the source of a retrieved chunk.
        """
        if embeddings is not None:
            from langchain_community.vectorstores import FAISS

            store = FAISS.from_texts(
                texts, embeddings, metadatas=metadatas, **vector_kwargs
            )
            retriever = store.as_retriever(search_kwargs={"k": top_k})
            return cls(retriever, top_k=top_k, score_threshold=score_threshold)

        metas = metadatas or [{} for _ in texts]
        docs = [Document(page_content=t, metadata=dict(m)) for t, m in zip(texts, metas)]
        return cls(
            _KeywordRetriever(docs),
            top_k=top_k,
            score_threshold=score_threshold,
        )

    def retrieve(self, query: str) -> list[Document]:
        """Return up to ``top_k`` documents scoring at/above the threshold."""
        if isinstance(self._retriever, _KeywordRetriever):
            scored = self._retriever.search(query)
        else:
            docs = self._retriever.invoke(query)
            scored = [(d, float(d.metadata.get("score", 1.0))) for d in docs]

        out: list[Document] = []
        for doc, score in scored:
            if score >= self.score_threshold:
                doc.metadata["score"] = round(score, 4)
                out.append(doc)
        return out[: self.top_k]


class _KeywordRetriever:
    """Deterministic, dependency-free retriever scoring by token overlap."""

    def __init__(self, documents: list[Document]) -> None:
        self._docs = documents

    @staticmethod
    def _tokens(text: str) -> set[str]:
        return set(re.findall(r"[a-z0-9]+", text.lower()))

    def search(self, query: str) -> list[tuple[Document, float]]:
        q = self._tokens(query)
        if not q:
            return []
        scored = []
        for doc in self._docs:
            overlap = len(q & self._tokens(doc.page_content))
            scored.append((doc, overlap / len(q)))
        scored.sort(key=lambda pair: pair[1], reverse=True)
        return scored
