from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.schemas.error import ErrorResponse


class GCAIError(Exception):
    def __init__(self, message: str, error_code: str = "internal_error", status_code: int = 500) -> None:
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        super().__init__(message)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(GCAIError)
    async def handle_gcai_error(request: Request, exc: GCAIError) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None)
        payload = ErrorResponse(
            request_id=request_id,
            error_code=exc.error_code,
            message=exc.message,
        )
        headers = {"X-Request-ID": request_id} if request_id else None
        return JSONResponse(status_code=exc.status_code, content=payload.model_dump(), headers=headers)

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, _: Exception) -> JSONResponse:
        request_id = getattr(request.state, "request_id", None)
        payload = ErrorResponse(
            request_id=request_id,
            error_code="internal_error",
            message="Unexpected server error",
        )
        headers = {"X-Request-ID": request_id} if request_id else None
        return JSONResponse(status_code=500, content=payload.model_dump(), headers=headers)
