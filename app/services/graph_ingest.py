from app.core.logging import get_logger
from app.core.settings import get_settings
from app.schemas.scan import CodebaseScanResult
from app.storage.neo4j.client import create_neo4j_driver, verify_neo4j_connectivity
from app.storage.neo4j.schema import ensure_neo4j_constraints
from app.storage.neo4j.writer import Neo4jGraphWriter

logger = get_logger(__name__)


def ingest_scan_result_to_neo4j(scan_result: CodebaseScanResult) -> dict[str, int]:
    settings = get_settings()
    driver = create_neo4j_driver(settings)
    try:
        verify_neo4j_connectivity(driver)
        ensure_neo4j_constraints(driver, database=settings.neo4j_database)
        writer = Neo4jGraphWriter(driver, database=settings.neo4j_database)

        all_symbols = [symbol for item in scan_result.scanned_files for symbol in item.symbols]
        all_relations = [relation for item in scan_result.scanned_files for relation in item.relations]

        upserted_nodes = writer.upsert_symbols(all_symbols)
        upserted_edges = writer.upsert_relations(all_relations)
        logger.info(
            "neo4j_ingest_completed",
            extra={
                "upserted_nodes": upserted_nodes,
                "upserted_edges": upserted_edges,
                "repo_path": scan_result.repo_path,
            },
        )
        return {"upserted_nodes": upserted_nodes, "upserted_edges": upserted_edges}
    finally:
        driver.close()
