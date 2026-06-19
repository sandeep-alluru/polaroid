"""Subgraph extraction and neighborhood queries."""
from __future__ import annotations

from collections import deque

from polaroid.store import SceneStore


def extract_subgraph(store: SceneStore, root_id: str, max_depth: int = 3) -> SceneStore:
    """Extract the subgraph reachable from root_id within max_depth hops.

    Returns a new in-memory SceneStore.
    """
    # Fetch all edges once upfront to avoid O(N×E) repeated queries inside the BFS loop.
    all_edges = store.list_edges()
    adjacency: dict[str, list] = {}
    for edge in all_edges:
        adjacency.setdefault(edge.source_id, []).append(edge)

    visited: set[str] = set()
    queue: deque[tuple[str, int]] = deque([(root_id, 0)])

    while queue:
        node_id, depth = queue.popleft()
        if node_id in visited:
            continue
        visited.add(node_id)
        if depth < max_depth:
            for edge in adjacency.get(node_id, []):
                if edge.target_id not in visited:
                    queue.append((edge.target_id, depth + 1))

    sub = SceneStore(":memory:")
    for node_id in visited:
        node = store.get_node(node_id)
        if node is not None:
            sub.upsert_node(node)

    for edge in all_edges:
        if edge.source_id in visited and edge.target_id in visited:
            sub.upsert_edge(edge)

    return sub


def filter_by_type(store: SceneStore, node_types: list[str]) -> SceneStore:
    """Return a new SceneStore with only nodes of the given types (and edges between them)."""
    type_set = set(node_types)
    nodes = [n for n in store.list_nodes() if n.node_type in type_set]
    node_ids = {n.id for n in nodes}

    sub = SceneStore(":memory:")
    for node in nodes:
        sub.upsert_node(node)

    for edge in store.list_edges():
        if edge.source_id in node_ids and edge.target_id in node_ids:
            sub.upsert_edge(edge)

    return sub


def neighborhood(store: SceneStore, node_id: str, radius: int = 1) -> list[str]:
    """Return all node IDs within `radius` hops of node_id."""
    # Fetch all edges once upfront to avoid O(radius×E) repeated queries.
    all_edges = store.list_edges()
    adjacency: dict[str, list[str]] = {}
    for edge in all_edges:
        adjacency.setdefault(edge.source_id, []).append(edge.target_id)

    visited: set[str] = {node_id}
    frontier: set[str] = {node_id}

    for _ in range(radius):
        next_frontier: set[str] = set()
        for nid in frontier:
            for neighbor in adjacency.get(nid, []):
                if neighbor not in visited:
                    next_frontier.add(neighbor)
        visited.update(next_frontier)
        frontier = next_frontier
        if not frontier:
            break

    visited.discard(node_id)
    return list(visited)
