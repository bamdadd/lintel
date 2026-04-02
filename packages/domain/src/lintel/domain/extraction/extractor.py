"""Domain model extractor — analyses Python source to extract entities and relationships."""

from __future__ import annotations

import ast

from lintel.domain.extraction.types import (
    BoundedContext,
    EntityType,
    ExtractedEntity,
    FieldInfo,
    MethodInfo,
    Relationship,
    RelationshipKind,
)


class DomainModelExtractor:
    """Extracts domain model entities from Python source code."""

    def extract_from_module(
        self, source_code: str, *, module_path: str = ""
    ) -> list[ExtractedEntity]:
        """Parse source code and extract all domain entities."""
        tree = ast.parse(source_code)
        entities: list[ExtractedEntity] = []
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.ClassDef):
                entity = self._extract_class(node, module_path)
                if entity is not None:
                    entities.append(entity)
        return entities

    def build_relationships(self, entities: list[ExtractedEntity]) -> list[Relationship]:
        """Infer relationships between extracted entities."""
        entity_names = {e.name for e in entities}
        relationships: list[Relationship] = []

        for entity in entities:
            for dep in entity.dependencies:
                if dep in entity_names:
                    relationships.append(
                        Relationship(
                            source=entity.name,
                            target=dep,
                            kind=RelationshipKind.INHERITS,
                        )
                    )
            # Field-type dependencies
            for f in entity.fields:
                for name in entity_names:
                    if name in f.type_annotation and name != entity.name:
                        relationships.append(
                            Relationship(
                                source=entity.name,
                                target=name,
                                kind=RelationshipKind.DEPENDS_ON,
                            )
                        )
        return relationships

    def identify_bounded_contexts(self, entities: list[ExtractedEntity]) -> list[BoundedContext]:
        """Group entities into bounded contexts by module path prefix."""
        contexts: dict[str, list[str]] = {}
        for entity in entities:
            parts = entity.module_path.rsplit(".", maxsplit=1)
            prefix = parts[0] if len(parts) > 1 else entity.module_path or "default"
            contexts.setdefault(prefix, []).append(entity.name)

        return [
            BoundedContext(
                name=ctx_name,
                entity_names=tuple(sorted(names)),
            )
            for ctx_name, names in sorted(contexts.items())
        ]

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _extract_class(self, node: ast.ClassDef, module_path: str) -> ExtractedEntity | None:
        """Extract an entity from a class definition AST node."""
        entity_type = self._classify(node)
        fields = self._extract_fields(node)
        methods = self._extract_methods(node)
        docstring = ast.get_docstring(node) or ""
        dependencies = self._extract_base_names(node)

        return ExtractedEntity(
            name=node.name,
            entity_type=entity_type,
            module_path=module_path,
            fields=tuple(fields),
            methods=tuple(methods),
            docstring=docstring,
            dependencies=tuple(dependencies),
        )

    @staticmethod
    def _classify(node: ast.ClassDef) -> EntityType:
        """Determine the entity type from decorators and base classes."""
        decorator_names = {DomainModelExtractor._decorator_name(d) for d in node.decorator_list}
        base_names = {DomainModelExtractor._base_name(b) for b in node.bases}

        if "dataclass" in decorator_names:
            return EntityType.DATACLASS
        if "Protocol" in base_names:
            return EntityType.PROTOCOL
        if "Enum" in base_names or "StrEnum" in base_names or "IntEnum" in base_names:
            return EntityType.ENUM
        if "ABC" in base_names or any("Abstract" in name for name in base_names if name):
            return EntityType.INTERFACE
        return EntityType.CLASS

    @staticmethod
    def _decorator_name(node: ast.expr) -> str:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            return node.func.id
        if isinstance(node, ast.Attribute):
            return node.attr
        return ""

    @staticmethod
    def _base_name(node: ast.expr) -> str:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            return node.attr
        if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name):
            return node.value.id
        return ""

    @staticmethod
    def _extract_base_names(node: ast.ClassDef) -> list[str]:
        names: list[str] = []
        for base in node.bases:
            name = DomainModelExtractor._base_name(base)
            if name:
                names.append(name)
        return names

    @staticmethod
    def _extract_fields(node: ast.ClassDef) -> list[FieldInfo]:
        fields: list[FieldInfo] = []
        for child in node.body:
            if isinstance(child, ast.AnnAssign) and isinstance(child.target, ast.Name):
                type_ann = ast.unparse(child.annotation) if child.annotation else "Any"
                default = ast.unparse(child.value) if child.value else None
                fields.append(
                    FieldInfo(
                        name=child.target.id,
                        type_annotation=type_ann,
                        default=default,
                    )
                )
        return fields

    @staticmethod
    def _extract_methods(node: ast.ClassDef) -> list[MethodInfo]:
        methods: list[MethodInfo] = []
        for child in node.body:
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                params = [a.arg for a in child.args.args if a.arg != "self" and a.arg != "cls"]
                ret = ast.unparse(child.returns) if child.returns else "None"
                methods.append(
                    MethodInfo(
                        name=child.name,
                        parameters=tuple(params),
                        return_type=ret,
                        is_async=isinstance(child, ast.AsyncFunctionDef),
                    )
                )
        return methods
