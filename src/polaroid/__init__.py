"""polaroid — Embeddable CRDT scene graph for embodied AI agents."""

from __future__ import annotations

from importlib.metadata import version as _version

from polaroid.graph import MergeResult, SceneEdge, SceneNode
from polaroid.merger import SceneMerger
from polaroid.query import SceneQuery
from polaroid.store import SceneStore

__version__ = _version("polaroid")

__all__ = [
    "MergeResult",
    "SceneEdge",
    "SceneMerger",
    "SceneNode",
    "SceneQuery",
    "SceneStore",
    "__version__",
]
