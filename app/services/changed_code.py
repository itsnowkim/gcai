from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from app.core.logging import get_logger
from app.parsers.exceptions import ParserConfigurationError, SourceFileReadError, SourceParseError, UnsupportedLanguageError
from app.schemas.changed_code import ChangedCodeContextResult, ChangedFileContext, ChangedSymbolSeed
from app.schemas.diff import ChangeType, DiffHunk, DiffLineRange, ParsedDiffResult
from app.schemas.symbols import SymbolKind
from app.services.source_analysis import analyze_source_file

logger = get_logger(__name__)

SEED_SYMBOL_KINDS: frozenset[SymbolKind] = frozenset(
    {
        SymbolKind.CLASS,
        SymbolKind.STRUCT,
        SymbolKind.INTERFACE,
        SymbolKind.ENUM,
        SymbolKind.RECORD,
        SymbolKind.ANNOTATION,
        SymbolKind.FUNCTION,
        SymbolKind.METHOD,
        SymbolKind.CONSTRUCTOR,
        SymbolKind.TYPE_ALIAS,
    }
)


def collect_changed_code_context(repo_path: str | Path, diff_result: ParsedDiffResult) -> ChangedCodeContextResult:
    root = Path(repo_path).resolve()
    _validate_repo_path(root)

    changed_files: dict[str, ChangedFileContext] = {}
    symbol_index: dict[str, ChangedSymbolSeed] = {}

    for diff_file in diff_result.files:
        file_context = _build_file_context(root, diff_file)
        changed_files[file_context.path] = file_context

        for symbol_seed in file_context.symbols:
            existing = symbol_index.get(symbol_seed.symbol.id)
            if existing is None:
                symbol_index[symbol_seed.symbol.id] = symbol_seed
            else:
                existing.matched_line_ranges = _merge_line_ranges(
                    [*existing.matched_line_ranges, *symbol_seed.matched_line_ranges]
                )

    result = ChangedCodeContextResult(
        repo_path=str(root),
        changed_files=list(changed_files.values()),
        changed_symbols=list(symbol_index.values()),
    )
    logger.info(
        "changed_code_context_collected",
        extra={
            "repo_path": result.repo_path,
            "changed_files": len(result.changed_files),
            "changed_symbols": len(result.changed_symbols),
        },
    )
    return result


def _build_file_context(repo_root: Path, diff_file) -> ChangedFileContext:
    source_path = _resolve_source_path(repo_root, diff_file.path, diff_file.new_path, diff_file.old_path)
    file_context = ChangedFileContext(
        path=diff_file.path,
        change_type=diff_file.change_type,
        old_path=diff_file.old_path,
        new_path=diff_file.new_path,
        changed_line_ranges=diff_file.changed_line_ranges,
        source_path=str(source_path) if source_path is not None else None,
    )

    if source_path is None:
        file_context.skip_reason = "source_missing"
        return file_context

    try:
        analysis = analyze_source_file(source_path, include_relations=False, fail_on_syntax_error=False)
    except UnsupportedLanguageError:
        file_context.skip_reason = "unsupported_language"
        return file_context
    except (SourceFileReadError, SourceParseError, ParserConfigurationError):
        file_context.skip_reason = "parse_error"
        return file_context

    source_code = analysis.parsed_source.source_bytes.decode("utf-8")
    matching_symbols = [
        _build_symbol_seed(symbol, diff_file.hunks)
        for symbol in analysis.symbol_result.symbols
        if symbol.kind in SEED_SYMBOL_KINDS and _symbol_overlaps_any_hunk(symbol, diff_file.hunks)
    ]

    file_context.language = analysis.language
    file_context.source_code = source_code
    file_context.source_loaded = True
    file_context.symbols = _dedupe_symbol_seeds(matching_symbols)
    return file_context


def _resolve_source_path(
    repo_root: Path,
    primary_path: str,
    new_path: str | None,
    old_path: str | None,
) -> Path | None:
    candidates: list[str] = [primary_path]
    if new_path and new_path not in candidates:
        candidates.append(new_path)
    if old_path and old_path not in candidates:
        candidates.append(old_path)

    for candidate in candidates:
        candidate_path = repo_root / candidate
        if candidate_path.exists():
            return candidate_path
    return None


def _symbol_overlaps_any_hunk(symbol, hunks: list[DiffHunk]) -> bool:
    return any(_symbol_overlaps_line_range(symbol, range_) for range_ in _hunk_line_ranges(hunks))


def _symbol_overlaps_line_range(symbol, line_range: DiffLineRange) -> bool:
    symbol_start = symbol.start_line
    symbol_end = symbol.end_line
    range_start = line_range.start_line
    range_end = line_range.start_line + max(line_range.line_count - 1, 0)
    if line_range.line_count == 0:
        return symbol_start <= range_start <= symbol_end
    return symbol_start <= range_end and symbol_end >= range_start


def _hunk_line_ranges(hunks: list[DiffHunk]) -> list[DiffLineRange]:
    line_ranges: list[DiffLineRange] = []
    for hunk in hunks:
        if hunk.old_line_count > 0:
            line_ranges.append(DiffLineRange(start_line=hunk.old_start_line, line_count=hunk.old_line_count))
        if hunk.new_line_count > 0:
            line_ranges.append(DiffLineRange(start_line=hunk.new_start_line, line_count=hunk.new_line_count))
        if hunk.old_line_count == 0 and hunk.new_line_count == 0:
            line_ranges.append(DiffLineRange(start_line=hunk.new_start_line, line_count=0))
    return line_ranges


def _build_symbol_seed(symbol, hunks: list[DiffHunk]) -> ChangedSymbolSeed:
    matched_line_ranges: list[DiffLineRange] = []
    for line_range in _hunk_line_ranges(hunks):
        if _symbol_overlaps_line_range(symbol, line_range):
            matched_line_ranges.append(line_range)

    return ChangedSymbolSeed(symbol=symbol, matched_line_ranges=_merge_line_ranges(matched_line_ranges))


def _dedupe_symbol_seeds(seeds: Iterable[ChangedSymbolSeed]) -> list[ChangedSymbolSeed]:
    deduped: dict[str, ChangedSymbolSeed] = {}
    for seed in seeds:
        existing = deduped.get(seed.symbol.id)
        if existing is None:
            deduped[seed.symbol.id] = seed
            continue
        existing.matched_line_ranges = _merge_line_ranges([*existing.matched_line_ranges, *seed.matched_line_ranges])
    return list(deduped.values())


def _merge_line_ranges(ranges: Iterable[DiffLineRange]) -> list[DiffLineRange]:
    unique: dict[tuple[int, int], DiffLineRange] = {}
    for line_range in ranges:
        unique[(line_range.start_line, line_range.line_count)] = line_range
    return list(unique.values())


def _validate_repo_path(path: Path) -> None:
    if not path.exists():
        raise ValueError(f"Repository path does not exist: {path}")
    if not path.is_dir():
        raise ValueError(f"Repository path is not a directory: {path}")
