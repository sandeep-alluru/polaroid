"""
Hospital Robot Fleet Coordination Demo
=======================================
Demonstrates polaroid + agentcrdt + groundcrew working together for a
hospital robot fleet coordination scenario.

Three delivery robots (Robot-A, Robot-B, Robot-C) navigate a hospital floor:

  1. polaroid  — Each robot keeps its own CRDT scene graph of the floor.
                 SceneMerger merges Robot-A and Robot-B views; shared Room-102
                 is deduplicated and the combined map has 5 unique locations.

  2. agentcrdt — All 3 robots simultaneously update their belief about which
                 room has the medication cart. LWW merge resolves conflicting
                 "cart_location" claims. A SemanticRule fires if both Room-101
                 and Room-102 are simultaneously marked occupied_by_cart=True.

  3. groundcrew — Robot-A uses Oracle to record a deterministic ActionReceipt:
                  "delivered medication to Room-101 at 14:32". StateSnapshot
                  before/after confirms the delivery changed room state from
                  "pending" to "delivered". ReceiptStore stores the receipt
                  for audit.

Run:
    pip install polaroid-ai agentcrdt groundcrew
    python 05_embodied_agent_stack.py
"""

from __future__ import annotations

import json
import tempfile
import time
from pathlib import Path

# polaroid
from polaroid.graph import SceneEdge, SceneNode
from polaroid.merger import SceneMerger
from polaroid.query import SceneQuery
from polaroid.store import SceneStore

# agentcrdt
from agentcrdt.fact import WorldFact
from agentcrdt.merger import WorldMerger
from agentcrdt.rules import RuleEngine, SemanticRule
from agentcrdt.store import WorldStore

# groundcrew
from groundcrew.codec import ActionSpec
from groundcrew.oracle import Oracle, ReceiptStore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _section(title: str) -> None:
    bar = "=" * 60
    print(f"\n{bar}")
    print(f"  {title}")
    print(bar)


def _step(msg: str) -> None:
    print(f"\n  >> {msg}")


# ---------------------------------------------------------------------------
# Part 1 — polaroid: CRDT scene graph merge
# ---------------------------------------------------------------------------

