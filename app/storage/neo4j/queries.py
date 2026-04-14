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
