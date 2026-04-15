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


def test_incremental_update_api_returns_service_result() -> None:
    app = create_app()
    fake_result = IncrementalUpdateResult(
        changed_files=["app/service.py"],
        updated_nodes=5,
        updated_edges=8,
        reindexed_embeddings=2,
        status="ok",
    )

    with (
        patch("app.api.routes.incremental_update.run_incremental_update", return_value=fake_result),
        TestClient(app) as client,
    ):
        response = client.post(
            "/graph/incremental-update",
            json={"repo_path": ".", "diff": "diff --git a/app/service.py b/app/service.py"},
            headers={"X-Request-ID": "req-incremental-success"},
        )

    assert response.status_code == 200
    assert response.json() == {
        "changed_files": ["app/service.py"],
        "updated_nodes": 5,
        "updated_edges": 8,
        "reindexed_embeddings": 2,
        "status": "ok",
    }
    assert response.headers["X-Request-ID"] == "req-incremental-success"


def test_incremental_update_api_rejects_invalid_repo_path() -> None:
    app = create_app()

    with TestClient(app) as client:
        response = client.post(
            "/graph/incremental-update",
            json={"repo_path": "/definitely/missing/repo", "diff": "diff --git a/a.py b/a.py"},
            headers={"X-Request-ID": "req-incremental-invalid-path"},
        )

    assert response.status_code == 400
    assert response.json()["request_id"] == "req-incremental-invalid-path"
    assert response.json()["error_code"] == "invalid_repo_path"


def test_incremental_update_api_rejects_invalid_diff() -> None:
    app = create_app()

    with TestClient(app) as client:
        response = client.post(
            "/graph/incremental-update",
            json={"repo_path": ".", "diff": "not a diff"},
            headers={"X-Request-ID": "req-incremental-invalid-diff"},
        )

    assert response.status_code == 400
    assert response.json() == {
        "request_id": "req-incremental-invalid-diff",
        "error_code": "diff_parse_error",
        "message": "Unexpected diff content before file header at line 1: not a diff",
    }
    assert response.headers["X-Request-ID"] == "req-incremental-invalid-diff"


def test_incremental_update_api_is_in_openapi() -> None:
    app = create_app()

    with TestClient(app) as client:
        response = client.get("/openapi.json")

    assert response.status_code == 200
    assert "/graph/incremental-update" in response.json()["paths"]
