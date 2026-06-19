"""CLI tests using Click's CliRunner (no subprocess, no temp files needed)."""

from __future__ import annotations

import json

import pytest
from click.testing import CliRunner

from polaroid.cli import main


@pytest.fixture
def db(tmp_path):
    return str(tmp_path / "scene.db")


# ── --help ────────────────────────────────────────────────────────────────────


def test_main_help():
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "CRDT" in result.output or "scene" in result.output.lower()


def test_add_node_help():
    runner = CliRunner()
    result = runner.invoke(main, ["add-node", "--help"])
    assert result.exit_code == 0


def test_add_edge_help():
    runner = CliRunner()
    result = runner.invoke(main, ["add-edge", "--help"])
    assert result.exit_code == 0


def test_query_help():
    runner = CliRunner()
    result = runner.invoke(main, ["query", "--help"])
    assert result.exit_code == 0


def test_status_help():
    runner = CliRunner()
    result = runner.invoke(main, ["status", "--help"])
    assert result.exit_code == 0


def test_merge_help():
    runner = CliRunner()
    result = runner.invoke(main, ["merge", "--help"])
    assert result.exit_code == 0


# ── add-node ──────────────────────────────────────────────────────────────────


def test_add_node_basic(db):
    runner = CliRunner()
    result = runner.invoke(main, ["--db", db, "add-node", "door-1", "object"])
    assert result.exit_code == 0
    assert "door-1" in result.output


def test_add_node_with_confidence(db):
    runner = CliRunner()
    result = runner.invoke(
        main, ["--db", db, "add-node", "table-A", "object", "--confidence", "0.8"]
    )
    assert result.exit_code == 0


def test_add_node_with_property(db):
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["--db", db, "add-node", "door-1", "object", "--property", "color=brown"],
    )
    assert result.exit_code == 0


def test_add_node_stores_in_db(db):
    runner = CliRunner()
    runner.invoke(main, ["--db", db, "add-node", "room-kitchen", "room"])
    # Check via status
    result = runner.invoke(main, ["--db", db, "status"])
    assert result.exit_code == 0
    assert "1" in result.output


# ── add-edge ──────────────────────────────────────────────────────────────────


def test_add_edge_basic(db):
    from polaroid.graph import SceneNode
    from polaroid.store import SceneStore

    # Pre-populate nodes
    with SceneStore(db) as store:
        n1 = SceneNode(label="room-a", node_type="room", properties={})
        n2 = SceneNode(label="table-b", node_type="object", properties={})
        store.upsert_node(n1)
        store.upsert_node(n2)
        src_id = n1.id
        tgt_id = n2.id

    runner = CliRunner()
    result = runner.invoke(main, ["--db", db, "add-edge", src_id, tgt_id, "contains"])
    assert result.exit_code == 0
    assert "contains" in result.output


# ── query ─────────────────────────────────────────────────────────────────────


def test_query_empty_store(db):
    runner = CliRunner()
    result = runner.invoke(main, ["--db", db, "query"])
    assert result.exit_code == 0


def test_query_with_nodes(db):
    runner = CliRunner()
    runner.invoke(main, ["--db", db, "add-node", "door-1", "object"])
    result = runner.invoke(main, ["--db", db, "query"])
    assert result.exit_code == 0
    assert "door-1" in result.output


def test_query_filter_by_type(db):
    runner = CliRunner()
    runner.invoke(main, ["--db", db, "add-node", "door-1", "object"])
    runner.invoke(main, ["--db", db, "add-node", "room-kitchen", "room"])
    result = runner.invoke(main, ["--db", db, "query", "--type", "object"])
    assert result.exit_code == 0
    assert "door-1" in result.output


def test_query_json_format(db):
    runner = CliRunner()
    runner.invoke(main, ["--db", db, "add-node", "x", "object"])
    result = runner.invoke(main, ["--db", db, "query", "--format", "json"])
    assert result.exit_code == 0
    parsed = json.loads(result.output.strip())
    assert "nodes" in parsed


