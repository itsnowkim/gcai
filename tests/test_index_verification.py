from unittest.mock import MagicMock, patch

from app.core.exceptions import GCAIError
from app.schemas.scan import CodebaseScanResult
from app.services.index_verification import verify_initial_index_storage


def test_verify_initial_index_storage_counts_indexed_records() -> None:
    scan_result = CodebaseScanResult(repo_path="/tmp/repo")
    fake_driver = MagicMock()
    fake_client = MagicMock()

    fake_collection = MagicMock()
    fake_collection.name = "gcai-python-code-impl"
    fake_collection.count.return_value = 4
    fake_client.list_collections.return_value = [fake_collection]

    neo4j_session = MagicMock()
    neo4j_driver_session = MagicMock()
    neo4j_driver_session.__enter__.return_value = neo4j_session
    fake_driver.session.return_value = neo4j_driver_session

    node_record = MagicMock()
    node_record.__getitem__.return_value = 10
    edge_record = MagicMock()
    edge_record.__getitem__.return_value = 20
    neo4j_session.run.side_effect = [
        MagicMock(single=MagicMock(return_value=node_record)),
        MagicMock(single=MagicMock(return_value=edge_record)),
    ]

    with (
        patch("app.services.index_verification.create_neo4j_driver", return_value=fake_driver),
        patch("app.services.index_verification.create_chroma_client", return_value=fake_client),
        patch("app.services.index_verification.verify_neo4j_connectivity") as verify_neo4j_mock,
        patch("app.services.index_verification.verify_chroma_connectivity") as verify_chroma_mock,
        patch("app.services.index_verification.build_chroma_documents", return_value={"python": []}),
    ):
        result = verify_initial_index_storage(
            scan_result,
            expected_nodes=10,
            expected_edges=20,
            expected_documents=4,
        )

    assert result.verified_nodes == 10
    assert result.verified_edges == 20
    assert result.verified_documents == 4
    verify_neo4j_mock.assert_called_once_with(fake_driver)
    verify_chroma_mock.assert_called_once_with(fake_client)
    fake_client.list_collections.assert_called_once()
    fake_driver.close.assert_called_once()
    fake_client.close.assert_called_once()


def test_verify_initial_index_storage_raises_on_mismatch() -> None:
    scan_result = CodebaseScanResult(repo_path="/tmp/repo")
    fake_driver = MagicMock()
    fake_client = MagicMock()

    fake_collection = MagicMock()
    fake_collection.name = "gcai-python-code-impl"
    fake_collection.count.return_value = 3
    fake_client.list_collections.return_value = [fake_collection]

    neo4j_session = MagicMock()
    neo4j_driver_session = MagicMock()
    neo4j_driver_session.__enter__.return_value = neo4j_session
    fake_driver.session.return_value = neo4j_driver_session

    node_record = MagicMock()
    node_record.__getitem__.return_value = 10
    edge_record = MagicMock()
    edge_record.__getitem__.return_value = 20
    neo4j_session.run.side_effect = [
        MagicMock(single=MagicMock(return_value=node_record)),
        MagicMock(single=MagicMock(return_value=edge_record)),
    ]

    with (
        patch("app.services.index_verification.create_neo4j_driver", return_value=fake_driver),
        patch("app.services.index_verification.create_chroma_client", return_value=fake_client),
        patch("app.services.index_verification.verify_neo4j_connectivity"),
        patch("app.services.index_verification.verify_chroma_connectivity"),
        patch("app.services.index_verification.build_chroma_documents", return_value={"python": []}),
    ):
        try:
            verify_initial_index_storage(
                scan_result,
                expected_nodes=10,
                expected_edges=20,
                expected_documents=4,
            )
        except GCAIError as exc:
            assert exc.error_code == "index_verification_error"
        else:  # pragma: no cover - defensive branch
            raise AssertionError("Expected verification mismatch to raise GCAIError")
