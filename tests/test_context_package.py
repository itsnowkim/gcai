import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch
from uuid import uuid4

from app.parsers.git_diff import parse_git_diff
from app.schemas.context_package import ContextPackageResult
from app.schemas.graph import GraphExploreResult, GraphNode, GraphPath
from app.services.changed_code import collect_changed_code_context
from app.services.context_package import build_context_package, build_modified_code, build_neighbor_code
from app.services.source_analysis import analyze_source_file


def test_build_modified_code_for_function_and_class_method() -> None:
    repo_path = _make_repo_dir("modified_code_python")
    try:
        (repo_path / "app").mkdir()
        (repo_path / "app" / "service.py").write_text(
            """
class Greeter:
    def greet(self, name):
        message = self.prefix
        return message


def helper(value):
    normalized = value.strip()
    return normalized
""".strip(),
            encoding="utf-8",
        )

        diff_result = parse_git_diff(
            """diff --git a/app/service.py b/app/service.py
index 1111111..2222222 100644
--- a/app/service.py
+++ b/app/service.py
@@ -1,4 +1,4 @@
 class Greeter:
     def greet(self, name):
         message = self.prefix
         return message
"""
        )

        changed_code_context = collect_changed_code_context(repo_path, diff_result)
        modified_code = build_modified_code(changed_code_context)

        assert [item.qualified_name for item in modified_code] == ["Greeter", "Greeter.greet"]
        assert modified_code[0].kind == "class"
        assert "class Greeter" in modified_code[0].code
        assert modified_code[1].kind == "method"
        assert "def greet(self, name)" in modified_code[1].code
    finally:
        shutil.rmtree(repo_path, ignore_errors=True)


def test_build_modified_code_skips_missing_deleted_files() -> None:
    repo_path = _make_repo_dir("modified_code_deleted")
    try:
        (repo_path / "app").mkdir()

        diff_result = parse_git_diff(
            """diff --git a/app/old.py b/app/old.py
deleted file mode 100644
--- a/app/old.py
+++ /dev/null
@@ -1,3 +0,0 @@
-a = 1
-b = 2
-c = 3
"""
        )

        changed_code_context = collect_changed_code_context(repo_path, diff_result)

        assert build_modified_code(changed_code_context) == []
    finally:
        shutil.rmtree(repo_path, ignore_errors=True)


def test_build_modified_code_skips_unsupported_language() -> None:
    repo_path = _make_repo_dir("modified_code_unsupported")
    try:
        (repo_path / "docs").mkdir()
        (repo_path / "docs" / "notes.txt").write_text("hello\nworld\n", encoding="utf-8")

        diff_result = parse_git_diff(
            """diff --git a/docs/notes.txt b/docs/notes.txt
index 1111111..2222222 100644
--- a/docs/notes.txt
+++ b/docs/notes.txt
@@ -1,2 +1,2 @@
 hello
 world
"""
        )

        changed_code_context = collect_changed_code_context(repo_path, diff_result)

        assert build_modified_code(changed_code_context) == []
    finally:
        shutil.rmtree(repo_path, ignore_errors=True)


def test_context_package_result_is_json_serializable() -> None:
    result = ContextPackageResult(
        repo_path="/repo",
        modified_code=[],
        neighbor_code=[],
    )

    dumped = result.model_dump(mode="json")

    assert dumped["repo_path"] == "/repo"
    assert dumped["modified_code"] == []
    assert dumped["neighbor_code"] == []


