# Case Study: Persistent NPC World State for an AI-Driven Open-World RPG

## Company Profile

**Emergent Studios** is an indie game studio based in Austin, TX. With 12 engineers, they build AI-driven narrative games where non-player character (NPC) behavior adapts to the player's history and world state. Their debut title, *Wandering Epoch*, is a single-player and cooperative open-world RPG with a 50,000+ node world graph — rooms, NPCs, items, quests, and spatial connections — where AI agents control every NPC's decision-making. The game shipped with 85,000 players and a 4.6-star average review.

## The Problem

The initial prototype of *Wandering Epoch* treated world state as a monolithic JSON blob loaded from save files at game start. This approach had three fatal problems at the scale the team was targeting.

**Load time**: a 50,000-node world state, serialized as JSON, took 2.8-3.4 seconds to load at game start — well above the 500ms budget for perceived snappiness. Players noticed. Early playtest feedback included "why does it freeze when I fast-travel?" and "I can't tell if the game crashed or if it's loading."

**Query performance**: NPCs needed to answer questions like "find all quest-giver NPCs within 3 rooms of the player," "what items are in the room directly north of the tavern?", and "is there a path from the player's current location to the dungeon entrance?" With a flat JSON blob, answering these required full-scan filtering in Python — taking 200-800ms per query, which stalled the NPC decision loop and caused visible animation stutters.

**Multiplayer conflict**: when two players in cooperative mode modified the same room simultaneously — one taking an item while the other dropped a different item — the game state diverged. The naive resolution (last-write-wins by timestamp) caused items to appear and disappear unpredictably, breaking the multiplayer experience.

The team needed a world state representation that loaded fast, answered spatial queries in under 1ms, and merged concurrent modifications from multiple players without conflicts.

## Solution Architecture

Emergent Studios replaced their JSON-blob world state with a polaroid `SceneStore`. Every room, NPC, item, and spatial connection is a `SceneNode` or `SceneEdge`. `SceneStore`'s SQLite backend handles fast startup (index-backed queries instead of full JSON parse). `list_nodes(node_type="npc")` answers NPC queries in under 1ms. `SceneMerger` handles multiplayer state synchronization using CRDT semantics — the same algorithm that makes warehouse robot map merges conflict-free works equally well for multiplayer game worlds.

```
┌────────────────────────────────────────────────────────────────────┐
│                    Wandering Epoch Game Engine                     │
│                                                                    │
│  Game start        ┌────────────────────────────────────────────┐ │
│      │             │  SceneStore.open("/saves/player-001.db")   │ │
│      └───────────► │  50,000 nodes loaded: 40ms                 │ │
│                    │  (vs 3,200ms for JSON blob)                │ │
│                    └──────────────────┬─────────────────────────┘ │
│                                       │                            │
│  NPC decision      ┌──────────────────▼─────────────────────────┐ │
│  loop (60Hz)    ─► │  store.list_nodes(node_type="npc")         │ │
│                    │  → all NPCs in <1ms                        │ │
│                    │  store.list_edges(source_id=room.id,        │ │
│                    │                   relation="contains")      │ │
│                    │  → items/npcs in room in <1ms              │ │
│                    └──────────────────┬─────────────────────────┘ │
│                                       │                            │
│  Multiplayer       ┌──────────────────▼─────────────────────────┐ │
│  sync           ─► │  SceneMerger.merge(player_a, player_b)     │ │
│                    │  CRDT: grow-only nodes, LWW edges           │ │
│                    │  → zero conflicts, deterministic merge      │ │
│                    └────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────────┘
```

## Implementation

