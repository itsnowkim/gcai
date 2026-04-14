"""Parser package."""

from app.parsers.files import read_source_file
from app.parsers.languages import (
    SUPPORTED_LANGUAGE_NAMES,
    get_language_for_path,
    get_parser_for_language,
)
from app.parsers.tree_sitter import ParsedSource, format_tree_for_debug, parse_file, parse_source_code

__all__ = [
    "ParsedSource",
    "SUPPORTED_LANGUAGE_NAMES",
    "format_tree_for_debug",
    "get_language_for_path",
    "get_parser_for_language",
    "parse_file",
    "parse_source_code",
    "read_source_file",
]
