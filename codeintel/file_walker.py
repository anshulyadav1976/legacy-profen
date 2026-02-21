"""File walking utilities."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable


DEFAULT_EXCLUDES = {".venv", "__pycache__", ".git", ".hg", ".svn"}


def iter_python_files(root: str | Path, excludes: Iterable[str] | None = None) -> list[str]:
    root_path = Path(root)
    exclude_set = set(excludes or DEFAULT_EXCLUDES)
    matches: list[str] = []

    for path in root_path.rglob("*.py"):
        if any(part in exclude_set for part in path.parts):
            continue
        matches.append(str(path))

    return matches