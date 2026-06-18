"""scenemem — Embeddable CRDT scene graph for embodied AI agents."""

from __future__ import annotations

from importlib.metadata import version as _version

from scenemem.graph import MergeResult, SceneEdge, SceneNode
from scenemem.merger import SceneMerger
from scenemem.query import SceneQuery
from scenemem.store import SceneStore

__version__ = _version("scenemem")

__all__ = [
    "MergeResult",
    "SceneEdge",
    "SceneMerger",
    "SceneNode",
    "SceneQuery",
    "SceneStore",
    "__version__",
]
