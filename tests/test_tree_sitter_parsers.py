from pathlib import Path

import pytest

from app.parsers.exceptions import SourceFileReadError, SourceParseError, UnsupportedLanguageError
from app.parsers.files import read_source_file
from app.parsers.languages import SUPPORTED_LANGUAGE_NAMES, get_language_for_path
from app.parsers.tree_sitter import format_tree_for_debug, parse_file, parse_source_code


def test_supported_language_scope_is_defined() -> None:
    assert SUPPORTED_LANGUAGE_NAMES == ("python", "java", "c", "cpp")


@pytest.mark.parametrize(
    ("path", "language"),
    [
        ("example.py", "python"),
        ("Example.java", "java"),
        ("example.c", "c"),
        ("example.cpp", "cpp"),
        ("example.hh", "cpp"),
    ],
)
def test_language_is_resolved_from_extension(path: str, language: str) -> None:
    assert get_language_for_path(path) == language


def test_unsupported_extension_raises_error() -> None:
    with pytest.raises(UnsupportedLanguageError):
        get_language_for_path("README.md")


def test_read_source_file_returns_bytes(tmp_path: Path) -> None:
    source_path = tmp_path / "sample.py"
    source_path.write_bytes(b"print('hello')\n")

    assert read_source_file(source_path) == b"print('hello')\n"


def test_read_source_file_raises_for_missing_file(tmp_path: Path) -> None:
    with pytest.raises(SourceFileReadError):
        read_source_file(tmp_path / "missing.py")


@pytest.mark.parametrize(
    ("language", "source_code", "root_type"),
    [
        ("python", "def greet(name):\n    return name\n", "module"),
        ("java", "class Greeter { String greet(String name) { return name; } }", "program"),
        ("c", "int add(int a, int b) { return a + b; }", "translation_unit"),
        ("cpp", "class Greeter { public: int greet(int value) { return value; } };", "translation_unit"),
    ],
)
def test_parse_source_code_returns_tree(language: str, source_code: str, root_type: str) -> None:
    parsed = parse_source_code(source_code, language)

    assert parsed.language == language
    assert parsed.tree.root_node.type == root_type


def test_parse_file_reads_and_parses_python(tmp_path: Path) -> None:
    source_path = tmp_path / "service.py"
    source_path.write_text("class Service:\n    pass\n", encoding="utf-8")

    parsed = parse_file(source_path)

    assert parsed.path == str(source_path)
    assert parsed.tree.root_node.type == "module"


def test_parse_source_code_raises_on_syntax_error() -> None:
    with pytest.raises(SourceParseError):
        parse_source_code("def broken(:\n    pass\n", "python")


def test_debug_formatter_contains_node_types() -> None:
    parsed = parse_source_code("def greet():\n    return 1\n", "python")

    debug_output = format_tree_for_debug(parsed.tree.root_node, max_depth=2)

    assert "module" in debug_output
    assert "function_definition" in debug_output
