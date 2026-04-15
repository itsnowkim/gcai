from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import create_app
from app.schemas.incremental_update import IncrementalUpdateResult


def test_incremental_update_api_returns_response_when_service_is_mocked() -> None:
    app = create_app()
    fake_result = IncrementalUpdateResult(
        changed_files=["app/service.py"],
        updated_nodes=2,
        updated_edges=3,
        reindexed_embeddings=1,
        status="ok",
    )

    with (
        patch("app.api.routes.incremental_update.run_incremental_update", return_value=fake_result) as service_mock,
        TestClient(app) as client,
    ):
        response = client.post(
            "/graph/incremental-update",
            json={"repo_path": "/repo", "diff": "diff --git a/a.py b/a.py"},
            headers={"X-Request-ID": "req-incremental-api"},
        )

    assert response.status_code == 200
    assert response.json()["changed_files"] == ["app/service.py"]
    assert response.json()["updated_nodes"] == 2
    assert response.headers["X-Request-ID"] == "req-incremental-api"
    service_mock.assert_called_once_with("/repo", "diff --git a/a.py b/a.py")


def test_incremental_update_api_validates_required_fields() -> None:
    app = create_app()

    with TestClient(app) as client:
        response = client.post("/graph/incremental-update", json={"repo_path": "", "diff": ""})

    assert response.status_code == 422


def test_incremental_update_api_surfaces_not_implemented_error() -> None:
    app = create_app()

    with TestClient(app) as client:
        response = client.post(
            "/graph/incremental-update",
            json={"repo_path": "/repo", "diff": "diff --git a/a.py b/a.py"},
            headers={"X-Request-ID": "req-incremental-error"},
        )

    assert response.status_code == 501
    assert response.json() == {
        "request_id": "req-incremental-error",
        "error_code": "incremental_update_not_implemented",
        "message": "Incremental graph update service is not implemented yet. Complete phase 3 first.",
    }
    assert response.headers["X-Request-ID"] == "req-incremental-error"


def test_incremental_update_api_is_in_openapi() -> None:
    app = create_app()

    with TestClient(app) as client:
        response = client.get("/openapi.json")

    assert response.status_code == 200
    assert "/graph/incremental-update" in response.json()["paths"]
