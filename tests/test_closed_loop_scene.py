"""DETACHED-PART / EMPTY-SCENE — spatial graph must refuse phantom maps.

Farm Qdrant: Roblox thrusters not welded → parts drift.
Public: PRIMAL3 pathfinding needs connected spatial structure.
"""

from __future__ import annotations

import pytest

from polaroid.closed_loop import (
    ClosedLoopError,
    assert_attached,
    assert_scene_ok,
    gate_attachment,
    gate_navigable,
    gate_scene,
)
from polaroid.graph import SceneEdge, SceneNode
from polaroid.store import SceneStore


def test_empty_scene_fails_loud(store: SceneStore) -> None:
    out = gate_scene(store)
    assert out.ok is False
    assert out.verdict == "FAIL_LOUD"
    assert out.exit_code == 2
    assert "empty" in out.reason.lower()


def test_detached_part_fails(store: SceneStore) -> None:
    body = SceneNode(label="robot-body", node_type="object", properties={})
    thruster = SceneNode(
        label="thruster-left",
        node_type="part",
        properties={"attached_to": "robot-body"},
    )
    store.upsert_node(body)
    store.upsert_node(thruster)
    # no weld edge — DETACHED-PART
    out = gate_scene(store)
    assert out.ok is False
    assert out.verdict == "FAIL"
    assert out.detached_count >= 1
    assert "DETACHED-PART" in out.reason


def test_welded_part_passes(store: SceneStore) -> None:
    body = SceneNode(label="robot-body", node_type="object", properties={})
    thruster = SceneNode(
        label="thruster-left",
        node_type="part",
        properties={"attached_to": "robot-body"},
    )
    store.upsert_node(body)
    store.upsert_node(thruster)
    store.upsert_edge(
        SceneEdge(source_id=body.id, target_id=thruster.id, relation="contains")
    )
    out = gate_scene(store)
    assert out.ok is True
    assert out.verdict == "PASS"
    assert out.detached_count == 0


def test_gate_attachment_specific(store: SceneStore) -> None:
    body = SceneNode(label="hull", node_type="object", properties={})
    wing = SceneNode(label="wing", node_type="part", properties={})
    store.upsert_node(body)
    store.upsert_node(wing)
    out = gate_attachment(store, wing.id, body.id)
    assert out.ok is False
    assert "DETACHED-PART" in out.reason
    store.upsert_edge(
        SceneEdge(source_id=wing.id, target_id=body.id, relation="welded-to")
    )
    out2 = gate_attachment(store, wing.id, body.id)
    assert out2.ok is True


def test_navigable_disconnected_rooms_fail(store: SceneStore) -> None:
    a = SceneNode(label="room-a", node_type="room", properties={})
    b = SceneNode(label="room-b", node_type="room", properties={})
    store.upsert_node(a)
    store.upsert_node(b)
    out = gate_navigable(store, min_rooms=2)
    assert out.ok is False
    assert out.verdict == "FAIL"
    assert "nav" in out.reason.lower() or "rooms" in out.reason.lower()


def test_navigable_connected_rooms_pass(store: SceneStore) -> None:
    a = SceneNode(label="room-a", node_type="room", properties={})
    b = SceneNode(label="room-b", node_type="room", properties={})
    store.upsert_node(a)
    store.upsert_node(b)
    store.upsert_edge(
        SceneEdge(source_id=a.id, target_id=b.id, relation="adjacent-to")
    )
    out = gate_navigable(store, min_rooms=2)
    assert out.ok is True
    assert out.verdict == "PASS"


def test_assert_scene_ok_raises(store: SceneStore) -> None:
    with pytest.raises(ClosedLoopError, match="FAIL_LOUD"):
        assert_scene_ok(store)


def test_assert_attached_raises(store: SceneStore) -> None:
    body = SceneNode(label="b", node_type="object", properties={})
    p = SceneNode(label="p", node_type="part", properties={})
    store.upsert_node(body)
    store.upsert_node(p)
    with pytest.raises(ClosedLoopError, match="DETACHED"):
        assert_attached(store, p.id, body.id)


def test_to_dict(store: SceneStore) -> None:
    store.upsert_node(SceneNode(label="solo", node_type="region", properties={}))
    payload = gate_scene(store, refuse_detached=False).to_dict()
    assert payload["ok"] is True
    assert payload["node_count"] == 1
