"""Tests for polaroid.subgraph module."""

from __future__ import annotations

from polaroid.graph import SceneEdge, SceneNode
from polaroid.store import SceneStore
from polaroid.subgraph import extract_subgraph, filter_by_type, neighborhood


def _node(label: str, node_type: str) -> SceneNode:
    return SceneNode(label=label, node_type=node_type, properties={})


def _edge(src: str, tgt: str, relation: str = "links") -> SceneEdge:
    return SceneEdge(source_id=src, target_id=tgt, relation=relation)


def make_chain_store() -> SceneStore:
    """A -> B -> C -> D chain."""
    store = SceneStore(":memory:")
    na = _node("A", "room")
    nb = _node("B", "object")
    nc = _node("C", "surface")
    nd = _node("D", "region")
    store.upsert_node(na)
    store.upsert_node(nb)
    store.upsert_node(nc)
    store.upsert_node(nd)
    store.upsert_edge(_edge(na.id, nb.id, "contains"))
    store.upsert_edge(_edge(nb.id, nc.id, "has"))
    store.upsert_edge(_edge(nc.id, nd.id, "connects"))
    return store, na, nb, nc, nd


class TestExtractSubgraph:
    def test_includes_reachable_nodes(self) -> None:
        store, na, nb, nc, nd = make_chain_store()
        with extract_subgraph(store, na.id, max_depth=3) as sub:
            node_ids = {n.id for n in sub.list_nodes()}
        store.close()
        assert na.id in node_ids
        assert nb.id in node_ids
        assert nc.id in node_ids
        assert nd.id in node_ids

    def test_max_depth_zero_only_root(self) -> None:
        store, na, _nb, _nc, _nd = make_chain_store()
        with extract_subgraph(store, na.id, max_depth=0) as sub:
            node_ids = {n.id for n in sub.list_nodes()}
        store.close()
        assert node_ids == {na.id}

    def test_max_depth_one_includes_direct_neighbors(self) -> None:
        store, na, nb, nc, nd = make_chain_store()
        with extract_subgraph(store, na.id, max_depth=1) as sub:
            node_ids = {n.id for n in sub.list_nodes()}
        store.close()
        assert na.id in node_ids
        assert nb.id in node_ids
        assert nc.id not in node_ids
        assert nd.id not in node_ids

    def test_max_depth_two(self) -> None:
        store, na, nb, nc, nd = make_chain_store()
        with extract_subgraph(store, na.id, max_depth=2) as sub:
            node_ids = {n.id for n in sub.list_nodes()}
        store.close()
        assert na.id in node_ids
        assert nb.id in node_ids
        assert nc.id in node_ids
        assert nd.id not in node_ids

    def test_edges_are_copied(self) -> None:
        store, na, nb, _nc, _nd = make_chain_store()
        with extract_subgraph(store, na.id, max_depth=1) as sub:
            edges = sub.list_edges()
        store.close()
        # Only edge from A->B should be in depth-1 subgraph
        assert len(edges) == 1
        assert edges[0].source_id == na.id
        assert edges[0].target_id == nb.id

    def test_edges_both_endpoints_in_subgraph(self) -> None:
        store, na, _nb, _nc, _nd = make_chain_store()
        with extract_subgraph(store, na.id, max_depth=3) as sub:
            edges = sub.list_edges()
            node_ids = {n.id for n in sub.list_nodes()}
        store.close()
        for edge in edges:
            assert edge.source_id in node_ids
            assert edge.target_id in node_ids

    def test_unreachable_node_excluded(self) -> None:
        store, na, _nb, _nc, _nd = make_chain_store()
        # Add a disconnected node
        isolated = _node("isolated", "agent")
        store.upsert_node(isolated)
        with extract_subgraph(store, na.id, max_depth=3) as sub:
            node_ids = {n.id for n in sub.list_nodes()}
        store.close()
        assert isolated.id not in node_ids

    def test_returns_scene_store(self) -> None:
        store, na, _nb, _nc, _nd = make_chain_store()
        sub = extract_subgraph(store, na.id)
        assert isinstance(sub, SceneStore)
        sub.close()
        store.close()

    def test_empty_store_root_missing(self) -> None:
        store = SceneStore(":memory:")
        with extract_subgraph(store, "nonexistent") as sub:
            assert sub.node_count() == 0
        store.close()


