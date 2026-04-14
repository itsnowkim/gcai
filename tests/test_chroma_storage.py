from unittest.mock import MagicMock, patch

from app.analyzers.symbols import extract_symbols
from app.parsers.tree_sitter import parse_source_code
from app.schemas.scan import CodebaseScanResult, ScannedFile
from app.services.chroma_ingest import ingest_scan_result_to_chroma
from app.storage.chroma.collections import build_callable_collection_name
from app.storage.chroma.documents import build_chroma_documents
from app.storage.chroma.writer import ChromaDocumentWriter, _batched


def test_build_callable_collection_name_sanitizes_inputs() -> None:
    collection_name = build_callable_collection_name(collection_prefix="GCAI Main", language="C++")

    assert collection_name == "gcai-main-c-code-impl"


def test_build_chroma_documents_includes_callable_bodies_only() -> None:
    parsed = parse_source_code(
        """
class Greeter:
    prefix = "hi"

    def greet(self, name):
        message = self.prefix
        return message

def helper(value):
    total = value + 1
    return total
""".strip(),
        "python",
        path="sample.py",
    )
    symbols = extract_symbols(parsed).symbols
    scan_result = CodebaseScanResult(
        repo_path="/tmp/repo",
        scanned_files=[
            ScannedFile(
                path="sample.py",
                language="python",
                symbols=symbols,
                relations=[],
            )
        ],
    )

    documents_by_language = build_chroma_documents(scan_result)

    assert set(documents_by_language) == {"python"}
    rows = documents_by_language["python"]
    assert len(rows) == 2
    assert all(row["id"] for row in rows)
    assert all("qualified_name" in row["metadata"] for row in rows)
    assert any("def helper(value)" in row["document"] for row in rows)


def test_chroma_writer_batches_upserts() -> None:
    client = MagicMock()
    collection = MagicMock()
    client.get_or_create_collection.return_value = collection
    writer = ChromaDocumentWriter(client, collection_prefix="gcai", batch_size=2)
    rows = [
        {"id": "1", "document": "doc1", "metadata": {"language": "python"}},
        {"id": "2", "document": "doc2", "metadata": {"language": "python"}},
        {"id": "3", "document": "doc3", "metadata": {"language": "python"}},
    ]

    upserted_count = writer.upsert_documents(language="python", rows=rows)

    assert upserted_count == 3
    assert collection.upsert.call_count == 2


def test_chroma_batch_helper_splits_rows() -> None:
    rows = [{"id": str(index)} for index in range(5)]

    batches = list(_batched(rows, 2))

    assert batches == [
        [{"id": "0"}, {"id": "1"}],
        [{"id": "2"}, {"id": "3"}],
        [{"id": "4"}],
    ]


def test_ingest_scan_result_to_chroma_orchestrates_client_and_writer() -> None:
    parsed = parse_source_code(
        """
def helper(value):
    total = value + 1
    return total
""".strip(),
        "python",
        path="sample.py",
    )
    symbols = extract_symbols(parsed).symbols
    scan_result = CodebaseScanResult(
        repo_path="/tmp/repo",
        scanned_files=[
            ScannedFile(
                path="sample.py",
                language="python",
                symbols=symbols,
                relations=[],
            )
        ],
    )

    fake_client = MagicMock()
    fake_writer = MagicMock()
    fake_writer.upsert_documents.return_value = 1

    with (
        patch("app.services.chroma_ingest.create_chroma_client", return_value=fake_client),
        patch("app.services.chroma_ingest.verify_chroma_connectivity") as verify_mock,
        patch("app.services.chroma_ingest.ChromaDocumentWriter", return_value=fake_writer) as writer_cls,
    ):
        result = ingest_scan_result_to_chroma(scan_result)

    assert result == {"upserted_documents": 1}
    verify_mock.assert_called_once_with(fake_client)
    writer_cls.assert_called_once_with(fake_client, collection_prefix="gcai")
    fake_writer.upsert_documents.assert_called_once()
