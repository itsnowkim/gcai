from tree_sitter import Node

from app.analyzers.symbols.c import CSymbolExtractor
from app.schemas.symbols import ExtractedSymbol, SymbolKind


class CppSymbolExtractor(CSymbolExtractor):
    def _extract_symbols(self) -> list[ExtractedSymbol]:
        return self._extract_nodes(self.parsed_source.tree.root_node.named_children, scope=None)

    def _extract_nodes(self, nodes, scope: str | None) -> list[ExtractedSymbol]:
        symbols: list[ExtractedSymbol] = []
        for child in nodes:
            if child.type == "namespace_definition":
                symbols.extend(self._extract_namespace(child, scope))
            elif child.type == "template_declaration":
                symbols.extend(self._extract_nodes(child.named_children, scope))
            elif child.type in {"class_specifier", "struct_specifier"}:
                kind = SymbolKind.CLASS if child.type == "class_specifier" else SymbolKind.STRUCT
                symbols.extend(self._extract_class_like(child, scope=scope, kind=kind))
            elif child.type in {"enum_specifier", "union_specifier"}:
                symbols.extend(self._extract_aggregate(child, scope=scope))
            elif child.type == "function_definition":
                function_symbol = self._build_scoped_function(child, scope=scope)
                symbols.append(function_symbol)
                symbols.extend(self._extract_local_variables(child, function_symbol.qualified_name))
            elif child.type == "declaration":
                symbols.extend(self._build_variable_symbols(child, parent_name=scope))
        return symbols

    def _extract_namespace(self, node: Node, scope: str | None) -> list[ExtractedSymbol]:
        name = self._node_name(node.child_by_field_name("name")) or "<anonymous-namespace>"
        body = node.child_by_field_name("body")
        qualified_name = self._compose_qualified_name(name, scope)
        symbols = [
            self._make_symbol(
                kind=SymbolKind.NAMESPACE,
                name=name,
                qualified_name=qualified_name,
                signature=self._aggregate_signature(node),
                node=node,
                code=self._node_text(node),
                body=self._node_text(body),
                parent_name=scope,
            )
        ]
        if body is not None:
            symbols.extend(self._extract_nodes(body.named_children, scope=qualified_name))
        return symbols

    def _extract_class_like(self, node: Node, *, scope: str | None, kind: SymbolKind) -> list[ExtractedSymbol]:
        class_name = self._node_name(node.child_by_field_name("name")) or "<anonymous-class>"
        body = node.child_by_field_name("body")
        qualified_name = self._compose_qualified_name(class_name, scope)
        symbols = [
            self._make_symbol(
                kind=kind,
                name=class_name,
                qualified_name=qualified_name,
                signature=self._aggregate_signature(node),
                node=node,
                code=self._node_text(node),
                body=self._node_text(body),
                parent_name=scope,
            )
        ]

        if body is None:
            return symbols

        for child in body.named_children:
            if child.type == "field_declaration":
                symbols.extend(self._build_variable_symbols(child, parent_name=qualified_name))
            elif child.type == "function_definition":
                method_symbol = self._build_method(child, qualified_name)
                symbols.append(method_symbol)
                symbols.extend(self._extract_local_variables(child, method_symbol.qualified_name))
            elif child.type in {"class_specifier", "struct_specifier"}:
                nested_kind = SymbolKind.CLASS if child.type == "class_specifier" else SymbolKind.STRUCT
                symbols.extend(self._extract_class_like(child, scope=qualified_name, kind=nested_kind))
            elif child.type in {"enum_specifier", "union_specifier"}:
                symbols.extend(self._extract_aggregate(child, scope=qualified_name))

        return symbols

    def _build_method(self, node: Node, class_name: str) -> ExtractedSymbol:
        declarator = node.child_by_field_name("declarator")
        name = self._declarator_name(declarator) or "<anonymous-method>"
        body = node.child_by_field_name("body")
        return self._make_symbol(
            kind=SymbolKind.METHOD,
            name=name,
            qualified_name=self._compose_qualified_name(name, class_name),
            signature=self._signature_without_body(node),
            node=node,
            code=self._node_text(node),
            body=self._node_text(body),
            parent_name=class_name,
        )

    def _build_scoped_function(self, node: Node, *, scope: str | None) -> ExtractedSymbol:
        declarator = node.child_by_field_name("declarator")
        name = self._declarator_name(declarator) or "<anonymous-function>"
        body = node.child_by_field_name("body")
        return self._make_symbol(
            kind=SymbolKind.FUNCTION,
            name=name,
            qualified_name=self._compose_qualified_name(name, scope),
            signature=self._signature_without_body(node),
            node=node,
            code=self._node_text(node),
            body=self._node_text(body),
            parent_name=scope,
        )
