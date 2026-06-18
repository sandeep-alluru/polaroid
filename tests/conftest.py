"""Shared pytest fixtures for polaroid tests."""

import pytest

from polaroid.store import SceneStore


@pytest.fixture
def store(tmp_path):
    """Return a fresh SceneStore backed by a temp file."""
    s = SceneStore(str(tmp_path / "scene.db"))
    yield s
    s.close()


@pytest.fixture
def store2(tmp_path):
    """Return a second fresh SceneStore for merge tests."""
    s = SceneStore(str(tmp_path / "scene2.db"))
    yield s
    s.close()
