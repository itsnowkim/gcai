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
            elif child.type == "alias_declaration":
                alias_symbol = self._build_alias(child, scope)
                if alias_symbol is not None:
                    symbols.append(alias_symbol)
            elif child.type == "using_declaration":
                symbols.append(self._build_import(child, scope))
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
                super_types=self._base_types(node),
            )
        ]

        if body is None:
            return symbols

        for child in body.named_children:
            if child.type == "field_declaration":
                symbols.extend(self._build_variable_symbols(child, parent_name=qualified_name))
                symbols.extend(self._extract_embedded_declarations(child, scope=qualified_name))
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

    def _extract_embedded_declarations(self, node: Node, *, scope: str | None) -> list[ExtractedSymbol]:
        symbols: list[ExtractedSymbol] = []
        for child in node.named_children:
            if child.type in {"class_specifier", "struct_specifier"}:
                nested_kind = SymbolKind.CLASS if child.type == "class_specifier" else SymbolKind.STRUCT
                symbols.extend(self._extract_class_like(child, scope=scope, kind=nested_kind))
            elif child.type in {"enum_specifier", "union_specifier"}:
                symbols.extend(self._extract_aggregate(child, scope=scope))
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
            parameters=self._parameter_texts(declarator),
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
            parameters=self._parameter_texts(declarator),
        )

    def _build_alias(self, node: Node, scope: str | None) -> ExtractedSymbol | None:
        alias_name = next(
            (self._node_text(child).strip() for child in node.named_children if child.type in {"type_identifier", "identifier"}),
            None,
        )
        aliased_type = next(
            (
                self._node_text(child).strip()
                for child in node.named_children
                if child.type not in {"type_identifier", "identifier"}
            ),
            None,
        )
        if alias_name is None or aliased_type is None:
            return None
        return self._make_symbol(
            kind=SymbolKind.TYPE_ALIAS,
            name=alias_name,
            qualified_name=self._compose_qualified_name(alias_name, scope),
            signature=self._node_text(node).strip(),
            node=node,
            code=self._node_text(node),
            body=None,
            parent_name=scope,
            aliased_type=aliased_type,
        )

    def _build_import(self, node: Node, scope: str | None) -> ExtractedSymbol:
        target = next((child for child in node.named_children if child.type == "qualified_identifier"), None)
        imported_name = self._node_text(target).strip() if target is not None else "<anonymous-import>"
        return self._make_symbol(
            kind=SymbolKind.IMPORT,
            name=imported_name.split("::")[-1],
            qualified_name=imported_name,
            signature=self._node_text(node).strip(),
            node=node,
            code=self._node_text(node),
            body=None,
            parent_name=scope,
        )

    def _base_types(self, node: Node) -> list[str]:
        base_clause = next((child for child in node.named_children if child.type == "base_class_clause"), None)
        if base_clause is None:
            return []
        base_types: list[str] = []
        for child in base_clause.named_children:
            if child.type in {"type_identifier", "qualified_identifier", "template_type"}:
                text = self._node_text(child).strip()
                if text and text not in base_types:
                    base_types.append(text)
        return base_types

    def _parameter_texts(self, declarator: Node | None) -> list[str]:
        if declarator is None:
            return []
        parameter_list = declarator.child_by_field_name("parameters")
        if parameter_list is None:
            for child in declarator.named_children:
                parameters = self._parameter_texts(child)
                if parameters:
                    return parameters
            return []
        return [
            self._node_text(child).strip()
            for child in parameter_list.named_children
            if child.type == "parameter_declaration"
        ]
