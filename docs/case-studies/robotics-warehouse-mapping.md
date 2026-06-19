# Case Study: Conflict-Free Fleet Mapping for 60 Autonomous Warehouse Robots

## Company Profile

**WareBot** is a warehouse robotics company based in Columbus, OH. With 40 engineers, they build autonomous mobile robots (AMRs) for e-commerce fulfillment centers. Their robots navigate warehouse floors to pick, transport, and stage inventory for shipping. As of 2025, they have deployed in 3 warehouse facilities with 60 robots operating across combined floor space of 580,000 square feet.

## The Problem

WareBot's 20-robot fleet in their first warehouse deployment was built around each robot maintaining an independent SLAM (Simultaneous Localization and Mapping) map of its environment. Individual robots built excellent maps. The problem was synchronization.

When two robots mapped the same area independently, they sometimes disagreed. Robot A, which had traversed Aisle 14 from the south, recorded a 3.2-meter-wide corridor with a support column at the north end. Robot B, which had approached from the north, recorded the same corridor as 3.1 meters wide with a loading bay door that Robot A hadn't seen (it was closed when Robot A passed). The fleet management system couldn't merge these into a consistent map — it didn't know whose dimensions were correct, whether the loading bay door was permanent or temporary, or how to route packages through an area with conflicting topology data.

The reconciliation process was manual: a WareBot field engineer would walk the disputed area, take measurements, and manually edit the canonical map. Each warehouse layout change — a new shelving unit installed, a pallet staging area reconfigured, a forklift lane added — required this manual reconciliation. The engineering team estimated 4 hours of engineer time per layout change, and layout changes happened 2-3 times per month per warehouse.

New robot onboarding was equally painful. When a 21st robot was added to a fleet, it needed a complete map of the warehouse before it could operate safely. Transferring the map meant exporting the canonical map from the fleet management server, loading it to the robot, and waiting for the robot to do its own validation pass — a 2-day process for each new robot.

## Solution Architecture

WareBot replaced their per-robot SLAM map storage with polaroid `SceneStore` instances — one SQLite database per robot, mounted on the robot's local storage. At the end of each shift, all 20 robots merge their stores using `SceneMerger` with CRDT semantics. New robots onboard using `extract_subgraph()` to receive only their zone's map data. `compute_stats()` gives fleet managers a real-time completeness report.

```
┌──────────────────────────────────────────────────────────────────────┐
│                       WareBot Fleet Platform                         │
│                                                                      │
│  Robot A explores    ┌───────────────────────────────────────────┐  │
│  Aisle 14        ─► │  Robot A SceneStore (/robot-a/scene.db)   │  │
│                      │  SceneNode("Aisle-14", "region", ...)     │  │
│                      │  SceneNode("Column-14N", "obstacle", ...) │  │
│                      │  SceneEdge(aisle→column, "contains")      │  │
│                      └──────────────────┬────────────────────────┘  │
│                                         │                            │
│  Robot B explores    ┌──────────────────▼────────────────────────┐  │
│  same area       ─► │  Robot B SceneStore (/robot-b/scene.db)   │  │
│                      │  SceneNode("Aisle-14", "region", ...)     │  │
│                      │  SceneNode("LoadingDoor-14N", "door", ...) │  │
│                      │  SceneEdge(aisle→door, "contains")        │  │
│                      └──────────────────┬────────────────────────┘  │
│                                         │                            │
│  Shift-end merge     ┌──────────────────▼────────────────────────┐  │
│                      │  SceneMerger.merge(robot_a, robot_b)      │  │
│                      │  CRDT: Aisle-14 ID = same (content-addr)  │  │
│                      │  Column-14N + LoadingDoor-14N both added  │  │
│                      │  Higher confidence observation wins        │  │
│                      │  → unified canonical map, 0 conflicts     │  │
│                      └───────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────┘
```

The key insight enabling conflict-free merges: `SceneNode.id = SHA-256[:16](label|node_type)`. Two robots observing the same physical area (same label, same type) always produce the same node ID. Merging is additive: both observations are incorporated, with the higher-confidence observation winning on property conflicts.

## Implementation

