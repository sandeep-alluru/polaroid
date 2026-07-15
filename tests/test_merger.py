"""Tests for SceneMerger CRDT merge algorithm."""

from __future__ import annotations

import pytest

from polaroid.graph import SceneEdge, SceneNode
from polaroid.merger import SceneMerger
from polaroid.store import SceneStore


@pytest.fixture
def local(tmp_path):
    s = SceneStore(str(tmp_path / "local.db"))
    yield s
    s.close()


@pytest.fixture
def remote(tmp_path):
    s = SceneStore(str(tmp_path / "remote.db"))
    yield s
    s.close()


# ── Node add-only semantics ────────────────────────────────────────────────────


def test_merge_adds_new_nodes(local, remote):
    n = SceneNode(label="door-1", node_type="object", properties={})
    remote.upsert_node(n)
    result = SceneMerger().merge(local, remote)
    assert len(result.added_nodes) == 1
    assert result.added_nodes[0].id == n.id
    assert local.get_node(n.id) is not None


def test_merge_does_not_duplicate_existing_nodes(local, remote):
    n = SceneNode(label="door-1", node_type="object", properties={})
    local.upsert_node(n)
    remote.upsert_node(n)
    result = SceneMerger().merge(local, remote)
    assert len(result.added_nodes) == 0
    assert local.node_count() == 1


def test_merge_adds_multiple_nodes(local, remote):
    for i in range(5):
        remote.upsert_node(SceneNode(label=f"node-{i}", node_type="object", properties={}))
    result = SceneMerger().merge(local, remote)
    assert len(result.added_nodes) == 5
    assert local.node_count() == 5


# ── Confidence-weighted conflict resolution ───────────────────────────────────


def test_merge_updates_node_with_higher_remote_confidence(local, remote):
    n_low = SceneNode(
        label="door-1", node_type="object", properties={"state": "closed"}, confidence=0.4
    )
    local.upsert_node(n_low)
    n_high = SceneNode(
        label="door-1", node_type="object", properties={"state": "open"}, confidence=0.9
    )
    remote.upsert_node(n_high)
    result = SceneMerger().merge(local, remote)
    assert len(result.updated_nodes) == 1
    assert result.conflicts_resolved == 1
    updated = local.get_node(n_low.id)
    assert updated is not None
    assert updated.confidence == 0.9
    assert updated.properties["state"] == "open"


def test_merge_keeps_local_when_higher_confidence(local, remote):
    n_high = SceneNode(
        label="door-1", node_type="object", properties={"state": "open"}, confidence=0.9
    )
    local.upsert_node(n_high)
    n_low = SceneNode(
        label="door-1", node_type="object", properties={"state": "closed"}, confidence=0.3
    )
    remote.upsert_node(n_low)
    result = SceneMerger().merge(local, remote)
    assert len(result.updated_nodes) == 0
    assert result.conflicts_resolved == 0
    kept = local.get_node(n_high.id)
    assert kept is not None
    assert kept.confidence == 0.9
    assert kept.properties["state"] == "open"


def test_merge_equal_confidence_keeps_local(local, remote):
    n_local = SceneNode(label="x", node_type="object", properties={"v": "local"}, confidence=0.5)
    n_remote = SceneNode(label="x", node_type="object", properties={"v": "remote"}, confidence=0.5)
    local.upsert_node(n_local)
    remote.upsert_node(n_remote)
    result = SceneMerger().merge(local, remote)
    assert result.conflicts_resolved == 0
    # local should be unchanged
    retrieved = local.get_node(n_local.id)
    assert retrieved is not None
    assert retrieved.properties["v"] == "local"


# ── Edge add-only semantics ───────────────────────────────────────────────────


def test_merge_adds_new_edges(local, remote):
    e = SceneEdge(source_id="aaa", target_id="bbb", relation="contains")
    remote.upsert_edge(e)
    result = SceneMerger().merge(local, remote)
    assert len(result.added_edges) == 1
    assert local.get_edge(e.id) is not None


def test_merge_does_not_duplicate_existing_edges(local, remote):
    e = SceneEdge(source_id="aaa", target_id="bbb", relation="contains")
    local.upsert_edge(e)
    remote.upsert_edge(e)
    result = SceneMerger().merge(local, remote)
    assert len(result.added_edges) == 0
    assert local.edge_count() == 1


def test_merge_updates_edge_with_higher_remote_confidence(local, remote):
    e_low = SceneEdge(source_id="aaa", target_id="bbb", relation="contains", confidence=0.3)
    local.upsert_edge(e_low)
    e_high = SceneEdge(source_id="aaa", target_id="bbb", relation="contains", confidence=0.8)
    remote.upsert_edge(e_high)
    result = SceneMerger().merge(local, remote)
    assert result.conflicts_resolved >= 1
    updated = local.get_edge(e_low.id)
    assert updated is not None
    assert updated.confidence == 0.8


# ── Idempotency ───────────────────────────────────────────────────────────────


def test_merge_is_idempotent(local, remote):
    n = SceneNode(label="x", node_type="object", properties={})
    remote.upsert_node(n)
    result1 = SceneMerger().merge(local, remote)
    result2 = SceneMerger().merge(local, remote)
    assert len(result1.added_nodes) == 1
    assert len(result2.added_nodes) == 0  # already merged
    assert local.node_count() == 1


# ── Empty cases ───────────────────────────────────────────────────────────────


def test_merge_empty_remote(local, remote):
    n = SceneNode(label="x", node_type="object", properties={})
    local.upsert_node(n)
    result = SceneMerger().merge(local, remote)
    assert len(result.added_nodes) == 0
    assert local.node_count() == 1


def test_merge_both_empty(local, remote):
    result = SceneMerger().merge(local, remote)
    assert len(result.added_nodes) == 0
    assert len(result.added_edges) == 0
    assert result.conflicts_resolved == 0
