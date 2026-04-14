from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    service: str
    request_id: str | None = None
