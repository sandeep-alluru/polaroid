"""SQLite-backed persistent store for scene nodes and edges."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from polaroid.graph import SceneEdge, SceneNode
from polaroid.paths import MEMORY_URI, connect_sqlite, ensure_parent_dir, resolve_store_path


class SceneStore:
    """SQLite-backed persistent store for scene nodes and edges.

    All writes are immediately committed. One SceneStore per process.

    Paths are confined to a data root (default ``.polaroid`` or
    ``POLAROID_DATA_DIR``) to prevent path-injection from API/MCP callers
    (CWE-22 / CodeQL ``py/path-injection``).
    """

    def __init__(self, path: str | Path, *, data_root: str | Path | None = None) -> None:
        """Open or create a store at *path*.

        Parameters
        ----------
        path:
            Store path or ``":memory:"``. Relative paths are resolved under
            *data_root*. Absolute paths must stay inside *data_root*.
        data_root:
            Optional root directory (defaults to env ``POLAROID_DATA_DIR`` or
            ``.polaroid``). Tests should pass the pytest ``tmp_path``.
        """
        full, base = resolve_store_path(path, root=data_root, default_name="scene.db")
        if full == MEMORY_URI:
            self._path = Path(MEMORY_URI)
            self._conn = connect_sqlite(MEMORY_URI, None)
        else:
            ensure_parent_dir(full, base)
            self._path = Path(full)
            self._conn = connect_sqlite(full, base)
        self._conn.row_factory = sqlite3.Row
        self._create_schema()

    # ── Schema ─────────────────────────────────────────────────────────────────

    def _create_schema(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS nodes (
                id          TEXT PRIMARY KEY,
                label       TEXT NOT NULL,
                node_type   TEXT NOT NULL,
                properties  TEXT NOT NULL DEFAULT '{}',
                confidence  REAL NOT NULL DEFAULT 1.0,
                observed_at REAL NOT NULL,
                agent_id    TEXT NOT NULL DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS edges (
                id          TEXT PRIMARY KEY,
                source_id   TEXT NOT NULL,
                target_id   TEXT NOT NULL,
                relation    TEXT NOT NULL,
                confidence  REAL NOT NULL DEFAULT 1.0,
                observed_at REAL NOT NULL
            );
        """)
        self._conn.commit()

    # ── Nodes ──────────────────────────────────────────────────────────────────

    def upsert_node(self, node: SceneNode) -> None:
        """Insert or update node - only overwrites if incoming confidence >= existing."""
        existing = self.get_node(node.id)
        if existing is None:
            self._conn.execute(
                """
                INSERT INTO nodes
                    (id, label, node_type, properties, confidence, observed_at, agent_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    node.id,
                    node.label,
                    node.node_type,
                    json.dumps(node.properties),
                    node.confidence,
                    node.observed_at,
                    node.agent_id,
                ),
            )
        elif node.confidence >= existing.confidence:
            self._conn.execute(
                """
                UPDATE nodes SET properties=?, confidence=?, observed_at=?, agent_id=?
                WHERE id=?
                """,
                (
                    json.dumps(node.properties),
                    node.confidence,
                    node.observed_at,
                    node.agent_id,
                    node.id,
                ),
            )
        self._conn.commit()

    def get_node(self, node_id: str) -> SceneNode | None:
        """Return a SceneNode by ID, or None if not found."""
        row = self._conn.execute("SELECT * FROM nodes WHERE id=?", (node_id,)).fetchone()
        if row is None:
            return None
        return self._row_to_node(row)

    def list_nodes(
        self,
        node_type: str | None = None,
        min_confidence: float = 0.0,
    ) -> list[SceneNode]:
        """Return nodes, optionally filtered by type and min confidence."""
        sql = "SELECT * FROM nodes WHERE confidence >= ?"
        params: list[Any] = [min_confidence]
        if node_type is not None:
            sql += " AND node_type=?"
            params.append(node_type)
        rows = self._conn.execute(sql, params).fetchall()
        return [self._row_to_node(r) for r in rows]

    def _row_to_node(self, row: sqlite3.Row) -> SceneNode:
        node = SceneNode(
            label=row["label"],
            node_type=row["node_type"],
            properties=json.loads(row["properties"]),
            confidence=row["confidence"],
            observed_at=row["observed_at"],
            agent_id=row["agent_id"],
        )
        return node

    # ── Edges ──────────────────────────────────────────────────────────────────

    def upsert_edge(self, edge: SceneEdge) -> None:
        """Insert or update edge - only overwrites if incoming confidence >= existing."""
        existing = self.get_edge(edge.id)
        if existing is None:
            self._conn.execute(
                """
                INSERT INTO edges (id, source_id, target_id, relation, confidence, observed_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    edge.id,
                    edge.source_id,
                    edge.target_id,
                    edge.relation,
                    edge.confidence,
                    edge.observed_at,
                ),
            )
        elif edge.confidence >= existing.confidence:
            self._conn.execute(
                "UPDATE edges SET confidence=?, observed_at=? WHERE id=?",
                (edge.confidence, edge.observed_at, edge.id),
            )
        self._conn.commit()

    def get_edge(self, edge_id: str) -> SceneEdge | None:
        """Return a SceneEdge by ID, or None if not found."""
        row = self._conn.execute("SELECT * FROM edges WHERE id=?", (edge_id,)).fetchone()
        if row is None:
            return None
        return self._row_to_edge(row)

    def list_edges(
        self,
        source_id: str | None = None,
        relation: str | None = None,
    ) -> list[SceneEdge]:
        """Return edges, optionally filtered by source_id and/or relation."""
        sql = "SELECT * FROM edges WHERE 1=1"
        params: list[Any] = []
        if source_id is not None:
            sql += " AND source_id=?"
            params.append(source_id)
        if relation is not None:
            sql += " AND relation=?"
            params.append(relation)
        rows = self._conn.execute(sql, params).fetchall()
        return [self._row_to_edge(r) for r in rows]

    def _row_to_edge(self, row: sqlite3.Row) -> SceneEdge:
        edge = SceneEdge(
            source_id=row["source_id"],
            target_id=row["target_id"],
            relation=row["relation"],
            confidence=row["confidence"],
            observed_at=row["observed_at"],
        )
        return edge

    # ── Counts ─────────────────────────────────────────────────────────────────

    def node_count(self) -> int:
        """Return total number of nodes."""
        row = self._conn.execute("SELECT COUNT(*) FROM nodes").fetchone()
        return int(row[0]) if row else 0

    def edge_count(self) -> int:
        """Return total number of edges."""
        row = self._conn.execute("SELECT COUNT(*) FROM edges").fetchone()
        return int(row[0]) if row else 0

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()

    def __enter__(self) -> SceneStore:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
