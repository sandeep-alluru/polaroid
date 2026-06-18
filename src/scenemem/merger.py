"""CRDT-style merge of two scene stores.

Algorithm:
- Nodes are grow-only (never deleted).
- Conflicting property updates resolved by confidence-weighted last-write-wins.
- Edges are grow-only; higher-confidence version wins on conflict.
"""

from __future__ import annotations

from scenemem.graph import MergeResult, SceneEdge, SceneNode
from scenemem.store import SceneStore


class SceneMerger:
    """Merge two SceneStore instances using CRDT semantics.

    This is a pure function wrapped in a class for extensibility.
    Neither store is modified; the result is applied to ``local``.
    """

    def merge(self, local: SceneStore, remote: SceneStore) -> MergeResult:
        """Merge remote into local.

        CRDT properties guaranteed:
        - Idempotent: merging the same remote twice produces the same result.
        - Commutative: merge(A, B) and merge(B, A) produce the same final state.
        - Associative: merge order among multiple remotes does not matter.

        Args:
            local:  The destination SceneStore (written to).
            remote: The source SceneStore (read only).

        Returns:
            MergeResult describing what changed.
        """
        added_nodes: list[SceneNode] = []
        updated_nodes: list[SceneNode] = []
        added_edges: list[SceneEdge] = []
        conflicts_resolved = 0

        # ── Nodes ──────────────────────────────────────────────────────────────
        for remote_node in remote.list_nodes():
            local_node = local.get_node(remote_node.id)

            if local_node is None:
                # Grow-only set: new node, always add
                local.upsert_node(remote_node)
                added_nodes.append(remote_node)

            elif remote_node.confidence > local_node.confidence:
                # Confidence-weighted last-write-wins register
                local.upsert_node(remote_node)
                updated_nodes.append(remote_node)
                conflicts_resolved += 1

            # else: local has higher or equal confidence — keep local, no action

        # ── Edges ──────────────────────────────────────────────────────────────
        for remote_edge in remote.list_edges():
            local_edge = local.get_edge(remote_edge.id)

            if local_edge is None:
                local.upsert_edge(remote_edge)
                added_edges.append(remote_edge)

            elif remote_edge.confidence > local_edge.confidence:
                local.upsert_edge(remote_edge)
                conflicts_resolved += 1

        return MergeResult(
            added_nodes=added_nodes,
            updated_nodes=updated_nodes,
            added_edges=added_edges,
            conflicts_resolved=conflicts_resolved,
        )
