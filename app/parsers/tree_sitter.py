from dataclasses import dataclass
from pathlib import Path

from tree_sitter import Node, Tree

from app.core.paths import to_posix_absolute_path
from app.parsers.exceptions import SourceParseError
from app.parsers.files import read_source_file
from app.parsers.languages import get_language_for_path, get_parser_for_language


@dataclass(slots=True)
class ParsedSource:
    path: str | None
    language: str
    source_bytes: bytes
    tree: Tree


def parse_source_code(
    source_code: str | bytes,
    language_name: str,
    *,
    path: str | None = None,
    fail_on_syntax_error: bool = True,
) -> ParsedSource:
    source_bytes = source_code.encode("utf-8") if isinstance(source_code, str) else source_code
    parser = get_parser_for_language(language_name)
    tree = parser.parse(source_bytes)

    if tree is None:
        raise SourceParseError(f"Tree-sitter returned no parse tree for language '{language_name}'")

    if fail_on_syntax_error and tree.root_node.has_error:
        location = _first_error_location(tree.root_node)
        target = path or "<memory>"
        raise SourceParseError(f"Tree-sitter detected syntax errors while parsing {target}{location}")

    return ParsedSource(path=path, language=language_name, source_bytes=source_bytes, tree=tree)


def parse_file(path: str | Path, *, fail_on_syntax_error: bool = True) -> ParsedSource:
    language_name = get_language_for_path(path)
    source_bytes = read_source_file(path)
    return parse_source_code(
        source_bytes,
        language_name,
        path=to_posix_absolute_path(path),
        fail_on_syntax_error=fail_on_syntax_error,
    )


def format_tree_for_debug(node: Node, *, max_depth: int = 3, indent: str = "  ") -> str:
    lines: list[str] = []

    def walk(current: Node, depth: int) -> None:
        position = f"{current.start_point[0] + 1}:{current.start_point[1] + 1}-{current.end_point[0] + 1}:{current.end_point[1] + 1}"
        lines.append(f"{indent * depth}{current.type} [{position}]")
        if depth >= max_depth:
            return
        for child in current.children:
            walk(child, depth + 1)

    walk(node, 0)
    return "\n".join(lines)


def _first_error_location(root_node: Node) -> str:
    error_node = _find_first_error_node(root_node)
    if error_node is None:
        return ""
    line, column = error_node.start_point
    return f" at line {line + 1}, column {column + 1}"


def _find_first_error_node(node: Node) -> Node | None:
    if node.type == "ERROR" or node.is_missing:
        return node
    for child in node.children:
        error_node = _find_first_error_node(child)
        if error_node is not None:
            return error_node
    return None
