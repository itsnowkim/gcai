from unittest.mock import MagicMock, patch
from pathlib import Path

from app.parsers.tree_sitter import parse_source_code
from app.schemas.scan import CodebaseScanResult, ScannedFile
from app.services.graph_ingest import ingest_scan_result_to_neo4j
from app.storage.neo4j.queries import (
    DELETE_RELATIONS_BY_PATHS_QUERY,
    DELETE_SYMBOLS_BY_PATHS_QUERY,
    GET_SYMBOL_IDS_BY_PATHS_QUERY,
    UPSERT_RELATIONS_QUERY,
    UPSERT_SYMBOLS_QUERY,
)
from app.storage.neo4j.reader import Neo4jGraphReader
from app.storage.neo4j.schema import CONSTRAINT_QUERIES, ensure_neo4j_constraints
from app.storage.neo4j.writer import Neo4jGraphWriter, _batched
from app.analyzers.symbols import extract_symbols
from app.analyzers.relations import extract_relations
from app.services.incremental_update import (
    IncrementalAnalysisFile,
    IncrementalAnalysisResult,
    _update_neo4j_incrementally,
)


def test_batched_splits_rows_by_batch_size() -> None:
    rows = [{"value": index} for index in range(5)]

    batches = list(_batched(rows, 2))

    assert batches == [
        [{"value": 0}, {"value": 1}],
        [{"value": 2}, {"value": 3}],
        [{"value": 4}],
    ]


def test_ensure_neo4j_constraints_runs_expected_queries() -> None:
    driver = MagicMock()
    session = MagicMock()
    driver.session.return_value.__enter__.return_value = session

    ensure_neo4j_constraints(driver, database="neo4j")

    assert session.run.call_count == len(CONSTRAINT_QUERIES)
    assert [call.args[0] for call in session.run.call_args_list] == list(CONSTRAINT_QUERIES)


def test_upsert_symbols_query_applies_file_label_conditionally() -> None:
    assert "CASE WHEN row.kind = 'file'" in UPSERT_SYMBOLS_QUERY
    assert "REMOVE n:File" in UPSERT_SYMBOLS_QUERY


def test_upsert_relations_query_stores_metadata_as_json() -> None:
    assert "metadata_json" in UPSERT_RELATIONS_QUERY
    assert "DELETE existing" in UPSERT_RELATIONS_QUERY


def test_incremental_queries_cover_file_level_cleanup() -> None:
    assert "symbol.path IN $paths" in GET_SYMBOL_IDS_BY_PATHS_QUERY
    assert "r.path IN $paths" in DELETE_RELATIONS_BY_PATHS_QUERY
    assert "DETACH DELETE node" in DELETE_SYMBOLS_BY_PATHS_QUERY


def test_neo4j_graph_writer_executes_batched_upserts() -> None:
    driver = MagicMock()
    session = MagicMock()
    driver.session.return_value.__enter__.return_value = session
    session.execute_write.side_effect = [2, 1]
    writer = Neo4jGraphWriter(driver, database="neo4j", batch_size=2)

    parsed = parse_source_code(
        """
class Greeter:
    def greet(self, name):
        return name
""".strip(),
        "python",
        path="sample.py",
    )
    symbols = extract_symbols(parsed).symbols[:3]

    upserted_count = writer.upsert_symbols(symbols)

    assert upserted_count == 3
    assert session.execute_write.call_count == 2


def test_upsert_relations_deduplicates_rows_by_relation_id() -> None:
    driver = MagicMock()
    session = MagicMock()
    driver.session.return_value.__enter__.return_value = session
    session.execute_write.return_value = 1
    writer = Neo4jGraphWriter(driver, database="neo4j", batch_size=10)

    relation = extract_relations(
        parse_source_code("value = 1\n", "python", path="sample.py")
    ).relations[0]

    upserted_count = writer.upsert_relations([relation, relation])

    assert upserted_count == 1
    rows = session.execute_write.call_args.args[2]
    assert len(rows) == 1


def test_neo4j_graph_reader_fetches_symbol_ids_by_path() -> None:
    driver = MagicMock()
    session = MagicMock()
    driver.session.return_value.__enter__.return_value = session
    session.execute_read.return_value = [
        {"path": "app/service.py", "symbol_id": "file:app/service.py:app/service.py:1"},
        {"path": "app/service.py", "symbol_id": "function:app/service.py:greet:3"},
        {"path": "app/other.py", "symbol_id": "file:app/other.py:app/other.py:1"},
    ]
    reader = Neo4jGraphReader(driver, database="neo4j")

    result = reader.get_symbol_ids_by_paths(["app/service.py", "app/other.py"])

    assert result == {
        "app/service.py": [
            "file:app/service.py:app/service.py:1",
            "function:app/service.py:greet:3",
        ],
        "app/other.py": ["file:app/other.py:app/other.py:1"],
    }
    session.execute_read.assert_called_once()


