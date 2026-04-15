from itertools import islice
import json

from neo4j import Driver

from app.schemas.relations import ExtractedRelation
from app.schemas.symbols import ExtractedSymbol
from app.storage.neo4j.exceptions import Neo4jStorageError
from app.storage.neo4j.queries import (
    DELETE_RELATIONS_BY_PATHS_QUERY,
    DELETE_SYMBOLS_BY_PATHS_QUERY,
    UPSERT_RELATIONS_QUERY,
    UPSERT_SYMBOLS_QUERY,
)

DEFAULT_BATCH_SIZE = 500


class Neo4jGraphWriter:
    def __init__(self, driver: Driver, *, database: str, batch_size: int = DEFAULT_BATCH_SIZE) -> None:
        self.driver = driver
        self.database = database
        self.batch_size = batch_size

    def upsert_symbols(self, symbols: list[ExtractedSymbol]) -> int:
        return self._write_batches(
            query=UPSERT_SYMBOLS_QUERY,
            rows=[symbol.model_dump(mode="json") for symbol in symbols],
        )

    def upsert_relations(self, relations: list[ExtractedRelation]) -> int:
        rows_by_id: dict[str, dict] = {}
        for relation in relations:
            if relation.source_id is None or relation.destination_id is None:
                continue
            rows_by_id[relation.id] = {
                **relation.model_dump(mode="json"),
                "metadata_json": json.dumps(relation.metadata, ensure_ascii=False, sort_keys=True),
            }
        return self._write_batches(
            query=UPSERT_RELATIONS_QUERY,
            rows=list(rows_by_id.values()),
        )

    def delete_relations_by_paths(self, paths: list[str]) -> int:
        return self._write_scalar(query=DELETE_RELATIONS_BY_PATHS_QUERY, values={"paths": paths})

    def delete_symbols_by_paths(self, paths: list[str]) -> int:
        return self._write_scalar(query=DELETE_SYMBOLS_BY_PATHS_QUERY, values={"paths": paths})

    def _write_batches(self, *, query: str, rows: list[dict]) -> int:
        if not rows:
            return 0

        total = 0
        try:
            with self.driver.session(database=self.database) as session:
                for batch in _batched(rows, self.batch_size):
                    total += session.execute_write(_run_upsert_query, query, batch)
        except Exception as exc:  # pragma: no cover - external database failure path
            raise Neo4jStorageError(
                f"Failed to upsert data into Neo4j: {exc}",
                error_code="neo4j_upsert_error",
            ) from exc
        return total

    def _write_scalar(self, *, query: str, values: dict[str, object]) -> int:
        if not values:
            return 0
        paths = values.get("paths")
        if isinstance(paths, list) and not paths:
            return 0

        try:
            with self.driver.session(database=self.database) as session:
                return session.execute_write(_run_scalar_query, query, values)
        except Exception as exc:  # pragma: no cover - external database failure path
            raise Neo4jStorageError(
                f"Failed to update data in Neo4j: {exc}",
                error_code="neo4j_upsert_error",
            ) from exc


def _run_upsert_query(tx, query: str, rows: list[dict]) -> int:
    result = tx.run(query, rows=rows)
    record = result.single()
    if record is None:
        return 0
    return int(record["upserted_count"])


def _run_scalar_query(tx, query: str, values: dict[str, object]) -> int:
    result = tx.run(query, **values)
    record = result.single()
    if record is None:
        return 0
    return int(record["deleted_count"])


def _batched(rows: list[dict], batch_size: int):
    iterator = iter(rows)
    while batch := list(islice(iterator, batch_size)):
        yield batch
