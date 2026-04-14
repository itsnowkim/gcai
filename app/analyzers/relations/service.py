from tree_sitter import Node

from app.analyzers.symbols import extract_symbols
from app.parsers.tree_sitter import ParsedSource, parse_file
from app.schemas.relations import ExtractedRelation, RelationExtractionResult, RelationKind
from app.schemas.symbols import SymbolExtractionResult, SymbolKind


def extract_relations(parsed_source: ParsedSource) -> RelationExtractionResult:
    symbol_result = extract_symbols(parsed_source)
    return _build_relation_result(symbol_result, parsed_source=parsed_source)


def extract_relations_from_file(path: str) -> RelationExtractionResult:
    parsed_source = parse_file(path)
    symbol_result = extract_symbols(parsed_source)
    return _build_relation_result(symbol_result, parsed_source=parsed_source)


def extract_relations_from_symbols(symbol_result: SymbolExtractionResult) -> RelationExtractionResult:
    return _build_relation_result(symbol_result, parsed_source=None)


def _build_relation_result(
    symbol_result: SymbolExtractionResult,
    *,
    parsed_source: ParsedSource | None,
) -> RelationExtractionResult:
    relations: list[ExtractedRelation] = []
    seen_ids: set[str] = set()
    file_symbol = next(symbol for symbol in symbol_result.symbols if symbol.kind == SymbolKind.FILE)
    known_symbols = {symbol.qualified_name for symbol in symbol_result.symbols}

    for symbol in symbol_result.symbols:
        if symbol.kind == SymbolKind.FILE:
            continue

        source = symbol.parent_name if symbol.parent_name in known_symbols else file_symbol.qualified_name
        contains_relation = _make_relation(
            kind=RelationKind.CONTAINS,
            path=symbol_result.path,
            source=source,
            destination=symbol.qualified_name,
        )
        if contains_relation.id not in seen_ids:
            relations.append(contains_relation)
            seen_ids.add(contains_relation.id)

        if symbol.kind == SymbolKind.IMPORT:
            imported_target = symbol.qualified_name.removeprefix("static:")
            imports_relation = _make_relation(
                kind=RelationKind.IMPORTS,
                path=symbol_result.path,
                source=file_symbol.qualified_name,
                destination=imported_target,
                metadata={"is_static": symbol.is_static},
            )
            if imports_relation.id not in seen_ids:
                relations.append(imports_relation)
                seen_ids.add(imports_relation.id)

    if parsed_source is not None:
        for call_relation in _extract_call_relations(parsed_source, symbol_result):
            if call_relation.id not in seen_ids:
                relations.append(call_relation)
                seen_ids.add(call_relation.id)

    return RelationExtractionResult(
        path=symbol_result.path,
        language=symbol_result.language,
        relations=relations,
    )


def _make_relation(
    *,
    kind: RelationKind,
    path: str,
    source: str,
    destination: str,
    metadata: dict[str, str | bool] | None = None,
) -> ExtractedRelation:
    relation_id = f"{kind}:{path}:{source}->{destination}"
    return ExtractedRelation(
        id=relation_id,
        kind=kind,
        path=path,
        source=source,
        destination=destination,
        metadata=metadata or {},
    )


def _extract_call_relations(
    parsed_source: ParsedSource,
    symbol_result: SymbolExtractionResult,
) -> list[ExtractedRelation]:
    callable_symbols = [
        symbol
        for symbol in symbol_result.symbols
        if symbol.kind in {SymbolKind.FUNCTION, SymbolKind.METHOD, SymbolKind.CONSTRUCTOR}
    ]
    relations: list[ExtractedRelation] = []
    for node in _walk(parsed_source.tree.root_node):
        if node.type not in {"call", "call_expression", "method_invocation"}:
            continue
        caller = _find_enclosing_callable(node, callable_symbols)
        callee = _call_destination(node, parsed_source.language)
        if caller is None or not callee:
            continue
        relations.append(
            _make_relation(
                kind=RelationKind.CALLS,
                path=symbol_result.path,
                source=caller.qualified_name,
                destination=callee,
            )
        )
    return relations


def _walk(node: Node):
    yield node
    for child in node.named_children:
        yield from _walk(child)


def _find_enclosing_callable(node: Node, callable_symbols):
    matching_symbols = [
        symbol
        for symbol in callable_symbols
        if symbol.start_line <= node.start_point[0] + 1 <= symbol.end_line
    ]
    if not matching_symbols:
        return None
    return min(matching_symbols, key=lambda symbol: symbol.end_line - symbol.start_line)


def _call_destination(node: Node, language: str) -> str | None:
    if language == "python":
        function_node = node.child_by_field_name("function")
        return _node_text(function_node)
    if language == "java":
        object_node = node.child_by_field_name("object")
        name_node = node.child_by_field_name("name")
        if name_node is None:
            return None
        name = _node_text(name_node)
        if object_node is None:
            return name
        return f"{_node_text(object_node)}.{name}"
    if language in {"c", "cpp"}:
        function_node = node.child_by_field_name("function")
        return _node_text(function_node)
    return None


def _node_text(node: Node | None) -> str | None:
    if node is None:
        return None
    return node.text.decode("utf-8").strip()