def test_neo4j_graph_writer_deletes_file_scoped_data() -> None:
    driver = MagicMock()
    session = MagicMock()
    driver.session.return_value.__enter__.return_value = session
    session.execute_write.side_effect = [3, 2]
    writer = Neo4jGraphWriter(driver, database="neo4j")

    deleted_edges = writer.delete_relations_by_paths(["app/service.py"])
    deleted_nodes = writer.delete_symbols_by_paths(["app/service.py"])

    assert deleted_edges == 3
    assert deleted_nodes == 2
    first_call = session.execute_write.call_args_list[0]
    second_call = session.execute_write.call_args_list[1]
    assert first_call.args[1] == DELETE_RELATIONS_BY_PATHS_QUERY
    assert first_call.args[2] == {"paths": ["app/service.py"]}
    assert second_call.args[1] == DELETE_SYMBOLS_BY_PATHS_QUERY
    assert second_call.args[2] == {"paths": ["app/service.py"]}


def test_ingest_scan_result_to_neo4j_orchestrates_driver_lifecycle() -> None:
    parsed = parse_source_code("value = 1\n", "python", path="sample.py")
    symbol_result = extract_symbols(parsed)
    relation_result = extract_relations(parsed)
    scan_result = CodebaseScanResult(
        repo_path="/tmp/repo",
        scanned_files=[
            ScannedFile(
                path="sample.py",
                language="python",
                symbols=symbol_result.symbols,
                relations=relation_result.relations,
            )
        ],
    )

    fake_driver = MagicMock()
    fake_writer = MagicMock()
    fake_writer.upsert_symbols.return_value = 2
    fake_writer.upsert_relations.return_value = 1

    with (
        patch("app.services.graph_ingest.create_neo4j_driver", return_value=fake_driver),
        patch("app.services.graph_ingest.verify_neo4j_connectivity") as verify_mock,
        patch("app.services.graph_ingest.ensure_neo4j_constraints") as constraints_mock,
        patch("app.services.graph_ingest.Neo4jGraphWriter", return_value=fake_writer) as writer_cls,
    ):
        result = ingest_scan_result_to_neo4j(scan_result)

    assert result == {"upserted_nodes": 2, "upserted_edges": 1}
    verify_mock.assert_called_once_with(fake_driver)
    constraints_mock.assert_called_once_with(fake_driver, database="neo4j")
    writer_cls.assert_called_once_with(fake_driver, database="neo4j")
    fake_driver.close.assert_called_once()


def test_update_neo4j_incrementally_orchestrates_cleanup_and_upsert() -> None:
    parsed = parse_source_code(
        """
def greet(name):
    return name
""".strip(),
        "python",
        path="app/service.py",
    )
    symbols = extract_symbols(parsed).symbols
    relations = extract_relations(parsed).relations
    analysis_result = IncrementalAnalysisResult(
        repo_path="/repo",
        changed_files=["app/service.py", "legacy/deleted.py"],
        analyzed_files=[
            IncrementalAnalysisFile(
                path="app/service.py",
                language="python",
                symbols=symbols,
                relations=relations,
            )
        ],
        deleted_files=["legacy/deleted.py"],
    )

    fake_driver = MagicMock()
    fake_reader = MagicMock()
    fake_reader.get_symbol_ids_by_paths.return_value = {
        "app/service.py": ["old-symbol-1", "old-symbol-2"],
        "legacy/deleted.py": ["legacy-symbol"],
    }
    fake_writer = MagicMock()
    fake_writer.delete_relations_by_paths.return_value = 4
    fake_writer.delete_symbols_by_paths.return_value = 3
    fake_writer.upsert_symbols.return_value = 2
    fake_writer.upsert_relations.return_value = 1

    with (
        patch("app.services.incremental_update.get_settings", return_value=MagicMock(neo4j_database="neo4j")),
        patch("app.services.incremental_update.create_neo4j_driver", return_value=fake_driver),
        patch("app.services.incremental_update.verify_neo4j_connectivity") as verify_mock,
        patch("app.services.incremental_update.ensure_neo4j_constraints") as constraints_mock,
        patch("app.services.incremental_update.Neo4jGraphReader", return_value=fake_reader) as reader_cls,
        patch("app.services.incremental_update.Neo4jGraphWriter", return_value=fake_writer) as writer_cls,
    ):
        result = _update_neo4j_incrementally(analysis_result)

    assert result == {"updated_nodes": 2, "updated_edges": 1}
    verify_mock.assert_called_once_with(fake_driver)
    constraints_mock.assert_called_once_with(fake_driver, database="neo4j")
    reader_cls.assert_called_once_with(fake_driver, database="neo4j")
    writer_cls.assert_called_once_with(fake_driver, database="neo4j")
    expected_paths = [
        (Path("/repo").resolve() / "app/service.py").resolve().as_posix(),
        (Path("/repo").resolve() / "legacy/deleted.py").resolve().as_posix(),
    ]
    fake_reader.get_symbol_ids_by_paths.assert_called_once_with(expected_paths)
    fake_writer.delete_relations_by_paths.assert_called_once_with(expected_paths)
    fake_writer.delete_symbols_by_paths.assert_called_once_with(expected_paths)
    fake_writer.upsert_symbols.assert_called_once_with(symbols)
    fake_writer.upsert_relations.assert_called_once_with(relations)
    fake_driver.close.assert_called_once()
