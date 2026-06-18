"""
polaroid demo — embeddable CRDT scene graph for embodied AI agents.

Demonstrates:
1. Creating two scene graphs (simulating two robots)
2. Each observing different parts of the same space
3. Merging them with CRDT semantics
4. Querying the unified scene

Run:
    python examples/demo.py
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from polaroid.graph import SceneEdge, SceneNode
from polaroid.merger import SceneMerger
from polaroid.query import SceneQuery
from polaroid.report import print_merge, print_scene, to_markdown
from polaroid.store import SceneStore


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        # ── Robot A observes the kitchen ──────────────────────────────────────
        print("\n=== Robot A observing kitchen ===")
        store_a = SceneStore(str(Path(tmp) / "robot-a.db"))

        kitchen = SceneNode(
            label="room-kitchen",
            node_type="room",
            properties={"floor": "tile", "area_sqm": 15},
            confidence=0.95,
            agent_id="robot-a",
        )
        table = SceneNode(
            label="table-A",
            node_type="object",
            properties={"color": "brown", "material": "wood"},
            confidence=0.9,
            agent_id="robot-a",
        )
        chair = SceneNode(
            label="chair-1",
            node_type="object",
            properties={"color": "grey"},
            confidence=0.85,
            agent_id="robot-a",
        )

        store_a.upsert_node(kitchen)
        store_a.upsert_node(table)
        store_a.upsert_node(chair)

        # Spatial relationships
        store_a.upsert_edge(SceneEdge(source_id=kitchen.id, target_id=table.id, relation="contains"))
        store_a.upsert_edge(SceneEdge(source_id=kitchen.id, target_id=chair.id, relation="contains"))
        store_a.upsert_edge(SceneEdge(source_id=table.id, target_id=chair.id, relation="adjacent-to"))

        print(f"Robot A sees: {store_a.node_count()} nodes, {store_a.edge_count()} edges")

        # ── Robot B observes the lounge ───────────────────────────────────────
        print("\n=== Robot B observing lounge ===")
        store_b = SceneStore(str(Path(tmp) / "robot-b.db"))

        lounge = SceneNode(
            label="room-lounge",
            node_type="room",
            properties={"floor": "carpet", "area_sqm": 25},
            confidence=0.9,
            agent_id="robot-b",
        )
        sofa = SceneNode(
            label="sofa-1",
            node_type="object",
            properties={"color": "blue"},
            confidence=0.8,
            agent_id="robot-b",
        )
        door = SceneNode(
            label="door-kitchen",
            node_type="object",
            properties={"state": "open"},
            confidence=0.7,
            agent_id="robot-b",
        )
        # Robot B also saw the kitchen (different confidence)
        kitchen_b = SceneNode(
            label="room-kitchen",
            node_type="room",
            properties={"floor": "tile"},
            confidence=0.5,  # lower — robot B only glimpsed it
            agent_id="robot-b",
        )

        store_b.upsert_node(lounge)
        store_b.upsert_node(sofa)
        store_b.upsert_node(door)
        store_b.upsert_node(kitchen_b)  # same label+type → same id, lower confidence

        store_b.upsert_edge(SceneEdge(source_id=lounge.id, target_id=sofa.id, relation="contains"))
        store_b.upsert_edge(SceneEdge(source_id=lounge.id, target_id=door.id, relation="contains"))
        store_b.upsert_edge(SceneEdge(source_id=kitchen.id, target_id=lounge.id, relation="connects", confidence=0.8))

        print(f"Robot B sees: {store_b.node_count()} nodes, {store_b.edge_count()} edges")

        # ── Merge B into A (CRDT) ─────────────────────────────────────────────
        print("\n=== Merging Robot B's map into Robot A (CRDT merge) ===")
        merger = SceneMerger()
        result = merger.merge(store_a, store_b)

        print_merge(result)
        print(result.summary())

        # ── Query the unified scene ────────────────────────────────────────────
        print("\n=== Querying the unified scene ===")
        q = SceneQuery(store_a)

        print("\nAll nodes:")
        all_nodes = q.find_nodes()
        print_scene(all_nodes)

        print("\nObjects only:")
        objects = q.find_nodes(node_type="object")
        for obj in objects:
            print(f"  - {obj.label} (conf={obj.confidence:.2f}, agent={obj.agent_id or '?'})")

        print("\nNeighbors of kitchen:")
        neighbors = q.find_neighbors(kitchen.id)
        for n in neighbors:
            print(f"  - {n.label} ({n.node_type})")

        print("\nContext summary:")
        print(q.context_summary())

        # ── Verify CRDT: kitchen kept A's higher confidence ──────────────────
        unified_kitchen = store_a.get_node(kitchen.id)
        assert unified_kitchen is not None
        assert unified_kitchen.confidence == 0.95, (
            f"Expected kitchen confidence=0.95 (robot A), got {unified_kitchen.confidence}"
        )
        print(f"\n✓ Kitchen confidence preserved at {unified_kitchen.confidence} (robot A wins)")

        # ── Markdown report ────────────────────────────────────────────────────
        md = to_markdown(all_nodes)
        assert "polaroid" in md
        print("\n✓ Markdown report generated successfully")

        store_a.close()
        store_b.close()

    print("\n✓ Demo completed successfully!\n")


if __name__ == "__main__":
    main()