```python
# emergent/world/scene_manager.py
from pathlib import Path
from polaroid.graph import SceneNode, SceneEdge, MergeResult
from polaroid.store import SceneStore
from polaroid.merger import SceneMerger
from polaroid.stats import compute_stats, GraphStats

SAVE_DIR = Path("/data/saves")


class WorldStateManager:
    """polaroid-backed world state manager for Wandering Epoch."""

    def __init__(self, save_slot: str) -> None:
        db_path = SAVE_DIR / f"{save_slot}.db"
        self.store = SceneStore(str(db_path))
        self.merger = SceneMerger()

    # ── World building ──────────────────────────────────────────────────────

    def add_room(self, label: str, properties: dict, confidence: float = 1.0) -> SceneNode:
        """Add a room node. Same label always produces the same ID."""
        node = SceneNode(label=label, node_type="room", properties=properties,
                         confidence=confidence)
        self.store.upsert_node(node)
        return node

    def add_npc(self, label: str, properties: dict, home_room_id: str) -> SceneNode:
        """Add an NPC and connect it to its home room."""
        npc = SceneNode(label=label, node_type="npc", properties=properties, confidence=1.0)
        self.store.upsert_node(npc)
        edge = SceneEdge(home_room_id, npc.id, "contains", confidence=1.0)
        self.store.upsert_edge(edge)
        return npc

    def add_item(self, label: str, properties: dict, in_room_id: str) -> SceneNode:
        """Add an item and place it in a room."""
        item = SceneNode(label=label, node_type="item", properties=properties, confidence=1.0)
        self.store.upsert_node(item)
        edge = SceneEdge(in_room_id, item.id, "contains", confidence=1.0)
        self.store.upsert_edge(edge)
        return item

    def connect_rooms(self, room_a_id: str, room_b_id: str) -> SceneEdge:
        """Add bidirectional adjacency between two rooms."""
        edge_ab = SceneEdge(room_a_id, room_b_id, "adjacent-to", confidence=1.0)
        edge_ba = SceneEdge(room_b_id, room_a_id, "adjacent-to", confidence=1.0)
        self.store.upsert_edge(edge_ab)
        self.store.upsert_edge(edge_ba)
        return edge_ab

    # ── NPC queries (all sub-1ms) ────────────────────────────────────────────

    def find_npcs(self, npc_type: str | None = None) -> list[SceneNode]:
        """Find all NPCs, optionally filtered by type property."""
        npcs = self.store.list_nodes(node_type="npc")
        if npc_type:
            npcs = [n for n in npcs if n.properties.get("type") == npc_type]
        return npcs

    def items_in_room(self, room_id: str) -> list[SceneNode]:
        """Return all items contained in a room."""
        contains_edges = self.store.list_edges(source_id=room_id, relation="contains")
        items = []
        for edge in contains_edges:
            node = self.store.get_node(edge.target_id)
            if node and node.node_type == "item":
                items.append(node)
        return items

    def npcs_in_room(self, room_id: str) -> list[SceneNode]:
        """Return all NPCs currently in a room."""
        contains_edges = self.store.list_edges(source_id=room_id, relation="contains")
        npcs = []
        for edge in contains_edges:
            node = self.store.get_node(edge.target_id)
            if node and node.node_type == "npc":
                npcs.append(node)
        return npcs

    def adjacent_rooms(self, room_id: str) -> list[SceneNode]:
        """Return all rooms directly adjacent to the given room."""
        adj_edges = self.store.list_edges(source_id=room_id, relation="adjacent-to")
        rooms = []
        for edge in adj_edges:
            node = self.store.get_node(edge.target_id)
            if node and node.node_type == "room":
                rooms.append(node)
        return rooms

    # ── Multiplayer sync ─────────────────────────────────────────────────────

    def sync_with_peer(self, peer_save_slot: str) -> MergeResult:
        """Merge a peer player's world state into this one using CRDT semantics."""
        peer_db = SAVE_DIR / f"{peer_save_slot}.db"
        peer_store = SceneStore(str(peer_db))
        result = self.merger.merge(self.store, peer_store)
        peer_store.close()
        return result

    # ── Scene context for NPC AI ─────────────────────────────────────────────

    def room_context(self, room_id: str) -> str:
        """Generate a text description of a room for NPC AI decision-making."""
        room = self.store.get_node(room_id)
        if room is None:
            return "Unknown room."

        npcs = self.npcs_in_room(room_id)
        items = self.items_in_room(room_id)
        exits = self.adjacent_rooms(room_id)
        stats = compute_stats(self.store)

        lines = [
            f"Room: {room.label} ({room.properties.get('description', '')})",
            f"NPCs present: {', '.join(n.label for n in npcs) or 'none'}",
            f"Items: {', '.join(i.label for i in items) or 'none'}",
            f"Exits: {', '.join(r.label for r in exits) or 'none'}",
            f"World size: {stats.node_count} nodes, {stats.edge_count} connections",
        ]
        return "\n".join(lines)

    def close(self) -> None:
        self.store.close()
```

