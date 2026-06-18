"""Tests for SceneStore SQLite persistence."""

from __future__ import annotations

from polaroid.graph import SceneEdge, SceneNode
from polaroid.store import SceneStore

# ── File creation ─────────────────────────────────────────────────────────────


def test_store_creates_file(tmp_path):
    db = tmp_path / "scene.db"
    s = SceneStore(str(db))
    s.close()
    assert db.exists()


def test_store_creates_parent_dirs(tmp_path):
    db = tmp_path / "subdir" / "nested" / "scene.db"
    s = SceneStore(str(db))
    s.close()
    assert db.exists()


# ── upsert_node / get_node ────────────────────────────────────────────────────


def test_upsert_node_and_get(store):
    n = SceneNode(label="table-A", node_type="object", properties={"color": "brown"})
    store.upsert_node(n)
    retrieved = store.get_node(n.id)
    assert retrieved is not None
    assert retrieved.id == n.id
    assert retrieved.label == n.label
    assert retrieved.properties["color"] == "brown"


def test_get_node_missing_returns_none(store):
    assert store.get_node("nonexistent-id") is None


def test_upsert_node_idempotent(store):
    n = SceneNode(label="table-A", node_type="object", properties={})
    store.upsert_node(n)
    store.upsert_node(n)
    assert store.node_count() == 1


def test_upsert_node_higher_confidence_updates(store):
    n_low = SceneNode(
        label="door-1", node_type="object", properties={"state": "closed"}, confidence=0.5
    )
    store.upsert_node(n_low)
    n_high = SceneNode(
        label="door-1", node_type="object", properties={"state": "open"}, confidence=0.9
    )
    store.upsert_node(n_high)
    retrieved = store.get_node(n_low.id)  # same id since label+type same
    assert retrieved is not None
    assert retrieved.confidence == 0.9
    assert retrieved.properties["state"] == "open"


def test_upsert_node_lower_confidence_does_not_update(store):
    n_high = SceneNode(
        label="door-1", node_type="object", properties={"state": "open"}, confidence=0.9
    )
    store.upsert_node(n_high)
    n_low = SceneNode(
        label="door-1", node_type="object", properties={"state": "closed"}, confidence=0.3
    )
    store.upsert_node(n_low)
    retrieved = store.get_node(n_high.id)
    assert retrieved is not None
    assert retrieved.confidence == 0.9
    assert retrieved.properties["state"] == "open"


# ── list_nodes ─────────────────────────────────────────────────────────────────


def test_list_nodes_empty(store):
    assert store.list_nodes() == []


def test_list_nodes_all(store):
    store.upsert_node(SceneNode(label="x", node_type="object", properties={}))
    store.upsert_node(SceneNode(label="y", node_type="room", properties={}))
    assert store.node_count() == 2


def test_list_nodes_filter_by_type(store):
    store.upsert_node(SceneNode(label="door-1", node_type="object", properties={}))
    store.upsert_node(SceneNode(label="room-a", node_type="room", properties={}))
    objects = store.list_nodes(node_type="object")
    assert len(objects) == 1
    assert objects[0].label == "door-1"


def test_list_nodes_filter_by_confidence(store):
    store.upsert_node(SceneNode(label="a", node_type="object", properties={}, confidence=0.9))
    store.upsert_node(SceneNode(label="b", node_type="object", properties={}, confidence=0.3))
    high = store.list_nodes(min_confidence=0.8)
    assert len(high) == 1
    assert high[0].label == "a"


# ── upsert_edge / get_edge ────────────────────────────────────────────────────


def test_upsert_edge_and_get(store):
    e = SceneEdge(source_id="aaa", target_id="bbb", relation="contains")
    store.upsert_edge(e)
    retrieved = store.get_edge(e.id)
    assert retrieved is not None
    assert retrieved.id == e.id
    assert retrieved.relation == "contains"


def test_get_edge_missing_returns_none(store):
    assert store.get_edge("nonexistent") is None


def test_upsert_edge_idempotent(store):
    e = SceneEdge(source_id="aaa", target_id="bbb", relation="contains")
    store.upsert_edge(e)
    store.upsert_edge(e)
    assert store.edge_count() == 1


def test_upsert_edge_higher_confidence_updates(store):
    e_low = SceneEdge(source_id="aaa", target_id="bbb", relation="contains", confidence=0.4)
    store.upsert_edge(e_low)
    e_high = SceneEdge(source_id="aaa", target_id="bbb", relation="contains", confidence=0.8)
    store.upsert_edge(e_high)
    retrieved = store.get_edge(e_low.id)
    assert retrieved is not None
    assert retrieved.confidence == 0.8


# ── list_edges ─────────────────────────────────────────────────────────────────


def test_list_edges_filter_by_source(store):
    e1 = SceneEdge(source_id="aaa", target_id="bbb", relation="contains")
    e2 = SceneEdge(source_id="ccc", target_id="bbb", relation="contains")
    store.upsert_edge(e1)
    store.upsert_edge(e2)
    edges = store.list_edges(source_id="aaa")
    assert len(edges) == 1
    assert edges[0].source_id == "aaa"


def test_list_edges_filter_by_relation(store):
    e1 = SceneEdge(source_id="aaa", target_id="bbb", relation="contains")
    e2 = SceneEdge(source_id="aaa", target_id="ccc", relation="adjacent-to")
    store.upsert_edge(e1)
    store.upsert_edge(e2)
    edges = store.list_edges(relation="adjacent-to")
    assert len(edges) == 1
    assert edges[0].relation == "adjacent-to"


# ── counts ────────────────────────────────────────────────────────────────────


def test_node_count(store):
    assert store.node_count() == 0
    store.upsert_node(SceneNode(label="a", node_type="object", properties={}))
    assert store.node_count() == 1


def test_edge_count(store):
    assert store.edge_count() == 0
    store.upsert_edge(SceneEdge(source_id="a", target_id="b", relation="contains"))
    assert store.edge_count() == 1


# ── context manager ───────────────────────────────────────────────────────────


def test_store_context_manager(tmp_path):
    with SceneStore(str(tmp_path / "scene.db")) as s:
        n = SceneNode(label="x", node_type="object", properties={})
        s.upsert_node(n)
        assert s.node_count() == 1
