from app.analyzers.symbols.base import BaseSymbolExtractor
from app.analyzers.symbols.c import CSymbolExtractor
from app.analyzers.symbols.cpp import CppSymbolExtractor
from app.analyzers.symbols.java import JavaSymbolExtractor
from app.analyzers.symbols.python import PythonSymbolExtractor
from app.parsers.exceptions import UnsupportedLanguageError
from app.parsers.tree_sitter import ParsedSource, parse_file
from app.schemas.symbols import SymbolExtractionResult

EXTRACTOR_BY_LANGUAGE: dict[str, type[BaseSymbolExtractor]] = {
    "python": PythonSymbolExtractor,
    "java": JavaSymbolExtractor,
    "c": CSymbolExtractor,
    "cpp": CppSymbolExtractor,
}


def extract_symbols(parsed_source: ParsedSource) -> SymbolExtractionResult:
    extractor_cls = EXTRACTOR_BY_LANGUAGE.get(parsed_source.language)
    if extractor_cls is None:
        raise UnsupportedLanguageError(parsed_source.path or parsed_source.language)
    return extractor_cls(parsed_source).extract()


def extract_symbols_from_file(path: str) -> SymbolExtractionResult:
    parsed_source = parse_file(path)
    return extract_symbols(parsed_source)