## Results

- **NPC world load time: 3,200ms → 40ms** — SQLite's indexed queries replace the full JSON parse. The 500ms player-facing load budget is met with headroom.
- **Navigation query latency: under 1ms** — `list_edges(source_id=room_id, relation="adjacent-to")` returns results in 0.3-0.8ms for the typical room size in *Wandering Epoch*; NPC AI decision loops run at 60Hz without stutter.
- **Supports 50,000+ node game worlds** — the SQLite backend scales comfortably to the world size without memory pressure. The full *Wandering Epoch* world (51,847 nodes, 134,293 edges) occupies 42MB on disk.
- **Zero multiplayer item-state conflicts** since shipping — the CRDT merge in `sync_with_peer()` handles concurrent player actions (one player picks up an item, another drops a different item in the same room) deterministically, without the "item teleportation" bugs that plagued the original JSON-blob approach.
- **85,000 players**, 4.6-star average review — "The NPCs actually remember things" and "The world feels persistent" appear repeatedly in player reviews, directly attributable to the polaroid-backed state persistence.

## Key Takeaways

- SQLite is faster than JSON for structured world state. Indexed queries on a 50,000-node SQLite database are 80x faster at startup than parsing an equivalent JSON blob, because SQLite reads only the data you ask for.
- `SceneNode.id` content-addressing makes multiplayer sync trivial. Two players placing the same type of object in the same location produce the same node ID — the merge is additive, not conflicting.
- CRDT semantics map naturally to game world logic. Grow-only nodes match the "discovered areas aren't un-discovered" semantic. Confidence-weighted LWW matches "the most recently confirmed state of an NPC or item wins."
- `list_nodes(node_type=...)` is the NPC AI's primary query pattern. Filtering by type at the SQLite level is faster and simpler than loading all nodes and filtering in Python.
- `room_context()` → LLM prompt injection makes NPC AI context-aware at negligible cost. The text description generated by `compute_stats()` and room queries gives the NPC's AI model exactly the situational awareness it needs in one database round trip.

## Try It Yourself

```bash
# Install polaroid
pip install polaroid-ai

# Build a small game world and query it
python -c "
from polaroid.graph import SceneNode, SceneEdge
from polaroid.store import SceneStore
from polaroid.stats import compute_stats

store = SceneStore('/tmp/game-world.db')

# Rooms
tavern = SceneNode('The Rusty Flagon', 'room', {'description': 'A cozy tavern'})
dungeon = SceneNode('Dungeon Entrance', 'room', {'description': 'A dark stairway'})
store.upsert_node(tavern)
store.upsert_node(dungeon)

# NPCs
innkeeper = SceneNode('Aldric the Innkeeper', 'npc', {'type': 'quest-giver', 'friendly': True})
store.upsert_node(innkeeper)

# Items
key = SceneNode('Rusty Iron Key', 'item', {'value': 5, 'weight': 0.1})
store.upsert_node(key)

# Connections
store.upsert_edge(SceneEdge(tavern.id, dungeon.id, 'adjacent-to'))
store.upsert_edge(SceneEdge(tavern.id, innkeeper.id, 'contains'))
store.upsert_edge(SceneEdge(dungeon.id, key.id, 'contains'))

stats = compute_stats(store)
print(f'World: {stats.node_count} nodes, {stats.edge_count} edges')

npcs = store.list_nodes(node_type='npc')
print(f'NPCs: {[n.label for n in npcs]}')
"

# Use the CLI
polaroid stats /tmp/game-world.db
polaroid nodes /tmp/game-world.db --type npc
```
