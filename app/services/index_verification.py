from app.core.exceptions import GCAIError
from app.core.logging import get_logger
from app.core.settings import get_settings
from app.schemas.indexing import InitialIndexVerificationResult
from app.schemas.scan import CodebaseScanResult
from app.storage.chroma.client import create_chroma_client, verify_chroma_connectivity
from app.storage.chroma.documents import build_chroma_documents
from app.storage.chroma.inspection import count_callable_documents
from app.storage.neo4j.client import create_neo4j_driver, verify_neo4j_connectivity
from app.storage.neo4j.inspection import count_indexed_graph_entities

logger = get_logger(__name__)


def verify_initial_index_storage(
    scan_result: CodebaseScanResult,
    *,
    expected_nodes: int,
    expected_edges: int,
    expected_documents: int,
) -> InitialIndexVerificationResult:
    settings = get_settings()
    driver = None
    client = None

    document_languages = tuple(build_chroma_documents(scan_result).keys())

    try:
        driver = create_neo4j_driver(settings)
        client = create_chroma_client(settings)

        verify_neo4j_connectivity(driver)
        verify_chroma_connectivity(client)

        graph_counts = count_indexed_graph_entities(driver, database=settings.neo4j_database)
        document_count = count_callable_documents(
            client,
            collection_prefix=settings.chroma_collection_prefix,
            languages=document_languages,
        )

        if graph_counts["node_count"] != expected_nodes:
            raise GCAIError(
                message=(
                    "Neo4j node count mismatch after initial indexing: "
                    f"expected {expected_nodes}, got {graph_counts['node_count']}"
                ),
                error_code="index_verification_error",
            )

        if graph_counts["edge_count"] != expected_edges:
            raise GCAIError(
                message=(
                    "Neo4j relation count mismatch after initial indexing: "
                    f"expected {expected_edges}, got {graph_counts['edge_count']}"
                ),
                error_code="index_verification_error",
            )

        if document_count != expected_documents:
            raise GCAIError(
                message=(
                    "Chroma document count mismatch after initial indexing: "
                    f"expected {expected_documents}, got {document_count}"
                ),
                error_code="index_verification_error",
            )
    finally:
        if driver is not None:
            driver.close()
        if client is not None:
            close_client = getattr(client, "close", None)
            if callable(close_client):
                close_client()

    logger.info(
        "initial_index_storage_verified",
        extra={
            "verified_nodes": graph_counts["node_count"],
            "verified_edges": graph_counts["edge_count"],
            "verified_documents": document_count,
            "repo_path": scan_result.repo_path,
        },
    )
    return InitialIndexVerificationResult(
        verified_nodes=graph_counts["node_count"],
        verified_edges=graph_counts["edge_count"],
        verified_documents=document_count,
    )
