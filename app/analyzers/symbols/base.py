from collections.abc import Iterable

from tree_sitter import Node

from app.parsers.tree_sitter import ParsedSource
from app.schemas.symbols import ExtractedSymbol, SymbolKind, SymbolExtractionResult


class BaseSymbolExtractor:
    def __init__(self, parsed_source: ParsedSource) -> None:
        self.parsed_source = parsed_source
        self.source = parsed_source.source_bytes
        self.path = parsed_source.path or "<memory>"
        self.language = parsed_source.language

    def extract(self) -> SymbolExtractionResult:
        symbols = [self._build_file_symbol(), *self._extract_symbols()]
        return SymbolExtractionResult(path=self.path, language=self.language, symbols=symbols)

    def _extract_symbols(self) -> list[ExtractedSymbol]:
        raise NotImplementedError

    def _build_file_symbol(self) -> ExtractedSymbol:
        root = self.parsed_source.tree.root_node
        return self._make_symbol(
            kind=SymbolKind.FILE,
            name=self.path.split("/")[-1],
            qualified_name=self.path,
            signature=self.path,
            node=root,
            code=self._node_text(root),
            parent_name=None,
            body=None,
        )

    def _make_symbol(
        self,
        *,
        kind: SymbolKind,
        name: str,
        qualified_name: str,
        signature: str,
        node: Node,
        code: str,
        parent_name: str | None,
        body: str | None,
        parameters: list[str] | None = None,
        super_types: list[str] | None = None,
        aliased_type: str | None = None,
        is_static: bool = False,
    ) -> ExtractedSymbol:
        start_line = node.start_point[0] + 1
        end_line = node.end_point[0] + 1
        return ExtractedSymbol(
            id=self._symbol_id(kind, qualified_name, start_line),
            kind=kind,
            language=self.language,
            path=self.path,
            name=name,
            qualified_name=qualified_name,
            signature=signature,
            start_line=start_line,
            end_line=end_line,
            code=code,
            body=body,
            parent_name=parent_name,
            parameters=parameters or [],
            super_types=super_types or [],
            aliased_type=aliased_type,
            is_static=is_static,
        )

    def _symbol_id(self, kind: SymbolKind, qualified_name: str, start_line: int) -> str:
        return f"{kind}:{self.path}:{qualified_name}:{start_line}"

    def _compose_qualified_name(self, name: str, parent_name: str | None) -> str:
        return f"{parent_name}.{name}" if parent_name else name

    def _node_text(self, node: Node | None) -> str:
        if node is None:
            return ""
        return self.source[node.start_byte : node.end_byte].decode("utf-8")

    def _node_name(self, node: Node | None) -> str | None:
        if node is None:
            return None
        return self._node_text(node).strip()

    def _named_children_by_type(self, node: Node, node_type: str) -> Iterable[Node]:
        for child in node.named_children:
            if child.type == node_type:
                yield child
