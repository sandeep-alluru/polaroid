"""Export scene graph to DOT, JSON, and adjacency matrix formats."""

from __future__ import annotations

import json

from polaroid.store import SceneStore

_TYPE_COLORS: dict[str, str] = {
    "object": "lightblue",
    "room": "lightyellow",
    "surface": "lightgreen",
    "region": "lightsalmon",
    "agent": "lightpink",
}


def to_dot(store: SceneStore, graph_name: str = "scene_graph") -> str:
    """Export scene graph as Graphviz DOT format. Nodes colored by node_type."""
    lines: list[str] = [
        f"digraph {graph_name} {{",
        "  rankdir=LR;",
        "  node [shape=box, style=filled];",
    ]

    for node in store.list_nodes():
        color = _TYPE_COLORS.get(node.node_type, "white")
        label = f"{node.label}\\n({node.node_type})"
        lines.append(f'  "{node.id}" [label="{label}", fillcolor={color}];')

    for edge in store.list_edges():
        lines.append(f'  "{edge.source_id}" -> "{edge.target_id}" [label="{edge.relation}"];')

    lines.append("}")
    return "\n".join(lines)


def to_json(store: SceneStore) -> str:
    """Export full scene graph as JSON with nodes and edges arrays."""
    nodes = store.list_nodes()
    edges = store.list_edges()
    data = {
        "nodes": [n.to_dict() for n in nodes],
        "edges": [e.to_dict() for e in edges],
        "node_count": len(nodes),
        "edge_count": len(edges),
    }
    return json.dumps(data, indent=2)


def to_adjacency_matrix(store: SceneStore) -> tuple[list[str], list[list[float]]]:
    """Return (node_ids, matrix) adjacency matrix for ML/analysis use."""
    nodes = store.list_nodes()
    node_ids = sorted(n.id for n in nodes)
    idx = {nid: i for i, nid in enumerate(node_ids)}
    size = len(node_ids)
    matrix: list[list[float]] = [[0.0] * size for _ in range(size)]

    for edge in store.list_edges():
        i = idx.get(edge.source_id)
        j = idx.get(edge.target_id)
        if i is not None and j is not None:
            matrix[i][j] = edge.confidence

    return node_ids, matrix
