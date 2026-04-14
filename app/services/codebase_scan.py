from pathlib import Path

from app.analyzers.relations import extract_relations
from app.analyzers.symbols import extract_symbols
from app.parsers.exceptions import SourceParseError, UnsupportedLanguageError
from app.parsers.languages import get_language_for_path
from app.parsers.tree_sitter import parse_file
from app.schemas.scan import CodebaseScanResult, ScannedFile, SkippedFile

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
        relative_path = str(path.relative_to(root))
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
            parsed_source = parse_file(path)
            symbol_result = extract_symbols(parsed_source)
            relation_result = extract_relations(parsed_source)
        except SourceParseError:
            skipped_files.append(SkippedFile(path=relative_path, reason="parse_error"))
            continue

        scanned_files.append(
            ScannedFile(
                path=relative_path,
                language=language,
                symbols=symbol_result.symbols,
                relations=relation_result.relations,
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
