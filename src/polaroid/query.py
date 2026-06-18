"""Query a SceneStore by type, label, relation, or spatial context."""

from __future__ import annotations

from polaroid.graph import SceneNode
from polaroid.store import SceneStore


class SceneQuery:
    """High-level query interface for a SceneStore.

    All methods are read-only — they never modify the store.
    """

    def __init__(self, store: SceneStore) -> None:
        self._store = store

    def find_nodes(
        self,
        node_type: str | None = None,
        label_contains: str | None = None,
        min_confidence: float = 0.0,
    ) -> list[SceneNode]:
        """Return nodes matching the given filters.

        Args:
            node_type:      Only return nodes of this type (e.g. "object", "room").
            label_contains: Case-insensitive substring match on node label.
            min_confidence: Exclude nodes with confidence below this threshold.

        Returns:
            List of matching SceneNode objects.
        """
        nodes = self._store.list_nodes(node_type=node_type, min_confidence=min_confidence)
        if label_contains is not None:
            needle = label_contains.lower()
            nodes = [n for n in nodes if needle in n.label.lower()]
        return nodes

    def find_neighbors(
        self,
        node_id: str,
        relation: str | None = None,
    ) -> list[SceneNode]:
        """Return nodes that are targets of edges originating from node_id.

        Args:
            node_id:  Source node ID.
            relation: If given, only follow edges with this relation type.

        Returns:
            List of neighbor SceneNode objects (may be empty).
        """
        edges = self._store.list_edges(source_id=node_id, relation=relation)
        neighbors: list[SceneNode] = []
        for edge in edges:
            target = self._store.get_node(edge.target_id)
            if target is not None:
                neighbors.append(target)
        return neighbors

    def context_summary(self, agent_id: str = "") -> str:
        """Return a human-readable description of the scene.

        Args:
            agent_id: If non-empty, only count nodes observed by this agent.

        Returns:
            A one-paragraph text summary of the scene graph.
        """
        all_nodes = self._store.list_nodes()
        if agent_id:
            all_nodes = [n for n in all_nodes if n.agent_id == agent_id]

        # Count by type
        counts: dict[str, int] = {}
        for node in all_nodes:
            counts[node.node_type] = counts.get(node.node_type, 0) + 1

        # Build header
        type_parts = []
        for t in sorted(counts):
            c = counts[t]
            type_parts.append(f"{c} {t}{'s' if c != 1 else ''}")

        if not type_parts:
            return "Empty scene graph — no nodes observed."

        header = ", ".join(type_parts) + "."

        # Known objects preview
        object_labels = [n.label for n in all_nodes if n.node_type == "object"][:10]
        edge_count = self._store.edge_count()

        parts = [header]
        if object_labels:
            parts.append(f"Known objects: {', '.join(object_labels)}.")
        if edge_count > 0:
            suffix = "s" if edge_count != 1 else ""
            parts.append(f"{edge_count} spatial relationship{suffix} recorded.")

        return " ".join(parts)
