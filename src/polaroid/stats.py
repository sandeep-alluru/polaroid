"""Graph statistics and clustering for scene stores."""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from polaroid.store import SceneStore


@dataclass
class GraphStats:
    """Statistics about a scene graph."""

    node_count: int
    edge_count: int
    node_types: dict[str, int]  # type → count
    edge_relations: dict[str, int]  # relation → count
    avg_degree: float
    max_degree: int
    connected_components: int
    diameter: int | None  # longest shortest path (None if disconnected)


def compute_stats(store: SceneStore) -> GraphStats:
    """Compute comprehensive statistics for the given scene store."""
    nodes = store.list_nodes()
    edges = store.list_edges()

    node_count = store.node_count()
    edge_count = store.edge_count()

    # node_types count
    node_types: dict[str, int] = {}
    for node in nodes:
        node_types[node.node_type] = node_types.get(node.node_type, 0) + 1

    # edge_relations count
    edge_relations: dict[str, int] = {}
    for edge in edges:
        edge_relations[edge.relation] = edge_relations.get(edge.relation, 0) + 1

    # degree computation (undirected: each edge adds 1 to both endpoints)
    degree: dict[str, int] = {n.id: 0 for n in nodes}
    for edge in edges:
        if edge.source_id in degree:
            degree[edge.source_id] += 1
        if edge.target_id in degree:
            degree[edge.target_id] += 1

    total_degree = sum(degree.values())
    avg_degree = total_degree / node_count if node_count > 0 else 0.0
    max_degree = max(degree.values(), default=0)

    # Build adjacency list (undirected) for BFS
    adj: dict[str, set[str]] = {n.id: set() for n in nodes}
    for edge in edges:
        if edge.source_id in adj and edge.target_id in adj:
            adj[edge.source_id].add(edge.target_id)
            adj[edge.target_id].add(edge.source_id)

    # Connected components via BFS
    all_ids = set(n.id for n in nodes)
    visited: set[str] = set()
    components: list[set[str]] = []

    for nid in all_ids:
        if nid not in visited:
            component: set[str] = set()
            q: deque[str] = deque([nid])
            while q:
                curr = q.popleft()
                if curr in visited:
                    continue
                visited.add(curr)
                component.add(curr)
                for neighbor in adj.get(curr, set()):
                    if neighbor not in visited:
                        q.append(neighbor)
            components.append(component)

    connected_components = len(components)

    # Diameter: BFS from each node to find max shortest path
    if node_count == 0:
        diameter: int | None = None
    elif connected_components > 1:
        diameter = None
    elif node_count == 1:
        diameter = 0
    else:
        max_dist = 0
        for start in all_ids:
            dist: dict[str, int] = {start: 0}
            bfsq: deque[str] = deque([start])
            while bfsq:
                curr = bfsq.popleft()
                for neighbor in adj.get(curr, set()):
                    if neighbor not in dist:
                        dist[neighbor] = dist[curr] + 1
                        bfsq.append(neighbor)
            if dist:
                max_dist = max(max_dist, max(dist.values()))
        diameter = max_dist

    return GraphStats(
        node_count=node_count,
        edge_count=edge_count,
        node_types=node_types,
        edge_relations=edge_relations,
        avg_degree=avg_degree,
        max_degree=max_degree,
        connected_components=connected_components,
        diameter=diameter,
    )


def cluster_by_type(store: SceneStore) -> dict[str, list[str]]:
    """Return {node_type: [node_ids]} grouping."""
    result: dict[str, list[str]] = {}
    for node in store.list_nodes():
        result.setdefault(node.node_type, []).append(node.id)
    return result


def most_connected(store: SceneStore, n: int = 10) -> list[tuple[str, int]]:
    """Return top-n nodes by degree (node_id, degree)."""
    nodes = store.list_nodes()
    degree: dict[str, int] = {node.id: 0 for node in nodes}

    for edge in store.list_edges():
        if edge.source_id in degree:
            degree[edge.source_id] += 1
        if edge.target_id in degree:
            degree[edge.target_id] += 1

    sorted_nodes = sorted(degree.items(), key=lambda x: x[1], reverse=True)
    return sorted_nodes[:n]
