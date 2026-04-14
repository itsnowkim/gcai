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
    symbols_by_qualified_name = {symbol.qualified_name: symbol for symbol in symbol_result.symbols}

    for symbol in symbol_result.symbols:
        if symbol.kind == SymbolKind.FILE:
            continue

        source = symbol.parent_name if symbol.parent_name in known_symbols else file_symbol.qualified_name
        source_symbol = symbols_by_qualified_name.get(source, file_symbol)
        contains_relation = _make_relation(
            kind=RelationKind.CONTAINS,
            path=symbol_result.path,
            source=source,
            destination=symbol.qualified_name,
            source_id=source_symbol.id,
            destination_id=symbol.id,
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
                source_id=file_symbol.id,
                destination_id=symbol.id,
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
        for access_relation in _extract_access_relations(parsed_source, symbol_result):
            if access_relation.id not in seen_ids:
                relations.append(access_relation)
                seen_ids.add(access_relation.id)

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
    source_id: str | None = None,
    destination_id: str | None = None,
    metadata: dict[str, str | bool] | None = None,
) -> ExtractedRelation:
    relation_id = f"{kind}:{path}:{source}->{destination}"
    return ExtractedRelation(
        id=relation_id,
        kind=kind,
        path=path,
        source=source,
        destination=destination,
        source_id=source_id,
        destination_id=destination_id,
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
    callable_symbols_by_qualified_name = {symbol.qualified_name: symbol for symbol in callable_symbols}
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
                source_id=caller.id,
                destination_id=callable_symbols_by_qualified_name.get(callee).id
                if callee in callable_symbols_by_qualified_name
                else None,
            )
        )
    return relations


def _extract_access_relations(
    parsed_source: ParsedSource,
    symbol_result: SymbolExtractionResult,
) -> list[ExtractedRelation]:
    owner_symbols = [
        symbol
        for symbol in symbol_result.symbols
        if symbol.kind
        in {
            SymbolKind.FILE,
            SymbolKind.CLASS,
            SymbolKind.STRUCT,
            SymbolKind.INTERFACE,
            SymbolKind.ENUM,
            SymbolKind.RECORD,
            SymbolKind.FUNCTION,
            SymbolKind.METHOD,
            SymbolKind.CONSTRUCTOR,
        }
    ]
    variable_symbols = [symbol for symbol in symbol_result.symbols if symbol.kind == SymbolKind.VARIABLE]
    variable_symbols_by_qualified_name = {symbol.qualified_name: symbol for symbol in variable_symbols}
    relations: list[ExtractedRelation] = []

    for node in _walk(parsed_source.tree.root_node):
        owner = _find_enclosing_owner(node, owner_symbols)
        if owner is None:
            continue

        if parsed_source.language == "python" and node.type == "assignment":
            relations.extend(_assignment_relations(parsed_source.language, node, owner, variable_symbols, variable_symbols_by_qualified_name))
        elif parsed_source.language == "python" and node.type == "return_statement":
            relations.extend(_expression_reads_relations(parsed_source.language, node, owner, variable_symbols, variable_symbols_by_qualified_name))
        elif parsed_source.language == "java":
            if node.type == "local_variable_declaration":
                relations.extend(_java_local_variable_relations(node, owner, variable_symbols, variable_symbols_by_qualified_name))
            elif node.type == "assignment_expression":
                relations.extend(_assignment_relations(parsed_source.language, node, owner, variable_symbols, variable_symbols_by_qualified_name))
            elif node.type == "return_statement":
                relations.extend(_expression_reads_relations(parsed_source.language, node, owner, variable_symbols, variable_symbols_by_qualified_name))
        elif parsed_source.language in {"c", "cpp"}:
            if node.type == "declaration":
                relations.extend(_c_declaration_relations(node, owner, variable_symbols, variable_symbols_by_qualified_name))
            elif node.type == "assignment_expression":
                relations.extend(_assignment_relations(parsed_source.language, node, owner, variable_symbols, variable_symbols_by_qualified_name))
            elif node.type == "return_statement":
                relations.extend(_expression_reads_relations(parsed_source.language, node, owner, variable_symbols, variable_symbols_by_qualified_name))

    return relations


def _walk(node: Node):
    yield node
    for child in node.named_children:
        yield from _walk(child)


