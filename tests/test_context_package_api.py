from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import create_app
from app.schemas.context_package import ContextPackageResult
from app.schemas.graph import GraphPath


def test_context_package_api_returns_context_package_response() -> None:
    app = create_app()
    fake_result = ContextPackageResult(
        repo_path="/repo",
        graph_paths=[
            GraphPath(
                seed_id="seed-1",
                terminal_node_id="node-1",
                node_ids=["seed-1", "node-1"],
                edge_ids=["edge-1"],
                hop_count=1,
            )
        ],
    )

    with (
        patch("app.api.routes.context_package.build_context_package", return_value=fake_result) as build_mock,
        TestClient(app) as client,
    ):
        response = client.post(
            "/analyze/context-package",
            json={"repo_path": "/repo", "diff": "diff --git a/a.py b/a.py"},
            headers={"X-Request-ID": "req-context-api"},
        )

    assert response.status_code == 200
    assert response.json()["repo_path"] == "/repo"
    assert response.json()["graph_paths"][0]["edge_ids"] == ["edge-1"]
    assert response.headers["X-Request-ID"] == "req-context-api"
    build_mock.assert_called_once_with("/repo", "diff --git a/a.py b/a.py")


def test_context_package_api_validates_required_fields() -> None:
    app = create_app()

    with TestClient(app) as client:
        response = client.post("/analyze/context-package", json={"repo_path": "", "diff": ""})

    assert response.status_code == 422


def test_context_package_api_surfaces_gcai_errors() -> None:
    from app.core.exceptions import GCAIError

    app = create_app()

    with (
        patch(
            "app.api.routes.context_package.build_context_package",
            side_effect=GCAIError("invalid diff", error_code="diff_invalid", status_code=400),
        ),
        TestClient(app) as client,
    ):
        response = client.post(
            "/analyze/context-package",
            json={"repo_path": "/repo", "diff": "bad diff"},
            headers={"X-Request-ID": "req-context-error"},
        )

    assert response.status_code == 400
    assert response.json() == {
        "request_id": "req-context-error",
        "error_code": "diff_invalid",
        "message": "invalid diff",
    }
    assert response.headers["X-Request-ID"] == "req-context-error"


def test_context_package_api_rejects_invalid_repo_path() -> None:
    app = create_app()

    with TestClient(app) as client:
        response = client.post(
            "/analyze/context-package",
            json={"repo_path": "/definitely/missing/repo", "diff": "diff --git a/a.py b/a.py"},
            headers={"X-Request-ID": "req-context-invalid-path"},
        )

    assert response.status_code == 400
    assert response.json()["request_id"] == "req-context-invalid-path"
    assert response.json()["error_code"] == "invalid_repo_path"


def test_context_package_api_rejects_invalid_diff() -> None:
    app = create_app()

    with TestClient(app) as client:
        response = client.post(
            "/analyze/context-package",
            json={"repo_path": ".", "diff": "not a diff"},
            headers={"X-Request-ID": "req-context-invalid-diff"},
        )

    assert response.status_code == 400
    assert response.json() == {
        "request_id": "req-context-invalid-diff",
        "error_code": "diff_parse_error",
        "message": "Unexpected diff content before file header at line 1: not a diff",
    }
    assert response.headers["X-Request-ID"] == "req-context-invalid-diff"


def test_context_package_api_is_in_openapi() -> None:
    app = create_app()

    with TestClient(app) as client:
        response = client.get("/openapi.json")

    assert response.status_code == 200
    assert "/analyze/context-package" in response.json()["paths"]
