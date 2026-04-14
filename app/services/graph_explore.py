from pathlib import Path

from app.core.settings import get_settings
from app.schemas.changed_code import ChangedCodeContextResult
from app.schemas.graph import GraphExploreResult, OneHopGraphResult, SeedNode
from app.schemas.relations import RelationKind
from app.storage.neo4j.client import create_neo4j_driver, verify_neo4j_connectivity
from app.storage.neo4j.reader import Neo4jGraphReader

DEFAULT_GRAPH_RELATION_ALLOWLIST: tuple[RelationKind, ...] = (
    RelationKind.CONTAINS,
    RelationKind.IMPORTS,
    RelationKind.CALLS,
    RelationKind.READS,
    RelationKind.WRITES,
)


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


def explore_two_hop_from_changed_code(
    changed_code_context: ChangedCodeContextResult,
    *,
    allowed_relation_kinds: tuple[RelationKind, ...] = DEFAULT_GRAPH_RELATION_ALLOWLIST,
) -> GraphExploreResult:
    seeds = build_seed_nodes(changed_code_context)
    return explore_graph_neighbors(
        seeds,
        max_depth=2,
        allowed_relation_kinds=allowed_relation_kinds,
    )


def explore_one_hop_neighbors(seeds: list[SeedNode]) -> OneHopGraphResult:
    result = explore_graph_neighbors(
        seeds,
        max_depth=1,
        allowed_relation_kinds=DEFAULT_GRAPH_RELATION_ALLOWLIST,
    )
    return OneHopGraphResult.model_validate(result.model_dump())


def explore_graph_neighbors(
    seeds: list[SeedNode],
    *,
    max_depth: int,
    allowed_relation_kinds: tuple[RelationKind, ...] = DEFAULT_GRAPH_RELATION_ALLOWLIST,
) -> GraphExploreResult:
    if not seeds:
        return GraphExploreResult(
            max_depth=max_depth,
            allowed_relation_kinds=list(allowed_relation_kinds),
        )

    settings = get_settings()
    driver = create_neo4j_driver(settings)
    try:
        verify_neo4j_connectivity(driver)
        reader = Neo4jGraphReader(driver, database=settings.neo4j_database)
        return reader.get_neighbors(
            seed_ids=[seed.id for seed in seeds],
            max_depth=max_depth,
            allowed_relation_kinds=[kind.value for kind in allowed_relation_kinds],
        )
    finally:
        driver.close()