def _find_enclosing_callable(node: Node, callable_symbols):
    matching_symbols = [symbol for symbol in callable_symbols if _symbol_contains_node(symbol, node)]
    if not matching_symbols:
        return None
    return min(matching_symbols, key=_symbol_span_key)


def _find_enclosing_owner(node: Node, owner_symbols):
    matching_symbols = [symbol for symbol in owner_symbols if _symbol_contains_node(symbol, node)]
    if not matching_symbols:
        return None
    return min(matching_symbols, key=_symbol_span_key)


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


def _assignment_relations(language: str, node: Node, owner, variable_symbols, variable_symbols_by_qualified_name) -> list[ExtractedRelation]:
    left = node.child_by_field_name("left") or (node.named_children[0] if node.named_children else None)
    right = node.child_by_field_name("right") or (node.named_children[-1] if node.named_children else None)
    relations: list[ExtractedRelation] = []
    relations.extend(_write_relations(owner, _resolve_references(language, left, owner, variable_symbols), variable_symbols_by_qualified_name))
    relations.extend(_read_relations(owner, _resolve_references(language, right, owner, variable_symbols), variable_symbols_by_qualified_name))
    return relations


def _java_local_variable_relations(node: Node, owner, variable_symbols, variable_symbols_by_qualified_name) -> list[ExtractedRelation]:
    relations: list[ExtractedRelation] = []
    for declarator in [child for child in node.named_children if child.type == "variable_declarator"]:
        name_node = declarator.child_by_field_name("name") or next(
            (child for child in declarator.named_children if child.type == "identifier"),
            None,
        )
        value_node = declarator.child_by_field_name("value") or (
            declarator.named_children[-1] if len(declarator.named_children) > 1 else None
        )
        relations.extend(_write_relations(owner, _resolve_references("java", name_node, owner, variable_symbols), variable_symbols_by_qualified_name))
        relations.extend(_read_relations(owner, _resolve_references("java", value_node, owner, variable_symbols), variable_symbols_by_qualified_name))
    return relations


def _c_declaration_relations(node: Node, owner, variable_symbols, variable_symbols_by_qualified_name) -> list[ExtractedRelation]:
    relations: list[ExtractedRelation] = []
    for declarator in [child for child in node.named_children if child.type == "init_declarator"]:
        name_node = next(
            (child for child in declarator.named_children if child.type in {"identifier", "field_identifier"}),
            None,
        )
        value_node = declarator.named_children[-1] if declarator.named_children else None
        relations.extend(_write_relations(owner, _resolve_references("c", name_node, owner, variable_symbols), variable_symbols_by_qualified_name))
        if value_node is not None and value_node is not name_node:
            relations.extend(_read_relations(owner, _resolve_references("c", value_node, owner, variable_symbols), variable_symbols_by_qualified_name))
    return relations


def _expression_reads_relations(language: str, node: Node, owner, variable_symbols, variable_symbols_by_qualified_name) -> list[ExtractedRelation]:
    expression = node.named_children[-1] if node.named_children else None
    return _read_relations(owner, _resolve_references(language, expression, owner, variable_symbols), variable_symbols_by_qualified_name)


def _write_relations(owner, destinations: list[str], variable_symbols_by_qualified_name) -> list[ExtractedRelation]:
    return [
        _make_relation(
            kind=RelationKind.WRITES,
            path=owner.path,
            source=owner.qualified_name,
            destination=destination,
            source_id=owner.id,
            destination_id=variable_symbols_by_qualified_name[destination].id,
        )
        for destination in destinations
    ]


def _read_relations(owner, destinations: list[str], variable_symbols_by_qualified_name) -> list[ExtractedRelation]:
    return [
        _make_relation(
            kind=RelationKind.READS,
            path=owner.path,
            source=owner.qualified_name,
            destination=destination,
            source_id=owner.id,
            destination_id=variable_symbols_by_qualified_name[destination].id,
        )
        for destination in destinations
    ]


def _resolve_references(language: str, node: Node | None, owner, variable_symbols) -> list[str]:
    names = _collect_reference_names(language, node)
    resolved: list[str] = []
    for name in names:
        qualified_name = _resolve_variable_name(name, owner, variable_symbols)
        if qualified_name is not None and qualified_name not in resolved:
            resolved.append(qualified_name)
    return resolved