def demo_polaroid(tmp: Path) -> None:
    _section("PART 1 — polaroid: Robot Scene Graph Merge")

    # ── Robot-A scans Room-101, Room-102, Hallway-North ──────────────────────
    _step("Robot-A scans Room-101, Room-102, and Hallway-North")

    store_a = SceneStore(str(tmp / "robot-a.db"))

    room_101 = SceneNode(
        label="Room-101",
        node_type="room",
        properties={"use": "patient-room", "floor": "linoleum"},
        confidence=0.97,
        agent_id="Robot-A",
    )
    room_102 = SceneNode(
        label="Room-102",
        node_type="room",
        properties={"use": "patient-room", "floor": "linoleum"},
        confidence=0.95,
        agent_id="Robot-A",
    )
    hallway_north = SceneNode(
        label="Hallway-North",
        node_type="corridor",
        properties={"width_m": 2.5, "lighting": "bright"},
        confidence=0.90,
        agent_id="Robot-A",
    )

    store_a.upsert_node(room_101)
    store_a.upsert_node(room_102)
    store_a.upsert_node(hallway_north)

    # Spatial relationships
    store_a.upsert_edge(
        SceneEdge(source_id=hallway_north.id, target_id=room_101.id, relation="connects")
    )
    store_a.upsert_edge(
        SceneEdge(source_id=hallway_north.id, target_id=room_102.id, relation="connects")
    )
    store_a.upsert_edge(
        SceneEdge(source_id=room_101.id, target_id=room_102.id, relation="adjacent-to")
    )

    print(
        f"     Robot-A map: {store_a.node_count()} nodes, "
        f"{store_a.edge_count()} edges"
    )

    # ── Robot-B scans Room-102, Room-103, and Pharmacy ───────────────────────
    _step("Robot-B scans Room-102, Room-103, and Pharmacy")

    store_b = SceneStore(str(tmp / "robot-b.db"))

    # Room-102 is scanned by both robots; Robot-B has lower confidence
    room_102_b = SceneNode(
        label="Room-102",
        node_type="room",
        properties={"use": "patient-room"},
        confidence=0.70,        # lower — Robot-B only glimpsed it in passing
        agent_id="Robot-B",
    )
    room_103 = SceneNode(
        label="Room-103",
        node_type="room",
        properties={"use": "patient-room", "floor": "linoleum"},
        confidence=0.93,
        agent_id="Robot-B",
    )
    pharmacy = SceneNode(
        label="Pharmacy",
        node_type="room",
        properties={"use": "dispensary", "access": "restricted"},
        confidence=0.98,
        agent_id="Robot-B",
    )

    store_b.upsert_node(room_102_b)
    store_b.upsert_node(room_103)
    store_b.upsert_node(pharmacy)

    store_b.upsert_edge(
        SceneEdge(source_id=room_103.id, target_id=pharmacy.id, relation="adjacent-to")
    )
    store_b.upsert_edge(
        SceneEdge(source_id=room_102_b.id, target_id=room_103.id, relation="adjacent-to")
    )

    print(
        f"     Robot-B map: {store_b.node_count()} nodes, "
        f"{store_b.edge_count()} edges"
    )

    # ── CRDT merge: Robot-B into Robot-A ────────────────────────────────────
    _step("Merging Robot-B scene graph into Robot-A (CRDT semantics)")

    merger = SceneMerger()
    result = merger.merge(store_a, store_b)

    print(f"     Merge result: {result.summary()}")
    print(f"     Combined node count: {store_a.node_count()}")
    print(f"     Combined edge count: {store_a.edge_count()}")

    try:
        # Verify Room-102: Robot-A's higher confidence (0.95) must be kept
        unified_room_102 = store_a.get_node(room_102.id)
        assert unified_room_102 is not None, "Room-102 missing from merged store"
        assert unified_room_102.confidence == 0.95, (
            f"Expected Room-102 confidence=0.95 (Robot-A wins), "
            f"got {unified_room_102.confidence}"
        )
        print(
            f"     CRDT verification: Room-102 confidence = {unified_room_102.confidence:.2f} "
            f"(Robot-A's higher-confidence scan wins)"
        )

        # ── Query the unified scene ──────────────────────────────────────────────
        _step("Querying the unified scene graph")

        q = SceneQuery(store_a)

        all_rooms = q.find_nodes(node_type="room")
        corridors = q.find_nodes(node_type="corridor")
        print(f"     Rooms in unified map ({len(all_rooms)}): "
              f"{', '.join(n.label for n in all_rooms)}")
        print(f"     Corridors: {', '.join(n.label for n in corridors)}")

        neighbors = q.find_neighbors(hallway_north.id, relation="connects")
        print(
            f"     Hallway-North connects to: "
            f"{', '.join(n.label for n in neighbors)}"
        )

        print(f"     Context: {q.context_summary()}")

        # Confirm 5 unique locations (3 from A + 2 new from B; Room-102 deduped)
        assert store_a.node_count() == 5, (
            f"Expected 5 unique locations after merge, got {store_a.node_count()}"
        )
        print("     Assertion passed: 5 unique locations in combined map")
    finally:
        store_a.close()
        store_b.close()


# ---------------------------------------------------------------------------
# Part 2 — agentcrdt: LWW belief merge + semantic contradiction detection
# ---------------------------------------------------------------------------

