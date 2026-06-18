"""Tests for report formatters: print_scene, print_merge, to_json, to_markdown."""

from __future__ import annotations

import io
import json

from rich.console import Console

from scenemem.graph import MergeResult, SceneEdge, SceneNode
from scenemem.report import print_merge, print_scene, to_json, to_markdown

# ── print_scene ───────────────────────────────────────────────────────────────


def test_print_scene_empty(capsys):
    buf = io.StringIO()
    con = Console(file=buf, highlight=False)
    print_scene([], console=con)
    output = buf.getvalue()
    assert "No nodes" in output


def test_print_scene_with_nodes():
    buf = io.StringIO()
    con = Console(file=buf, highlight=False)
    nodes = [
        SceneNode(label="table-A", node_type="object", properties={}, confidence=0.9),
        SceneNode(label="room-kitchen", node_type="room", properties={}),
    ]
    print_scene(nodes, console=con)
    output = buf.getvalue()
    assert "table-A" in output
    assert "room-kitchen" in output


def test_print_scene_shows_confidence():
    buf = io.StringIO()
    con = Console(file=buf, highlight=False)
    nodes = [SceneNode(label="door-1", node_type="object", properties={}, confidence=0.75)]
    print_scene(nodes, console=con)
    output = buf.getvalue()
    assert "0.75" in output


# ── print_merge ───────────────────────────────────────────────────────────────


def test_print_merge_shows_summary():
    buf = io.StringIO()
    con = Console(file=buf, highlight=False)
    n = SceneNode(label="new-node", node_type="object", properties={})
    e = SceneEdge(source_id="a", target_id="b", relation="contains")
    result = MergeResult(
        added_nodes=[n],
        updated_nodes=[],
        added_edges=[e],
        conflicts_resolved=0,
    )
    print_merge(result, console=con)
    output = buf.getvalue()
    assert "Merge" in output or "merge" in output


def test_print_merge_shows_added_node_label():
    buf = io.StringIO()
    con = Console(file=buf, highlight=False)
    n = SceneNode(label="special-node", node_type="object", properties={})
    result = MergeResult(added_nodes=[n], updated_nodes=[], added_edges=[], conflicts_resolved=0)
    print_merge(result, console=con)
    output = buf.getvalue()
    assert "special-node" in output


# ── to_json ───────────────────────────────────────────────────────────────────


def test_to_json_valid_json():
    nodes = [SceneNode(label="x", node_type="object", properties={})]
    result = to_json(nodes)
    parsed = json.loads(result)
    assert isinstance(parsed, dict)


def test_to_json_node_count():
    nodes = [
        SceneNode(label="a", node_type="object", properties={}),
        SceneNode(label="b", node_type="room", properties={}),
    ]
    parsed = json.loads(to_json(nodes))
    assert parsed["node_count"] == 2
    assert len(parsed["nodes"]) == 2


def test_to_json_with_edges():
    nodes = [SceneNode(label="x", node_type="object", properties={})]
    edges = [SceneEdge(source_id="a", target_id="b", relation="contains")]
    parsed = json.loads(to_json(nodes, edges))
    assert "edges" in parsed
    assert parsed["edge_count"] == 1


def test_to_json_without_edges_no_edge_key():
    nodes = [SceneNode(label="x", node_type="object", properties={})]
    parsed = json.loads(to_json(nodes))
    assert "edges" not in parsed


# ── to_markdown ───────────────────────────────────────────────────────────────


def test_to_markdown_empty():
    md = to_markdown([])
    assert "scenemem" in md
    assert "No nodes" in md or "no nodes" in md.lower()


def test_to_markdown_has_table():
    nodes = [SceneNode(label="table-A", node_type="object", properties={}, confidence=0.9)]
    md = to_markdown(nodes)
    assert "|" in md
    assert "table-A" in md


def test_to_markdown_shows_node_type():
    nodes = [SceneNode(label="room-kitchen", node_type="room", properties={})]
    md = to_markdown(nodes)
    assert "room" in md


def test_to_markdown_truncates_at_50():
    nodes = [SceneNode(label=f"node-{i}", node_type="object", properties={}) for i in range(60)]
    md = to_markdown(nodes)
    assert "more" in md


def test_to_markdown_contains_branding():
    nodes = [SceneNode(label="x", node_type="object", properties={})]
    md = to_markdown(nodes)
    assert "scenemem" in md
