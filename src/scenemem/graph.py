"""Core data model for scenemem scene graph.

SceneNode, SceneEdge, and MergeResult dataclasses with content-addressing.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field


def _sha16(text: str) -> str:
    """Return the first 16 hex characters of SHA-256(text)."""
    return hashlib.sha256(text.encode()).hexdigest()[:16]


@dataclass
class SceneNode:
    """A node in the scene graph (object, room, surface, region, or agent)."""

    label: str
    node_type: str
    properties: dict  # type: ignore[type-arg]
    confidence: float = 1.0
    observed_at: float = field(default_factory=time.time)
    agent_id: str = ""
    id: str = field(init=False)

    def __post_init__(self) -> None:
        self.id = _sha16(f"{self.label}|{self.node_type}")

    def to_dict(self) -> dict:  # type: ignore[type-arg]
        """Serialize to a plain dict."""
        return {
            "id": self.id,
            "label": self.label,
            "node_type": self.node_type,
            "properties": self.properties,
            "confidence": self.confidence,
            "observed_at": self.observed_at,
            "agent_id": self.agent_id,
        }

    @classmethod
    def from_dict(cls, d: dict) -> SceneNode:  # type: ignore[type-arg]
        """Deserialize from a plain dict."""
        node = cls(
            label=d["label"],
            node_type=d["node_type"],
            properties=d.get("properties", {}),
            confidence=d.get("confidence", 1.0),
            observed_at=d.get("observed_at", time.time()),
            agent_id=d.get("agent_id", ""),
        )
        return node


@dataclass
class SceneEdge:
    """A directed spatial relationship between two nodes."""

    source_id: str
    target_id: str
    relation: str
    confidence: float = 1.0
    observed_at: float = field(default_factory=time.time)
    id: str = field(init=False)

    def __post_init__(self) -> None:
        self.id = _sha16(f"{self.source_id}|{self.target_id}|{self.relation}")

    def to_dict(self) -> dict:  # type: ignore[type-arg]
        """Serialize to a plain dict."""
        return {
            "id": self.id,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "relation": self.relation,
            "confidence": self.confidence,
            "observed_at": self.observed_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> SceneEdge:  # type: ignore[type-arg]
        """Deserialize from a plain dict."""
        edge = cls(
            source_id=d["source_id"],
            target_id=d["target_id"],
            relation=d["relation"],
            confidence=d.get("confidence", 1.0),
            observed_at=d.get("observed_at", time.time()),
        )
        return edge


@dataclass
class MergeResult:
    """Result of merging two scene graphs."""

    added_nodes: list[SceneNode]
    updated_nodes: list[SceneNode]
    added_edges: list[SceneEdge]
    conflicts_resolved: int

    def to_dict(self) -> dict:  # type: ignore[type-arg]
        """Serialize to a plain dict."""
        return {
            "added_nodes": [n.to_dict() for n in self.added_nodes],
            "updated_nodes": [n.to_dict() for n in self.updated_nodes],
            "added_edges": [e.to_dict() for e in self.added_edges],
            "conflicts_resolved": self.conflicts_resolved,
        }

    def summary(self) -> str:
        """Return a one-line summary string."""
        return (
            f"Added {len(self.added_nodes)} nodes, "
            f"updated {len(self.updated_nodes)} nodes, "
            f"added {len(self.added_edges)} edges, "
            f"resolved {self.conflicts_resolved} conflict(s)."
        )


def _sha16_export() -> str:
    """Re-export _sha16 for use in tests."""
    return _sha16.__doc__ or ""