```python
# warebot/mapping/fleet_merge.py
from pathlib import Path
from polaroid.graph import SceneNode, SceneEdge
from polaroid.store import SceneStore
from polaroid.merger import SceneMerger
from polaroid.stats import compute_stats, GraphStats

ROBOT_DB_TEMPLATE = "/data/robots/{robot_id}/scene.db"
CANONICAL_MAP_DB = "/data/fleet/canonical-map.db"
ZONES = {
    "zone-a": ["Aisle-1", "Aisle-2", "Aisle-3", "Aisle-4", "Aisle-5"],
    "zone-b": ["Aisle-6", "Aisle-7", "Aisle-8", "Aisle-9", "Aisle-10"],
    # ...
}


def record_observation(
    robot_id: str,
    label: str,
    node_type: str,
    properties: dict,
    confidence: float,
    adjacent_to: list[str] | None = None,
) -> SceneNode:
    """Record a robot's observation of an area or object.

    SceneNode.id is deterministic — same label+type always produces the same ID.
    Two robots observing the same area will record the same node ID.
    """
    db_path = ROBOT_DB_TEMPLATE.format(robot_id=robot_id)
    store = SceneStore(db_path)

    node = SceneNode(
        label=label,
        node_type=node_type,
        properties=properties,
        confidence=confidence,
        agent_id=robot_id,
    )
    store.upsert_node(node)

    # Record spatial relationships
    if adjacent_to:
        for neighbor_label in adjacent_to:
            # Find neighbor node by label
            all_nodes = store.list_nodes()
            for neighbor in all_nodes:
                if neighbor.label == neighbor_label:
                    edge = SceneEdge(
                        source_id=node.id,
                        target_id=neighbor.id,
                        relation="adjacent-to",
                        confidence=confidence,
                    )
                    store.upsert_edge(edge)
                    break

    store.close()
    return node


def merge_fleet_maps(robot_ids: list[str]) -> GraphStats:
    """Merge all robot scene stores into the canonical fleet map.

    CRDT guarantees: this is safe to call multiple times with the same robots
    (idempotent), in any order (commutative), and for any subset of robots first
    then the rest (associative).

    Returns GraphStats for the merged canonical map.
    """
    canonical = SceneStore(CANONICAL_MAP_DB)
    merger = SceneMerger()

    for robot_id in robot_ids:
        db_path = ROBOT_DB_TEMPLATE.format(robot_id=robot_id)
        robot_store = SceneStore(db_path)
        result = merger.merge(canonical, robot_store)
        robot_store.close()

        print(f"  Merged robot {robot_id}: {result.summary()}")

    stats = compute_stats(canonical)
    canonical.close()
    return stats


def onboard_new_robot(new_robot_id: str, zone: str) -> int:
    """Seed a new robot's scene store with only its zone's map data.

    Uses list_nodes(node_type=...) and list_edges() to extract the subgraph
    for the new robot's operating zone, avoiding loading the full fleet map.

    Returns the number of nodes seeded.
    """
    canonical = SceneStore(CANONICAL_MAP_DB)
    new_robot_db = ROBOT_DB_TEMPLATE.format(robot_id=new_robot_id)
    new_store = SceneStore(new_robot_db)
    merger = SceneMerger()

    zone_labels = set(ZONES.get(zone, []))
    all_nodes = canonical.list_nodes()
    zone_nodes = [n for n in all_nodes if n.label in zone_labels
                  or any(label in n.properties.get("zone", "") for label in zone_labels)]

    zone_node_ids = {n.id for n in zone_nodes}
    zone_edges = [e for e in canonical.list_edges()
                  if e.source_id in zone_node_ids or e.target_id in zone_node_ids]

    # Seed the new robot's store
    for node in zone_nodes:
        new_store.upsert_node(node)
    for edge in zone_edges:
        new_store.upsert_edge(edge)

    node_count = new_store.node_count()
    canonical.close()
    new_store.close()

    print(f"  Robot {new_robot_id} seeded with {node_count} nodes for zone '{zone}'")
    return node_count


def fleet_map_health_report(robot_ids: list[str]) -> str:
    """Generate a completeness report for the fleet map."""
    stats = merge_fleet_maps(robot_ids)

    lines = [
        "# Fleet Map Health Report",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Total nodes | {stats.node_count} |",
        f"| Total edges | {stats.edge_count} |",
        f"| Avg connections per node | {stats.avg_degree:.1f} |",
        f"| Max connections | {stats.max_degree} |",
        f"| Connected components | {stats.connected_components} |",
        f"| Map diameter | {stats.diameter if stats.diameter is not None else 'disconnected'} |",
        "",
        "## Node Types",
        "",
    ]
    for node_type, count in sorted(stats.node_types.items()):
        lines.append(f"- **{node_type}**: {count} nodes")

    lines += ["", "## Spatial Relations", ""]
    for relation, count in sorted(stats.edge_relations.items()):
        lines.append(f"- **{relation}**: {count} edges")

    return "\n".join(lines)
```

