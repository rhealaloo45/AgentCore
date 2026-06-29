"""Unit tests for Phase 4 memory: conversation, persistent, knowledge."""

from langchain_core.messages import AIMessage, HumanMessage

from roscoe.memory import ConversationMemory, KnowledgeMemory, PersistentMemory


# --- conversation ---


def test_conversation_recalls_earlier_turn():
    mem = ConversationMemory(window_size=10)
    mem.add("s1", HumanMessage(content="My name is Rhea"), AIMessage(content="Hi Rhea"))
    history = mem.get("s1")
    assert len(history) == 2
    assert "Rhea" in history[0].content


def test_conversation_window_trims():
    mem = ConversationMemory(window_size=2)
    for i in range(5):
        mem.add("s1", HumanMessage(content=f"m{i}"))
    history = mem.get("s1")
    assert len(history) == 2
    assert history[-1].content == "m4"  # keeps most recent


def test_conversation_sessions_isolated():
    mem = ConversationMemory()
    mem.add("a", HumanMessage(content="x"))
    assert mem.get("b") == []


# --- persistent ---


def test_persistent_set_get_all():
    mem = PersistentMemory(backend="sqlite", connection=":memory:")
    mem.set("u1", "department", "Engineering")
    assert mem.get("u1", "department") == "Engineering"
    assert mem.all("u1") == {"department": "Engineering"}


def test_persistent_survives_across_instances(tmp_path):
    db = str(tmp_path / "facts.db")
    run1 = PersistentMemory(connection=db)
    run1.set("u1", "manager", "Priya")
    run1.close()

    run2 = PersistentMemory(connection=db)  # simulate a new run
    assert run2.get("u1", "manager") == "Priya"
    run2.close()


def test_persistent_unknown_backend_raises():
    import pytest

    with pytest.raises(NotImplementedError):
        PersistentMemory(backend="postgres", connection="postgres://x")


# --- knowledge ---


def test_knowledge_returns_relevant_docs_above_threshold():
    km = KnowledgeMemory.from_texts(
        [
            "The liability cap is 2x the contract value.",
            "Payment terms are net 30 days.",
            "The office is open Monday to Friday.",
        ],
        top_k=2,
        score_threshold=0.2,
    )
    docs = km.retrieve("What is the liability cap?")
    assert docs
    assert "liability" in docs[0].page_content.lower()
    assert docs[0].metadata["score"] >= 0.2


def test_knowledge_threshold_filters_out_irrelevant():
    km = KnowledgeMemory.from_texts(
        ["completely unrelated text about gardening"],
        score_threshold=0.9,
    )
    assert km.retrieve("quantum computing finance") == []
