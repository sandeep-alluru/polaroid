"""polaroid — Embeddable CRDT scene graph for embodied AI agents."""

from __future__ import annotations

from importlib.metadata import version as _version

from polaroid.export import to_adjacency_matrix, to_dot, to_json
from polaroid.graph import MergeResult, SceneEdge, SceneNode
from polaroid.merger import SceneMerger
from polaroid.query import SceneQuery
from polaroid.stats import GraphStats, cluster_by_type, compute_stats, most_connected
from polaroid.store import SceneStore
from polaroid.subgraph import extract_subgraph, filter_by_type, neighborhood

__version__ = _version("polaroid")

__all__ = [
    "GraphStats",
    "MergeResult",
    "SceneEdge",
    "SceneMerger",
    "SceneNode",
    "SceneQuery",
    "SceneStore",
    "__version__",
    "cluster_by_type",
    "compute_stats",
    "extract_subgraph",
    "filter_by_type",
    "most_connected",
    "neighborhood",
    "to_adjacency_matrix",
    "to_dot",
    "to_json",
]
