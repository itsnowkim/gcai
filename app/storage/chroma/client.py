import chromadb

from app.core.settings import Settings
from app.storage.chroma.exceptions import ChromaStorageError


def create_chroma_client(settings: Settings):
    try:
        return chromadb.HttpClient(
            host=settings.chroma_host,
            port=settings.chroma_port,
        )
    except Exception as exc:  # pragma: no cover - external client failure path
        raise ChromaStorageError(f"Failed to create Chroma client: {exc}", error_code="chroma_client_error") from exc


def verify_chroma_connectivity(client) -> None:
    try:
        client.heartbeat()
    except Exception as exc:  # pragma: no cover - external connectivity failure path
        raise ChromaStorageError(
            f"Failed to verify Chroma connectivity: {exc}",
            error_code="chroma_connectivity_error",
        ) from exc
