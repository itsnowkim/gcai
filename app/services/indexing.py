from pathlib import Path

from app.core.logging import get_logger
from app.schemas.indexing import InitialIndexResult
from app.services.chroma_ingest import ingest_scan_result_to_chroma
from app.services.codebase_scan import scan_codebase
from app.services.index_verification import verify_initial_index_storage
from app.services.graph_ingest import ingest_scan_result_to_neo4j

logger = get_logger(__name__)


def run_initial_index(repo_path: str | Path) -> InitialIndexResult:
    scan_result = scan_codebase(repo_path)
    neo4j_result = ingest_scan_result_to_neo4j(scan_result)
    chroma_result = ingest_scan_result_to_chroma(scan_result)
    verification_result = verify_initial_index_storage(
        scan_result,
        expected_nodes=neo4j_result["upserted_nodes"],
        expected_edges=neo4j_result["upserted_edges"],
        expected_documents=chroma_result["upserted_documents"],
    )

    result = InitialIndexResult(
        repo_path=scan_result.repo_path,
        scanned_files=scan_result.scanned_file_count,
        skipped_files=scan_result.skipped_file_count,
        upserted_nodes=neo4j_result["upserted_nodes"],
        upserted_edges=neo4j_result["upserted_edges"],
        upserted_documents=chroma_result["upserted_documents"],
        verified_nodes=verification_result.verified_nodes,
        verified_edges=verification_result.verified_edges,
        verified_documents=verification_result.verified_documents,
    )
    logger.info(
        "initial_index_completed",
        extra={
            "repo_path": result.repo_path,
            "scanned_files": result.scanned_files,
            "skipped_files": result.skipped_files,
            "upserted_nodes": result.upserted_nodes,
            "upserted_edges": result.upserted_edges,
            "upserted_documents": result.upserted_documents,
            "verified_nodes": result.verified_nodes,
            "verified_edges": result.verified_edges,
            "verified_documents": result.verified_documents,
        },
    )
    return result
