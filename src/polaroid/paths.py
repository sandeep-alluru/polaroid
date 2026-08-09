"""Safe path helpers for polaroid stores (CWE-22 path injection).

User-controlled ``db`` paths from the REST API / MCP must not escape the
configured data root. CodeQL: py/path-injection on SceneStore.
"""

from __future__ import annotations

import os
from pathlib import Path

# Default on-disk root when POLAROID_DATA_DIR is unset.
DEFAULT_DATA_DIR = ".polaroid"
MEMORY_URI = ":memory:"


class PathEscapeError(ValueError):
    """Raised when a db path resolves outside the allowed data root."""


def data_root(root: str | Path | None = None) -> Path:
    """Resolve the allowed store root directory."""
    if root is not None:
        return Path(root).expanduser().resolve()
    env = os.environ.get("POLAROID_DATA_DIR", DEFAULT_DATA_DIR)
    return Path(env).expanduser().resolve()


def safe_db_path(path: str | Path, *, root: str | Path | None = None) -> Path | str:
    """Normalize *path* and ensure it stays under the data root.

    Parameters
    ----------
    path:
        Requested store path (relative preferred). Absolute paths are allowed
        only when they resolve inside the data root.
    root:
        Override data root (defaults to ``POLAROID_DATA_DIR`` or ``.polaroid``).

    Returns
    -------
    Path
        Resolved path under the data root.
    str
        The literal ``":memory:"`` for in-memory SQLite (unchanged).

    Raises
    ------
    PathEscapeError
        If the path contains a NUL byte or escapes the data root.
    """
    raw_s = str(path)
    if raw_s == MEMORY_URI:
        return MEMORY_URI
    if "\x00" in raw_s:
        raise PathEscapeError("db path must not contain NUL bytes")

    base = data_root(root)
    raw = Path(raw_s)

    if raw.is_absolute():
        full = raw.resolve()
    else:
        # Allow legacy default ".polaroid/scene.db" when root is ".polaroid"
        parts = raw.parts
        if parts and parts[0] in (DEFAULT_DATA_DIR, "polaroid"):
            raw = Path(*parts[1:]) if len(parts) > 1 else Path("scene.db")
        full = (base / raw).resolve()

    try:
        full.relative_to(base)
    except ValueError as exc:
        raise PathEscapeError(f"db path escapes data root {base}: {path!r}") from exc

    return full
