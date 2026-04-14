from pathlib import Path

from app.parsers.exceptions import SourceParseError, UnsupportedLanguageError
from app.parsers.languages import get_language_for_path
from app.schemas.scan import CodebaseScanResult, ScannedFile, SkippedFile
from app.services.source_analysis import analyze_source_file

DEFAULT_EXCLUDED_DIRECTORIES: tuple[str, ...] = (
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    "dist",
    "build",
    ".mypy_cache",
    ".pytest_cache",
)
DEFAULT_MAX_FILE_BYTES = 512 * 1024


def scan_codebase(
    repo_path: str | Path,
    *,
    excluded_directories: tuple[str, ...] = DEFAULT_EXCLUDED_DIRECTORIES,
    max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
) -> CodebaseScanResult:
    root = Path(repo_path).resolve()
    _validate_repo_path(root)

    scanned_files: list[ScannedFile] = []
    skipped_files: list[SkippedFile] = []

    for path in _iter_candidate_files(root, excluded_directories=excluded_directories):
        relative_path = path.relative_to(root).as_posix()
        try:
            language = get_language_for_path(path)
        except UnsupportedLanguageError:
            skipped_files.append(SkippedFile(path=relative_path, reason="unsupported_language"))
            continue

        file_size = path.stat().st_size
        if file_size > max_file_bytes:
            skipped_files.append(SkippedFile(path=relative_path, reason="file_too_large"))
            continue

        try:
            analysis = analyze_source_file(path, include_relations=True)
        except SourceParseError:
            skipped_files.append(SkippedFile(path=relative_path, reason="parse_error"))
            continue

        scanned_files.append(
            ScannedFile(
                path=relative_path,
                language=analysis.language,
                symbols=analysis.symbol_result.symbols,
                relations=analysis.relation_result.relations if analysis.relation_result is not None else [],
            )
        )

    return CodebaseScanResult(
        repo_path=str(root),
        scanned_files=scanned_files,
        skipped_files=skipped_files,
    )


def _validate_repo_path(path: Path) -> None:
    if not path.exists():
        raise ValueError(f"Repository path does not exist: {path}")
    if not path.is_dir():
        raise ValueError(f"Repository path is not a directory: {path}")


def _iter_candidate_files(root: Path, *, excluded_directories: tuple[str, ...]):
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if any(part in excluded_directories for part in path.relative_to(root).parts[:-1]):
            continue
        yield path
