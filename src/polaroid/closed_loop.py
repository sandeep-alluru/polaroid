"""Closed-loop scene gates for polaroid (DETACHED-PART / EMPTY-SCENE).

Who reads the output?
  Embodied agents, navigation stacks, merge pipelines, eagle-eyes CI.

What outcome changes?
  Empty scene → FAIL_LOUD (cannot navigate a phantom map).
  Claimed attachment without spatial edge → FAIL (DETACHED-PART).
  Multi-room maps without connectivity edges → FAIL for navigation.

Farm / Qdrant case (Roblox thrusters):
  Parts claimed as part of a body without weld/attachment → drift under physics.
  In the scene graph: object nodes without ``contains`` / ``on-top-of`` /
  ``attached-to`` edges are *detached* - gate refuses silent pass.

Public map: PRIMAL3 pathfinding multi-agent spatial coordination (Track B).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from polaroid.graph import SceneEdge, SceneNode
from polaroid.store import SceneStore

# Spatial relations that count as physical attachment (weld / part-of).
ATTACHMENT_RELATIONS: frozenset[str] = frozenset(
    {
        "contains",
        "on-top-of",
        "attached-to",
        "welded-to",
        "part-of",
        "fixed-to",
    }
)

# Relations that support pathfinding / multi-room navigation.
NAV_RELATIONS: frozenset[str] = frozenset(
    {
        "adjacent-to",
        "connects",
        "connects-to",
        "leads-to",
    }
)


class ClosedLoopError(ValueError):
    """Raised when the scene gate refuses empty or detached structure."""


@dataclass(frozen=True)
class GateOutcome:
    """Result of a closed-loop scene graph read.

    Attributes:
        ok: True only when navigation/attachment may proceed.
        verdict: ``PASS``, ``FAIL``, or ``FAIL_LOUD``.
        reason: Always non-empty.
        exit_code: 0 PASS, 1 FAIL, 2 FAIL_LOUD.
        node_count: Nodes examined.
        edge_count: Edges examined.
        detached_count: Nodes missing required attachment.
        orphan_room_count: Rooms with no nav edges.
    """

    ok: bool
    verdict: str
    reason: str
    exit_code: int
    node_count: int = 0
    edge_count: int = 0
    detached_count: int = 0
    orphan_room_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "verdict": self.verdict,
            "reason": self.reason,
            "exit_code": self.exit_code,
            "node_count": self.node_count,
            "edge_count": self.edge_count,
            "detached_count": self.detached_count,
            "orphan_room_count": self.orphan_room_count,
        }


def _fail_loud(reason: str, **kwargs: Any) -> GateOutcome:
    return GateOutcome(ok=False, verdict="FAIL_LOUD", reason=reason, exit_code=2, **kwargs)


def _fail(reason: str, **kwargs: Any) -> GateOutcome:
    return GateOutcome(ok=False, verdict="FAIL", reason=reason, exit_code=1, **kwargs)


def _norm_rel(relation: str) -> str:
    return (relation or "").strip().lower().replace("_", "-").replace(" ", "-")


def is_attachment_relation(relation: str) -> bool:
    return _norm_rel(relation) in ATTACHMENT_RELATIONS


def is_nav_relation(relation: str) -> bool:
    return _norm_rel(relation) in NAV_RELATIONS


def attachment_edges(store: SceneStore) -> list[SceneEdge]:
    return [e for e in store.list_edges() if is_attachment_relation(e.relation)]


def nav_edges(store: SceneStore) -> list[SceneEdge]:
    return [e for e in store.list_edges() if is_nav_relation(e.relation)]


def is_attached(store: SceneStore, part_id: str, parent_id: str | None = None) -> bool:
    """True if *part_id* has an attachment edge (optionally to *parent_id*)."""
    for e in attachment_edges(store):
        # parent contains part OR part attached-to parent
        if e.source_id == parent_id and e.target_id == part_id:
            return True
        if e.source_id == part_id and e.target_id == parent_id:
            return True
        if parent_id is None and (e.source_id == part_id or e.target_id == part_id):
            return True
    return False


def detached_parts(
    store: SceneStore,
    *,
    part_types: Iterable[str] = ("object", "part", "component"),
    require_parent_types: Iterable[str] = ("object", "agent", "region", "surface"),
) -> list[SceneNode]:
    """Return part-like nodes that claim body membership without attachment edges.

    DETACHED-PART: nodes with ``properties.attached_to`` / ``parent`` set, or
    node_type in *part_types* coexisting with a parent-type node, without any
    attachment relation incident on the part.
    """
    nodes = store.list_nodes()
    by_id = {n.id: n for n in nodes}
    parts: list[SceneNode] = []
    part_type_set = {t.lower() for t in part_types}

    for n in nodes:
        props = n.properties or {}
        claimed_parent = props.get("attached_to") or props.get("parent") or props.get("welded_to")
        is_part = n.node_type.lower() in part_type_set or bool(claimed_parent)
        if not is_part:
            continue
        parent_id: str | None = None
        if isinstance(claimed_parent, str) and claimed_parent:
            # may be label or id
            parent_id = claimed_parent
            if claimed_parent not in by_id:
                for cand in nodes:
                    if cand.label == claimed_parent:
                        parent_id = cand.id
                        break
        if not is_attached(store, n.id, parent_id if parent_id in by_id else None):
            # If no explicit parent, still detached if zero attachment edges at all
            if parent_id is None and is_attached(store, n.id, None):
                continue
            if parent_id is None:
                # only flag free-floating parts when other attachable parents exist
                parents_exist = any(
                    p.node_type.lower() in {t.lower() for t in require_parent_types}
                    and p.id != n.id
                    for p in nodes
                )
                if not parents_exist:
                    continue
                if is_attached(store, n.id, None):
                    continue
            parts.append(n)
    return parts


def gate_scene(
    store: SceneStore,
    *,
    min_nodes: int = 1,
    refuse_detached: bool = True,
) -> GateOutcome:
    """Gate a scene store: empty FAIL_LOUD; detached parts FAIL.

    This is the load-bearing closed-loop reader for embodied agents.
    """
    n = store.node_count()
    e = store.edge_count()
    if n < min_nodes:
        return _fail_loud(
            f"empty scene graph - {n} nodes (<{min_nodes}); "
            f"cannot navigate or merge a phantom map (EMPTY-SCENE)",
            node_count=n,
            edge_count=e,
        )

    if refuse_detached:
        det = detached_parts(store)
        if det:
            labels = [d.label for d in det[:5]]
            return _fail(
                f"DETACHED-PART: {len(det)} node(s) without attachment edges "
                f"(e.g. {labels}) - refuse silent weld (Roblox thruster class)",
                node_count=n,
                edge_count=e,
                detached_count=len(det),
            )

    return GateOutcome(
        ok=True,
        verdict="PASS",
        reason=f"scene ok: nodes={n} edges={e}",
        exit_code=0,
        node_count=n,
        edge_count=e,
        detached_count=0,
    )


def gate_attachment(
    store: SceneStore,
    part_id: str,
    parent_id: str,
) -> GateOutcome:
    """Gate a specific part→parent attachment claim (DETACHED-PART)."""
    n = store.node_count()
    e = store.edge_count()
    part = store.get_node(part_id)
    parent = store.get_node(parent_id)
    if part is None or parent is None:
        return _fail_loud(
            f"missing nodes for attachment part={part_id!r} parent={parent_id!r}",
            node_count=n,
            edge_count=e,
            detached_count=1,
        )
    if is_attached(store, part_id, parent_id):
        return GateOutcome(
            ok=True,
            verdict="PASS",
            reason=f"attachment ok: {part.label!r} linked to {parent.label!r}",
            exit_code=0,
            node_count=n,
            edge_count=e,
        )
    return _fail(
        f"DETACHED-PART: {part.label!r} ({part_id[:8]}…) has no attachment edge "
        f"to {parent.label!r} - thruster/body weld missing",
        node_count=n,
        edge_count=e,
        detached_count=1,
    )


def gate_navigable(
    store: SceneStore,
    *,
    min_rooms: int = 2,
) -> GateOutcome:
    """Gate multi-room navigation: rooms need adjacent/connects edges.

    PRIMAL3 / multi-agent pathfinding class - disconnected rooms are not a map.
    """
    nodes = store.list_nodes()
    rooms = [n for n in nodes if n.node_type.lower() in {"room", "region", "area"}]
    n, e = len(nodes), store.edge_count()
    if len(rooms) < min_rooms:
        # Not a multi-room map - pass navigable check (single space)
        if store.node_count() == 0:
            return _fail_loud("empty scene - not navigable", node_count=0, edge_count=0)
        return GateOutcome(
            ok=True,
            verdict="PASS",
            reason=f"navigable: {len(rooms)} room(s) (<{min_rooms} multi-room threshold)",
            exit_code=0,
            node_count=n,
            edge_count=e,
        )

    nav = nav_edges(store)
    if not nav:
        return _fail(
            f"EMPTY-SCENE connectivity: {len(rooms)} rooms but 0 nav edges "
            f"(adjacent-to/connects) - pathfinding impossible",
            node_count=n,
            edge_count=e,
            orphan_room_count=len(rooms),
        )

    # rooms with no incident nav edge
    linked: set[str] = set()
    for edge in nav:
        linked.add(edge.source_id)
        linked.add(edge.target_id)
    orphans = [r for r in rooms if r.id not in linked]
    if orphans:
        return _fail(
            f"orphan rooms without nav edges: {[o.label for o in orphans[:5]]}",
            node_count=n,
            edge_count=e,
            orphan_room_count=len(orphans),
        )

    return GateOutcome(
        ok=True,
        verdict="PASS",
        reason=f"navigable: {len(rooms)} rooms, {len(nav)} nav edges",
        exit_code=0,
        node_count=n,
        edge_count=e,
        orphan_room_count=0,
    )


def assert_scene_ok(store: SceneStore, **kwargs: Any) -> GateOutcome:
    outcome = gate_scene(store, **kwargs)
    if not outcome.ok:
        raise ClosedLoopError(f"{outcome.verdict}: {outcome.reason}")
    return outcome


def assert_attached(store: SceneStore, part_id: str, parent_id: str) -> GateOutcome:
    outcome = gate_attachment(store, part_id, parent_id)
    if not outcome.ok:
        raise ClosedLoopError(f"{outcome.verdict}: {outcome.reason}")
    return outcome
