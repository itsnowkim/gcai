from app.storage.chroma.exceptions import ChromaStorageError

CALLABLE_COLLECTION_SUFFIX = "code-impl"


def get_callable_collection(client, *, collection_prefix: str, language: str):
    collection_name = build_callable_collection_name(collection_prefix=collection_prefix, language=language)
    try:
        return client.get_or_create_collection(
            name=collection_name,
            metadata={
                "purpose": "callable_implementations",
                "language": language,
            },
        )
    except Exception as exc:  # pragma: no cover - external collection failure path
        raise ChromaStorageError(
            f"Failed to get or create Chroma collection '{collection_name}': {exc}",
            error_code="chroma_collection_error",
        ) from exc


def build_callable_collection_name(*, collection_prefix: str, language: str) -> str:
    safe_prefix = _sanitize_collection_part(collection_prefix)
    safe_language = _sanitize_collection_part(language)
    return f"{safe_prefix}-{safe_language}-{CALLABLE_COLLECTION_SUFFIX}"


def _sanitize_collection_part(value: str) -> str:
    sanitized = "".join(character.lower() if character.isalnum() else "-" for character in value)
    sanitized = "-".join(part for part in sanitized.split("-") if part)
    if not sanitized:
        raise ChromaStorageError("Collection name part cannot be empty", error_code="chroma_collection_name_error")
    return sanitized
