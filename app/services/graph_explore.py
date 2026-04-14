from pathlib import Path

from app.core.settings import get_settings
from app.schemas.changed_code import ChangedCodeContextResult
from app.schemas.graph import OneHopGraphResult, SeedNode
from app.storage.neo4j.client import create_neo4j_driver, verify_neo4j_connectivity
from app.storage.neo4j.reader import Neo4jGraphReader


def build_seed_nodes(changed_code_context: ChangedCodeContextResult) -> list[SeedNode]:
    return [
        SeedNode(
            id=item.symbol.id,
            path=item.symbol.path,
            kind=item.symbol.kind.value,
            qualified_name=item.symbol.qualified_name,
        )
        for item in changed_code_context.changed_symbols
    ]


def explore_one_hop_from_changed_code(
    changed_code_context: ChangedCodeContextResult,
) -> OneHopGraphResult:
    seeds = build_seed_nodes(changed_code_context)
    return explore_one_hop_neighbors(seeds)


def explore_one_hop_neighbors(seeds: list[SeedNode]) -> OneHopGraphResult:
    if not seeds:
        return OneHopGraphResult()

    settings = get_settings()
    driver = create_neo4j_driver(settings)
    try:
        verify_neo4j_connectivity(driver)
        reader = Neo4jGraphReader(driver, database=settings.neo4j_database)
        return reader.get_one_hop_neighbors([seed.id for seed in seeds])
    finally:
        driver.close()
