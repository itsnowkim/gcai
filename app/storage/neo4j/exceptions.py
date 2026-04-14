from app.core.exceptions import GCAIError


class Neo4jStorageError(GCAIError):
    def __init__(self, message: str, *, error_code: str = "neo4j_storage_error", status_code: int = 500) -> None:
        super().__init__(message=message, error_code=error_code, status_code=status_code)