## Results

- **Map merge: 4 hours manual reconciliation → 0** — the CRDT merge is fully automated. Every shift-end merge across 20 robots takes under 30 seconds and requires zero engineer involvement.
- **New robot onboarding: 2 days → 30 minutes** — `onboard_new_robot()` seeds a robot with its zone's subgraph from the canonical map. The robot starts its first shift with full knowledge of its operating area; human-guided exploration is needed only for areas not yet in the canonical map.
- **3 warehouses deployed, 60 robots** operating across WareBot's customer base with polaroid as the map storage layer
- **Zero routing conflicts** due to map inconsistencies since deployment — the CRDT's grow-only node semantics ensure that every robot's unique observations are always incorporated, never discarded
- **`compute_stats()` is the operations dashboard** — fleet managers check `connected_components` daily; a value greater than 1 indicates an unmapped area (a corridor not yet explored by any robot) and triggers a directed exploration task

## Key Takeaways

- CRDT semantics turn a hard problem (distributed map consistency) into a solved one. Grow-only nodes and confidence-weighted last-write-wins eliminate the entire category of "which robot is right?" conflicts.
- Content-addressing is the foundation. Two robots observing the same corridor produce the same `SceneNode.id` because the ID is derived from `label|node_type`, not from robot state. This is what makes merging additive rather than conflicting.
- Extract-subgraph onboarding solves the cold-start problem. New robots don't need the full warehouse map — they need their zone. `list_nodes()` with zone filtering gives them exactly what they need without loading irrelevant data.
- `compute_stats().connected_components > 1` is an operational alarm. Disconnected subgraphs indicate unexplored areas, which are navigation hazards. This metric catches gaps before they affect routing.
- SQLite-per-robot is simpler than a shared server. Each robot carries its own database. Merges are pull operations at shift end. There's no central server to fail.

## Try It Yourself

```bash
# Install polaroid
pip install polaroid

# Simulate two robots mapping the same area and merging
python -c "
from polaroid.graph import SceneNode, SceneEdge
from polaroid.store import SceneStore
from polaroid.merger import SceneMerger
from polaroid.stats import compute_stats

# Robot A maps aisle 14
store_a = SceneStore('/tmp/robot-a.db')
aisle = SceneNode('Aisle-14', 'region', {'width_m': 3.2, 'length_m': 45.0}, confidence=0.9, agent_id='robot-a')
column = SceneNode('Column-14N', 'obstacle', {'type': 'support_column'}, confidence=0.95, agent_id='robot-a')
store_a.upsert_node(aisle)
store_a.upsert_node(column)
store_a.upsert_edge(SceneEdge(aisle.id, column.id, 'contains', confidence=0.9))

# Robot B maps same aisle, sees a door Robot A missed
store_b = SceneStore('/tmp/robot-b.db')
aisle_b = SceneNode('Aisle-14', 'region', {'width_m': 3.1}, confidence=0.85, agent_id='robot-b')
door = SceneNode('LoadingDoor-14N', 'door', {'state': 'closed'}, confidence=0.98, agent_id='robot-b')
store_b.upsert_node(aisle_b)
store_b.upsert_node(door)

# Merge: Robot A has higher confidence on Aisle-14, Robot B adds LoadingDoor
canonical = SceneStore('/tmp/canonical.db')
merger = SceneMerger()
merger.merge(canonical, store_a)
result = merger.merge(canonical, store_b)
print(result.summary())

stats = compute_stats(canonical)
print(f'Nodes: {stats.node_count}, Edges: {stats.edge_count}')
"

# Use the CLI
polaroid merge /tmp/robot-a.db /tmp/canonical.db
polaroid stats /tmp/canonical.db
```
