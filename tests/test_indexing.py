from unittest.mock import patch

from app.schemas.indexing import InitialIndexResult
from app.schemas.scan import CodebaseScanResult
from app.services.indexing import run_initial_index


def test_run_initial_index_orchestrates_scan_and_ingest() -> None:
    scan_result = CodebaseScanResult(repo_path="/tmp/repo")

    with (
        patch("app.services.indexing.scan_codebase", return_value=scan_result) as scan_mock,
        patch(
            "app.services.indexing.ingest_scan_result_to_neo4j",
            return_value={"upserted_nodes": 10, "upserted_edges": 20},
        ) as neo4j_mock,
        patch(
            "app.services.indexing.ingest_scan_result_to_chroma",
            return_value={"upserted_documents": 4},
        ) as chroma_mock,
    ):
        result = run_initial_index("/tmp/repo")

    assert result == InitialIndexResult(
        repo_path="/tmp/repo",
        scanned_files=0,
        skipped_files=0,
        upserted_nodes=10,
        upserted_edges=20,
        upserted_documents=4,
    )
    scan_mock.assert_called_once_with("/tmp/repo")
    neo4j_mock.assert_called_once_with(scan_result)
    chroma_mock.assert_called_once_with(scan_result)
