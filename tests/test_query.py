"""Tests for SceneQuery."""

from __future__ import annotations

import pytest

from scenemem.graph import SceneEdge, SceneNode
from scenemem.query import SceneQuery
from scenemem.store import SceneStore


@pytest.fixture
def populated_store(tmp_path):
    """A store with a small scene: 2 rooms, 3 objects, 2 edges."""
    s = SceneStore(str(tmp_path / "scene.db"))
    kitchen = SceneNode(label="room-kitchen", node_type="room", properties={})
    lounge = SceneNode(label="room-lounge", node_type="room", properties={})
    table = SceneNode(
        label="table-A", node_type="object", properties={}, confidence=0.9, agent_id="robot-a"
    )
    door = SceneNode(label="door-1", node_type="object", properties={}, confidence=0.7)
    chair = SceneNode(label="chair-1", node_type="object", properties={}, confidence=0.5)
    for node in [kitchen, lounge, table, door, chair]:
        s.upsert_node(node)
    e1 = SceneEdge(source_id=kitchen.id, target_id=table.id, relation="contains")
    e2 = SceneEdge(source_id=kitchen.id, target_id=door.id, relation="contains")
    s.upsert_edge(e1)
    s.upsert_edge(e2)
    yield s, kitchen, lounge, table, door, chair
    s.close()


# ── find_nodes ────────────────────────────────────────────────────────────────


def test_find_nodes_all(populated_store):
    s, *_ = populated_store
    q = SceneQuery(s)
    nodes = q.find_nodes()
    assert len(nodes) == 5


def test_find_nodes_by_type(populated_store):
    s, _kitchen, _lounge, _table, _door, _chair = populated_store
    q = SceneQuery(s)
    rooms = q.find_nodes(node_type="room")
    assert len(rooms) == 2
    labels = {n.label for n in rooms}
    assert "room-kitchen" in labels
    assert "room-lounge" in labels


def test_find_nodes_by_label_contains(populated_store):
    s, *_ = populated_store
    q = SceneQuery(s)
    doors = q.find_nodes(label_contains="door")
    assert len(doors) == 1
    assert doors[0].label == "door-1"


def test_find_nodes_label_case_insensitive(populated_store):
    s, *_ = populated_store
    q = SceneQuery(s)
    results = q.find_nodes(label_contains="DOOR")
    assert len(results) == 1


def test_find_nodes_by_min_confidence(populated_store):
    s, *_ = populated_store
    q = SceneQuery(s)
    # min_confidence=0.8: table-A (0.9) + room-kitchen (1.0) + room-lounge (1.0) qualify
    high = q.find_nodes(min_confidence=0.8)
    assert all(n.confidence >= 0.8 for n in high)
    assert len(high) >= 1


def test_find_nodes_combined_filters(populated_store):
    s, *_ = populated_store
    q = SceneQuery(s)
    results = q.find_nodes(node_type="object", min_confidence=0.6)
    # table-A (0.9) and door-1 (0.7) qualify; chair-1 (0.5) does not
    assert len(results) == 2


def test_find_nodes_empty_when_no_match(populated_store):
    s, *_ = populated_store
    q = SceneQuery(s)
    results = q.find_nodes(node_type="surface")
    assert results == []


# ── find_neighbors ────────────────────────────────────────────────────────────


def test_find_neighbors_contains(populated_store):
    s, kitchen, _lounge, table, door, _chair = populated_store
    q = SceneQuery(s)
    neighbors = q.find_neighbors(kitchen.id)
    neighbor_ids = {n.id for n in neighbors}
    assert table.id in neighbor_ids
    assert door.id in neighbor_ids


def test_find_neighbors_filter_by_relation(populated_store):
    s, kitchen, _lounge, _table, _door, _chair = populated_store
    q = SceneQuery(s)
    neighbors = q.find_neighbors(kitchen.id, relation="contains")
    assert len(neighbors) == 2


def test_find_neighbors_no_edges_returns_empty(populated_store):
    s, _kitchen, lounge, _table, _door, _chair = populated_store
    q = SceneQuery(s)
    # lounge has no outgoing edges
    neighbors = q.find_neighbors(lounge.id)
    assert neighbors == []


def test_find_neighbors_nonexistent_node(populated_store):
    s, *_ = populated_store
    q = SceneQuery(s)
    neighbors = q.find_neighbors("nonexistent")
    assert neighbors == []


# ── context_summary ───────────────────────────────────────────────────────────


def test_context_summary_nonempty(populated_store):
    s, *_ = populated_store
    q = SceneQuery(s)
    summary = q.context_summary()
    assert len(summary) > 0
    assert "room" in summary.lower() or "object" in summary.lower()


def test_context_summary_contains_counts(populated_store):
    s, *_ = populated_store
    q = SceneQuery(s)
    summary = q.context_summary()
    assert "2" in summary  # 2 rooms
    assert "3" in summary  # 3 objects


def test_context_summary_mentions_objects(populated_store):
    s, *_ = populated_store
    q = SceneQuery(s)
    summary = q.context_summary()
    assert "table-A" in summary or "door-1" in summary


def test_context_summary_mentions_edges(populated_store):
    s, *_ = populated_store
    q = SceneQuery(s)
    summary = q.context_summary()
    assert "relationship" in summary or "relation" in summary


def test_context_summary_empty_store(tmp_path):
    with SceneStore(str(tmp_path / "empty.db")) as s:
        q = SceneQuery(s)
        summary = q.context_summary()
        assert "empty" in summary.lower() or "no node" in summary.lower()


def test_context_summary_agent_filter(populated_store):
    s, *_ = populated_store
    q = SceneQuery(s)
    # Only robot-a nodes
    summary = q.context_summary(agent_id="robot-a")
    # robot-a has 1 node (table-A)
    assert "1" in summary
