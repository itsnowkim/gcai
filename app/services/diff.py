from app.parsers.git_diff import parse_git_diff
from app.schemas.diff import ParsedDiffResult


def collect_changed_files_from_diff(raw_diff: str) -> ParsedDiffResult:
    return parse_git_diff(raw_diff)
