from pathlib import Path


def to_posix_path(path: str | Path) -> str:
    return Path(path).as_posix()


def to_posix_absolute_path(path: str | Path) -> str:
    return Path(path).resolve().as_posix()


def join_repo_relative_path(repo_path: str | Path, relative_path: str | Path) -> str:
    return (Path(repo_path).resolve() / Path(relative_path)).resolve().as_posix()
