"""CWE-22 / CodeQL py/path-injection — db paths must not escape data root."""

from __future__ import annotations

from pathlib import Path

import pytest

from polaroid.paths import PathEscapeError, safe_db_path
from polaroid.store import SceneStore


def test_safe_db_path_relative_under_root(tmp_path: Path) -> None:
    full = safe_db_path("scene.db", root=tmp_path)
    assert isinstance(full, Path)
    assert full == (tmp_path / "scene.db").resolve()
    assert full.relative_to(tmp_path.resolve())


def test_safe_db_path_strips_legacy_polaroid_prefix(tmp_path: Path) -> None:
    full = safe_db_path(".polaroid/scene.db", root=tmp_path)
    assert full == (tmp_path / "scene.db").resolve()


def test_safe_db_path_rejects_traversal(tmp_path: Path) -> None:
    with pytest.raises(PathEscapeError):
        safe_db_path("../../../etc/passwd", root=tmp_path)


def test_safe_db_path_rejects_absolute_outside_root(tmp_path: Path) -> None:
    with pytest.raises(PathEscapeError):
        safe_db_path("/etc/passwd", root=tmp_path)


def test_safe_db_path_allows_absolute_inside_root(tmp_path: Path) -> None:
    target = (tmp_path / "nested" / "s.db").resolve()
    full = safe_db_path(str(target), root=tmp_path)
    assert full == target


def test_safe_db_path_memory() -> None:
    assert safe_db_path(":memory:") == ":memory:"


def test_safe_db_path_rejects_nul(tmp_path: Path) -> None:
    with pytest.raises(PathEscapeError):
        safe_db_path("evil\x00.db", root=tmp_path)


def test_scene_store_rejects_escape(tmp_path: Path) -> None:
    with pytest.raises(PathEscapeError):
        SceneStore("/etc/passwd", data_root=tmp_path)


def test_scene_store_ok_under_root(tmp_path: Path) -> None:
    with SceneStore("ok.db", data_root=tmp_path) as store:
        assert store._path == (tmp_path / "ok.db").resolve()
