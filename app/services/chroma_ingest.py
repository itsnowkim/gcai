from app.core.logging import get_logger
from app.core.settings import get_settings
from app.schemas.scan import CodebaseScanResult
from app.storage.chroma.client import create_chroma_client, verify_chroma_connectivity
from app.storage.chroma.documents import build_chroma_documents
from app.storage.chroma.writer import ChromaDocumentWriter

logger = get_logger(__name__)


def ingest_scan_result_to_chroma(scan_result: CodebaseScanResult) -> dict[str, int]:
    settings = get_settings()
    client = create_chroma_client(settings)
    try:
        verify_chroma_connectivity(client)

        writer = ChromaDocumentWriter(client, collection_prefix=settings.chroma_collection_prefix)
        documents_by_language = build_chroma_documents(scan_result)

        upserted_documents = 0
        for language, rows in documents_by_language.items():
            upserted_documents += writer.upsert_documents(language=language, rows=rows)

        logger.info(
            "chroma_ingest_completed",
            extra={
                "upserted_documents": upserted_documents,
                "repo_path": scan_result.repo_path,
            },
        )
        return {"upserted_documents": upserted_documents}
    finally:
        close_client = getattr(client, "close", None)
        if callable(close_client):
            close_client()
