from tree_sitter import Node

from app.analyzers.symbols.base import BaseSymbolExtractor
from app.schemas.symbols import ExtractedSymbol, SymbolKind


class JavaSymbolExtractor(BaseSymbolExtractor):
    def _extract_symbols(self) -> list[ExtractedSymbol]:
        symbols: list[ExtractedSymbol] = []
        root = self.parsed_source.tree.root_node
        package_name = self._package_name(root)

        for child in root.named_children:
            if child.type == "import_declaration":
                symbols.append(self._build_import(child, package_name))
            else:
                symbols.extend(self._extract_declaration(child, scope=package_name))

        return symbols

    def _extract_declaration(self, node: Node, *, scope: str | None) -> list[ExtractedSymbol]:
        if node.type == "class_declaration":
            return self._extract_type(node, kind=SymbolKind.CLASS, scope=scope)
        if node.type == "interface_declaration":
            return self._extract_type(node, kind=SymbolKind.INTERFACE, scope=scope)
        if node.type == "enum_declaration":
            return self._extract_enum(node, scope=scope)
        if node.type == "record_declaration":
            return self._extract_type(node, kind=SymbolKind.RECORD, scope=scope)
        if node.type == "annotation_type_declaration":
            return self._extract_type(node, kind=SymbolKind.ANNOTATION, scope=scope)
        return []

    def _extract_type(self, node: Node, *, kind: SymbolKind, scope: str | None) -> list[ExtractedSymbol]:
        class_name = self._node_name(node.child_by_field_name("name")) or "<anonymous-type>"
        body = node.child_by_field_name("body")
        qualified_name = self._compose_qualified_name(class_name, scope)
        symbols = [
            self._make_symbol(
                kind=kind,
                name=class_name,
                qualified_name=qualified_name,
                signature=self._type_signature(node),
                node=node,
                code=self._node_text(node),
                body=self._node_text(body),
                parent_name=scope,
                super_types=self._type_super_types(node),
            )
        ]

        if body is None:
            return symbols

        for child in body.named_children:
            if child.type == "field_declaration":
                symbols.extend(self._build_variable_symbols(child, qualified_name))
            elif child.type == "method_declaration":
                method_symbol = self._build_method(child, qualified_name)
                symbols.append(method_symbol)
                symbols.extend(self._extract_local_variables(child, qualified_name))
            elif child.type == "constructor_declaration":
                constructor_symbol = self._build_constructor(child, qualified_name, class_name)
                symbols.append(constructor_symbol)
                symbols.extend(self._extract_local_variables(child, qualified_name, constructor_name=class_name))
            else:
                symbols.extend(self._extract_declaration(child, scope=qualified_name))

        return symbols

    def _extract_enum(self, node: Node, *, scope: str | None) -> list[ExtractedSymbol]:
        enum_name = self._node_name(node.child_by_field_name("name")) or "<anonymous-enum>"
        body = node.child_by_field_name("body")
        qualified_name = self._compose_qualified_name(enum_name, scope)
        symbols = [
            self._make_symbol(
                kind=SymbolKind.ENUM,
                name=enum_name,
                qualified_name=qualified_name,
                signature=self._type_signature(node),
                node=node,
                code=self._node_text(node),
                body=self._node_text(body),
                parent_name=scope,
                super_types=self._type_super_types(node),
            )
        ]
        if body is None:
            return symbols
        for child in body.named_children:
            if child.type == "enum_constant":
                name = self._node_name(child.child_by_field_name("name")) or self._node_name(child) or "<enum-member>"
                symbols.append(
                    self._make_symbol(
                        kind=SymbolKind.ENUM_MEMBER,
                        name=name,
                        qualified_name=self._compose_qualified_name(name, qualified_name),
                        signature=self._node_text(child).strip(),
                        node=child,
                        code=self._node_text(child),
                        body=None,
                        parent_name=qualified_name,
                    )
                )
            elif child.type == "enum_body_declarations":
                for member in child.named_children:
                    if member.type == "field_declaration":
                        symbols.extend(self._build_variable_symbols(member, qualified_name))
                    elif member.type == "method_declaration":
                        method_symbol = self._build_method(member, qualified_name)
                        symbols.append(method_symbol)
                        symbols.extend(self._extract_local_variables(member, qualified_name))
                    elif member.type == "constructor_declaration":
                        constructor_symbol = self._build_constructor(member, qualified_name, enum_name)
                        symbols.append(constructor_symbol)
                        symbols.extend(self._extract_local_variables(member, qualified_name, constructor_name=enum_name))
                    else:
                        symbols.extend(self._extract_declaration(member, scope=qualified_name))
        return symbols

    def _build_method(self, node: Node, parent_name: str) -> ExtractedSymbol:
        name = self._node_name(node.child_by_field_name("name")) or "<anonymous-method>"
        body = node.child_by_field_name("body")
        return self._make_symbol(
            kind=SymbolKind.METHOD,
            name=name,
            qualified_name=self._compose_qualified_name(name, parent_name),
            signature=self._method_signature(node),
            node=node,
            code=self._node_text(node),
            body=self._node_text(body),
            parent_name=parent_name,
            parameters=self._formal_parameters(node.child_by_field_name("parameters")),
        )

    def _build_constructor(self, node: Node, parent_name: str, constructor_name: str) -> ExtractedSymbol:
        body = node.child_by_field_name("body")
        return self._make_symbol(
            kind=SymbolKind.CONSTRUCTOR,
            name=constructor_name,
            qualified_name=self._compose_qualified_name(constructor_name, parent_name),
            signature=self._method_signature(node),
            node=node,
            code=self._node_text(node),
            body=self._node_text(body),
            parent_name=parent_name,
            parameters=self._formal_parameters(node.child_by_field_name("parameters")),
        )

    def _method_signature(self, node: Node) -> str:
        body = node.child_by_field_name("body")
        end_byte = body.start_byte if body is not None else node.end_byte
        return self.source[node.start_byte:end_byte].decode("utf-8").strip()

    def _type_signature(self, node: Node) -> str:
        body = node.child_by_field_name("body")
        end_byte = body.start_byte if body is not None else node.end_byte
        return self.source[node.start_byte:end_byte].decode("utf-8").strip()

    def _build_variable_symbols(self, node: Node, parent_name: str) -> list[ExtractedSymbol]:
        symbols: list[ExtractedSymbol] = []
        for declarator in self._named_children_by_type(node, "variable_declarator"):
            name = self._node_name(declarator.child_by_field_name("name"))
            if name is None:
                continue
            symbols.append(
                self._make_symbol(
                    kind=SymbolKind.VARIABLE,
                    name=name,
                    qualified_name=self._compose_qualified_name(name, parent_name),
                    signature=self._node_text(node).strip(),
                    node=declarator,
                    code=self._node_text(node),
                    body=None,
                    parent_name=parent_name,
                )
            )
        return symbols

    def _extract_local_variables(
        self,
        node: Node,
        class_name: str,
        *,
        constructor_name: str | None = None,
    ) -> list[ExtractedSymbol]:
        method_name = constructor_name or self._node_name(node.child_by_field_name("name")) or "<anonymous-method>"
        parent_name = self._compose_qualified_name(method_name, class_name)
        variables: list[ExtractedSymbol] = []
        for item in self._walk(node.child_by_field_name("body")):
            if item.type == "local_variable_declaration":
                variables.extend(self._build_variable_symbols(item, parent_name))
        return variables

    def _walk(self, node: Node | None):
        if node is None:
            return
        yield node
        for child in node.named_children:
            yield from self._walk(child)

    def _package_name(self, root: Node) -> str | None:
        package = next((child for child in root.named_children if child.type == "package_declaration"), None)
        if package is None:
            return None
        name = next((child for child in package.named_children if child.type == "identifier" or child.type == "scoped_identifier"), None)
        return self._node_name(name)

    def _build_import(self, node: Node, package_name: str | None) -> ExtractedSymbol:
        scoped_identifier = next(
            (child for child in node.named_children if child.type in {"identifier", "scoped_identifier", "asterisk"}),
            None,
        )
        imported_name = self._node_name(scoped_identifier) or "<anonymous-import>"
        is_static = any(child.type == "static" for child in node.children)
        qualified_name = f"static:{imported_name}" if is_static else imported_name
        return self._make_symbol(
            kind=SymbolKind.IMPORT,
            name=imported_name.split(".")[-1],
            qualified_name=qualified_name,
            signature=self._node_text(node).strip(),
            node=node,
            code=self._node_text(node),
            body=None,
            parent_name=package_name,
            is_static=is_static,
        )

    def _formal_parameters(self, node: Node | None) -> list[str]:
        if node is None:
            return []
        return [self._node_text(child).strip() for child in node.named_children if child.type == "formal_parameter"]

    def _type_super_types(self, node: Node) -> list[str]:
        super_types: list[str] = []
        for child in node.named_children:
            if child.type == "superclass":
                super_types.extend(self._named_type_texts(child))
            elif child.type in {"super_interfaces", "extends_interfaces"}:
                super_types.extend(self._named_type_texts(child))
        return super_types

    def _named_type_texts(self, node: Node) -> list[str]:
        names: list[str] = []
        for child in self._walk(node):
            if child.type in {"type_identifier", "generic_type", "scoped_type_identifier"}:
                text = self._node_text(child).strip()
                if text and text not in names:
                    names.append(text)
        return names
