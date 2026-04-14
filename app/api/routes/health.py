from fastapi import APIRouter, Request

from app.schemas.health import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check(request: Request) -> HealthResponse:
    return HealthResponse(
        status="ok",
        service="gcai",
        request_id=getattr(request.state, "request_id", None),
    )
