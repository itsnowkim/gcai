from neo4j import Driver, GraphDatabase

from app.core.settings import Settings
from app.storage.neo4j.exceptions import Neo4jStorageError


def create_neo4j_driver(settings: Settings) -> Driver:
    try:
        return GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_username, settings.neo4j_password),
        )
    except Exception as exc:  # pragma: no cover - external driver failure path
        raise Neo4jStorageError(f"Failed to create Neo4j driver: {exc}", error_code="neo4j_driver_error") from exc


def verify_neo4j_connectivity(driver: Driver) -> None:
    try:
        driver.verify_connectivity()
    except Exception as exc:  # pragma: no cover - external connectivity failure path
        raise Neo4jStorageError(
            f"Failed to verify Neo4j connectivity: {exc}",
            error_code="neo4j_connectivity_error",
        ) from exc
