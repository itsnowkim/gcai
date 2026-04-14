from neo4j import Driver

from app.storage.neo4j.exceptions import Neo4jStorageError

NODE_COUNT_QUERY = "MATCH (n:Symbol) RETURN count(n) AS node_count"
EDGE_COUNT_QUERY = "MATCH ()-[r:RELATES_TO]->() RETURN count(r) AS edge_count"


def count_indexed_graph_entities(driver: Driver, *, database: str) -> dict[str, int]:
    try:
        with driver.session(database=database) as session:
            node_count = int(session.run(NODE_COUNT_QUERY).single()["node_count"])
            edge_count = int(session.run(EDGE_COUNT_QUERY).single()["edge_count"])
    except Exception as exc:  # pragma: no cover - external database failure path
        raise Neo4jStorageError(
            f"Failed to inspect Neo4j indexed entities: {exc}",
            error_code="neo4j_inspection_error",
        ) from exc

    return {"node_count": node_count, "edge_count": edge_count}
