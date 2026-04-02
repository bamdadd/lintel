"""Tests for KnowledgeCache."""

from lintel.domain.knowledge.cache import KnowledgeCache
from lintel.domain.knowledge.models import ResearchNode


def _node(nid: str, topic: str = "t") -> ResearchNode:
    return ResearchNode(id=nid, topic=topic)


def test_put_and_get() -> None:
    cache = KnowledgeCache()
    n = _node("a")
    cache.put("auth", n)
    assert cache.get("auth") == [n]


def test_get_missing_topic() -> None:
    cache = KnowledgeCache()
    assert cache.get("nope") == []


def test_search_case_insensitive() -> None:
    cache = KnowledgeCache()
    cache.put("Authentication", _node("a"))
    cache.put("Database", _node("b"))
    results = cache.search("auth")
    assert len(results) == 1
    assert results[0].id == "a"


def test_clear() -> None:
    cache = KnowledgeCache()
    cache.put("x", _node("a"))
    cache.clear()
    assert len(cache) == 0
    assert cache.topics == []


def test_topics_property() -> None:
    cache = KnowledgeCache()
    cache.put("alpha", _node("a"))
    cache.put("beta", _node("b"))
    assert set(cache.topics) == {"alpha", "beta"}


def test_len_counts_all_nodes() -> None:
    cache = KnowledgeCache()
    cache.put("t", _node("a"))
    cache.put("t", _node("b"))
    cache.put("u", _node("c"))
    assert len(cache) == 3


def test_get_returns_copy() -> None:
    cache = KnowledgeCache()
    cache.put("t", _node("a"))
    result = cache.get("t")
    result.clear()
    assert len(cache.get("t")) == 1
