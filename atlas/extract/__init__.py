"""Shared helpers for extractors: file discovery and path canonicalization."""
import ast
import os
import re
from pathlib import Path
from typing import Iterator

SKIP_DIRS = {
    ".git", ".hg", ".svn", "node_modules", ".venv", "venv", "env", "dist", "build",
    "__pycache__", ".mypy_cache", ".pytest_cache", "site-packages",
}

_PARAM_SEGMENT = re.compile(r"^(\{[^}]+\}|<[^>]+>|:[^/]+)$")


def path_pattern(path: str) -> str:
    """Turn a route path into a regex: every parameter becomes one path segment."""
    segments = path.split("/")
    return "^" + "/".join(
        "[^/]+" if _PARAM_SEGMENT.match(seg) else re.escape(seg) for seg in segments
    ) + "$"


def iter_files(repo_root: Path, suffixes: tuple[str, ...] | list[str]) -> Iterator[Path]:
    """Yield files with the given suffixes, in stable order, honouring SKIP_DIRS."""
    for dirpath, dirnames, filenames in os.walk(repo_root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for filename in sorted(filenames):
            if filename.endswith(tuple(suffixes)):
                yield Path(dirpath) / filename


def parse_file(path: Path) -> ast.Module | None:
    """Parse a Python file; return None on SyntaxError/UnicodeDecodeError (caller records skipped)."""
    try:
        return ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError):
        return None