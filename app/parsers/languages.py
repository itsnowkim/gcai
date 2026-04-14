from functools import lru_cache
from pathlib import Path

from tree_sitter import Language, Parser
import tree_sitter_javascript
import tree_sitter_python
import tree_sitter_typescript

from app.parsers.exceptions import ParserConfigurationError, UnsupportedLanguageError

EXTENSION_LANGUAGE_MAP: dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".ts": "typescript",
    ".tsx": "tsx",
}

SUPPORTED_LANGUAGE_NAMES: tuple[str, ...] = ("python", "javascript", "typescript", "tsx")

LANGUAGE_BINDINGS: dict[str, object] = {
    "python": tree_sitter_python.language,
    "javascript": tree_sitter_javascript.language,
    "typescript": tree_sitter_typescript.language_typescript,
    "tsx": tree_sitter_typescript.language_tsx,
}


def get_language_for_path(path: str | Path) -> str:
    extension = Path(path).suffix.lower()
    language_name = EXTENSION_LANGUAGE_MAP.get(extension)
    if language_name is None:
        raise UnsupportedLanguageError(str(path))
    return language_name


@lru_cache
def load_language(language_name: str) -> Language:
    if language_name not in SUPPORTED_LANGUAGE_NAMES:
        raise ParserConfigurationError(f"Unsupported Tree-sitter language configuration: {language_name}")

    try:
        language_factory = LANGUAGE_BINDINGS[language_name]
        return Language(language_factory())
    except Exception as exc:  # pragma: no cover - external package failure path
        raise ParserConfigurationError(
            f"Failed to load Tree-sitter language '{language_name}': {exc}"
        ) from exc


@lru_cache
def get_parser_for_language(language_name: str) -> Parser:
    try:
        language = load_language(language_name)
        return Parser(language)
    except Exception as exc:  # pragma: no cover - external package failure path
        raise ParserConfigurationError(
            f"Failed to create Tree-sitter parser for '{language_name}': {exc}"
        ) from exc
