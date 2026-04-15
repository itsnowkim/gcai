from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from app.core.exceptions import GCAIError
from app.core.logging import get_logger
from app.parsers.exceptions import SourceParseError, UnsupportedLanguageError
from app.parsers.languages import get_language_for_path
from app.schemas.diff import ChangeType, ParsedDiffResult
from app.schemas.relations import ExtractedRelation
from app.schemas.scan import CodebaseScanResult, ScannedFile
from app.schemas.symbols import ExtractedSymbol
from app.core.settings import get_settings
from app.services.diff import collect_changed_files_from_diff
from app.services.source_analysis import analyze_source_file
from app.storage.chroma.client import create_chroma_client, verify_chroma_connectivity
from app.storage.chroma.documents import build_chroma_documents
from app.storage.chroma.reader import ChromaCodeReader
from app.storage.chroma.writer import ChromaDocumentWriter
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


def _update_chroma_incrementally(analysis_result: IncrementalAnalysisResult) -> dict[str, int]:
    settings = get_settings()
    client = create_chroma_client(settings)
    try:
        verify_chroma_connectivity(client)

        reader = ChromaCodeReader(client, collection_prefix=settings.chroma_collection_prefix)
        writer = ChromaDocumentWriter(client, collection_prefix=settings.chroma_collection_prefix)

        paths_by_language = _collect_incremental_chroma_paths_by_language(analysis_result)
        existing_document_ids_by_language: dict[str, dict[str, list[str]]] = {}
        deleted_documents = 0

        for language, paths in paths_by_language.items():
            document_ids_by_path = reader.get_document_ids_by_paths(language=language, paths=paths)
            existing_document_ids_by_language[language] = document_ids_by_path
            document_ids = [document_id for ids in document_ids_by_path.values() for document_id in ids]
            deleted_documents += writer.delete_documents(language=language, ids=document_ids)

        documents_by_language = _build_incremental_chroma_documents(analysis_result)
        reindexed_embeddings = 0
        for language, rows in documents_by_language.items():
            reindexed_embeddings += writer.upsert_documents(language=language, rows=rows)

        logger.info(
            "incremental_update_chroma_completed",
            extra={
                "changed_files": analysis_result.changed_files,
                "languages": sorted(paths_by_language),
                "existing_document_count": sum(
                    len(document_ids)
                    for paths in existing_document_ids_by_language.values()
                    for document_ids in paths.values()
                ),
                "deleted_documents": deleted_documents,
                "reindexed_embeddings": reindexed_embeddings,
            },
        )

        return {"reindexed_embeddings": reindexed_embeddings}
    finally:
        close_client = getattr(client, "close", None)
        if callable(close_client):
            close_client()


def _build_incremental_chroma_documents(analysis_result: IncrementalAnalysisResult) -> dict[str, list[dict[str, object]]]:
    if not analysis_result.analyzed_files:
        return {}

    scan_result = CodebaseScanResult(
        repo_path="",
        scanned_files=[
            ScannedFile(
                path=item.path,
                language=item.language,
                symbols=item.symbols,
                relations=item.relations,
            )
            for item in analysis_result.analyzed_files
        ],
    )
    return build_chroma_documents(scan_result)


def _collect_incremental_chroma_paths_by_language(analysis_result: IncrementalAnalysisResult) -> dict[str, list[str]]:
    paths_by_language: dict[str, set[str]] = {}

    for item in analysis_result.analyzed_files:
        paths_by_language.setdefault(item.language, set()).add(item.path)

    deleted_or_skipped_paths = [
        *analysis_result.deleted_files,
        *(item.path for item in analysis_result.skipped_files if item.reason == "missing_file"),
    ]
    for path in deleted_or_skipped_paths:
        try:
            language = get_language_for_path(path)
        except UnsupportedLanguageError:
            continue
        paths_by_language.setdefault(language, set()).add(path)

    return {
        language: sorted(paths)
        for language, paths in sorted(paths_by_language.items())
    }
