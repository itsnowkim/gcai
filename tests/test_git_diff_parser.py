import pytest

from app.parsers.exceptions import DiffParseError
from app.parsers.git_diff import parse_git_diff
from app.schemas.diff import ChangeType, ParsedDiffResult
from app.services.diff import collect_changed_files_from_diff


def test_parse_git_diff_extracts_modified_files_and_hunks() -> None:
    raw_diff = """diff --git a/app/main.py b/app/main.py
index 1111111..2222222 100644
--- a/app/main.py
+++ b/app/main.py
@@ -10,2 +10,3 @@ def run():
 line1
-line2
+line2_updated
+line3
@@ -30 +31,0 @@ def cleanup():
-line4
"""

    result = parse_git_diff(raw_diff)

    assert result == ParsedDiffResult(
        files=[
            {
                "path": "app/main.py",
                "change_type": ChangeType.MODIFIED,
                "old_path": "app/main.py",
                "new_path": "app/main.py",
                "changed_line_ranges": [
                    {"start_line": 10, "line_count": 3},
                    {"start_line": 31, "line_count": 0},
                ],
                "hunks": [
                    {
                        "old_start_line": 10,
                        "old_line_count": 2,
                        "new_start_line": 10,
                        "new_line_count": 3,
                    },
                    {
                        "old_start_line": 30,
                        "old_line_count": 1,
                        "new_start_line": 31,
                        "new_line_count": 0,
                    },
                ],
            }
        ]
    )


def test_parse_git_diff_classifies_added_and_deleted_files() -> None:
    raw_diff = """diff --git a/app/new.py b/app/new.py
new file mode 100644
--- /dev/null
+++ b/app/new.py
@@ -0,0 +1,2 @@
+print("hello")
+print("world")
diff --git a/app/old.py b/app/old.py
deleted file mode 100644
--- a/app/old.py
+++ /dev/null
@@ -4,3 +0,0 @@
-a
-b
-c
"""

    result = parse_git_diff(raw_diff)

    assert [item.path for item in result.files] == ["app/new.py", "app/old.py"]
    assert [item.change_type for item in result.files] == [ChangeType.ADDED, ChangeType.DELETED]
    assert result.files[0].changed_line_ranges[0].model_dump() == {"start_line": 1, "line_count": 2}
    assert result.files[1].changed_line_ranges[0].model_dump() == {"start_line": 4, "line_count": 3}


def test_parse_git_diff_normalizes_quoted_paths() -> None:
    raw_diff = """diff --git "a/src/my file.py" "b/src/my file.py"
--- "a/src/my file.py"
+++ "b/src/my file.py"
@@ -1 +1 @@
-before
+after
"""

    result = parse_git_diff(raw_diff)

    assert result.files[0].path == "src/my file.py"
    assert result.files[0].old_path == "src/my file.py"
    assert result.files[0].new_path == "src/my file.py"


def test_parse_git_diff_raises_for_invalid_hunk_header() -> None:
    raw_diff = """diff --git a/app/main.py b/app/main.py
--- a/app/main.py
+++ b/app/main.py
@@ broken @@
"""

    with pytest.raises(DiffParseError):
        parse_git_diff(raw_diff)


def test_collect_changed_files_from_diff_uses_parser() -> None:
    raw_diff = """diff --git a/app/main.py b/app/main.py
--- a/app/main.py
+++ b/app/main.py
@@ -1 +1 @@
-before
+after
"""

    result = collect_changed_files_from_diff(raw_diff)

    assert isinstance(result, ParsedDiffResult)
    assert result.files[0].path == "app/main.py"
