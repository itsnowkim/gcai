from app.core.exceptions import GCAIError


class ChromaStorageError(GCAIError):
    def __init__(self, message: str, *, error_code: str = "chroma_storage_error", status_code: int = 500) -> None:
        super().__init__(message=message, error_code=error_code, status_code=status_code)