# ── status ────────────────────────────────────────────────────────────────────


def test_status_empty(db):
    runner = CliRunner()
    result = runner.invoke(main, ["--db", db, "status"])
    assert result.exit_code == 0
    assert "0" in result.output


def test_status_with_data(db):
    runner = CliRunner()
    runner.invoke(main, ["--db", db, "add-node", "door-1", "object"])
    result = runner.invoke(main, ["--db", db, "status"])
    assert result.exit_code == 0
    assert "1" in result.output


# ── merge ─────────────────────────────────────────────────────────────────────


def test_merge_command(tmp_path):
    from polaroid.graph import SceneNode
    from polaroid.store import SceneStore

    local_db = str(tmp_path / "local.db")
    remote_db = str(tmp_path / "remote.db")

    with SceneStore(remote_db) as remote:
        n = SceneNode(label="peer-node", node_type="object", properties={})
        remote.upsert_node(n)

    runner = CliRunner()
    result = runner.invoke(main, ["--db", local_db, "merge", remote_db])
    assert result.exit_code == 0


# ── stats ─────────────────────────────────────────────────────────────────────


def test_stats_help():
    runner = CliRunner()
    result = runner.invoke(main, ["stats", "--help"])
    assert result.exit_code == 0


def test_stats_empty_store(db):
    runner = CliRunner()
    result = runner.invoke(main, ["--db", db, "stats"])
    assert result.exit_code == 0
    assert "Nodes:" in result.output
    assert "Edges:" in result.output


def test_stats_with_data(db):
    runner = CliRunner()
    runner.invoke(main, ["--db", db, "add-node", "kitchen", "room"])
    runner.invoke(main, ["--db", db, "add-node", "table", "surface"])
    result = runner.invoke(main, ["--db", db, "stats"])
    assert result.exit_code == 0
    assert "2" in result.output
    assert "room" in result.output
    assert "surface" in result.output


def test_stats_shows_components_and_diameter(db):
    runner = CliRunner()
    runner.invoke(main, ["--db", db, "add-node", "A", "room"])
    result = runner.invoke(main, ["--db", db, "stats"])
    assert result.exit_code == 0
    assert "Connected components" in result.output
    assert "Diameter" in result.output


# ── export ────────────────────────────────────────────────────────────────────


def test_export_help():
    runner = CliRunner()
    result = runner.invoke(main, ["export", "--help"])
    assert result.exit_code == 0


def test_export_json_empty(db):
    runner = CliRunner()
    result = runner.invoke(main, ["--db", db, "export", "--format", "json"])
    assert result.exit_code == 0
    data = json.loads(result.output.strip())
    assert "nodes" in data
    assert "edges" in data


def test_export_json_with_data(db):
    runner = CliRunner()
    runner.invoke(main, ["--db", db, "add-node", "door", "object"])
    result = runner.invoke(main, ["--db", db, "export", "--format", "json"])
    assert result.exit_code == 0
    data = json.loads(result.output.strip())
    assert data["node_count"] == 1


def test_export_dot_format(db):
    runner = CliRunner()
    runner.invoke(main, ["--db", db, "add-node", "room-A", "room"])
    result = runner.invoke(main, ["--db", db, "export", "--format", "dot"])
    assert result.exit_code == 0
    assert "digraph" in result.output


def test_export_dot_empty(db):
    runner = CliRunner()
    result = runner.invoke(main, ["--db", db, "export", "--format", "dot"])
    assert result.exit_code == 0
    assert "digraph" in result.output


def test_export_to_file(db, tmp_path):
    out_file = str(tmp_path / "output.json")
    runner = CliRunner()
    runner.invoke(main, ["--db", db, "add-node", "x", "object"])
    result = runner.invoke(main, ["--db", db, "export", "--format", "json", "-o", out_file])
    assert result.exit_code == 0
    import pathlib
    content = pathlib.Path(out_file).read_text()
    data = json.loads(content)
    assert data["node_count"] == 1