def demo_agentcrdt(tmp: Path) -> None:
    _section("PART 2 — agentcrdt: Conflicting Beliefs & LWW Resolution")

    db_a = str(tmp / "robot-a-world.db")
    db_b = str(tmp / "robot-b-world.db")
    db_c = str(tmp / "robot-c-world.db")

    # ── Robot-A believes cart is in Room-101 (observed first) ───────────────
    _step("Robot-A records: medication cart is in Room-101")

    cart_in_101_a = WorldFact(
        domain="location",
        entity="medication-cart",
        attribute="cart_location",
        value="Room-101",
        version=1,
        agent_id="Robot-A",
        timestamp=time.time(),
    )
    room_101_occupied = WorldFact(
        domain="occupancy",
        entity="Room-101",
        attribute="occupied_by_cart",
        value=True,
        version=1,
        agent_id="Robot-A",
        timestamp=time.time(),
    )

    with WorldStore(db_a) as store:
        store.set_fact(cart_in_101_a)
        store.set_fact(room_101_occupied)
        print(f"     Robot-A world: {len(store.list_facts())} fact(s)")

    # ── Robot-B believes cart is in Room-102 (slightly later, higher version) -
    _step("Robot-B records: medication cart is in Room-102 (newer observation)")

    cart_in_102_b = WorldFact(
        domain="location",
        entity="medication-cart",
        attribute="cart_location",
        value="Room-102",
        version=2,              # higher version — more recent scan
        agent_id="Robot-B",
        timestamp=time.time() + 1,
    )
    room_102_occupied = WorldFact(
        domain="occupancy",
        entity="Room-102",
        attribute="occupied_by_cart",
        value=True,
        version=2,
        agent_id="Robot-B",
        timestamp=time.time() + 1,
    )

    with WorldStore(db_b) as store:
        store.set_fact(cart_in_102_b)
        store.set_fact(room_102_occupied)
        print(f"     Robot-B world: {len(store.list_facts())} fact(s)")

    # ── Robot-C agrees with Robot-B (same version, later timestamp) ─────────
    _step("Robot-C records: medication cart is in Room-102 (corroborates B)")

    cart_in_102_c = WorldFact(
        domain="location",
        entity="medication-cart",
        attribute="cart_location",
        value="Room-102",
        version=2,
        agent_id="Robot-C",
        timestamp=time.time() + 2,
    )

    with WorldStore(db_c) as store:
        store.set_fact(cart_in_102_c)

    # ── Define SemanticRule: cart cannot be in two rooms simultaneously ──────
    _step(
        "Defining SemanticRule: if Room-101 occupied_by_cart=True, "
        "Room-102 must have occupied_by_cart=False (and vice versa)"
    )

    # Rule fires when Room-101 is marked occupied AND Room-102 is also occupied
    # We model this as: if entity=Room-101 occupied_by_cart=True then
    # entity=Room-102 must have occupied_by_cart=False.
    # implies_entity_same=False lets the rule check a *different* entity.
    cart_conflict_rule = SemanticRule(
        name="single-room-cart-constraint",
        trigger_domain="occupancy",
        trigger_attribute="occupied_by_cart",
        trigger_value=True,
        implies_domain="occupancy",
        implies_entity_same=False,
        implies_attribute="occupied_by_cart",
        implies_value=False,
    )
    engine = RuleEngine(rules=[cart_conflict_rule])

    # ── Merge all three views: B into A, then C into A ──────────────────────
    _step("Merging Robot-B world into Robot-A (with semantic rule checking)")

    with WorldStore(db_a) as local, WorldStore(db_b) as remote:
        result_ab = WorldMerger(rule_engine=engine).merge(local, remote)

    print(f"     Merged {result_ab.merged_count} fact(s) from Robot-B into Robot-A")
    print(f"     Contradictions detected: {len(result_ab.conflicts)}")
    if result_ab.conflicts:
        for c in result_ab.conflicts:
            print(f"     [!] Rule '{c.rule}' fired: agents {c.agent_a} vs {c.agent_b}")

    _step("Merging Robot-C world into Robot-A (LWW resolves cart_location)")

    with WorldStore(db_a) as local, WorldStore(db_c) as remote:
        result_ac = WorldMerger(rule_engine=engine).merge(local, remote)

    print(f"     Merged {result_ac.merged_count} fact(s) from Robot-C into Robot-A")

    # ── Inspect final resolved state ─────────────────────────────────────────
    _step("Inspecting resolved world state after LWW merge")

    with WorldStore(db_a) as store:
        all_facts = store.list_facts()
        events = store.list_events()

        cart_fact = store.get_fact_by_key("location", "medication-cart", "cart_location")
        assert cart_fact is not None, "cart_location fact missing"

        print(f"     Total facts in merged world: {len(all_facts)}")
        print(
            f"     LWW winner for cart_location: '{cart_fact.value}' "
            f"(version={cart_fact.version}, agent={cart_fact.agent_id})"
        )
        print(f"     Total contradiction events stored: {len(events)}")

    # LWW: Robot-B/C (version=2) beats Robot-A (version=1) → cart in Room-102
    assert cart_fact.value == "Room-102", (
        f"Expected LWW to resolve cart_location='Room-102', got '{cart_fact.value}'"
    )
    print(
        "     Assertion passed: LWW correctly resolved cart to Room-102 "
        "(version 2 beats version 1)"
    )


