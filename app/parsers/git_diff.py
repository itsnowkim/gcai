from __future__ import annotations

import re
import shlex

from app.parsers.exceptions import DiffParseError
from app.schemas.diff import ChangeType, DiffHunk, DiffLineRange, ParsedDiffFile, ParsedDiffResult

_HUNK_HEADER_RE = re.compile(
    r"^@@ -(?P<old_start>\d+)(?:,(?P<old_count>\d+))? \+(?P<new_start>\d+)(?:,(?P<new_count>\d+))? @@"
)


def parse_git_diff(raw_diff: str) -> ParsedDiffResult:
    lines = raw_diff.splitlines()
    parsed_files: list[ParsedDiffFile] = []
    current: _DiffFileBuilder | None = None

    for index, line in enumerate(lines, start=1):
        if line.startswith("diff --git "):
            if current is not None:
                parsed_files.append(current.build())

            old_path, new_path = _parse_diff_header(line, index)
            current = _DiffFileBuilder(old_path=old_path, new_path=new_path)
            continue

        if current is None:
            if not line.strip():
                continue
            raise DiffParseError(f"Unexpected diff content before file header at line {index}: {line}")

        if line.startswith("new file mode "):
            current.change_type = ChangeType.ADDED
            continue

        if line.startswith("deleted file mode "):
            current.change_type = ChangeType.DELETED
            continue

        if line.startswith("--- "):
            current.old_path = _normalize_diff_path(_extract_path_token(line[4:]))
            continue

        if line.startswith("+++ "):
            current.new_path = _normalize_diff_path(_extract_path_token(line[4:]))
            continue

        if line.startswith("@@ "):
            current.hunks.append(_parse_hunk_header(line, index))
            continue

    if current is not None:
        parsed_files.append(current.build())

    return ParsedDiffResult(files=parsed_files)


def _parse_diff_header(line: str, line_number: int) -> tuple[str | None, str | None]:
    try:
        tokens = shlex.split(line, posix=True)
    except ValueError as exc:
        raise DiffParseError(f"Invalid diff header at line {line_number}: {line}") from exc

    if len(tokens) != 4 or tokens[0] != "diff" or tokens[1] != "--git":
        raise DiffParseError(f"Invalid diff header at line {line_number}: {line}")

    return _normalize_diff_path(tokens[2]), _normalize_diff_path(tokens[3])


def _extract_path_token(value: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise DiffParseError("Diff path line is missing a path value")

    try:
        return shlex.split(stripped, posix=True)[0]
    except ValueError:
        return stripped.split("\t", maxsplit=1)[0].split(" ", maxsplit=1)[0]


def _normalize_diff_path(path: str | None) -> str | None:
    if path in (None, "/dev/null"):
        return None

    normalized = path.replace("\\", "/")
    if normalized.startswith("a/") or normalized.startswith("b/"):
        normalized = normalized[2:]
    return normalized


def _parse_hunk_header(line: str, line_number: int) -> DiffHunk:
    match = _HUNK_HEADER_RE.match(line)
    if match is None:
        raise DiffParseError(f"Invalid hunk header at line {line_number}: {line}")

    return DiffHunk(
        old_start_line=int(match.group("old_start")),
        old_line_count=int(match.group("old_count") or 1),
        new_start_line=int(match.group("new_start")),
        new_line_count=int(match.group("new_count") or 1),
    )


class _DiffFileBuilder:
    def __init__(self, old_path: str | None, new_path: str | None) -> None:
        self.old_path = old_path
        self.new_path = new_path
        self.change_type: ChangeType | None = None
        self.hunks: list[DiffHunk] = []

    def build(self) -> ParsedDiffFile:
        change_type = self.change_type or _infer_change_type(self.old_path, self.new_path)
        path = self.new_path if change_type != ChangeType.DELETED else self.old_path
        if path is None:
            raise DiffParseError("Unable to determine target file path from diff")

        return ParsedDiffFile(
            path=path,
            change_type=change_type,
            old_path=self.old_path,
            new_path=self.new_path,
            changed_line_ranges=_build_changed_line_ranges(change_type, self.hunks),
            hunks=self.hunks,
        )


def _infer_change_type(old_path: str | None, new_path: str | None) -> ChangeType:
    if old_path is None and new_path is not None:
        return ChangeType.ADDED
    if new_path is None and old_path is not None:
        return ChangeType.DELETED
    return ChangeType.MODIFIED


def _build_changed_line_ranges(change_type: ChangeType, hunks: list[DiffHunk]) -> list[DiffLineRange]:
    if change_type == ChangeType.DELETED:
        return [
            DiffLineRange(start_line=hunk.old_start_line, line_count=hunk.old_line_count)
            for hunk in hunks
        ]

    return [
        DiffLineRange(start_line=hunk.new_start_line, line_count=hunk.new_line_count)
        for hunk in hunks
    ]
