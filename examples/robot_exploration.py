"""robot_exploration.py — Two robots explore opposite sides of a warehouse.

Robot A maps the west wing; Robot B maps the east wing. Both store their
observations in independent SceneStores. At the end of their shifts the
two maps are merged into a single store. corridor_c appears in both wings
(it connects them) and deduplicates automatically via content-addressed IDs.

A manual BFS using find_neighbors() then finds the shortest path from
room_101 (west wing) to the charging_station (east wing).
"""

import collections
import os
import shutil
import tempfile

from polaroid import SceneEdge, SceneMerger, SceneNode, SceneQuery, SceneStore

# ---------------------------------------------------------------------------
# Temporary database paths
# ---------------------------------------------------------------------------
tmp = tempfile.mkdtemp()
store_a = SceneStore(os.path.join(tmp, "robot_a.db"))
store_b = SceneStore(os.path.join(tmp, "robot_b.db"))
merged_store = SceneStore(os.path.join(tmp, "merged.db"))

# ---------------------------------------------------------------------------
# Robot A — west wing
# ---------------------------------------------------------------------------
# Rooms
rooms_a = []
for i in range(1, 6):
    node = SceneNode(
        label=f"room_10{i}",
        node_type="room",
        properties={"wing": "west", "index": i},
        confidence=0.9,
        agent_id="robot-a",
    )
    store_a.upsert_node(node)
    rooms_a.append(node)

corridor_a = SceneNode(
    label="corridor_a",
    node_type="corridor",
    properties={"wing": "west", "length_m": 30},
    confidence=0.9,
    agent_id="robot-a",
)
corridor_b = SceneNode(
    label="corridor_b",
    node_type="corridor",
    properties={"wing": "west", "length_m": 20},
    confidence=0.9,
    agent_id="robot-a",
)
# corridor_c is the shared central corridor — same label+type → same SHA16 id
corridor_c = SceneNode(
    label="corridor_c",
    node_type="corridor",
    properties={"wing": "central", "length_m": 50},
    confidence=0.85,
    agent_id="robot-a",
)
exit_west_1 = SceneNode(
    label="exit_west_1",
    node_type="exit",
    properties={"side": "west", "door": "rolling shutter"},
    confidence=0.9,
    agent_id="robot-a",
)
exit_west_2 = SceneNode(
    label="exit_west_2",
    node_type="exit",
    properties={"side": "west", "door": "fire door"},
    confidence=0.9,
    agent_id="robot-a",
)

for node in [corridor_a, corridor_b, corridor_c, exit_west_1, exit_west_2]:
    store_a.upsert_node(node)

# Edges: rooms 101-103 off corridor_a, rooms 104-105 off corridor_b
for room in rooms_a[:3]:
    store_a.upsert_edge(SceneEdge(corridor_a.id, room.id, "leads_to"))
    store_a.upsert_edge(SceneEdge(room.id, corridor_a.id, "leads_to"))

for room in rooms_a[3:]:
    store_a.upsert_edge(SceneEdge(corridor_b.id, room.id, "leads_to"))
    store_a.upsert_edge(SceneEdge(room.id, corridor_b.id, "leads_to"))

store_a.upsert_edge(SceneEdge(corridor_a.id, corridor_b.id, "connects_to"))
store_a.upsert_edge(SceneEdge(corridor_b.id, corridor_c.id, "connects_to"))
store_a.upsert_edge(SceneEdge(corridor_a.id, exit_west_1.id, "leads_to"))
store_a.upsert_edge(SceneEdge(corridor_b.id, exit_west_2.id, "leads_to"))

print(f"Robot A stored: {store_a.node_count()} nodes, {store_a.edge_count()} edges")

# ---------------------------------------------------------------------------
# Robot B — east wing
# ---------------------------------------------------------------------------
rooms_b = []
for i in range(1, 6):
    node = SceneNode(
        label=f"room_20{i}",
        node_type="room",
        properties={"wing": "east", "index": i},
        confidence=0.88,
        agent_id="robot-b",
    )
    store_b.upsert_node(node)
    rooms_b.append(node)

