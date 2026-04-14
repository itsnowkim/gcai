import shutil
from pathlib import Path
from uuid import uuid4

from app.parsers.git_diff import parse_git_diff
from app.services.changed_code import collect_changed_code_context


def test_collect_changed_code_context_loads_python_symbols_and_dedupes_overlaps() -> None:
    repo_path = _make_repo_dir("python")
    try:
        (repo_path / "app").mkdir()
        (repo_path / "app" / "service.py").write_text(
            """
class Greeter:
    def greet(self, name):
        message = self.prefix
        return message

    def farewell(self, name):
        return f"bye {name}"
""".strip(),
            encoding="utf-8",
        )

        raw_diff = """diff --git a/app/service.py b/app/service.py
index 1111111..2222222 100644
--- a/app/service.py
+++ b/app/service.py
@@ -2,3 +2,4 @@ class Greeter:
     def greet(self, name):
         message = self.prefix
         return message
"""

        result = collect_changed_code_context(repo_path, parse_git_diff(raw_diff))

        assert result.repo_path == str(repo_path.resolve())
        assert len(result.changed_files) == 1
        file_context = result.changed_files[0]
        assert file_context.path == "app/service.py"
        assert file_context.source_loaded is True
        assert file_context.language == "python"
        assert file_context.skip_reason is None
        assert [seed.symbol.qualified_name for seed in file_context.symbols] == ["Greeter", "Greeter.greet"]
        assert [seed.symbol.qualified_name for seed in result.changed_symbols] == ["Greeter", "Greeter.greet"]
    finally:
        shutil.rmtree(repo_path, ignore_errors=True)


def test_collect_changed_code_context_loads_java_symbols() -> None:
    repo_path = _make_repo_dir("java")
    try:
        (repo_path / "app").mkdir()
        (repo_path / "app" / "Service.java").write_text(
            """
package demo;

class Service {
    String greet(String name) {
        return name;
    }
}
""".strip(),
            encoding="utf-8",
        )

        raw_diff = """diff --git a/app/Service.java b/app/Service.java
index 1111111..2222222 100644
--- a/app/Service.java
+++ b/app/Service.java
@@ -3,3 +3,4 @@ class Service {
     String greet(String name) {
         return name;
     }
 }
"""

        result = collect_changed_code_context(repo_path, parse_git_diff(raw_diff))

        assert result.changed_files[0].language == "java"
        assert [seed.symbol.qualified_name for seed in result.changed_symbols] == [
            "demo.Service",
            "demo.Service.greet",
        ]
    finally:
        shutil.rmtree(repo_path, ignore_errors=True)


def test_collect_changed_code_context_loads_c_symbols() -> None:
    repo_path = _make_repo_dir("c")
    try:
        (repo_path / "src").mkdir()
        (repo_path / "src" / "main.c").write_text(
            """
int add(int a, int b) {
    int result = a + b;
    return result;
}
""".strip(),
            encoding="utf-8",
        )

        raw_diff = """diff --git a/src/main.c b/src/main.c
index 1111111..2222222 100644
--- a/src/main.c
+++ b/src/main.c
@@ -1,4 +1,4 @@
 int add(int a, int b) {
     int result = a + b;
     return result;
 }
"""

        result = collect_changed_code_context(repo_path, parse_git_diff(raw_diff))

        assert result.changed_files[0].language == "c"
        assert [seed.symbol.qualified_name for seed in result.changed_symbols] == ["add"]
    finally:
        shutil.rmtree(repo_path, ignore_errors=True)


def test_collect_changed_code_context_loads_cpp_symbols() -> None:
    repo_path = _make_repo_dir("cpp")
    try:
        (repo_path / "src").mkdir()
        (repo_path / "src" / "service.cpp").write_text(
            """
class Service {
public:
    int greet(int value) {
        return value;
    }
};
""".strip(),
            encoding="utf-8",
        )

        raw_diff = """diff --git a/src/service.cpp b/src/service.cpp
index 1111111..2222222 100644
--- a/src/service.cpp
+++ b/src/service.cpp
@@ -1,6 +1,6 @@
 class Service {
 public:
     int greet(int value) {
         return value;
     }
 };
"""

        result = collect_changed_code_context(repo_path, parse_git_diff(raw_diff))

        assert result.changed_files[0].language == "cpp"
        assert [seed.symbol.qualified_name for seed in result.changed_symbols] == [
            "Service",
            "Service.greet",
        ]
    finally:
        shutil.rmtree(repo_path, ignore_errors=True)


def test_collect_changed_code_context_keeps_missing_deleted_files() -> None:
    repo_path = _make_repo_dir("deleted")
    try:
        (repo_path / "app").mkdir()

        raw_diff = """diff --git a/app/old.py b/app/old.py
deleted file mode 100644
--- a/app/old.py
+++ /dev/null
@@ -1,3 +0,0 @@
-a = 1
-b = 2
-c = 3
"""

        result = collect_changed_code_context(repo_path, parse_git_diff(raw_diff))

        assert len(result.changed_files) == 1
        file_context = result.changed_files[0]
        assert file_context.path == "app/old.py"
        assert file_context.source_loaded is False
        assert file_context.skip_reason == "source_missing"
        assert result.changed_symbols == []
    finally:
        shutil.rmtree(repo_path, ignore_errors=True)


def _make_repo_dir(label: str) -> Path:
    path = Path(".tmp_changed_code_tests") / f"{label}_{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=False)
    return path
