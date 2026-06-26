"""Legal agent tools.

Tools over a local contract store held in roscoe's knowledge memory (FAISS with
embeddings, or the dependency-free keyword retriever for dev/tests). Every result
carries its source document so the agent can cite it. SharePoint swaps in as the
document source at v0.2.0.
"""

from __future__ import annotations

from typing import Any

from roscoe.tools import tool

#: Naive risk signals scanned for by ``flag_risk`` — illustrative, not legal advice.
_RISK_TERMS = (
    "unlimited liability",
    "indemnify",
    "perpetual",
    "irrevocable",
    "auto-renew",
    "non-compete",
    "exclusive",
)


def build_tools(knowledge: Any) -> list:
    """Build legal tools bound to a knowledge-memory contract store."""

    def _cite(query: str) -> list[dict]:
        return [
            {"text": d.page_content, "source": d.metadata.get("source", "unknown")}
            for d in knowledge.retrieve(query)
        ]

    @tool
    def search_contracts(query: str) -> list:
        """Search the contract store and return matching passages with their source."""
        return _cite(query)

    @tool
    def extract_clause(clause_type: str) -> dict:
        """Find the passage most relevant to a clause type (e.g. 'liability',
        'termination') and return it with its source document for citation."""
        hits = _cite(clause_type)
        if not hits:
            return {"found": False, "clause_type": clause_type}
        top = hits[0]
        return {"found": True, "clause_type": clause_type, "text": top["text"], "source": top["source"]}

    @tool
    def compare_documents(topic_a: str, topic_b: str) -> dict:
        """Retrieve passages on two topics so they can be compared side by side."""
        return {"a": _cite(topic_a), "b": _cite(topic_b)}

    @tool
    def flag_risk(query: str) -> dict:
        """Scan the most relevant passages for common risk terms and flag any found."""
        hits = _cite(query)
        flags = []
        for hit in hits:
            lowered = hit["text"].lower()
            found = [term for term in _RISK_TERMS if term in lowered]
            if found:
                flags.append({"source": hit["source"], "terms": found})
        return {"risk_found": bool(flags), "flags": flags}

    return [search_contracts, extract_clause, compare_documents, flag_risk]
