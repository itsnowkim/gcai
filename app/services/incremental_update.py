from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from app.core.exceptions import GCAIError
from app.core.logging import get_logger
from app.parsers.exceptions import SourceParseError, UnsupportedLanguageError
from app.schemas.diff import ChangeType, ParsedDiffResult
from app.schemas.relations import ExtractedRelation
from app.schemas.symbols import ExtractedSymbol
from app.core.settings import get_settings
from app.services.diff import collect_changed_files_from_diff
from app.services.source_analysis import analyze_source_file
from app.storage.neo4j.client import create_neo4j_driver, verify_neo4j_connectivity
from app.storage.neo4j.reader import Neo4jGraphReader
from app.storage.neo4j.schema import ensure_neo4j_constraints
from app.storage.neo4j.writer import Neo4jGraphWriter

logger = get_logger(__name__)


@dataclass(slots=True)
class IncrementalAnalysisFile:
    path: str
    language: str
    symbols: list[ExtractedSymbol]
    relations: list[ExtractedRelation]


@dataclass(slots=True)
class IncrementalSkippedFile:
    path: str
    reason: str


@dataclass(slots=True)
class IncrementalAnalysisResult:
    changed_files: list[str] = field(default_factory=list)
    analyzed_files: list[IncrementalAnalysisFile] = field(default_factory=list)
    deleted_files: list[str] = field(default_factory=list)
    skipped_files: list[IncrementalSkippedFile] = field(default_factory=list)


def run_incremental_update(repo_path: str, raw_diff: str):
    _validate_repo_path(repo_path)
    collect_changed_files_from_diff(raw_diff)
    raise GCAIError(
        "Incremental graph update service is not implemented yet. Complete phase 3 first.",
        error_code="incremental_update_not_implemented",
        status_code=501,
    )


def _validate_repo_path(repo_path: str) -> None:
    path = Path(repo_path).resolve()
    if not path.exists():
        raise GCAIError(f"Repository path does not exist: {path}", error_code="invalid_repo_path", status_code=400)
    if not path.is_dir():
        raise GCAIError(f"Repository path is not a directory: {path}", error_code="invalid_repo_path", status_code=400)


def _analyze_incremental_changes(repo_path: str | Path, parsed_diff: ParsedDiffResult) -> IncrementalAnalysisResult:
    root = Path(repo_path).resolve()
    result = IncrementalAnalysisResult()

    for diff_file in parsed_diff.files:
        normalized_path = _normalize_repo_relative_path(diff_file.path)
        result.changed_files.append(normalized_path)

        if diff_file.change_type == ChangeType.DELETED:
            result.deleted_files.append(normalized_path)
            continue

        absolute_path = root / Path(normalized_path)
        if not absolute_path.exists() or not absolute_path.is_file():
            _record_skipped_file(result, path=normalized_path, reason="missing_file")
            continue

        try:
            analysis = analyze_source_file(absolute_path, include_relations=True)
        except UnsupportedLanguageError:
            _record_skipped_file(result, path=normalized_path, reason="unsupported_language")
            continue
        except SourceParseError:
            _record_skipped_file(result, path=normalized_path, reason="parse_error")
            continue

        result.analyzed_files.append(
            IncrementalAnalysisFile(
                path=normalized_path,
                language=analysis.language,
                symbols=analysis.symbol_result.symbols,
                relations=analysis.relation_result.relations if analysis.relation_result is not None else [],
            )
        )

    return result


def _normalize_repo_relative_path(path: str) -> str:
    return Path(path).as_posix()


def _record_skipped_file(result: IncrementalAnalysisResult, *, path: str, reason: str) -> None:
    result.skipped_files.append(IncrementalSkippedFile(path=path, reason=reason))
    logger.info(
        "incremental_update_file_skipped",
        extra={
            "path": path,
            "reason": reason,
        },
    )


def _update_neo4j_incrementally(analysis_result: IncrementalAnalysisResult) -> dict[str, int]:
    settings = get_settings()
    driver = create_neo4j_driver(settings)
    try:
        verify_neo4j_connectivity(driver)
        ensure_neo4j_constraints(driver, database=settings.neo4j_database)

        reader = Neo4jGraphReader(driver, database=settings.neo4j_database)
        writer = Neo4jGraphWriter(driver, database=settings.neo4j_database)

        paths_to_replace = sorted({*analysis_result.deleted_files, *(item.path for item in analysis_result.analyzed_files)})
        existing_symbol_ids_by_path = reader.get_symbol_ids_by_paths(paths_to_replace)

        deleted_edges = writer.delete_relations_by_paths(paths_to_replace)
        deleted_nodes = writer.delete_symbols_by_paths(paths_to_replace)

        all_symbols = [symbol for item in analysis_result.analyzed_files for symbol in item.symbols]
        all_relations = [relation for item in analysis_result.analyzed_files for relation in item.relations]

        updated_nodes = writer.upsert_symbols(all_symbols)
        updated_edges = writer.upsert_relations(all_relations)

        logger.info(
            "incremental_update_neo4j_completed",
            extra={
                "changed_files": analysis_result.changed_files,
                "replaced_paths": paths_to_replace,
                "existing_symbol_count": sum(len(symbol_ids) for symbol_ids in existing_symbol_ids_by_path.values()),
                "deleted_nodes": deleted_nodes,
                "deleted_edges": deleted_edges,
                "updated_nodes": updated_nodes,
                "updated_edges": updated_edges,
            },
        )

        return {"updated_nodes": updated_nodes, "updated_edges": updated_edges}
    finally:
        driver.close()