class TestFilterByType:
    def test_only_specified_types(self) -> None:
        store, _na, _nb, _nc, _nd = make_chain_store()
        with filter_by_type(store, ["room", "object"]) as sub:
            nodes = sub.list_nodes()
            types = {n.node_type for n in nodes}
        store.close()
        assert types == {"room", "object"}

    def test_excludes_other_types(self) -> None:
        store, _na, _nb, _nc, _nd = make_chain_store()
        with filter_by_type(store, ["room"]) as sub:
            nodes = sub.list_nodes()
        store.close()
        assert all(n.node_type == "room" for n in nodes)

    def test_edges_between_filtered_nodes(self) -> None:
        store, _na, _nb, _nc, _nd = make_chain_store()
        # A(room) -> B(object): both kept; B->C edge not kept (C is surface)
        with filter_by_type(store, ["room", "object"]) as sub:
            edges = sub.list_edges()
            node_ids = {n.id for n in sub.list_nodes()}
        store.close()
        for edge in edges:
            assert edge.source_id in node_ids
            assert edge.target_id in node_ids

    def test_no_cross_type_edges(self) -> None:
        store, _na, _nb, _nc, _nd = make_chain_store()
        # Only room type: A alone, no edges
        with filter_by_type(store, ["room"]) as sub:
            edges = sub.list_edges()
        store.close()
        assert edges == []

    def test_empty_types_list(self) -> None:
        store, _na, _nb, _nc, _nd = make_chain_store()
        with filter_by_type(store, []) as sub:
            assert sub.node_count() == 0
            assert sub.edge_count() == 0
        store.close()

    def test_empty_store(self) -> None:
        store = SceneStore(":memory:")
        with filter_by_type(store, ["room"]) as sub:
            assert sub.node_count() == 0
        store.close()

    def test_returns_scene_store(self) -> None:
        store, _na, _nb, _nc, _nd = make_chain_store()
        sub = filter_by_type(store, ["room"])
        assert isinstance(sub, SceneStore)
        sub.close()
        store.close()


class TestNeighborhood:
    def test_direct_neighbors(self) -> None:
        store, na, nb, _nc, _nd = make_chain_store()
        result = neighborhood(store, na.id, radius=1)
        store.close()
        assert nb.id in result
        assert na.id not in result  # root excluded

    def test_radius_one_not_two_hops(self) -> None:
        store, na, _nb, nc, _nd = make_chain_store()
        result = neighborhood(store, na.id, radius=1)
        store.close()
        assert nc.id not in result

    def test_radius_two(self) -> None:
        store, na, nb, nc, nd = make_chain_store()
        result = neighborhood(store, na.id, radius=2)
        store.close()
        assert nb.id in result
        assert nc.id in result
        assert nd.id not in result

    def test_radius_three(self) -> None:
        store, na, _nb, _nc, nd = make_chain_store()
        result = neighborhood(store, na.id, radius=3)
        store.close()
        assert nd.id in result

    def test_excludes_root_itself(self) -> None:
        store, na, _nb, _nc, _nd = make_chain_store()
        result = neighborhood(store, na.id, radius=5)
        store.close()
        assert na.id not in result

    def test_no_neighbors_isolated_node(self) -> None:
        store = SceneStore(":memory:")
        n = _node("solo", "agent")
        store.upsert_node(n)
        result = neighborhood(store, n.id, radius=2)
        store.close()
        assert result == []

    def test_empty_store(self) -> None:
        store = SceneStore(":memory:")
        result = neighborhood(store, "nonexistent", radius=1)
        store.close()
        assert result == []

    def test_returns_list(self) -> None:
        store, na, _nb, _nc, _nd = make_chain_store()
        result = neighborhood(store, na.id)
        store.close()
        assert isinstance(result, list)
