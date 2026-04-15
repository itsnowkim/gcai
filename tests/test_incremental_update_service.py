from pathlib import Path
from unittest.mock import patch

from app.services.incremental_update import (
    IncrementalAnalysisFile,
    IncrementalAnalysisResult,
    IncrementalSkippedFile,
    run_incremental_update,
)


def test_run_incremental_update_orchestrates_analysis_and_storage() -> None:
    repo_path = "."
    parsed_diff = object()
    analysis_result = IncrementalAnalysisResult(
        changed_files=["app/service.py", "legacy/deleted.py"],
        analyzed_files=[
            IncrementalAnalysisFile(
                path="app/service.py",
                language="python",
                symbols=[],
                relations=[],
            )
        ],
        deleted_files=["legacy/deleted.py"],
        skipped_files=[IncrementalSkippedFile(path="README.md", reason="unsupported_language")],
    )

    with (
        patch("app.services.incremental_update.collect_changed_files_from_diff", return_value=parsed_diff) as diff_mock,
        patch("app.services.incremental_update._analyze_incremental_changes", return_value=analysis_result) as analyze_mock,
        patch(
            "app.services.incremental_update._update_neo4j_incrementally",
            return_value={"updated_nodes": 2, "updated_edges": 3},
        ) as neo4j_mock,
        patch(
            "app.services.incremental_update._update_chroma_incrementally",
            return_value={"reindexed_embeddings": 1},
        ) as chroma_mock,
    ):
        result = run_incremental_update(repo_path, "diff --git a/a.py b/a.py")

    assert result.changed_files == ["app/service.py", "legacy/deleted.py"]
    assert result.updated_nodes == 2
    assert result.updated_edges == 3
    assert result.reindexed_embeddings == 1
    assert result.status == "ok"
    diff_mock.assert_called_once_with("diff --git a/a.py b/a.py")
    analyze_mock.assert_called_once_with(Path(repo_path).resolve(), parsed_diff)
    neo4j_mock.assert_called_once_with(analysis_result)
    chroma_mock.assert_called_once_with(analysis_result)


def test_run_incremental_update_returns_ok_for_empty_diff_result() -> None:
    repo_path = "."
    analysis_result = IncrementalAnalysisResult()

    with (
        patch("app.services.incremental_update.collect_changed_files_from_diff", return_value=object()),
        patch("app.services.incremental_update._analyze_incremental_changes", return_value=analysis_result),
        patch(
            "app.services.incremental_update._update_neo4j_incrementally",
            return_value={"updated_nodes": 0, "updated_edges": 0},
        ),
        patch(
            "app.services.incremental_update._update_chroma_incrementally",
            return_value={"reindexed_embeddings": 0},
        ),
    ):
        result = run_incremental_update(repo_path, "diff --git a/a.py b/a.py")

    assert result.changed_files == []
    assert result.updated_nodes == 0
    assert result.updated_edges == 0
    assert result.reindexed_embeddings == 0
    assert result.status == "ok"
