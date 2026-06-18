"""Tests for the FastAPI REST server using TestClient."""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi", reason="fastapi not installed")

from fastapi.testclient import TestClient

from scenemem.api import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def db(tmp_path):
    return str(tmp_path / "scene.db")


# ── /health ───────────────────────────────────────────────────────────────────


def test_health_returns_ok(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_health_returns_version(client):
    r = client.get("/health")
    assert "version" in r.json()
    assert r.json()["version"] != ""


# ── /node ─────────────────────────────────────────────────────────────────────


def test_post_node_returns_node(client, db):
    r = client.post(
        "/node",
        json={"label": "door-1", "node_type": "object", "db": db},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["label"] == "door-1"
    assert data["node_type"] == "object"
    assert "id" in data


def test_post_node_with_confidence(client, db):
    r = client.post(
        "/node",
        json={"label": "table-A", "node_type": "object", "confidence": 0.8, "db": db},
    )
    assert r.status_code == 200
    assert r.json()["confidence"] == 0.8


def test_post_node_with_properties(client, db):
    r = client.post(
        "/node",
        json={
            "label": "door-1",
            "node_type": "object",
            "properties": {"color": "brown"},
            "db": db,
        },
    )
    assert r.status_code == 200
    assert r.json()["properties"]["color"] == "brown"


# ── /edge ─────────────────────────────────────────────────────────────────────


def test_post_edge_returns_edge(client, db):
    r = client.post(
        "/edge",
        json={"source_id": "aaa", "target_id": "bbb", "relation": "contains", "db": db},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["relation"] == "contains"
    assert "id" in data


# ── /nodes ────────────────────────────────────────────────────────────────────


def test_get_nodes_empty(client, db):
    r = client.get("/nodes", params={"db": db})
    assert r.status_code == 200
    assert r.json()["count"] == 0
    assert r.json()["nodes"] == []


def test_get_nodes_after_post(client, db):
    client.post("/node", json={"label": "x", "node_type": "object", "db": db})
    r = client.get("/nodes", params={"db": db})
    assert r.json()["count"] == 1


def test_get_nodes_filter_by_type(client, db):
    client.post("/node", json={"label": "door", "node_type": "object", "db": db})
    client.post("/node", json={"label": "kitchen", "node_type": "room", "db": db})
    r = client.get("/nodes", params={"db": db, "node_type": "object"})
    assert r.json()["count"] == 1
    assert r.json()["nodes"][0]["node_type"] == "object"


def test_get_nodes_filter_by_confidence(client, db):
    client.post("/node", json={"label": "a", "node_type": "object", "confidence": 0.9, "db": db})
    client.post("/node", json={"label": "b", "node_type": "object", "confidence": 0.3, "db": db})
    r = client.get("/nodes", params={"db": db, "min_confidence": 0.8})
    assert r.json()["count"] == 1


# ── /merge ────────────────────────────────────────────────────────────────────


def test_post_merge_adds_nodes(client, db):
    from scenemem.graph import SceneNode

    remote_node = SceneNode(label="peer-node", node_type="object", properties={})
    r = client.post(
        "/merge",
        json={"other_nodes": [remote_node.to_dict()], "other_edges": [], "db": db},
    )
    assert r.status_code == 200
    data = r.json()
    assert len(data["added_nodes"]) == 1
    assert data["added_nodes"][0]["label"] == "peer-node"


def test_post_merge_empty(client, db):
    r = client.post("/merge", json={"other_nodes": [], "other_edges": [], "db": db})
    assert r.status_code == 200
    assert r.json()["conflicts_resolved"] == 0


# ── /context ──────────────────────────────────────────────────────────────────


def test_get_context_empty(client, db):
    r = client.get("/context", params={"db": db})
    assert r.status_code == 200
    assert "context" in r.json()
    assert len(r.json()["context"]) > 0


def test_get_context_with_nodes(client, db):
    client.post("/node", json={"label": "table-A", "node_type": "object", "db": db})
    r = client.get("/context", params={"db": db})
    assert r.status_code == 200
    assert "object" in r.json()["context"]