def test_build_neighbor_code_from_graph_results() -> None:
    repo_path = _make_repo_dir("neighbor_graph")
    try:
        (repo_path / "app").mkdir()
        (repo_path / "app" / "service.py").write_text(
            """
def normalize(value):
    return value.strip()


def helper(value):
    return normalize(value)


class Greeter:
    def greet(self, name):
        return helper(name)
""".strip(),
            encoding="utf-8",
        )

        diff_result = parse_git_diff(
            """diff --git a/app/service.py b/app/service.py
index 1111111..2222222 100644
--- a/app/service.py
+++ b/app/service.py
@@ -9,3 +9,3 @@ class Greeter:
 class Greeter:
     def greet(self, name):
         return helper(name)
"""
        )
        changed_code_context = collect_changed_code_context(repo_path, diff_result)
        graph_result = GraphExploreResult(
            nodes=[
                GraphNode(
                    id=changed_code_context.changed_symbols[1].symbol.id,
                    kind="method",
                    language="python",
                    path="app/service.py",
                    name="greet",
                    qualified_name="Greeter.greet",
                    signature="def greet(self, name)",
                    start_line=9,
                    end_line=10,
                ),
                GraphNode(
                    id="function:app/service.py:helper:5",
                    kind="function",
                    language="python",
                    path="app/service.py",
                    name="helper",
                    qualified_name="helper",
                    signature="def helper(value)",
                    start_line=5,
                    end_line=6,
                ),
            ]
        )

        with (
            patch("app.services.context_package.create_chroma_client"),
            patch("app.services.context_package.verify_chroma_connectivity"),
            patch("app.services.context_package.ChromaCodeReader") as reader_cls,
        ):
            reader_cls.return_value.query_similar_code.return_value = []
            neighbor_code = build_neighbor_code(repo_path, changed_code_context, graph_result)

        assert [item.qualified_name for item in neighbor_code] == ["helper"]
        assert neighbor_code[0].source == "graph"
        assert "def helper(value)" in neighbor_code[0].code
    finally:
        shutil.rmtree(repo_path, ignore_errors=True)


def test_build_neighbor_code_from_vector_results() -> None:
    repo_path = _make_repo_dir("neighbor_vector")
    try:
        (repo_path / "app").mkdir()
        (repo_path / "app" / "service.py").write_text(
            """
def helper(value):
    return value


class Greeter:
    def greet(self, name):
        return helper(name)
""".strip(),
            encoding="utf-8",
        )

        diff_result = parse_git_diff(
            """diff --git a/app/service.py b/app/service.py
index 1111111..2222222 100644
--- a/app/service.py
+++ b/app/service.py
@@ -5,3 +5,3 @@ class Greeter:
 class Greeter:
     def greet(self, name):
         return helper(name)
"""
        )
        changed_code_context = collect_changed_code_context(repo_path, diff_result)
        fake_client = MagicMock()
        fake_reader = MagicMock()
        fake_reader.query_similar_code.return_value = [
            {
                "id": "helper:vector",
                "document": "def remote_helper(value):\n    return value",
                "metadata": {
                    "symbol_id": "helper:vector",
                    "symbol_kind": "function",
                    "language": "python",
                    "path": "other/module.py",
                    "qualified_name": "remote_helper",
                    "start_line": 1,
                    "end_line": 2,
                },
                "distance": 0.2,
            }
        ]

        with (
            patch("app.services.context_package.create_chroma_client", return_value=fake_client),
            patch("app.services.context_package.verify_chroma_connectivity"),
            patch("app.services.context_package.ChromaCodeReader", return_value=fake_reader),
        ):
            neighbor_code = build_neighbor_code(repo_path, changed_code_context, GraphExploreResult())

        assert [item.qualified_name for item in neighbor_code] == ["remote_helper"]
        assert neighbor_code[0].source == "vector"
        fake_reader.query_similar_code.assert_called()
    finally:
        shutil.rmtree(repo_path, ignore_errors=True)


def test_build_neighbor_code_dedupes_graph_and_vector_results() -> None:
    repo_path = _make_repo_dir("neighbor_dedupe")
    try:
        (repo_path / "app").mkdir()
        (repo_path / "app" / "service.py").write_text(
            """
def helper(value):
    return value


class Greeter:
    def greet(self, name):
        return helper(name)
""".strip(),
            encoding="utf-8",
        )

        diff_result = parse_git_diff(
            """diff --git a/app/service.py b/app/service.py
index 1111111..2222222 100644
--- a/app/service.py
+++ b/app/service.py
@@ -5,3 +5,3 @@ class Greeter:
 class Greeter:
     def greet(self, name):
         return helper(name)
"""
        )
        changed_code_context = collect_changed_code_context(repo_path, diff_result)
        analysis = analyze_source_file(repo_path / "app" / "service.py", include_relations=False)
        helper_id = next(symbol.id for symbol in analysis.symbol_result.symbols if symbol.qualified_name == "helper")
        graph_result = GraphExploreResult(
            nodes=[
                GraphNode(
                    id=helper_id,
                    kind="function",
                    language="python",
                    path="app/service.py",
                    name="helper",
                    qualified_name="helper",
                    signature="def helper(value)",
                    start_line=1,
                    end_line=2,
                )
            ]
        )
        fake_client = MagicMock()
        fake_reader = MagicMock()
        fake_reader.query_similar_code.return_value = [
            {
                "id": helper_id,
                "document": "def helper(value):\n    return value",
                "metadata": {
                    "symbol_id": helper_id,
                    "symbol_kind": "function",
                    "language": "python",
                    "path": "app/service.py",
                    "qualified_name": "helper",
                    "start_line": 1,
                    "end_line": 2,
                },
                "distance": 0.2,
            }
        ]

        with (
            patch("app.services.context_package.create_chroma_client", return_value=fake_client),
            patch("app.services.context_package.verify_chroma_connectivity"),
            patch("app.services.context_package.ChromaCodeReader", return_value=fake_reader),
        ):
            neighbor_code = build_neighbor_code(repo_path, changed_code_context, graph_result)

        assert len(neighbor_code) == 1
        assert neighbor_code[0].source == "graph"
    finally:
        shutil.rmtree(repo_path, ignore_errors=True)


