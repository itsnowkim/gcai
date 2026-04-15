from unittest.mock import MagicMock, patch

from app.analyzers.symbols import extract_symbols
from app.parsers.tree_sitter import parse_source_code
from app.schemas.scan import CodebaseScanResult, ScannedFile
from app.services.chroma_ingest import ingest_scan_result_to_chroma
from app.services.incremental_update import (
    IncrementalAnalysisFile,
    IncrementalAnalysisResult,
    IncrementalSkippedFile,
    _build_incremental_chroma_documents,
    _collect_incremental_chroma_paths_by_language,
    _update_chroma_incrementally,
)
from app.storage.chroma.collections import build_callable_collection_name
from app.storage.chroma.documents import build_chroma_documents
from app.storage.chroma.reader import ChromaCodeReader
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


def test_chroma_writer_batches_deletes() -> None:
    client = MagicMock()
    collection = MagicMock()
    client.get_or_create_collection.return_value = collection
    writer = ChromaDocumentWriter(client, collection_prefix="gcai", batch_size=2)

    deleted_count = writer.delete_documents(language="python", ids=["1", "2", "3"])

    assert deleted_count == 3
    assert collection.delete.call_count == 2
    assert collection.delete.call_args_list[0].kwargs == {"ids": ["1", "2"]}
    assert collection.delete.call_args_list[1].kwargs == {"ids": ["3"]}


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


def test_chroma_reader_queries_collection() -> None:
    client = MagicMock()
    collection = MagicMock()
    collection.query.return_value = {
        "ids": [["symbol-1"]],
        "documents": [["def helper(value):\n    return value"]],
        "metadatas": [[{"symbol_id": "symbol-1", "language": "python", "path": "app/service.py"}]],
        "distances": [[0.1]],
    }
    client.get_or_create_collection.return_value = collection

    reader = ChromaCodeReader(client, collection_prefix="gcai")

    rows = reader.query_similar_code(language="python", query_text="def greet(self): pass", top_k=3)

    assert rows == [
        {
            "id": "symbol-1",
            "document": "def helper(value):\n    return value",
            "metadata": {"symbol_id": "symbol-1", "language": "python", "path": "app/service.py"},
            "distance": 0.1,
        }
    ]
    collection.query.assert_called_once_with(
        query_texts=["def greet(self): pass"],
        n_results=3,
        include=["documents", "metadatas", "distances"],
    )


def test_chroma_reader_fetches_document_ids_by_paths() -> None:
    client = MagicMock()
    collection = MagicMock()
    collection.get.return_value = {
        "ids": ["symbol-1", "symbol-2", "symbol-3"],
        "metadatas": [
            {"path": "app/service.py", "language": "python"},
            {"path": "app/service.py", "language": "python"},
            {"path": "app/other.py", "language": "python"},
        ],
    }
    client.get_or_create_collection.return_value = collection
    reader = ChromaCodeReader(client, collection_prefix="gcai")

    result = reader.get_document_ids_by_paths(language="python", paths=["app/service.py", "app/other.py"])

    assert result == {
        "app/service.py": ["symbol-1", "symbol-2"],
        "app/other.py": ["symbol-3"],
    }
    collection.get.assert_called_once_with(
        where={"path": {"$in": ["app/service.py", "app/other.py"]}},
        include=["metadatas"],
    )


def test_build_incremental_chroma_documents_uses_analyzed_files() -> None:
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
    analysis_result = IncrementalAnalysisResult(
        analyzed_files=[
            IncrementalAnalysisFile(
                path="sample.py",
                language="python",
                symbols=symbols,
                relations=[],
            )
        ]
    )

    result = _build_incremental_chroma_documents(analysis_result)

    assert set(result) == {"python"}
    assert len(result["python"]) == 1
    assert result["python"][0]["metadata"]["path"] == "sample.py"


def test_collect_incremental_chroma_paths_by_language_includes_deleted_and_missing_supported_files() -> None:
    analysis_result = IncrementalAnalysisResult(
        analyzed_files=[
            IncrementalAnalysisFile(
                path="app/service.py",
                language="python",
                symbols=[],
                relations=[],
            )
        ],
        deleted_files=["legacy/deleted.py", "docs/readme.md"],
        skipped_files=[
            IncrementalSkippedFile(path="missing/module.py", reason="missing_file"),
            IncrementalSkippedFile(path="README.md", reason="unsupported_language"),
        ],
    )

    result = _collect_incremental_chroma_paths_by_language(analysis_result)

    assert result == {
        "python": ["app/service.py", "legacy/deleted.py", "missing/module.py"],
    }


def test_update_chroma_incrementally_orchestrates_cleanup_and_upsert() -> None:
    parsed = parse_source_code(
        """
def helper(value):
    total = value + 1
    return total
""".strip(),
        "python",
        path="app/service.py",
    )
    symbols = extract_symbols(parsed).symbols
    analysis_result = IncrementalAnalysisResult(
        changed_files=["app/service.py", "legacy/deleted.py"],
        analyzed_files=[
            IncrementalAnalysisFile(
                path="app/service.py",
                language="python",
                symbols=symbols,
                relations=[],
            )
        ],
        deleted_files=["legacy/deleted.py"],
    )

    fake_client = MagicMock()
    fake_reader = MagicMock()
    fake_reader.get_document_ids_by_paths.return_value = {
        "app/service.py": ["symbol-1"],
        "legacy/deleted.py": ["symbol-2"],
    }
    fake_writer = MagicMock()
    fake_writer.delete_documents.return_value = 2
    fake_writer.upsert_documents.return_value = 1

    with (
        patch("app.services.incremental_update.get_settings", return_value=MagicMock(chroma_collection_prefix="gcai")),
        patch("app.services.incremental_update.create_chroma_client", return_value=fake_client),
        patch("app.services.incremental_update.verify_chroma_connectivity") as verify_mock,
        patch("app.services.incremental_update.ChromaCodeReader", return_value=fake_reader) as reader_cls,
        patch("app.services.incremental_update.ChromaDocumentWriter", return_value=fake_writer) as writer_cls,
    ):
        result = _update_chroma_incrementally(analysis_result)

    assert result == {"reindexed_embeddings": 1}
    verify_mock.assert_called_once_with(fake_client)
    reader_cls.assert_called_once_with(fake_client, collection_prefix="gcai")
    writer_cls.assert_called_once_with(fake_client, collection_prefix="gcai")
    fake_reader.get_document_ids_by_paths.assert_called_once_with(
        language="python",
        paths=["app/service.py", "legacy/deleted.py"],
    )
    fake_writer.delete_documents.assert_called_once_with(language="python", ids=["symbol-1", "symbol-2"])
    fake_writer.upsert_documents.assert_called_once()
    fake_client.close.assert_called_once()
