"""Safe path helpers for polaroid stores (CWE-22 path injection)."""

from __future__ import annotations

import os
from pathlib import Path

DEFAULT_DATA_DIR = ".polaroid"
MEMORY_URI = ":memory:"


class PathEscapeError(ValueError):
    """Raised when a db path resolves outside the allowed data root."""


def data_root(root: str | Path | None = None) -> str:
    if root is not None:
        return os.path.realpath(os.path.expanduser(str(root)))
    env = os.environ.get("POLAROID_DATA_DIR", DEFAULT_DATA_DIR)
    return os.path.realpath(os.path.expanduser(env))


def safe_db_path(path: str | Path, *, root: str | Path | None = None) -> str:
    """Normalize path under data root; absolute paths confined to parent realpath."""
    raw_s = str(path)
    if raw_s == MEMORY_URI:
        return MEMORY_URI
    if chr(0) in raw_s:
        raise PathEscapeError("db path must not contain NUL bytes")

    expanded = os.path.expanduser(raw_s)

    if ".." in Path(expanded).parts:
        raise PathEscapeError("path must not contain '..' components")

    if root is not None or not os.path.isabs(expanded):
        base = data_root(root)
        cleaned = expanded
        for prefix in (
            DEFAULT_DATA_DIR + "/",
            DEFAULT_DATA_DIR + os.sep,
            "polaroid/",
            "polaroid" + os.sep,
            "./" + DEFAULT_DATA_DIR + "/",
        ):
            if cleaned.startswith(prefix):
                cleaned = cleaned[len(prefix) :]
                break
        if os.path.isabs(cleaned):
            full = os.path.realpath(cleaned)
        else:
            full = os.path.realpath(os.path.join(base, cleaned or "scene.db"))
        base_prefix = base if base.endswith(os.sep) else base + os.sep
        if full != base and not full.startswith(base_prefix):
            raise PathEscapeError(f"db path escapes data root {base}: {path!r}")
        return full

    parent_given = os.path.dirname(expanded) or os.curdir
    given_dir = os.path.realpath(parent_given)
    full = os.path.realpath(expanded)
    base_prefix = given_dir if given_dir.endswith(os.sep) else given_dir + os.sep
    if full != given_dir and not full.startswith(base_prefix):
        raise PathEscapeError(f"absolute path escapes its parent dir {given_dir}: {path!r}")
    return full
