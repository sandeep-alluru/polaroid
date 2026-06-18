# polaroid Architecture

This document is the authoritative developer reference for polaroid internals. It covers the data flow, module responsibilities, key invariants, the SQLite schema, and the CRDT merge algorithm.

---

## Data Flow

```
┌─────────────┐   upsert_node()   ┌──────────────┐
│    Agent    │ ────────────────► │  SceneStore  │
│  (or CLI)   │   upsert_edge()   │  (SQLite)    │
└─────────────┘ ────────────────► │              │
                                  │  nodes       │
                                  │  edges       │
                                  └──────────────┘
                                         │
                                  SceneMerger
                                  .merge(local, remote)
                                         │
                                         ▼
                                  ┌──────────────┐
                                  │ MergeResult  │
                                  │ added_nodes  │
                                  │ updated_nodes│
                                  │ added_edges  │
                                  │ conflicts    │
                                  └──────────────┘
                                         │
                                  SceneQuery
                                         │
                                         ▼
                                  ┌──────────────┐
                                  │ find_nodes() │
                                  │ find_neigh.. │
                                  │ context_     │
                                  │ summary()    │
                                  └──────────────┘
```

**Sequence (typical multi-agent workflow):**

1. Agent calls `store.upsert_node(node)` — node is inserted (or updated if confidence is higher).
2. Agent calls `store.upsert_edge(edge)` — edge is inserted (or updated if confidence is higher).
3. Peer agent has its own `SceneStore` with a different view of the world.
4. `SceneMerger().merge(local, remote)` is called — CRDT semantics guarantee a deterministic result.
5. `SceneQuery(store).find_nodes(...)` or `context_summary()` answers spatial queries.

---

## Module Map

| File | Responsibility |
|------|---------------|
| `graph.py` | Core dataclasses: `SceneNode`, `SceneEdge`, `MergeResult`. All content-addressed IDs computed here via `_sha16()`. |
| `store.py` | SQLite persistence layer. `SceneStore` owns the database connection. Upsert logic enforces confidence-weighted updates. |
| `merger.py` | CRDT merge algorithm. `SceneMerger.merge(local, remote)` is a pure operation: reads from remote, writes to local, returns `MergeResult`. |
| `query.py` | Read-only query interface. `SceneQuery` wraps a `SceneStore` and exposes `find_nodes`, `find_neighbors`, `context_summary`. |
| `report.py` | Output formatters: `print_scene()` (Rich terminal), `print_merge()`, `to_json()`, `to_markdown()`. |
| `cli.py` | Click CLI. Subcommands: `add-node`, `add-edge`, `query`, `merge`, `status`. Reads `--db` from context. |
| `api.py` | FastAPI REST server. Endpoints mirror the CLI subcommands. Suitable for OpenAI function-calling integration. |
| `mcp_server.py` | Model Context Protocol server. Exposes `add_scene_node`, `query_nodes`, `get_context` tools to MCP-compatible agents. |

---

## Key Invariants

### 1. SceneNode.id is deterministic

```
SceneNode.id = SHA-256[:16]("{label}|{node_type}")
```

The same label+type always produces the same 16-character hex ID, regardless of `confidence`, `properties`, or `agent_id`. This means:

- `upsert_node()` is idempotent for the same label+type.
- Two independent agents observing the same object will refer to it by the same ID.
- Confidence and properties are **metadata**, not identity. They can be updated.

### 2. SceneEdge.id is deterministic

```
SceneEdge.id = SHA-256[:16]("{source_id}|{target_id}|{relation}")
```

Direction matters: `contains(A, B)` and `contains(B, A)` produce different IDs.

### 3. CRDT merge is idempotent, commutative, and associative

- **Idempotent**: `merge(A, B)` applied twice = applied once.
- **Commutative**: after `merge(A, B)` and `merge(B, A)`, both stores contain the same nodes and edges (highest confidence wins in both cases).
- **Associative**: order of pairwise merges among N stores does not affect the final result.

### 4. Confidence-weighted last-write-wins

When the same node (by ID) exists in both stores with different properties:

- If `remote.confidence > local.confidence`: remote wins (update local).
- If `remote.confidence <= local.confidence`: local wins (no change).

