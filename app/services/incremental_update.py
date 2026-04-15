from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from app.core.exceptions import GCAIError
from app.core.logging import get_logger
from app.parsers.exceptions import SourceParseError, UnsupportedLanguageError
from app.schemas.diff import ChangeType, ParsedDiffResult
from app.schemas.relations import ExtractedRelation
from app.schemas.symbols import ExtractedSymbol
from app.services.diff import collect_changed_files_from_diff
from app.services.source_analysis import analyze_source_file

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
