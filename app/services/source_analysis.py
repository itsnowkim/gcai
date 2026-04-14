from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.analyzers.relations import extract_relations
from app.analyzers.symbols import extract_symbols
from app.parsers.tree_sitter import ParsedSource, parse_file
from app.schemas.relations import RelationExtractionResult
from app.schemas.symbols import SymbolExtractionResult


@dataclass(slots=True)
class SourceAnalysisResult:
    path: str
    language: str
    parsed_source: ParsedSource
    symbol_result: SymbolExtractionResult
    relation_result: RelationExtractionResult | None = None


def analyze_source_file(
    path: str | Path,
    *,
    include_relations: bool,
    fail_on_syntax_error: bool = True,
) -> SourceAnalysisResult:
    parsed_source = parse_file(path, fail_on_syntax_error=fail_on_syntax_error)
    symbol_result = extract_symbols(parsed_source)
    relation_result = extract_relations(parsed_source) if include_relations else None
    return SourceAnalysisResult(
        path=str(path),
        language=parsed_source.language,
        parsed_source=parsed_source,
        symbol_result=symbol_result,
        relation_result=relation_result,
    )
