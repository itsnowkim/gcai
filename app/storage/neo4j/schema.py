from neo4j import Driver

from app.storage.neo4j.exceptions import Neo4jStorageError

CONSTRAINT_QUERIES: tuple[str, ...] = (
    "CREATE CONSTRAINT symbol_id_unique IF NOT EXISTS FOR (n:Symbol) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT relation_id_unique IF NOT EXISTS FOR ()-[r:RELATES_TO]-() REQUIRE r.id IS UNIQUE",
    "CREATE CONSTRAINT file_path_unique IF NOT EXISTS FOR (f:File) REQUIRE f.path IS UNIQUE",
)


def ensure_neo4j_constraints(driver: Driver, *, database: str) -> None:
    try:
        with driver.session(database=database) as session:
            for query in CONSTRAINT_QUERIES:
                session.run(query).consume()
    except Exception as exc:  # pragma: no cover - external database failure path
        raise Neo4jStorageError(
            f"Failed to ensure Neo4j constraints: {exc}",
            error_code="neo4j_constraint_error",
        ) from exc