corridor_d = SceneNode(
    label="corridor_d",
    node_type="corridor",
    properties={"wing": "east", "length_m": 28},
    confidence=0.88,
    agent_id="robot-b",
)
corridor_e = SceneNode(
    label="corridor_e",
    node_type="corridor",
    properties={"wing": "east", "length_m": 18},
    confidence=0.88,
    agent_id="robot-b",
)
# Same label+type as A's corridor_c → same id — will merge cleanly
corridor_c_b = SceneNode(
    label="corridor_c",
    node_type="corridor",
    properties={"wing": "central", "length_m": 50},
    confidence=0.88,  # slightly higher — wins CRDT if B merged after A
    agent_id="robot-b",
)
exit_east_1 = SceneNode(
    label="exit_east_1",
    node_type="exit",
    properties={"side": "east", "door": "sliding"},
    confidence=0.88,
    agent_id="robot-b",
)
charging_station = SceneNode(
    label="charging_station",
    node_type="charging_station",
    properties={"bays": 4, "max_kw": 20},
    confidence=0.95,
    agent_id="robot-b",
)

for node in [corridor_d, corridor_e, corridor_c_b, exit_east_1, charging_station]:
    store_b.upsert_node(node)

# Edges: rooms 201-203 off corridor_d, rooms 204-205 off corridor_e
for room in rooms_b[:3]:
    store_b.upsert_edge(SceneEdge(corridor_d.id, room.id, "leads_to"))
    store_b.upsert_edge(SceneEdge(room.id, corridor_d.id, "leads_to"))

for room in rooms_b[3:]:
    store_b.upsert_edge(SceneEdge(corridor_e.id, room.id, "leads_to"))
    store_b.upsert_edge(SceneEdge(room.id, corridor_e.id, "leads_to"))

store_b.upsert_edge(SceneEdge(corridor_d.id, corridor_e.id, "connects_to"))
store_b.upsert_edge(SceneEdge(corridor_c_b.id, corridor_d.id, "connects_to"))
store_b.upsert_edge(SceneEdge(corridor_d.id, exit_east_1.id, "leads_to"))
store_b.upsert_edge(SceneEdge(corridor_e.id, charging_station.id, "leads_to"))

print(f"Robot B stored: {store_b.node_count()} nodes, {store_b.edge_count()} edges")

# ---------------------------------------------------------------------------
# Merge: A into merged, then B into merged
# ---------------------------------------------------------------------------
merger = SceneMerger()
result_a = merger.merge(merged_store, store_a)
result_b = merger.merge(merged_store, store_b)

total_conflicts = result_a.conflicts_resolved + result_b.conflicts_resolved
print(
    f"MERGE COMPLETE: {merged_store.node_count()} nodes, "
    f"{merged_store.edge_count()} edges merged "
    f"({total_conflicts} conflicts)."
)

# ---------------------------------------------------------------------------
# BFS: shortest path from room_101 → charging_station
# ---------------------------------------------------------------------------
# Build adjacency list from all edges in the merged store
adj: dict[str, list[str]] = collections.defaultdict(list)
for edge in merged_store.list_edges():
    adj[edge.source_id].append(edge.target_id)

# IDs for start and end nodes
start_id = rooms_a[0].id          # room_101
end_id = charging_station.id      # charging_station (from B, same object)

# BFS
visited = {start_id}
queue: collections.deque[list[str]] = collections.deque([[start_id]])
path_ids: list[str] = []

while queue:
    path = queue.popleft()
    current = path[-1]
    if current == end_id:
        path_ids = path
        break
    for neighbor in adj.get(current, []):
        if neighbor not in visited:
            visited.add(neighbor)
            queue.append(path + [neighbor])

# Resolve IDs → labels
def label_of(node_id: str) -> str:
    node = merged_store.get_node(node_id)
    return node.label if node else node_id

if path_ids:
    labels = [label_of(nid) for nid in path_ids]
    hops = len(labels) - 1
    path_str = " → ".join(labels)
    print(f"Shortest path room_101→charging_station: {hops} hops via {path_str}")
else:
    print("No path found from room_101 to charging_station.")

# ---------------------------------------------------------------------------
# Clean up
# ---------------------------------------------------------------------------
store_a.close()
store_b.close()
merged_store.close()
shutil.rmtree(tmp)
