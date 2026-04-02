"""Tests for DomainModelExtractor."""

from lintel.domain.extraction.extractor import DomainModelExtractor
from lintel.domain.extraction.types import EntityType, RelationshipKind

SAMPLE_SOURCE = '''\
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol


class Status(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"


@dataclass(frozen=True)
class Order:
    """An order in the system."""

    order_id: str
    status: Status
    total: float = 0.0

    def validate(self) -> bool:
        return self.total >= 0


class OrderRepository(Protocol):
    def get(self, order_id: str) -> Order: ...


class BaseService:
    pass


class OrderService(BaseService):
    async def process(self, order: Order) -> None:
        pass
'''


def test_extract_from_module_finds_all_classes() -> None:
    extractor = DomainModelExtractor()
    entities = extractor.extract_from_module(SAMPLE_SOURCE, module_path="shop.orders")
    names = {e.name for e in entities}
    assert names == {"Status", "Order", "OrderRepository", "BaseService", "OrderService"}


def test_classifies_enum() -> None:
    extractor = DomainModelExtractor()
    entities = extractor.extract_from_module(SAMPLE_SOURCE)
    status = next(e for e in entities if e.name == "Status")
    assert status.entity_type == EntityType.ENUM


def test_classifies_dataclass() -> None:
    extractor = DomainModelExtractor()
    entities = extractor.extract_from_module(SAMPLE_SOURCE)
    order = next(e for e in entities if e.name == "Order")
    assert order.entity_type == EntityType.DATACLASS


def test_classifies_protocol() -> None:
    extractor = DomainModelExtractor()
    entities = extractor.extract_from_module(SAMPLE_SOURCE)
    repo = next(e for e in entities if e.name == "OrderRepository")
    assert repo.entity_type == EntityType.PROTOCOL


def test_extracts_fields() -> None:
    extractor = DomainModelExtractor()
    entities = extractor.extract_from_module(SAMPLE_SOURCE)
    order = next(e for e in entities if e.name == "Order")
    field_names = {f.name for f in order.fields}
    assert "order_id" in field_names
    assert "status" in field_names
    assert "total" in field_names
    total = next(f for f in order.fields if f.name == "total")
    assert total.default == "0.0"


def test_extracts_methods() -> None:
    extractor = DomainModelExtractor()
    entities = extractor.extract_from_module(SAMPLE_SOURCE)
    order = next(e for e in entities if e.name == "Order")
    method_names = {m.name for m in order.methods}
    assert "validate" in method_names


def test_extracts_async_methods() -> None:
    extractor = DomainModelExtractor()
    entities = extractor.extract_from_module(SAMPLE_SOURCE)
    svc = next(e for e in entities if e.name == "OrderService")
    process = next(m for m in svc.methods if m.name == "process")
    assert process.is_async is True


def test_extracts_docstring() -> None:
    extractor = DomainModelExtractor()
    entities = extractor.extract_from_module(SAMPLE_SOURCE)
    order = next(e for e in entities if e.name == "Order")
    assert "order in the system" in order.docstring.lower()


def test_extracts_dependencies() -> None:
    extractor = DomainModelExtractor()
    entities = extractor.extract_from_module(SAMPLE_SOURCE)
    svc = next(e for e in entities if e.name == "OrderService")
    assert "BaseService" in svc.dependencies


def test_build_relationships_inherits() -> None:
    extractor = DomainModelExtractor()
    entities = extractor.extract_from_module(SAMPLE_SOURCE, module_path="shop")
    rels = extractor.build_relationships(entities)
    inherits = [r for r in rels if r.kind == RelationshipKind.INHERITS]
    assert any(r.source == "OrderService" and r.target == "BaseService" for r in inherits)


def test_build_relationships_depends_on() -> None:
    extractor = DomainModelExtractor()
    entities = extractor.extract_from_module(SAMPLE_SOURCE, module_path="shop")
    rels = extractor.build_relationships(entities)
    deps = [r for r in rels if r.kind == RelationshipKind.DEPENDS_ON]
    assert any(r.source == "Order" and r.target == "Status" for r in deps)


def test_identify_bounded_contexts() -> None:
    extractor = DomainModelExtractor()
    src1 = "class Foo: pass"
    src2 = "class Bar: pass"
    e1 = extractor.extract_from_module(src1, module_path="billing.models")
    e2 = extractor.extract_from_module(src2, module_path="shipping.models")
    contexts = extractor.identify_bounded_contexts(e1 + e2)
    ctx_names = {c.name for c in contexts}
    assert "billing" in ctx_names
    assert "shipping" in ctx_names


def test_identify_bounded_contexts_same_module() -> None:
    extractor = DomainModelExtractor()
    entities = extractor.extract_from_module(SAMPLE_SOURCE, module_path="shop.orders")
    contexts = extractor.identify_bounded_contexts(entities)
    assert len(contexts) == 1
    assert contexts[0].name == "shop"
