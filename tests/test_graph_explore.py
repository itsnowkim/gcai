from unittest.mock import MagicMock, patch

from app.schemas.changed_code import ChangedCodeContextResult, ChangedSymbolSeed
from app.schemas.diff import DiffLineRange
from app.schemas.graph import GraphExploreResult, OneHopGraphResult, SeedNode
from app.schemas.relations import RelationKind
from app.schemas.symbols import ExtractedSymbol, SymbolKind
from app.services.graph_explore import build_seed_nodes, explore_graph_neighbors, explore_one_hop_neighbors
from app.storage.neo4j.reader import Neo4jGraphReader
from app.storage.neo4j.queries import GET_SEED_NODES_QUERY, build_graph_paths_query


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


def test_graph_queries_are_defined() -> None:
    query = build_graph_paths_query(2)

    assert "MATCH (seed:Symbol)" in GET_SEED_NODES_QUERY
    assert "RELATES_TO*1..2" in query
    assert "allowed_relation_kinds" in query


def test_neo4j_graph_reader_returns_graph_explore_result() -> None:
    driver = MagicMock()
    session = MagicMock()
    driver.session.return_value.__enter__.return_value = session
    seed_node = {
        "seed": {
            "id": "seed-1",
            "path": "app/service.py",
            "kind": "method",
            "qualified_name": "Greeter.greet",
        }
    }
    path_node_seed = {
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
    path_node_neighbor = {
        "id": "node-2",
        "kind": "function",
        "language": "python",
        "path": "app/service.py",
        "name": "helper",
        "qualified_name": "helper",
        "signature": "def helper(name)",
        "start_line": 1,
        "end_line": 2,
    }
    relationship = MagicMock()
    relationship.__getitem__.side_effect = {
        "id": "calls:app/service.py:Greeter.greet->helper",
        "kind": "calls",
        "path": "app/service.py",
        "source": "Greeter.greet",
        "destination": "helper",
    }.__getitem__
    relationship.start_node = {"id": "seed-1"}
    relationship.end_node = {"id": "node-2"}
    path = MagicMock()
    path.nodes = [path_node_seed, path_node_neighbor]
    path.relationships = [relationship]
    session.execute_read.side_effect = [[seed_node], [{"seed_id": "seed-1", "path": path}]]

    reader = Neo4jGraphReader(driver, database="neo4j")

    result = reader.get_neighbors(
        seed_ids=["seed-1"],
        max_depth=2,
        allowed_relation_kinds=["calls"],
    )

    assert isinstance(result, GraphExploreResult)
    assert result.seeds[0].id == "seed-1"
    assert {node.qualified_name for node in result.nodes} == {"Greeter.greet", "helper"}
    assert result.edges[0].kind.value == "calls"
    assert result.graph_paths[0].node_ids == ["seed-1", "node-2"]
    assert result.max_depth == 2
    assert result.allowed_relation_kinds == [RelationKind.CALLS]


def test_explore_one_hop_neighbors_orchestrates_driver_lifecycle() -> None:
    fake_driver = MagicMock()
    fake_reader = MagicMock()
    fake_reader.get_neighbors.return_value = GraphExploreResult()

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
    fake_reader.get_neighbors.assert_called_once_with(
        seed_ids=["seed-1"],
        max_depth=1,
        allowed_relation_kinds=["contains", "imports", "calls", "reads", "writes"],
    )
    fake_driver.close.assert_called_once()


def test_explore_graph_neighbors_passes_depth_and_allowlist() -> None:
    fake_driver = MagicMock()
    fake_reader = MagicMock()
    fake_reader.get_neighbors.return_value = GraphExploreResult()

    with (
        patch("app.services.graph_explore.create_neo4j_driver", return_value=fake_driver),
        patch("app.services.graph_explore.verify_neo4j_connectivity"),
        patch("app.services.graph_explore.Neo4jGraphReader", return_value=fake_reader),
    ):
        explore_graph_neighbors(
            [SeedNode(id="seed-1", path="app/service.py", kind="method", qualified_name="Greeter.greet")],
            max_depth=2,
            allowed_relation_kinds=(RelationKind.CALLS, RelationKind.IMPORTS),
        )

    fake_reader.get_neighbors.assert_called_once_with(
        seed_ids=["seed-1"],
        max_depth=2,
        allowed_relation_kinds=["calls", "imports"],
    )
