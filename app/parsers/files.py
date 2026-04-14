from pathlib import Path

from app.parsers.exceptions import SourceFileReadError


def read_source_file(path: str | Path) -> bytes:
    file_path = Path(path)

    try:
        return file_path.read_bytes()
    except OSError as exc:
        raise SourceFileReadError(str(file_path)) from exc
