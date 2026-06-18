"""Tests for SceneNode, SceneEdge, and MergeResult dataclasses."""

from __future__ import annotations

from polaroid.graph import MergeResult, SceneEdge, SceneNode, _sha16

# ── _sha16 ────────────────────────────────────────────────────────────────────


def test_sha16_length():
    result = _sha16("hello|world")
    assert len(result) == 16


def test_sha16_deterministic():
    assert _sha16("a|b") == _sha16("a|b")


def test_sha16_unique():
    assert _sha16("a|b") != _sha16("a|c")


# ── SceneNode ─────────────────────────────────────────────────────────────────


def test_scene_node_content_addressed():
    n1 = SceneNode(label="door-1", node_type="object", properties={})
    n2 = SceneNode(label="door-1", node_type="object", properties={})
    assert n1.id == n2.id, "Same label+type must produce same ID"


def test_scene_node_different_labels():
    n1 = SceneNode(label="door-1", node_type="object", properties={})
    n2 = SceneNode(label="door-2", node_type="object", properties={})
    assert n1.id != n2.id


def test_scene_node_different_types():
    n1 = SceneNode(label="kitchen", node_type="room", properties={})
    n2 = SceneNode(label="kitchen", node_type="surface", properties={})
    assert n1.id != n2.id


def test_scene_node_confidence_does_not_affect_id():
    n1 = SceneNode(label="table-A", node_type="object", properties={}, confidence=0.9)
    n2 = SceneNode(label="table-A", node_type="object", properties={}, confidence=0.5)
    assert n1.id == n2.id, "Confidence is metadata, not identity"


def test_scene_node_default_confidence():
    n = SceneNode(label="table-A", node_type="object", properties={})
    assert n.confidence == 1.0


def test_scene_node_default_agent_id():
    n = SceneNode(label="table-A", node_type="object", properties={})
    assert n.agent_id == ""


def test_scene_node_to_dict():
    n = SceneNode(
        label="door-1",
        node_type="object",
        properties={"color": "brown"},
        confidence=0.8,
        agent_id="robot-a",
    )
    d = n.to_dict()
    assert d["id"] == n.id
    assert d["label"] == "door-1"
    assert d["node_type"] == "object"
    assert d["properties"]["color"] == "brown"
    assert d["confidence"] == 0.8
    assert d["agent_id"] == "robot-a"
    assert "observed_at" in d


def test_scene_node_from_dict_roundtrip():
    n = SceneNode(
        label="room-kitchen",
        node_type="room",
        properties={"floor": "tile"},
        confidence=0.95,
        agent_id="robot-b",
    )
    d = n.to_dict()
    n2 = SceneNode.from_dict(d)
    assert n2.id == n.id
    assert n2.label == n.label
    assert n2.node_type == n.node_type
    assert n2.confidence == n.confidence
    assert n2.properties == n.properties
    assert n2.agent_id == n.agent_id


def test_scene_node_from_dict_defaults():
    n = SceneNode.from_dict({"label": "x", "node_type": "object"})
    assert n.confidence == 1.0
    assert n.agent_id == ""
    assert n.properties == {}


# ── SceneEdge ─────────────────────────────────────────────────────────────────


def test_scene_edge_content_addressed():
    e1 = SceneEdge(source_id="aaa", target_id="bbb", relation="contains")
    e2 = SceneEdge(source_id="aaa", target_id="bbb", relation="contains")
    assert e1.id == e2.id


def test_scene_edge_different_relations():
    e1 = SceneEdge(source_id="aaa", target_id="bbb", relation="contains")
    e2 = SceneEdge(source_id="aaa", target_id="bbb", relation="adjacent-to")
    assert e1.id != e2.id


def test_scene_edge_different_direction():
    e1 = SceneEdge(source_id="aaa", target_id="bbb", relation="contains")
    e2 = SceneEdge(source_id="bbb", target_id="aaa", relation="contains")
    assert e1.id != e2.id


def test_scene_edge_to_dict():
    e = SceneEdge(source_id="src", target_id="tgt", relation="on-top-of", confidence=0.7)
    d = e.to_dict()
    assert d["id"] == e.id
    assert d["source_id"] == "src"
    assert d["target_id"] == "tgt"
    assert d["relation"] == "on-top-of"
    assert d["confidence"] == 0.7
    assert "observed_at" in d


def test_scene_edge_from_dict_roundtrip():
    e = SceneEdge(source_id="aaa", target_id="bbb", relation="blocks", confidence=0.6)
    d = e.to_dict()
    e2 = SceneEdge.from_dict(d)
    assert e2.id == e.id
    assert e2.source_id == e.source_id
    assert e2.confidence == e.confidence


# ── MergeResult ───────────────────────────────────────────────────────────────


def test_merge_result_to_dict():
    n = SceneNode(label="x", node_type="object", properties={})
    e = SceneEdge(source_id="a", target_id="b", relation="contains")
    mr = MergeResult(
        added_nodes=[n],
        updated_nodes=[],
        added_edges=[e],
        conflicts_resolved=1,
    )
    d = mr.to_dict()
    assert len(d["added_nodes"]) == 1
    assert len(d["updated_nodes"]) == 0
    assert len(d["added_edges"]) == 1
    assert d["conflicts_resolved"] == 1


def test_merge_result_summary():
    mr = MergeResult(added_nodes=[], updated_nodes=[], added_edges=[], conflicts_resolved=0)
    s = mr.summary()
    assert "Added 0 nodes" in s
    assert "resolved 0 conflict" in s