def test_build_context_package_end_to_end() -> None:
    repo_path = _make_repo_dir("context_package_end_to_end")
    try:
        (repo_path / "app").mkdir()
        (repo_path / "app" / "service.py").write_text(
            """
def helper(value):
    return value.strip()


class Greeter:
    def greet(self, name):
        return helper(name)
""".strip(),
            encoding="utf-8",
        )

        raw_diff = """diff --git a/app/service.py b/app/service.py
index 1111111..2222222 100644
--- a/app/service.py
+++ b/app/service.py
@@ -5,3 +5,3 @@ class Greeter:
 class Greeter:
     def greet(self, name):
         return helper(name)
"""

        fake_graph_result = GraphExploreResult(
            graph_paths=[
                GraphPath(
                    seed_id="seed-1",
                    terminal_node_id="node-1",
                    node_ids=["seed-1", "node-1"],
                    edge_ids=["edge-1"],
                    hop_count=1,
                )
            ]
        )

        with (
            patch("app.services.context_package.explore_two_hop_from_changed_code", return_value=fake_graph_result),
            patch("app.services.context_package.build_neighbor_code", return_value=[]),
        ):
            result = build_context_package(repo_path, raw_diff)

        assert result.repo_path == str(repo_path.resolve())
        assert [item.path for item in result.changed_files] == ["app/service.py"]
        assert [item.qualified_name for item in result.modified_code] == ["Greeter", "Greeter.greet"]
        assert result.graph_paths[0].edge_ids == ["edge-1"]
        assert result.neighbor_code == []
    finally:
        shutil.rmtree(repo_path, ignore_errors=True)


def test_build_context_package_handles_import_only_change_without_symbols() -> None:
    repo_path = _make_repo_dir("context_package_import_only")
    try:
        (repo_path / "app").mkdir()
        (repo_path / "app" / "service.py").write_text(
            """
import os


def helper(value):
    return value
""".strip(),
            encoding="utf-8",
        )

        raw_diff = """diff --git a/app/service.py b/app/service.py
index 1111111..2222222 100644
--- a/app/service.py
+++ b/app/service.py
@@ -1,1 +1,1 @@
 import os
"""

        with (
            patch("app.services.context_package.explore_two_hop_from_changed_code", return_value=GraphExploreResult()),
            patch("app.services.context_package.build_neighbor_code", return_value=[]),
        ):
            result = build_context_package(repo_path, raw_diff)

        assert len(result.changed_files) == 1
        assert result.changed_symbols == []
        assert result.modified_code == []
        assert result.neighbor_code == []
    finally:
        shutil.rmtree(repo_path, ignore_errors=True)


def test_build_context_package_keeps_deleted_file_without_modified_code() -> None:
    repo_path = _make_repo_dir("context_package_deleted")
    try:
        (repo_path / "app").mkdir()

        raw_diff = """diff --git a/app/old.py b/app/old.py
deleted file mode 100644
--- a/app/old.py
+++ /dev/null
@@ -1,2 +0,0 @@
-a = 1
-b = 2
"""

        with (
            patch("app.services.context_package.explore_two_hop_from_changed_code", return_value=GraphExploreResult()),
            patch("app.services.context_package.build_neighbor_code", return_value=[]),
        ):
            result = build_context_package(repo_path, raw_diff)

        assert result.changed_files[0].skip_reason == "source_missing"
        assert result.modified_code == []
        assert result.neighbor_code == []
    finally:
        shutil.rmtree(repo_path, ignore_errors=True)


def _make_repo_dir(label: str) -> Path:
    path = Path(".tmp_context_package_tests") / f"{label}_{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=False)
    return path
