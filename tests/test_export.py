"""Tests for polaroid.export module."""
from __future__ import annotations

import json

import pytest

from polaroid.export import to_adjacency_matrix, to_dot, to_json
from polaroid.graph import SceneEdge, SceneNode
from polaroid.store import SceneStore


def _node(label: str, node_type: str, confidence: float = 1.0) -> SceneNode:
    return SceneNode(label=label, node_type=node_type, properties={}, confidence=confidence)


def _edge(source_id: str, target_id: str, relation: str, confidence: float = 1.0) -> SceneEdge:
    return SceneEdge(source_id=source_id, target_id=target_id, relation=relation, confidence=confidence)


def make_store() -> SceneStore:
    store = SceneStore(":memory:")
    n1 = _node("kitchen", "room")
    n2 = _node("table", "surface")
    n3 = _node("cup", "object")
    store.upsert_node(n1)
    store.upsert_node(n2)
    store.upsert_node(n3)
    store.upsert_edge(_edge(n1.id, n2.id, "contains"))
    store.upsert_edge(_edge(n2.id, n3.id, "has"))
    return store


class TestToDot:
    def test_returns_string(self) -> None:
        with make_store() as store:
            result = to_dot(store)
        assert isinstance(result, str)

    def test_contains_digraph(self) -> None:
        with make_store() as store:
            result = to_dot(store)
        assert "digraph" in result

    def test_custom_graph_name(self) -> None:
        with make_store() as store:
            result = to_dot(store, graph_name="my_graph")
        assert "digraph my_graph" in result

    def test_contains_node_labels(self) -> None:
        with make_store() as store:
            result = to_dot(store)
        assert "kitchen" in result
        assert "table" in result
        assert "cup" in result

    def test_contains_node_types_in_labels(self) -> None:
        with make_store() as store:
            result = to_dot(store)
        assert "(room)" in result
        assert "(surface)" in result
        assert "(object)" in result

    def test_contains_edge_relations(self) -> None:
        with make_store() as store:
            result = to_dot(store)
        assert "contains" in result
        assert "has" in result

    def test_node_colors_by_type(self) -> None:
        with make_store() as store:
            result = to_dot(store)
        assert "lightyellow" in result   # room
        assert "lightgreen" in result    # surface
        assert "lightblue" in result     # object

    def test_default_color_for_unknown_type(self) -> None:
        store = SceneStore(":memory:")
        store.upsert_node(_node("drone", "aircraft"))
        result = to_dot(store)
        assert "white" in result
        store.close()

    def test_agent_type_color(self) -> None:
        store = SceneStore(":memory:")
        store.upsert_node(_node("bot-1", "agent"))
        result = to_dot(store)
        assert "lightpink" in result
        store.close()

    def test_region_color(self) -> None:
        store = SceneStore(":memory:")
        store.upsert_node(_node("hall", "region"))
        result = to_dot(store)
        assert "lightsalmon" in result
        store.close()

    def test_rankdir_lr(self) -> None:
        with make_store() as store:
            result = to_dot(store)
        assert "rankdir=LR" in result

    def test_empty_store(self) -> None:
        store = SceneStore(":memory:")
        result = to_dot(store)
        assert "digraph scene_graph" in result
        assert "}" in result
        store.close()

    def test_edge_arrow_format(self) -> None:
        with make_store() as store:
            result = to_dot(store)
        assert "->" in result


class TestToJson:
    def test_returns_valid_json(self) -> None:
        with make_store() as store:
            result = to_json(store)
        data = json.loads(result)
        assert isinstance(data, dict)

    def test_has_nodes_key(self) -> None:
        with make_store() as store:
            result = to_json(store)
        data = json.loads(result)
        assert "nodes" in data
        assert isinstance(data["nodes"], list)

    def test_has_edges_key(self) -> None:
        with make_store() as store:
            result = to_json(store)
        data = json.loads(result)
        assert "edges" in data
        assert isinstance(data["edges"], list)

    def test_node_count(self) -> None:
        with make_store() as store:
            result = to_json(store)
        data = json.loads(result)
        assert data["node_count"] == 3

    def test_edge_count(self) -> None:
        with make_store() as store:
            result = to_json(store)
        data = json.loads(result)
        assert data["edge_count"] == 2

    def test_node_fields(self) -> None:
        with make_store() as store:
            result = to_json(store)
        data = json.loads(result)
        node = data["nodes"][0]
        assert "id" in node
        assert "label" in node
        assert "node_type" in node

    def test_edge_fields(self) -> None:
        with make_store() as store:
            result = to_json(store)
        data = json.loads(result)
        edge = data["edges"][0]
        assert "source_id" in edge
        assert "target_id" in edge
        assert "relation" in edge

    def test_empty_store(self) -> None:
        store = SceneStore(":memory:")
        result = to_json(store)
        data = json.loads(result)
        assert data["nodes"] == []
        assert data["edges"] == []
        assert data["node_count"] == 0
        assert data["edge_count"] == 0
        store.close()


class TestToAdjacencyMatrix:
    def test_returns_tuple(self) -> None:
        with make_store() as store:
            result = to_adjacency_matrix(store)
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_node_ids_sorted(self) -> None:
        with make_store() as store:
            node_ids, _ = to_adjacency_matrix(store)
        assert node_ids == sorted(node_ids)

    def test_matrix_shape(self) -> None:
        with make_store() as store:
            node_ids, matrix = to_adjacency_matrix(store)
        n = len(node_ids)
        assert len(matrix) == n
        for row in matrix:
            assert len(row) == n

    def test_matrix_values_for_edges(self) -> None:
        store = SceneStore(":memory:")
        n1 = _node("A", "room")
        n2 = _node("B", "object")
        store.upsert_node(n1)
        store.upsert_node(n2)
        e = _edge(n1.id, n2.id, "contains", confidence=0.9)
        store.upsert_edge(e)

        node_ids, matrix = to_adjacency_matrix(store)
        i = node_ids.index(n1.id)
        j = node_ids.index(n2.id)
        assert abs(matrix[i][j] - 0.9) < 1e-9
        assert matrix[j][i] == 0.0
        store.close()

    def test_no_self_loops(self) -> None:
        with make_store() as store:
            node_ids, matrix = to_adjacency_matrix(store)
        for k in range(len(node_ids)):
            assert matrix[k][k] == 0.0

    def test_empty_store(self) -> None:
        store = SceneStore(":memory:")
        node_ids, matrix = to_adjacency_matrix(store)
        assert node_ids == []
        assert matrix == []
        store.close()
