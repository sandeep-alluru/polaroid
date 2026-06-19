"""Tests for polaroid.stats module."""
from __future__ import annotations

import pytest

from polaroid.graph import SceneEdge, SceneNode
from polaroid.stats import GraphStats, cluster_by_type, compute_stats, most_connected
from polaroid.store import SceneStore


def _node(label: str, node_type: str, confidence: float = 1.0) -> SceneNode:
    return SceneNode(label=label, node_type=node_type, properties={}, confidence=confidence)


def _edge(src: str, tgt: str, relation: str = "links", confidence: float = 1.0) -> SceneEdge:
    return SceneEdge(source_id=src, target_id=tgt, relation=relation, confidence=confidence)


def make_simple_store() -> SceneStore:
    """3-node, 2-edge chain: A(room) --contains--> B(object) --has--> C(surface)."""
    store = SceneStore(":memory:")
    na = _node("A", "room")
    nb = _node("B", "object")
    nc = _node("C", "surface")
    store.upsert_node(na)
    store.upsert_node(nb)
    store.upsert_node(nc)
    store.upsert_edge(_edge(na.id, nb.id, "contains"))
    store.upsert_edge(_edge(nb.id, nc.id, "has"))
    return store, na, nb, nc


class TestComputeStats:
    def test_empty_store(self) -> None:
        store = SceneStore(":memory:")
        s = compute_stats(store)
        store.close()
        assert s.node_count == 0
        assert s.edge_count == 0
        assert s.node_types == {}
        assert s.edge_relations == {}
        assert s.avg_degree == 0.0
        assert s.max_degree == 0
        assert s.connected_components == 0
        assert s.diameter is None

    def test_single_node(self) -> None:
        store = SceneStore(":memory:")
        n = _node("solo", "room")
        store.upsert_node(n)
        s = compute_stats(store)
        store.close()
        assert s.node_count == 1
        assert s.edge_count == 0
        assert s.connected_components == 1
        assert s.diameter == 0

    def test_node_count(self) -> None:
        store, na, nb, nc = make_simple_store()
        s = compute_stats(store)
        store.close()
        assert s.node_count == 3

    def test_edge_count(self) -> None:
        store, na, nb, nc = make_simple_store()
        s = compute_stats(store)
        store.close()
        assert s.edge_count == 2

    def test_node_types(self) -> None:
        store, na, nb, nc = make_simple_store()
        s = compute_stats(store)
        store.close()
        assert s.node_types == {"room": 1, "object": 1, "surface": 1}

    def test_edge_relations(self) -> None:
        store, na, nb, nc = make_simple_store()
        s = compute_stats(store)
        store.close()
        assert s.edge_relations == {"contains": 1, "has": 1}

    def test_avg_degree_chain(self) -> None:
        # Chain A->B->C: A has degree 1, B has degree 2 (A->B and B->C), C has degree 1
        # total = 4, avg = 4/3
        store, na, nb, nc = make_simple_store()
        s = compute_stats(store)
        store.close()
        assert abs(s.avg_degree - 4 / 3) < 1e-9

    def test_max_degree(self) -> None:
        store, na, nb, nc = make_simple_store()
        s = compute_stats(store)
        store.close()
        assert s.max_degree == 2  # B is endpoint of both edges

    def test_connected_components_connected(self) -> None:
        store, na, nb, nc = make_simple_store()
        s = compute_stats(store)
        store.close()
        assert s.connected_components == 1

    def test_connected_components_disconnected(self) -> None:
        store = SceneStore(":memory:")
        n1 = _node("X", "room")
        n2 = _node("Y", "object")
        store.upsert_node(n1)
        store.upsert_node(n2)
        s = compute_stats(store)
        store.close()
        assert s.connected_components == 2

    def test_diameter_chain_of_three(self) -> None:
        store, na, nb, nc = make_simple_store()
        s = compute_stats(store)
        store.close()
        assert s.diameter == 2

    def test_diameter_disconnected_is_none(self) -> None:
        store = SceneStore(":memory:")
        n1 = _node("X", "room")
        n2 = _node("Y", "object")
        store.upsert_node(n1)
        store.upsert_node(n2)
        s = compute_stats(store)
        store.close()
        assert s.diameter is None

    def test_returns_graph_stats(self) -> None:
        store = SceneStore(":memory:")
        s = compute_stats(store)
        store.close()
        assert isinstance(s, GraphStats)

    def test_multiple_same_type(self) -> None:
        store = SceneStore(":memory:")
        store.upsert_node(_node("r1", "room"))
        store.upsert_node(_node("r2", "room"))
        store.upsert_node(_node("o1", "object"))
        s = compute_stats(store)
        store.close()
        assert s.node_types["room"] == 2
        assert s.node_types["object"] == 1

    def test_multiple_same_relation(self) -> None:
        store = SceneStore(":memory:")
        na = _node("A", "room")
        nb = _node("B", "object")
        nc = _node("C", "object")
        store.upsert_node(na)
        store.upsert_node(nb)
        store.upsert_node(nc)
        store.upsert_edge(_edge(na.id, nb.id, "contains"))
        store.upsert_edge(_edge(na.id, nc.id, "contains"))
        s = compute_stats(store)
        store.close()
        assert s.edge_relations["contains"] == 2

    def test_diameter_single_edge(self) -> None:
        store = SceneStore(":memory:")
        na = _node("A", "room")
        nb = _node("B", "object")
        store.upsert_node(na)
        store.upsert_node(nb)
        store.upsert_edge(_edge(na.id, nb.id, "links"))
        s = compute_stats(store)
        store.close()
        assert s.diameter == 1


