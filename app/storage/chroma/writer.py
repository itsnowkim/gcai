from itertools import islice

from app.storage.chroma.collections import get_callable_collection
from app.storage.chroma.exceptions import ChromaStorageError

DEFAULT_BATCH_SIZE = 200


class ChromaDocumentWriter:
    def __init__(self, client, *, collection_prefix: str, batch_size: int = DEFAULT_BATCH_SIZE) -> None:
        self.client = client
        self.collection_prefix = collection_prefix
        self.batch_size = batch_size

    def upsert_documents(self, *, language: str, rows: list[dict[str, object]]) -> int:
        if not rows:
            return 0

        collection = get_callable_collection(
            self.client,
            collection_prefix=self.collection_prefix,
            language=language,
        )

        try:
            for batch in _batched(rows, self.batch_size):
                collection.upsert(
                    ids=[row["id"] for row in batch],
                    documents=[row["document"] for row in batch],
                    metadatas=[row["metadata"] for row in batch],
                )
        except Exception as exc:  # pragma: no cover - external Chroma failure path
            raise ChromaStorageError(
                f"Failed to upsert Chroma documents: {exc}",
                error_code="chroma_upsert_error",
            ) from exc

        return len(rows)


def _batched(rows: list[dict[str, object]], batch_size: int):
    iterator = iter(rows)
    while batch := list(islice(iterator, batch_size)):
        yield batch
