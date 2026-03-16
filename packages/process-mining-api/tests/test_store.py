"""Tests for process mining in-memory store."""

import pytest

from lintel.process_mining_api.store import InMemoryProcessMiningStore
from lintel.process_mining_api.types import (
    FlowDiagram,
    FlowEntry,
    FlowMetrics,
    FlowStep,
    ProcessFlowMap,
)


@pytest.fixture()
def store() -> InMemoryProcessMiningStore:
    return InMemoryProcessMiningStore()


@pytest.fixture()
def sample_map() -> ProcessFlowMap:
    return ProcessFlowMap(
        flow_map_id="m1",
        repository_id="r1",
        workflow_run_id="w1",
        status="pending",
        created_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
    )


async def test_create_and_get_map(
    store: InMemoryProcessMiningStore, sample_map: ProcessFlowMap
) -> None:
    await store.create_map(sample_map)
    result = await store.get_map("m1")
    assert result is not None
    assert result.repository_id == "r1"


async def test_list_maps_filter(
    store: InMemoryProcessMiningStore, sample_map: ProcessFlowMap
) -> None:
    await store.create_map(sample_map)
    assert len(await store.list_maps(repository_id="r1")) == 1
    assert len(await store.list_maps(repository_id="r999")) == 0


async def test_update_map_status(
    store: InMemoryProcessMiningStore, sample_map: ProcessFlowMap
) -> None:
    await store.create_map(sample_map)
    await store.update_map_status("m1", "completed")
    result = await store.get_map("m1")
    assert result is not None
    assert result.status == "completed"


async def test_add_and_get_flows(store: InMemoryProcessMiningStore) -> None:
    step = FlowStep(file_path="a.py", function_name="f", line_number=1, step_type="entrypoint")
    flow = FlowEntry(
        flow_id="f1",
        flow_map_id="m1",
        flow_type="http_request",
        name="GET /items",
        source=step,
    )
    await store.add_flows([flow])
    result = await store.get_flows("m1")
    assert len(result) == 1
    assert result[0].name == "GET /items"


async def test_get_flows_by_type(store: InMemoryProcessMiningStore) -> None:
    step = FlowStep(file_path="a.py", function_name="f", line_number=1, step_type="entrypoint")
    f1 = FlowEntry(flow_id="f1", flow_map_id="m1", flow_type="http_request", name="a", source=step)
    f2 = FlowEntry(
        flow_id="f2", flow_map_id="m1", flow_type="event_sourcing", name="b", source=step
    )
    await store.add_flows([f1, f2])
    assert len(await store.get_flows("m1", flow_type="http_request")) == 1


async def test_add_and_get_diagrams(store: InMemoryProcessMiningStore) -> None:
    d = FlowDiagram(
        diagram_id="d1",
        flow_map_id="m1",
        flow_type="http_request",
        title="HTTP",
        mermaid_source="sequenceDiagram",
    )
    await store.add_diagrams([d])
    result = await store.get_diagrams("m1")
    assert len(result) == 1


async def test_set_and_get_metrics(store: InMemoryProcessMiningStore) -> None:
    m = FlowMetrics(metrics_id="x1", flow_map_id="m1", total_flows=10)
    await store.set_metrics(m)
    result = await store.get_metrics("m1")
    assert result is not None
    assert result.total_flows == 10
