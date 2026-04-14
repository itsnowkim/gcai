from itertools import islice

from neo4j import Driver

from app.schemas.relations import ExtractedRelation
from app.schemas.symbols import ExtractedSymbol
from app.storage.neo4j.exceptions import Neo4jStorageError
from app.storage.neo4j.queries import UPSERT_RELATIONS_QUERY, UPSERT_SYMBOLS_QUERY

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
        return self._write_batches(
            query=UPSERT_RELATIONS_QUERY,
            rows=[relation.model_dump(mode="json") for relation in relations],
        )

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


def _run_upsert_query(tx, query: str, rows: list[dict]) -> int:
    result = tx.run(query, rows=rows)
    record = result.single()
    if record is None:
        return 0
    return int(record["upserted_count"])


def _batched(rows: list[dict], batch_size: int):
    iterator = iter(rows)
    while batch := list(islice(iterator, batch_size)):
        yield batch
