from neo4j import Driver

from app.schemas.graph import GraphEdge, GraphExploreResult, GraphNode, GraphPath, OneHopGraphResult, SeedNode
from app.schemas.relations import RelationKind
from app.storage.neo4j.exceptions import Neo4jStorageError
from app.storage.neo4j.queries import GET_SEED_NODES_QUERY, build_graph_paths_query


class Neo4jGraphReader:
    def __init__(self, driver: Driver, *, database: str) -> None:
        self.driver = driver
        self.database = database

    def get_one_hop_neighbors(self, seed_ids: list[str]) -> OneHopGraphResult:
        result = self.get_neighbors(
            seed_ids=seed_ids,
            max_depth=1,
            allowed_relation_kinds=[kind.value for kind in RelationKind],
        )
        return OneHopGraphResult.model_validate(result.model_dump())

    def get_neighbors(
        self,
        *,
        seed_ids: list[str],
        max_depth: int,
        allowed_relation_kinds: list[str],
    ) -> GraphExploreResult:
        if not seed_ids:
            return GraphExploreResult(max_depth=max_depth)

        try:
            with self.driver.session(database=self.database) as session:
                seed_records = session.execute_read(_run_seed_query, seed_ids)
                path_records = session.execute_read(
                    _run_graph_paths_query,
                    seed_ids,
                    max_depth,
                    allowed_relation_kinds,
                )
        except Exception as exc:  # pragma: no cover - external database failure path
            raise Neo4jStorageError(
                f"Failed to read graph data from Neo4j: {exc}",
                error_code="neo4j_read_error",
            ) from exc

        seeds = [SeedNode.model_validate(item["seed"]) for item in seed_records]
        nodes_by_id: dict[str, GraphNode] = {}
        edges_by_id: dict[str, GraphEdge] = {}
        paths_by_key: dict[tuple[str, tuple[str, ...]], GraphPath] = {}

        for seed in seeds:
            nodes_by_id[seed.id] = GraphNode(
                id=seed.id,
                kind=seed.kind,
                language="",
                path=seed.path,
                name=seed.qualified_name.split(".")[-1],
                qualified_name=seed.qualified_name,
                signature=seed.qualified_name,
                start_line=0,
                end_line=0,
            )

        for record in path_records:
            path = record["path"]
            seed_id = record["seed_id"]
            node_ids: list[str] = []
            edge_ids: list[str] = []

            for node in path.nodes:
                graph_node = _graph_node_from_neo4j(node)
                nodes_by_id[graph_node.id] = graph_node
                node_ids.append(graph_node.id)

            for relationship in path.relationships:
                graph_edge = _graph_edge_from_neo4j(relationship)
                edges_by_id[graph_edge.id] = graph_edge
                edge_ids.append(graph_edge.id)

            if not node_ids:
                continue

            graph_path = GraphPath(
                seed_id=seed_id,
                terminal_node_id=node_ids[-1],
                node_ids=node_ids,
                edge_ids=edge_ids,
                hop_count=len(edge_ids),
            )
            paths_by_key[(seed_id, tuple(edge_ids))] = graph_path

        return GraphExploreResult(
            seeds=_sort_seeds(seeds),
            nodes=_sort_nodes(nodes_by_id.values()),
            edges=_sort_edges(edges_by_id.values()),
            graph_paths=_sort_paths(paths_by_key.values()),
            max_depth=max_depth,
            allowed_relation_kinds=[RelationKind(kind) for kind in sorted(set(allowed_relation_kinds))],
        )


def _run_seed_query(tx, seed_ids: list[str]):
    return list(tx.run(GET_SEED_NODES_QUERY, seed_ids=seed_ids))


def _run_graph_paths_query(tx, seed_ids: list[str], max_depth: int, allowed_relation_kinds: list[str]):
    query = build_graph_paths_query(max_depth)
    return list(
        tx.run(
            query,
            seed_ids=seed_ids,
            allowed_relation_kinds=allowed_relation_kinds,
        )
    )


def _graph_node_from_neo4j(node) -> GraphNode:
    return GraphNode(
        id=node["id"],
        kind=node["kind"],
        language=node.get("language") or "",
        path=node["path"],
        name=node["name"],
        qualified_name=node["qualified_name"],
        signature=node.get("signature") or "",
        start_line=int(node.get("start_line") or 0),
        end_line=int(node.get("end_line") or 0),
    )


def _graph_edge_from_neo4j(relationship) -> GraphEdge:
    return GraphEdge(
        id=relationship["id"],
        kind=RelationKind(relationship["kind"]),
        source_id=relationship.start_node["id"],
        destination_id=relationship.end_node["id"],
        path=relationship["path"],
        source=relationship["source"],
        destination=relationship["destination"],
    )


def _sort_seeds(seeds: list[SeedNode]) -> list[SeedNode]:
    return sorted(seeds, key=lambda item: (item.qualified_name, item.id))


def _sort_nodes(nodes) -> list[GraphNode]:
    return sorted(
        nodes,
        key=lambda item: (item.path, item.start_line, item.end_line, item.qualified_name, item.id),
    )


def _sort_edges(edges) -> list[GraphEdge]:
    return sorted(
        edges,
        key=lambda item: (item.kind.value, item.source_id, item.destination_id, item.id),
    )


def _sort_paths(paths) -> list[GraphPath]:
    return sorted(
        paths,
        key=lambda item: (item.hop_count, item.seed_id, item.terminal_node_id, tuple(item.edge_ids)),
    )
