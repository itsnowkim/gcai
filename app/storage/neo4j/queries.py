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
WITH n, row
SET n:File
FOREACH (_ IN CASE WHEN row.kind <> 'file' THEN [1] ELSE [] END | SET n:CodeEntity)
RETURN count(n) AS upserted_count
""".strip()

UPSERT_RELATIONS_QUERY = """
UNWIND $rows AS row
MATCH (source:Symbol {qualified_name: row.source, path: row.path})
MATCH (destination:Symbol {qualified_name: row.destination, path: row.path})
MERGE (source)-[r:RELATES_TO {id: row.id}]->(destination)
SET r.kind = row.kind,
    r.path = row.path,
    r.source = row.source,
    r.destination = row.destination,
    r.metadata = row.metadata
RETURN count(r) AS upserted_count
""".strip()
