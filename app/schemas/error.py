from pydantic import BaseModel


class ErrorResponse(BaseModel):
    request_id: str | None = None
    error_code: str
    message: str