def _collect_reference_names(language: str, node: Node | None) -> list[str]:
    if node is None:
        return []

    if language == "python":
        return _collect_python_reference_names(node)
    if language == "java":
        return _collect_java_reference_names(node)
    if language in {"c", "cpp"}:
        return _collect_c_reference_names(node)
    return []


def _collect_python_reference_names(node: Node) -> list[str]:
    if node.type == "call":
        argument_lists = [child for child in node.named_children if child.type == "argument_list"]
        names: list[str] = []
        for child in argument_lists:
            names.extend(_collect_python_reference_names(child))
        return names
    if node.type == "attribute":
        object_node = node.child_by_field_name("object")
        attribute_node = node.child_by_field_name("attribute")
        if _node_text(object_node) == "self" and attribute_node is not None:
            text = _node_text(attribute_node)
            return [text] if text else []
        return []
    if node.type == "identifier":
        text = _node_text(node)
        return [text] if text and text != "self" else []
    names: list[str] = []
    for child in node.named_children:
        names.extend(_collect_python_reference_names(child))
    return names


def _collect_java_reference_names(node: Node) -> list[str]:
    if node.type == "method_invocation":
        object_node = node.child_by_field_name("object")
        argument_nodes = [child for child in node.named_children if child.type == "argument_list"]
        names: list[str] = []
        if object_node is not None and _node_text(object_node) not in {None, "this"}:
            object_text = _node_text(object_node)
            if object_text:
                names.append(object_text)
        for child in argument_nodes:
            names.extend(_collect_java_reference_names(child))
        return names
    if node.type == "field_access":
        object_node = node.child_by_field_name("object")
        field_node = node.child_by_field_name("field")
        if _node_text(object_node) == "this" and field_node is not None:
            text = _node_text(field_node)
            return [text] if text else []
        return []
    if node.type == "identifier":
        text = _node_text(node)
        return [text] if text and text != "this" else []
    names: list[str] = []
    for child in node.named_children:
        names.extend(_collect_java_reference_names(child))
    return names


def _collect_c_reference_names(node: Node) -> list[str]:
    if node.type == "call_expression":
        argument_nodes = [child for child in node.named_children if child.type == "argument_list"]
        names: list[str] = []
        for child in argument_nodes:
            names.extend(_collect_c_reference_names(child))
        return names
    if node.type in {"identifier", "field_identifier"}:
        text = _node_text(node)
        return [text] if text else []
    names: list[str] = []
    for child in node.named_children:
        names.extend(_collect_c_reference_names(child))
    return names


def _resolve_variable_name(name: str, owner, variable_symbols) -> str | None:
    owner_scope = owner.parent_name
    owner_type_scope = owner_scope.rsplit(".", 1)[0] if owner_scope and owner.kind in {SymbolKind.METHOD, SymbolKind.CONSTRUCTOR} else owner_scope

    candidates = []
    for symbol in variable_symbols:
        if symbol.name != name:
            continue
        if owner.kind in {SymbolKind.METHOD, SymbolKind.CONSTRUCTOR, SymbolKind.FUNCTION} and symbol.parent_name == owner.qualified_name:
            candidates.append((0, symbol))
        elif owner_type_scope and symbol.parent_name == owner_type_scope:
            candidates.append((1, symbol))
        elif owner_scope and symbol.parent_name == owner_scope:
            candidates.append((1, symbol))
        elif symbol.parent_name is None:
            candidates.append((2, symbol))

    if not candidates:
        return None
    candidates.sort(key=lambda item: (item[0], item[1].start_line))
    return candidates[0][1].qualified_name


def _symbol_contains_node(symbol, node: Node) -> bool:
    start = (symbol.start_line, symbol.start_column)
    end = (symbol.end_line, symbol.end_column)
    node_start = (node.start_point[0] + 1, node.start_point[1] + 1)
    node_end = (node.end_point[0] + 1, node.end_point[1] + 1)
    return start <= node_start and node_end <= end


def _symbol_span_key(symbol) -> tuple[int, int, int, int]:
    return (
        symbol.end_line - symbol.start_line,
        symbol.end_column - symbol.start_column,
        symbol.start_line,
        symbol.start_column,
    )
