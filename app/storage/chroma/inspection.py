from collections.abc import Iterable

from app.storage.chroma.collections import build_callable_collection_name
from app.storage.chroma.exceptions import ChromaStorageError


def count_callable_documents(
    client,
    *,
    collection_prefix: str,
    languages: Iterable[str],
) -> int:
    try:
        collections_by_name = {collection.name: collection for collection in client.list_collections()}
        total_documents = 0
        for language in sorted(set(languages)):
            collection_name = build_callable_collection_name(
                collection_prefix=collection_prefix,
                language=language,
            )
            collection = collections_by_name.get(collection_name)
            if collection is None:
                continue
            total_documents += int(collection.count())
    except Exception as exc:  # pragma: no cover - external database failure path
        raise ChromaStorageError(
            f"Failed to inspect Chroma indexed documents: {exc}",
            error_code="chroma_inspection_error",
        ) from exc

    return total_documents