class TestClusterByType:
    def test_groups_by_type(self) -> None:
        store, na, nb, nc = make_simple_store()
        result = cluster_by_type(store)
        store.close()
        assert "room" in result
        assert "object" in result
        assert "surface" in result
        assert na.id in result["room"]
        assert nb.id in result["object"]
        assert nc.id in result["surface"]

    def test_empty_store(self) -> None:
        store = SceneStore(":memory:")
        result = cluster_by_type(store)
        store.close()
        assert result == {}

    def test_multiple_nodes_same_type(self) -> None:
        store = SceneStore(":memory:")
        n1 = _node("r1", "room")
        n2 = _node("r2", "room")
        store.upsert_node(n1)
        store.upsert_node(n2)
        result = cluster_by_type(store)
        store.close()
        assert len(result["room"]) == 2
        assert n1.id in result["room"]
        assert n2.id in result["room"]

    def test_returns_dict(self) -> None:
        store = SceneStore(":memory:")
        result = cluster_by_type(store)
        store.close()
        assert isinstance(result, dict)


class TestMostConnected:
    def test_sorted_by_degree_desc(self) -> None:
        store, na, nb, nc = make_simple_store()
        result = most_connected(store)
        store.close()
        degrees = [deg for _, deg in result]
        assert degrees == sorted(degrees, reverse=True)

    def test_most_connected_node(self) -> None:
        # B is endpoint of both edges: degree=2, A and C have degree=1
        store, na, nb, nc = make_simple_store()
        result = most_connected(store, n=1)
        store.close()
        assert result[0][0] == nb.id
        assert result[0][1] == 2

    def test_top_n_limit(self) -> None:
        store, na, nb, nc = make_simple_store()
        result = most_connected(store, n=2)
        store.close()
        assert len(result) == 2

    def test_n_larger_than_nodes(self) -> None:
        store, na, nb, nc = make_simple_store()
        result = most_connected(store, n=100)
        store.close()
        assert len(result) == 3

    def test_empty_store(self) -> None:
        store = SceneStore(":memory:")
        result = most_connected(store)
        store.close()
        assert result == []

    def test_returns_list_of_tuples(self) -> None:
        store, na, nb, nc = make_simple_store()
        result = most_connected(store)
        store.close()
        assert isinstance(result, list)
        for item in result:
            assert isinstance(item, tuple)
            assert len(item) == 2

    def test_isolated_nodes_have_zero_degree(self) -> None:
        store = SceneStore(":memory:")
        n = _node("alone", "agent")
        store.upsert_node(n)
        result = most_connected(store)
        store.close()
        assert result[0][1] == 0
