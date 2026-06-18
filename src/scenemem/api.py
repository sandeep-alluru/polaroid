"""FastAPI REST wrapper for scenemem.

Start:   uvicorn scenemem.api:app --reload
Install: pip install "scenemem[api]"
Docs:    http://localhost:8000/docs
"""

from __future__ import annotations

import tempfile
from typing import Any

try:
    from fastapi import FastAPI
    from pydantic import BaseModel, Field
except ImportError as exc:
    raise ImportError("API server requires: pip install 'scenemem[api]'") from exc

from scenemem import __version__
from scenemem.graph import SceneEdge, SceneNode
from scenemem.merger import SceneMerger
from scenemem.query import SceneQuery
from scenemem.store import SceneStore

app = FastAPI(
    title="scenemem API",
    description="Embeddable CRDT scene graph for embodied AI agents.",
    version=__version__,
    license_info={
        "name": "MIT",
        "url": "https://github.com/sandeep-alluru/scenemem/blob/main/LICENSE",
    },
)

_DEFAULT_DB = ".scenemem/scene.db"


class HealthResponse(BaseModel):
    """Response body for GET /health."""

    status: str
    version: str


class NodeRequest(BaseModel):
    """Request body for POST /node."""

    label: str = Field(..., description="Human-readable node label.")
    node_type: str = Field(..., description="Node type: object, room, surface, region, agent.")
    properties: dict = Field(default_factory=dict)  # type: ignore[type-arg]
    confidence: float = Field(1.0, ge=0.0, le=1.0)
    agent_id: str = Field("")
    db: str = Field(_DEFAULT_DB)


class EdgeRequest(BaseModel):
    """Request body for POST /edge."""

    source_id: str = Field(..., description="Source node ID.")
    target_id: str = Field(..., description="Target node ID.")
    relation: str = Field(..., description="Spatial relation type.")
    confidence: float = Field(1.0, ge=0.0, le=1.0)
    db: str = Field(_DEFAULT_DB)


class MergeRequest(BaseModel):
    """Request body for POST /merge."""

    other_nodes: list[dict] = Field(default_factory=list)  # type: ignore[type-arg]
    other_edges: list[dict] = Field(default_factory=list)  # type: ignore[type-arg]
    db: str = Field(_DEFAULT_DB)


@app.get("/health", response_model=HealthResponse)
async def health() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok", "version": __version__}


@app.post("/node")
async def add_node(request: NodeRequest) -> Any:
    """Add or update a scene node."""
    node = SceneNode(
        label=request.label,
        node_type=request.node_type,
        properties=request.properties,
        confidence=request.confidence,
        agent_id=request.agent_id,
    )
    with SceneStore(request.db) as store:
        store.upsert_node(node)
    return node.to_dict()


@app.post("/edge")
async def add_edge(request: EdgeRequest) -> Any:
    """Add or update a scene edge."""
    edge = SceneEdge(
        source_id=request.source_id,
        target_id=request.target_id,
        relation=request.relation,
        confidence=request.confidence,
    )
    with SceneStore(request.db) as store:
        store.upsert_edge(edge)
    return edge.to_dict()


@app.get("/nodes")
async def list_nodes(
    node_type: str | None = None,
    min_confidence: float = 0.0,
    db: str = _DEFAULT_DB,
) -> Any:
    """List nodes with optional filters."""
    with SceneStore(db) as store:
        nodes = store.list_nodes(node_type=node_type, min_confidence=min_confidence)
    return {"nodes": [n.to_dict() for n in nodes], "count": len(nodes)}


@app.post("/merge")
async def merge(request: MergeRequest) -> Any:
    """Merge a set of nodes and edges into the local store."""
    with SceneStore(request.db) as local:
        # Build a temporary in-memory remote store
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            tmp_path = f.name

        with SceneStore(tmp_path) as remote:
            for nd in request.other_nodes:
                remote.upsert_node(SceneNode.from_dict(nd))
            for ed in request.other_edges:
                remote.upsert_edge(SceneEdge.from_dict(ed))
            result = SceneMerger().merge(local, remote)

    return result.to_dict()


@app.get("/context")
async def context_summary(agent_id: str = "", db: str = _DEFAULT_DB) -> Any:
    """Return a text description of the current scene."""
    with SceneStore(db) as store:
        q = SceneQuery(store)
        summary = q.context_summary(agent_id=agent_id)
    return {"context": summary}
