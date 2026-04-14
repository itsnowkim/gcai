from tree_sitter import Node

from app.analyzers.symbols.base import BaseSymbolExtractor
from app.schemas.symbols import ExtractedSymbol, SymbolKind


class CSymbolExtractor(BaseSymbolExtractor):
    def _extract_symbols(self) -> list[ExtractedSymbol]:
        symbols: list[ExtractedSymbol] = []
        root = self.parsed_source.tree.root_node

        for child in root.named_children:
            if child.type == "function_definition":
                function_symbol = self._build_function(child)
                symbols.append(function_symbol)
                symbols.extend(self._extract_local_variables(child, function_symbol.qualified_name))
            elif child.type == "declaration":
                symbols.extend(self._build_variable_symbols(child, parent_name=None))
            elif child.type == "type_definition":
                symbols.extend(self._extract_type_definition(child))
            elif child.type in {"struct_specifier", "union_specifier", "enum_specifier"}:
                symbols.extend(self._extract_aggregate(child, scope=None))

        return symbols

    def _build_function(self, node: Node) -> ExtractedSymbol:
        declarator = node.child_by_field_name("declarator")
        name = self._declarator_name(declarator) or "<anonymous-function>"
        body = node.child_by_field_name("body")
        return self._make_symbol(
            kind=SymbolKind.FUNCTION,
            name=name,
            qualified_name=name,
            signature=self._signature_without_body(node),
            node=node,
            code=self._node_text(node),
            body=self._node_text(body),
            parent_name=None,
        )

    def _extract_local_variables(self, node: Node, parent_name: str) -> list[ExtractedSymbol]:
        body = node.child_by_field_name("body")
        if body is None:
            return []

        variables: list[ExtractedSymbol] = []
        for child in body.named_children:
            if child.type == "declaration":
                variables.extend(self._build_variable_symbols(child, parent_name=parent_name))
        return variables

    def _build_variable_symbols(self, node: Node, parent_name: str | None) -> list[ExtractedSymbol]:
        symbols: list[ExtractedSymbol] = []
        for declarator in self._variable_declarators(node):
            name = self._declarator_name(declarator)
            if name is None:
                continue
            qualified_name = self._compose_qualified_name(name, parent_name)
            symbols.append(
                self._make_symbol(
                    kind=SymbolKind.VARIABLE,
                    name=name,
                    qualified_name=qualified_name,
                    signature=self._node_text(node).strip(),
                    node=declarator,
                    code=self._node_text(node),
                    body=None,
                    parent_name=parent_name,
                )
            )
        return symbols

    def _variable_declarators(self, node: Node) -> list[Node]:
        return [
            child
            for child in node.named_children
            if child.type
            in {"init_declarator", "identifier", "field_identifier", "pointer_declarator", "array_declarator"}
        ]

    def _declarator_name(self, node: Node | None) -> str | None:
        if node is None:
            return None
        if node.type in {"identifier", "field_identifier"}:
            return self._node_name(node)
        for child in node.named_children:
            name = self._declarator_name(child)
            if name is not None:
                return name
        return None

    def _signature_without_body(self, node: Node) -> str:
        body = node.child_by_field_name("body")
        end_byte = body.start_byte if body is not None else node.end_byte
        return self.source[node.start_byte:end_byte].decode("utf-8").strip()

    def _extract_type_definition(self, node: Node) -> list[ExtractedSymbol]:
        type_node = node.child_by_field_name("type")
        alias_node = node.child_by_field_name("declarator")
        symbols = self._extract_aggregate(type_node, scope=None)
        alias_name = self._node_name(alias_node)
        if alias_name and type_node is not None:
            kind = self._aggregate_kind(type_node)
            symbols.append(
                self._make_symbol(
                    kind=kind,
                    name=alias_name,
                    qualified_name=alias_name,
                    signature=self._node_text(node).strip(),
                    node=alias_node,
                    code=self._node_text(node),
                    body=None,
                    parent_name=None,
                )
            )
        return symbols

    def _extract_aggregate(self, node: Node | None, scope: str | None) -> list[ExtractedSymbol]:
        if node is None:
            return []
        kind = self._aggregate_kind(node)
        name = self._node_name(node.child_by_field_name("name")) or f"<anonymous-{kind}>"
        body = node.child_by_field_name("body")
        qualified_name = self._compose_qualified_name(name, scope)
        symbols = [
            self._make_symbol(
                kind=kind,
                name=name,
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
        if node.type == "enum_specifier":
            for child in body.named_children:
                if child.type == "enumerator":
                    member_name = self._node_name(child.child_by_field_name("name")) or self._node_name(child) or "<enum-member>"
                    symbols.append(
                        self._make_symbol(
                            kind=SymbolKind.ENUM_MEMBER,
                            name=member_name,
                            qualified_name=self._compose_qualified_name(member_name, qualified_name),
                            signature=self._node_text(child).strip(),
                            node=child,
                            code=self._node_text(child),
                            body=None,
                            parent_name=qualified_name,
                        )
                    )
        else:
            for child in body.named_children:
                if child.type == "field_declaration":
                    symbols.extend(self._build_variable_symbols(child, qualified_name))
        return symbols

    def _aggregate_kind(self, node: Node) -> SymbolKind:
        if node.type == "struct_specifier":
            return SymbolKind.STRUCT
        if node.type == "union_specifier":
            return SymbolKind.UNION
        return SymbolKind.ENUM

    def _aggregate_signature(self, node: Node) -> str:
        body = node.child_by_field_name("body")
        end_byte = body.start_byte if body is not None else node.end_byte
        return self.source[node.start_byte:end_byte].decode("utf-8").strip()
