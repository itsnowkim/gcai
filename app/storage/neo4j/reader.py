from neo4j import Driver

from app.schemas.graph import GraphEdge, GraphNode, OneHopGraphResult, SeedNode
from app.storage.neo4j.exceptions import Neo4jStorageError
from app.storage.neo4j.queries import GET_ONE_HOP_NEIGHBORS_QUERY


class Neo4jGraphReader:
    def __init__(self, driver: Driver, *, database: str) -> None:
        self.driver = driver
        self.database = database

    def get_one_hop_neighbors(self, seed_ids: list[str]) -> OneHopGraphResult:
        if not seed_ids:
            return OneHopGraphResult()

        try:
            with self.driver.session(database=self.database) as session:
                record = session.execute_read(_run_one_hop_query, seed_ids)
        except Exception as exc:  # pragma: no cover - external database failure path
            raise Neo4jStorageError(
                f"Failed to read graph data from Neo4j: {exc}",
                error_code="neo4j_read_error",
            ) from exc

        if record is None:
            return OneHopGraphResult()

        return OneHopGraphResult(
            seeds=[SeedNode.model_validate(item) for item in record["seeds"]],
            nodes=[GraphNode.model_validate(item) for item in record["nodes"]],
            edges=[GraphEdge.model_validate(item) for item in record["edges"]],
        )


def _run_one_hop_query(tx, seed_ids: list[str]):
    result = tx.run(GET_ONE_HOP_NEIGHBORS_QUERY, seed_ids=seed_ids)
    return result.single()
