"""Tests for architectural antipattern detection."""

import pytest

from lintel.skills_api.integration_scanning import detect_antipatterns


@pytest.mark.asyncio
async def test_detects_tight_coupling() -> None:
    nodes = [{"name": "service_a"}]
    edges = []
    coupling_scores = [
        {"service": "service_a", "efferent_coupling": 8},
    ]

    findings = await detect_antipatterns(nodes, edges, coupling_scores)
    tight = [f for f in findings if f["antipattern_type"] == "tight_coupling"]
    assert len(tight) == 1
    assert tight[0]["affected_nodes"] == ["service_a"]
    assert tight[0]["severity"] in ("medium", "high")


@pytest.mark.asyncio
async def test_detects_chatty_interface() -> None:
    nodes = [{"name": "svc_a"}, {"name": "svc_b"}]
    edges = [
        {"source": "svc_a", "target": "svc_b", "protocol": "http"},
        {"source": "svc_a", "target": "svc_b", "protocol": "http"},
        {"source": "svc_a", "target": "svc_b", "protocol": "http"},
        {"source": "svc_a", "target": "svc_b", "protocol": "http"},
    ]
    coupling_scores = []

    findings = await detect_antipatterns(nodes, edges, coupling_scores)
    chatty = [f for f in findings if f["antipattern_type"] == "chatty_interface"]
    assert len(chatty) == 1
    assert set(chatty[0]["affected_nodes"]) == {"svc_a", "svc_b"}


@pytest.mark.asyncio
async def test_detects_circular_dependency() -> None:
    nodes = [{"name": "alpha"}, {"name": "beta"}]
    edges = [
        {"source": "alpha", "target": "beta", "protocol": "http"},
        {"source": "beta", "target": "alpha", "protocol": "http"},
    ]
    coupling_scores = []

    findings = await detect_antipatterns(nodes, edges, coupling_scores)
    circular = [f for f in findings if f["antipattern_type"] == "circular_dependency"]
    assert len(circular) == 1
    assert set(circular[0]["affected_nodes"]) == {"alpha", "beta"}
    assert circular[0]["severity"] == "high"
