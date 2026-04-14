from unittest.mock import MagicMock, patch

from app.schemas.changed_code import ChangedCodeContextResult, ChangedSymbolSeed
from app.schemas.diff import DiffLineRange
from app.schemas.graph import OneHopGraphResult, SeedNode
from app.schemas.symbols import ExtractedSymbol, SymbolKind
from app.services.graph_explore import build_seed_nodes, explore_one_hop_neighbors
from app.storage.neo4j.reader import Neo4jGraphReader
from app.storage.neo4j.queries import GET_ONE_HOP_NEIGHBORS_QUERY


def test_build_seed_nodes_uses_changed_symbols() -> None:
    changed_code_context = ChangedCodeContextResult(
        repo_path="/repo",
        changed_symbols=[
            ChangedSymbolSeed(
                symbol=ExtractedSymbol(
                    id="method:/repo/app.py:Greeter.greet:10",
                    kind=SymbolKind.METHOD,
                    language="python",
                    path="/repo/app.py",
                    name="greet",
                    qualified_name="Greeter.greet",
                    signature="def greet(self)",
                    start_line=10,
                    start_column=1,
                    end_line=12,
                    end_column=1,
                    code="def greet(self): pass",
                ),
                matched_line_ranges=[DiffLineRange(start_line=10, line_count=1)],
            )
        ],
    )

    seeds = build_seed_nodes(changed_code_context)

    assert seeds == [
        SeedNode(
            id="method:/repo/app.py:Greeter.greet:10",
            path="/repo/app.py",
            kind="method",
            qualified_name="Greeter.greet",
        )
    ]


def test_get_one_hop_query_is_defined() -> None:
    assert "MATCH (seed:Symbol)" in GET_ONE_HOP_NEIGHBORS_QUERY
    assert "RELATES_TO" in GET_ONE_HOP_NEIGHBORS_QUERY


def test_neo4j_graph_reader_returns_one_hop_graph_result() -> None:
    driver = MagicMock()
    session = MagicMock()
    driver.session.return_value.__enter__.return_value = session
    session.execute_read.return_value = {
        "seeds": [
            {
                "id": "seed-1",
                "path": "app/service.py",
                "kind": "method",
                "qualified_name": "Greeter.greet",
            }
        ],
        "nodes": [
            {
                "id": "seed-1",
                "kind": "method",
                "language": "python",
                "path": "app/service.py",
                "name": "greet",
                "qualified_name": "Greeter.greet",
                "signature": "def greet(self, name)",
                "start_line": 10,
                "end_line": 12,
            }
        ],
        "edges": [
            {
                "id": "calls:app/service.py:Greeter.greet->helper",
                "kind": "calls",
                "source_id": "seed-1",
                "destination_id": "node-2",
                "path": "app/service.py",
                "source": "Greeter.greet",
                "destination": "helper",
            }
        ],
    }

    reader = Neo4jGraphReader(driver, database="neo4j")

    result = reader.get_one_hop_neighbors(["seed-1"])

    assert isinstance(result, OneHopGraphResult)
    assert result.seeds[0].id == "seed-1"
    assert result.nodes[0].qualified_name == "Greeter.greet"
    assert result.edges[0].kind.value == "calls"


def test_explore_one_hop_neighbors_orchestrates_driver_lifecycle() -> None:
    fake_driver = MagicMock()
    fake_reader = MagicMock()
    fake_reader.get_one_hop_neighbors.return_value = OneHopGraphResult()

    with (
        patch("app.services.graph_explore.create_neo4j_driver", return_value=fake_driver),
        patch("app.services.graph_explore.verify_neo4j_connectivity") as verify_mock,
        patch("app.services.graph_explore.Neo4jGraphReader", return_value=fake_reader) as reader_cls,
    ):
        result = explore_one_hop_neighbors(
            [SeedNode(id="seed-1", path="app/service.py", kind="method", qualified_name="Greeter.greet")]
        )

    assert result == OneHopGraphResult()
    verify_mock.assert_called_once_with(fake_driver)
    reader_cls.assert_called_once_with(fake_driver, database="neo4j")
    fake_reader.get_one_hop_neighbors.assert_called_once_with(["seed-1"])
    fake_driver.close.assert_called_once()
