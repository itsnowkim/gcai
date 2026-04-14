from tree_sitter import Node

from app.analyzers.symbols.base import BaseSymbolExtractor
from app.schemas.symbols import ExtractedSymbol, SymbolKind


class PythonSymbolExtractor(BaseSymbolExtractor):
    def _extract_symbols(self) -> list[ExtractedSymbol]:
        symbols: list[ExtractedSymbol] = []
        root = self.parsed_source.tree.root_node

        for node in root.named_children:
            node = self._unwrap_definition(node)
            if node is None:
                continue
            if node.type == "class_definition":
                symbols.extend(self._extract_class(node))
            elif node.type == "function_definition":
                function_symbol = self._build_function(node)
                symbols.append(function_symbol)
                symbols.extend(self._extract_local_variables(node, function_symbol.qualified_name))
            elif node.type == "expression_statement":
                assignment = next((item for item in node.named_children if item.type == "assignment"), None)
                if assignment is not None:
                    variable_symbol = self._build_assignment_variable(assignment, None)
                    if variable_symbol is not None:
                        symbols.append(variable_symbol)

        return symbols

    def _extract_class(self, node: Node) -> list[ExtractedSymbol]:
        class_name = self._node_name(node.child_by_field_name("name")) or "<anonymous-class>"
        body = node.child_by_field_name("body")
        symbols = [
            self._make_symbol(
                kind=SymbolKind.CLASS,
                name=class_name,
                qualified_name=class_name,
                signature=f"class {class_name}",
                node=node,
                code=self._node_text(node),
                body=self._node_text(body),
                parent_name=None,
            )
        ]

        if body is None:
            return symbols

        for child in body.named_children:
            child = self._unwrap_definition(child)
            if child is None:
                continue
            if child.type == "function_definition":
                method_symbol = self._build_method(child, class_name)
                symbols.append(method_symbol)
                symbols.extend(self._extract_local_variables(child, method_symbol.qualified_name))
            elif child.type == "expression_statement":
                assignment = next((item for item in child.named_children if item.type == "assignment"), None)
                if assignment is not None:
                    variable_symbol = self._build_assignment_variable(assignment, class_name)
                    if variable_symbol is not None:
                        symbols.append(variable_symbol)

        return symbols

    def _build_function(self, node: Node) -> ExtractedSymbol:
        name = self._node_name(node.child_by_field_name("name")) or "<anonymous-function>"
        return self._make_callable_symbol(node, name=name, kind=SymbolKind.FUNCTION, parent_name=None)

    def _build_method(self, node: Node, class_name: str) -> ExtractedSymbol:
        name = self._node_name(node.child_by_field_name("name")) or "<anonymous-method>"
        return self._make_callable_symbol(
            node,
            name=name,
            kind=SymbolKind.METHOD,
            parent_name=class_name,
        )

    def _make_callable_symbol(
        self,
        node: Node,
        *,
        name: str,
        kind: SymbolKind,
        parent_name: str | None,
    ) -> ExtractedSymbol:
        body = node.child_by_field_name("body")
        qualified_name = f"{parent_name}.{name}" if parent_name else name
        return self._make_symbol(
            kind=kind,
            name=name,
            qualified_name=qualified_name,
            signature=self._callable_signature(node),
            node=node,
            code=self._node_text(node),
            body=self._node_text(body),
            parent_name=parent_name,
        )

    def _callable_signature(self, node: Node) -> str:
        body = node.child_by_field_name("body")
        end_byte = body.start_byte if body is not None else node.end_byte
        return self.source[node.start_byte:end_byte].decode("utf-8").strip().rstrip(":")

    def _build_assignment_variable(self, node: Node, parent_name: str) -> ExtractedSymbol | None:
        target = node.child_by_field_name("left") or next(
            (child for child in node.named_children if child.type == "identifier"),
            None,
        )
        name = self._node_name(target)
        if name is None:
            return None
        return self._make_symbol(
            kind=SymbolKind.VARIABLE,
            name=name,
            qualified_name=self._compose_qualified_name(name, parent_name),
            signature=f"{name} = ...",
            node=node,
            code=self._node_text(node),
            body=None,
            parent_name=parent_name,
        )

    def _extract_local_variables(self, node: Node, parent_name: str) -> list[ExtractedSymbol]:
        body = node.child_by_field_name("body")
        if body is None:
            return []

        variables: list[ExtractedSymbol] = []
        for child in body.named_children:
            if child.type != "expression_statement":
                continue
            assignment = next((item for item in child.named_children if item.type == "assignment"), None)
            if assignment is None:
                continue
            variable_symbol = self._build_assignment_variable(assignment, parent_name)
            if variable_symbol is not None:
                variables.append(variable_symbol)
        return variables

    def _unwrap_definition(self, node: Node) -> Node | None:
        if node.type != "decorated_definition":
            return node
        definition = next(
            (child for child in node.named_children if child.type in {"class_definition", "function_definition"}),
            None,
        )
        return definition
