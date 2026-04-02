"""Tests for domain extraction types."""

from lintel.domain.extraction.types import (
    BoundedContext,
    DomainModel,
    EntityType,
    ExtractedEntity,
    FieldInfo,
    MethodInfo,
    Relationship,
    RelationshipKind,
)


def test_entity_type_values() -> None:
    assert EntityType.CLASS == "class"
    assert EntityType.PROTOCOL == "protocol"
    assert EntityType.DATACLASS == "dataclass"
    assert EntityType.ENUM == "enum"
    assert EntityType.INTERFACE == "interface"


def test_extracted_entity_frozen() -> None:
    entity = ExtractedEntity(
        name="Foo",
        entity_type=EntityType.CLASS,
        module_path="mod.foo",
    )
    assert entity.name == "Foo"
    assert entity.fields == ()
    assert entity.methods == ()


def test_field_info() -> None:
    f = FieldInfo(name="x", type_annotation="int", default="0")
    assert f.name == "x"
    assert f.default == "0"


def test_method_info() -> None:
    m = MethodInfo(name="run", parameters=("x", "y"), return_type="bool", is_async=True)
    assert m.is_async is True
    assert m.parameters == ("x", "y")


def test_relationship() -> None:
    r = Relationship(source="A", target="B", kind=RelationshipKind.INHERITS)
    assert r.kind == "inherits"


def test_bounded_context() -> None:
    bc = BoundedContext(name="billing", entity_names=("Invoice", "Payment"))
    assert len(bc.entity_names) == 2


def test_domain_model_defaults() -> None:
    dm = DomainModel()
    assert dm.entities == ()
    assert dm.relationships == ()
    assert dm.bounded_contexts == ()


def test_domain_model_with_data() -> None:
    entity = ExtractedEntity(
        name="Order", entity_type=EntityType.DATACLASS, module_path="shop.orders"
    )
    dm = DomainModel(entities=(entity,))
    assert len(dm.entities) == 1
    assert dm.entities[0].name == "Order"