# ---------------------------------------------------------------------------
# Part 3 — groundcrew: deterministic action receipt + StateSnapshot audit
# ---------------------------------------------------------------------------

def demo_groundcrew(tmp: Path) -> None:
    _section("PART 3 — groundcrew: Deterministic Delivery Receipt & Audit")

    # We simulate Robot-A's delivery state using JSON files in a work directory.
    workdir = tmp / "robot-a-workdir"
    workdir.mkdir(parents=True, exist_ok=True)
    receipt_db = tmp / "receipts.db"

    # ── Set up initial room state ("pending") ────────────────────────────────
    _step("Setting initial room state: Room-101 delivery_status = pending")

    room_state_file = workdir / "room_101_state.json"
    room_state_file.write_text(
        json.dumps({"room": "Room-101", "delivery_status": "pending", "cart_present": False})
    )

    delivery_log = workdir / "delivery_log.jsonl"
    delivery_log.write_text("")       # empty log

    print(f"     Wrote initial state: {room_state_file.name}")
    print(f"     Files in workdir before delivery: {[f.name for f in workdir.iterdir()]}")

    # ── Define the ActionSpec ────────────────────────────────────────────────
    _step(
        "Defining ActionSpec: Robot-A delivers medication to Room-101 at 14:32"
    )

    spec = ActionSpec(
        verb="deliver",
        target="Room-101",
        params={
            "robot_id": "Robot-A",
            "item": "medication",
            "scheduled_time": "14:32",
            "patient_id": "P-4471",
        },
    )
    print(f"     ActionSpec ID: {spec.id}")
    print(f"     Verb: {spec.verb}  Target: {spec.target}")
    print(f"     Params: {json.dumps(spec.params)}")

    # ── Oracle: capture before snapshot, perform delivery, capture after ─────
    _step(
        "Oracle capturing StateSnapshot before delivery, performing delivery, "
        "then capturing snapshot after"
    )

    oracle = Oracle(str(workdir), spec)
    with oracle:
        # --- Simulate the actual delivery work ---
        # 1. Update room state to "delivered"
        room_state_file.write_text(
            json.dumps({
                "room": "Room-101",
                "delivery_status": "delivered",
                "cart_present": False,
                "delivered_at": "14:32",
            })
        )
        # 2. Append entry to delivery log
        with delivery_log.open("a") as fh:
            fh.write(
                json.dumps({
                    "robot": "Robot-A",
                    "room": "Room-101",
                    "item": "medication",
                    "timestamp": "14:32",
                    "patient_id": "P-4471",
                }) + "\n"
            )

    receipt = oracle.record(spec)

    # ── Inspect the receipt ──────────────────────────────────────────────────
    _step("Inspecting ActionReceipt")

    print(f"     Receipt ID:      {receipt.id}")
    print(f"     Success:         {receipt.success}")
    print(f"     Before snapshot: {receipt.before_id}")
    print(f"     After snapshot:  {receipt.after_id}")
    assert receipt.before_id != receipt.after_id, (
        "before/after snapshot IDs must differ — delivery changed state"
    )
    print("     Assertion passed: before_id != after_id (state changed)")

    changed = receipt.diff.changed_paths
    print(f"     Changed paths:   {changed}")
    assert "room_101_state.json" in changed, (
        "room_101_state.json must appear in diff.changed_paths"
    )
    assert "delivery_log.jsonl" in changed, (
        "delivery_log.jsonl must appear in diff.changed_paths"
    )
    print("     Assertion passed: both room state and delivery log appear in diff")

    # Confirm state transition in the diff
    modified_map = {
        before.path: (before, after)
        for before, after in receipt.diff.modified
    }
    if "room_101_state.json" in modified_map:
        before_fs, after_fs = modified_map["room_101_state.json"]
        print(
            f"     room_101_state.json digest: "
            f"{before_fs.sha256[:8]}... -> {after_fs.sha256[:8]}... "
            f"(content changed: pending -> delivered)"
        )

    # ── Persist receipt in ReceiptStore for audit ────────────────────────────
    _step("Saving ActionReceipt to ReceiptStore for audit trail")

    receipt_store = ReceiptStore(str(receipt_db))
    try:
        receipt_store.save(receipt)

        retrieved = receipt_store.get(receipt.id)
        assert retrieved is not None, "Receipt not found in store after save"
        assert retrieved.id == receipt.id, "Retrieved receipt ID mismatch"
        assert retrieved.spec.verb == "deliver", "Spec verb not preserved on round-trip"
        assert retrieved.spec.target == "Room-101", "Spec target not preserved on round-trip"

        print(f"     Saved and retrieved receipt {retrieved.id}")
        print(
            f"     Stored spec: verb='{retrieved.spec.verb}', "
            f"target='{retrieved.spec.target}'"
        )
        print(
            f"     Params round-tripped: "
            f"robot_id='{retrieved.spec.params['robot_id']}', "
            f"item='{retrieved.spec.params['item']}'"
        )

        all_receipts = receipt_store.list_receipts()
        print(f"     Total receipts in audit store: {len(all_receipts)}")
        assert len(all_receipts) == 1, "Expected exactly 1 receipt in store"
    finally:
        receipt_store.close()

    print("\n     Audit summary:")
    print(f"       Action : {retrieved.spec.verb} {retrieved.spec.target}")
    print(f"       Robot  : {retrieved.spec.params['robot_id']}")
    print(f"       Item   : {retrieved.spec.params['item']}")
    print(f"       Files changed: {len(receipt.diff.added) + len(receipt.diff.modified)}")
    print(f"       Receipt ID: {retrieved.id} (deterministic, content-addressed)")


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Run the full hospital robot fleet coordination integration demo."""
    print("\n" + "#" * 60)
    print("#  Hospital Robot Fleet Coordination Demo")
    print("#  polaroid  +  agentcrdt  +  groundcrew")
    print("#" * 60)

    with tempfile.TemporaryDirectory() as tmp_str:
        tmp = Path(tmp_str)

        demo_polaroid(tmp)
        demo_agentcrdt(tmp)
        demo_groundcrew(tmp)

    _section("COMPLETE")
    print("\n  All three library integrations ran successfully.")
    print("  polaroid  : 5-location CRDT map merged from 2 robots")
    print("  agentcrdt : LWW resolved cart to Room-102 (version 2 wins)")
    print("  groundcrew: delivery receipt recorded + audited with snapshot diff")
    print()


if __name__ == "__main__":
    main()