This is a **conflict-free replicated data type (CRDT)** register: the "write" with the highest confidence always wins, globally.

### 5. SceneStore is thread-unsafe

`SceneStore` holds a single `sqlite3.Connection` that is not shared across threads. Use one `SceneStore` per process. For concurrent access, use separate database files.

---

## SQLite Schema

```sql
-- Content-addressed spatial entities
CREATE TABLE nodes (
    id          TEXT PRIMARY KEY,   -- SHA-256[:16] of "label|node_type"
    label       TEXT NOT NULL,      -- human-readable: "door-1", "room-kitchen"
    node_type   TEXT NOT NULL,      -- "object", "room", "surface", "region", "agent"
    properties  TEXT NOT NULL DEFAULT '{}',  -- JSON blob
    confidence  REAL NOT NULL DEFAULT 1.0,
    observed_at REAL NOT NULL,      -- Unix timestamp
    agent_id    TEXT NOT NULL DEFAULT ''
);

-- Directed spatial relationships
CREATE TABLE edges (
    id          TEXT PRIMARY KEY,   -- SHA-256[:16] of "source_id|target_id|relation"
    source_id   TEXT NOT NULL,      -- SceneNode.id of source
    target_id   TEXT NOT NULL,      -- SceneNode.id of target
    relation    TEXT NOT NULL,      -- "contains", "adjacent-to", "on-top-of", "blocks", "connects"
    confidence  REAL NOT NULL DEFAULT 1.0,
    observed_at REAL NOT NULL
);
```

**Notes:**
- `properties` is stored as a JSON string. `SceneStore` serializes/deserializes via `json.dumps` / `json.loads`.
- No foreign key enforcement — Python layer maintains integrity.
- Both tables use `TEXT PRIMARY KEY` on the content-addressed ID for O(1) lookup and automatic deduplication.

---

## CRDT Merge Algorithm

```python
def merge(local: SceneStore, remote: SceneStore) -> MergeResult:
    added_nodes = []
    updated_nodes = []
    added_edges = []
    conflicts_resolved = 0

    for remote_node in remote.list_nodes():
        local_node = local.get_node(remote_node.id)

        if local_node is None:
            # Grow-only set: new node from remote, always add
            local.upsert_node(remote_node)
            added_nodes.append(remote_node)

        elif remote_node.confidence > local_node.confidence:
            # Confidence-weighted LWW register: remote has more certainty
            local.upsert_node(remote_node)
            updated_nodes.append(remote_node)
            conflicts_resolved += 1

        # else: local.confidence >= remote.confidence — keep local, skip

    for remote_edge in remote.list_edges():
        local_edge = local.get_edge(remote_edge.id)

        if local_edge is None:
            local.upsert_edge(remote_edge)
            added_edges.append(remote_edge)

        elif remote_edge.confidence > local_edge.confidence:
            local.upsert_edge(remote_edge)
            conflicts_resolved += 1

    return MergeResult(
        added_nodes=added_nodes,
        updated_nodes=updated_nodes,
        added_edges=added_edges,
        conflicts_resolved=conflicts_resolved,
    )
```

**Why confidence-weighted LWW instead of timestamp-based?**

Timestamps require synchronized clocks, which are unavailable in offline multi-agent scenarios. Confidence is a semantic signal from the agent about how certain it is. A robot with a calibrated sensor at close range (confidence=0.95) should override a rough estimate from a distant sensor (confidence=0.4), regardless of when the observations were made.

---

## Extension Points

- **Async store** — replace `SceneStore` with an `aiosqlite`-backed async adapter for use in `asyncio`-based agent frameworks.
- **Remote store** — implement the same `upsert_node` / `get_node` / `list_nodes` interface against Postgres or DynamoDB for cloud multi-agent scenarios.
- **3D spatial indexing** — add an R-tree index on `properties->>'position'` for radius queries.
- **Semantic node types** — subclass `SceneNode` and override `__post_init__` to add type-specific validation (e.g. require `position` for `object` nodes).
- **Merge webhooks** — call `SceneMerger().merge()` in a background thread and POST the `MergeResult` to a webhook URL whenever a peer store is updated.
