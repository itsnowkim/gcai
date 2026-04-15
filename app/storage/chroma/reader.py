from __future__ import annotations

from app.storage.chroma.collections import get_callable_collection
from app.storage.chroma.exceptions import ChromaStorageError


class ChromaCodeReader:
    def __init__(self, client, *, collection_prefix: str) -> None:
        self.client = client
        self.collection_prefix = collection_prefix

    def query_similar_code(self, *, language: str, query_text: str, top_k: int) -> list[dict[str, object]]:
        if not query_text.strip() or top_k < 1:
            return []

        collection = get_callable_collection(
            self.client,
            collection_prefix=self.collection_prefix,
            language=language,
        )

        try:
            result = collection.query(
                query_texts=[query_text],
                n_results=top_k,
                include=["documents", "metadatas", "distances"],
            )
        except Exception as exc:  # pragma: no cover - external Chroma failure path
            raise ChromaStorageError(
                f"Failed to query Chroma documents: {exc}",
                error_code="chroma_query_error",
            ) from exc

        documents = result.get("documents", [[]])
        metadatas = result.get("metadatas", [[]])
        distances = result.get("distances", [[]])
        ids = result.get("ids", [[]])

        rows: list[dict[str, object]] = []
        for document, metadata, distance, row_id in zip(
            documents[0],
            metadatas[0],
            distances[0] if distances else [],
            ids[0] if ids else [],
            strict=False,
        ):
            rows.append(
                {
                    "id": row_id,
                    "document": document,
                    "metadata": metadata or {},
                    "distance": distance,
                }
            )
        return rows
