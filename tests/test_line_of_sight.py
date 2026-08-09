"""LINE-OF-SIGHT — refuse observe/target without visibility path."""

from __future__ import annotations

import pytest

from polaroid.closed_loop import (
    ClosedLoopError,
    assert_line_of_sight,
    gate_line_of_sight,
    has_line_of_sight,
)
from polaroid.graph import SceneEdge, SceneNode
from polaroid.store import SceneStore


def test_empty_scene_fails_loud(store: SceneStore) -> None:
    out = gate_line_of_sight(store, "a", "b")
    assert out.ok is False
    assert out.verdict == "FAIL_LOUD"
    assert "LINE-OF-SIGHT" in out.reason


def test_missing_nodes_fails_loud(store: SceneStore) -> None:
    a = SceneNode(label="agent", node_type="agent", properties={})
    store.upsert_node(a)
    out = gate_line_of_sight(store, a.id, "missing-target")
    assert out.ok is False
    assert out.verdict == "FAIL_LOUD"


def test_direct_sees_passes(store: SceneStore) -> None:
    agent = SceneNode(label="bot", node_type="agent", properties={})
    target = SceneNode(label="button", node_type="object", properties={})
    store.upsert_node(agent)
    store.upsert_node(target)
    store.upsert_edge(
        SceneEdge(source_id=agent.id, target_id=target.id, relation="sees")
    )
    out = gate_line_of_sight(store, agent.id, target.id, action="click")
    assert out.ok is True
    assert out.verdict == "PASS"
    assert has_line_of_sight(store, agent.id, target.id) is True


def test_no_los_fails(store: SceneStore) -> None:
    agent = SceneNode(label="bot", node_type="agent", properties={})
    target = SceneNode(label="chest", node_type="object", properties={})
    store.upsert_node(agent)
    store.upsert_node(target)
    # no edges at all
    out = gate_line_of_sight(store, agent.id, target.id, action="open")
    assert out.ok is False
    assert out.verdict == "FAIL"
    assert "LINE-OF-SIGHT" in out.reason


def test_occluder_blocks_nav_path(store: SceneStore) -> None:
    agent = SceneNode(label="bot", node_type="agent", properties={})
    wall = SceneNode(label="wall", node_type="object", properties={})
    target = SceneNode(label="gem", node_type="object", properties={})
    store.upsert_node(agent)
    store.upsert_node(wall)
    store.upsert_node(target)
    # path agent-wall-target via adjacent but wall occludes gem
    store.upsert_edge(
        SceneEdge(source_id=agent.id, target_id=wall.id, relation="adjacent-to")
    )
    store.upsert_edge(
        SceneEdge(source_id=wall.id, target_id=target.id, relation="adjacent-to")
    )
    store.upsert_edge(
        SceneEdge(source_id=wall.id, target_id=target.id, relation="occludes")
    )
    out = gate_line_of_sight(store, agent.id, target.id)
    assert out.ok is False
    assert out.verdict == "FAIL"


def test_room_chain_los_passes(store: SceneStore) -> None:
    agent = SceneNode(label="bot", node_type="agent", properties={})
    room_a = SceneNode(label="hall", node_type="room", properties={})
    room_b = SceneNode(label="lab", node_type="room", properties={})
    target = SceneNode(label="console", node_type="object", properties={})
    store.upsert_node(agent)
    store.upsert_node(room_a)
    store.upsert_node(room_b)
    store.upsert_node(target)
    store.upsert_edge(
        SceneEdge(source_id=agent.id, target_id=room_a.id, relation="adjacent-to")
    )
    store.upsert_edge(
        SceneEdge(source_id=room_a.id, target_id=room_b.id, relation="connects")
    )
    store.upsert_edge(
        SceneEdge(source_id=room_b.id, target_id=target.id, relation="adjacent-to")
    )
    out = gate_line_of_sight(store, agent.id, target.id, action="inspect")
    assert out.ok is True


def test_assert_raises(store: SceneStore) -> None:
    a = SceneNode(label="a", node_type="agent", properties={})
    b = SceneNode(label="b", node_type="object", properties={})
    store.upsert_node(a)
    store.upsert_node(b)
    with pytest.raises(ClosedLoopError):
        assert_line_of_sight(store, a.id, b.id)


def test_embodied_los_fixture(store: SceneStore) -> None:
    """End-to-end: agent clicks occluded button → refuse; clear sees → pass."""
    bot = SceneNode(label="cua-agent", node_type="agent", properties={})
    door = SceneNode(label="door", node_type="object", properties={})
    btn = SceneNode(label="unlock-btn", node_type="object", properties={})
    store.upsert_node(bot)
    store.upsert_node(door)
    store.upsert_node(btn)
    store.upsert_edge(
        SceneEdge(source_id=bot.id, target_id=door.id, relation="adjacent-to")
    )
    store.upsert_edge(
        SceneEdge(source_id=door.id, target_id=btn.id, relation="occludes")
    )
    refuse = gate_line_of_sight(store, bot.id, btn.id, action="click")
    assert refuse.ok is False

    store.upsert_edge(
        SceneEdge(source_id=bot.id, target_id=btn.id, relation="sees")
    )
    ok = gate_line_of_sight(store, bot.id, btn.id, action="click")
    assert ok.ok is True
