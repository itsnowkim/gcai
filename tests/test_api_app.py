from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.exceptions import GCAIError, register_exception_handlers
from app.main import create_app
from app.middleware.request_context import RequestContextMiddleware


def test_create_app_exposes_health_endpoint_and_openapi() -> None:
    app = create_app()

    with TestClient(app) as client:
        response = client.get("/health")
        openapi_response = client.get("/openapi.json")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["service"] == "gcai"
    assert response.headers["X-Request-ID"].startswith("req-")
    assert response.json()["request_id"] == response.headers["X-Request-ID"]
    assert openapi_response.status_code == 200
    assert "/health" in openapi_response.json()["paths"]


def test_health_endpoint_echoes_request_id_header() -> None:
    app = create_app()

    with TestClient(app) as client:
        response = client.get("/health", headers={"X-Request-ID": "req-test-123"})

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "req-test-123"
    assert response.json()["request_id"] == "req-test-123"


def test_gcai_error_handler_returns_error_schema() -> None:
    app = _build_exception_test_app()

    @app.get("/boom")
    async def boom():
        raise GCAIError("bad request", error_code="bad_request", status_code=400)

    with TestClient(app) as client:
        response = client.get("/boom", headers={"X-Request-ID": "req-error-1"})

    assert response.status_code == 400
    assert response.json() == {
        "request_id": "req-error-1",
        "error_code": "bad_request",
        "message": "bad request",
    }
    assert response.headers["X-Request-ID"] == "req-error-1"


def test_unexpected_error_handler_returns_error_schema() -> None:
    app = _build_exception_test_app()

    @app.get("/explode")
    async def explode():
        raise RuntimeError("unexpected")

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/explode", headers={"X-Request-ID": "req-error-2"})

    assert response.status_code == 500
    assert response.json() == {
        "request_id": "req-error-2",
        "error_code": "internal_error",
        "message": "Unexpected server error",
    }
    assert response.headers["X-Request-ID"] == "req-error-2"


def _build_exception_test_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)
    register_exception_handlers(app)
    return app
