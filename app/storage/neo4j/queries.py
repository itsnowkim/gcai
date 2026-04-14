UPSERT_SYMBOLS_QUERY = """
UNWIND $rows AS row
MERGE (n:Symbol {id: row.id})
SET n.kind = row.kind,
    n.language = row.language,
    n.path = row.path,
    n.name = row.name,
    n.qualified_name = row.qualified_name,
    n.signature = row.signature,
    n.start_line = row.start_line,
    n.start_column = row.start_column,
    n.end_line = row.end_line,
    n.end_column = row.end_column,
    n.code = row.code,
    n.body = row.body,
    n.parent_name = row.parent_name,
    n.parameters = row.parameters,
    n.super_types = row.super_types,
    n.aliased_type = row.aliased_type,
    n.is_static = row.is_static
FOREACH (_ IN CASE WHEN row.kind = 'file' THEN [1] ELSE [] END | SET n:File)
FOREACH (_ IN CASE WHEN row.kind <> 'file' THEN [1] ELSE [] END | REMOVE n:File)
FOREACH (_ IN CASE WHEN row.kind <> 'file' THEN [1] ELSE [] END | SET n:CodeEntity)
FOREACH (_ IN CASE WHEN row.kind = 'file' THEN [1] ELSE [] END | REMOVE n:CodeEntity)
RETURN count(n) AS upserted_count
""".strip()

UPSERT_RELATIONS_QUERY = """
UNWIND $rows AS row
MATCH (source:Symbol {id: row.source_id})
MATCH (destination:Symbol {id: row.destination_id})
OPTIONAL MATCH ()-[existing:RELATES_TO {id: row.id}]->()
FOREACH (_ IN CASE WHEN existing IS NULL THEN [] ELSE [1] END | DELETE existing)
MERGE (source)-[r:RELATES_TO {id: row.id}]->(destination)
SET r.kind = row.kind,
    r.path = row.path,
    r.source = row.source,
    r.destination = row.destination,
    r.metadata_json = row.metadata_json
RETURN count(r) AS upserted_count
""".strip()

GET_ONE_HOP_NEIGHBORS_QUERY = """
MATCH (seed:Symbol)
WHERE seed.id IN $seed_ids
OPTIONAL MATCH (seed)-[r:RELATES_TO]-(neighbor:Symbol)
WITH
    collect(DISTINCT {
        id: seed.id,
        path: seed.path,
        kind: seed.kind,
        qualified_name: seed.qualified_name
    }) AS seeds,
    collect(DISTINCT {
        id: seed.id,
        kind: seed.kind,
        language: seed.language,
        path: seed.path,
        name: seed.name,
        qualified_name: seed.qualified_name,
        signature: seed.signature,
        start_line: seed.start_line,
        end_line: seed.end_line
    }) +
    collect(DISTINCT CASE
        WHEN neighbor IS NULL THEN NULL
        ELSE {
            id: neighbor.id,
            kind: neighbor.kind,
            language: neighbor.language,
            path: neighbor.path,
            name: neighbor.name,
            qualified_name: neighbor.qualified_name,
            signature: neighbor.signature,
            start_line: neighbor.start_line,
            end_line: neighbor.end_line
        }
    END) AS raw_nodes,
    collect(DISTINCT CASE
        WHEN r IS NULL THEN NULL
        ELSE {
            id: r.id,
            kind: r.kind,
            source_id: startNode(r).id,
            destination_id: endNode(r).id,
            path: r.path,
            source: r.source,
            destination: r.destination
        }
    END) AS raw_edges
RETURN
    seeds,
    [node IN raw_nodes WHERE node IS NOT NULL] AS nodes,
    [edge IN raw_edges WHERE edge IS NOT NULL] AS edges
""".strip()
