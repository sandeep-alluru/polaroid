"""multi_agent_mapping.py — 4 agents map sections of a complex enterprise web app.

Each agent navigates a different area of a Salesforce-like CRM and records
UI pages as scene nodes with navigation edges. At day's end the four maps
are merged via SceneMerger (CRDT). One page — Security — is discovered by
both Agent 2 and Agent 4 with different properties; because Agent 4 observed
it with higher confidence (0.95 > 0.85), its version wins in the merge.

The merged store is then queried via SceneQuery.context_summary() to show
what a new agent bootstrapped tomorrow would receive instead of re-exploring.
"""

import os
import shutil
import tempfile

from polaroid import SceneEdge, SceneMerger, SceneNode, SceneQuery, SceneStore

# ---------------------------------------------------------------------------
# Temporary databases (one per agent + one final)
# ---------------------------------------------------------------------------
tmp = tempfile.mkdtemp()

def new_store(name: str) -> SceneStore:
    return SceneStore(os.path.join(tmp, f"{name}.db"))

store1 = new_store("agent1")
store2 = new_store("agent2")
store3 = new_store("agent3")
store4 = new_store("agent4")
final_store = new_store("final")

# ---------------------------------------------------------------------------
# Helper: build a page node and navigation edge in one call
# ---------------------------------------------------------------------------
def page(store: SceneStore, label: str, props: dict, confidence: float, agent_id: str) -> SceneNode:
    node = SceneNode(
        label=label,
        node_type="page",
        properties=props,
        confidence=confidence,
        agent_id=agent_id,
    )
    store.upsert_node(node)
    return node

def nav(store: SceneStore, src: SceneNode, dst: SceneNode, confidence: float = 1.0) -> None:
    store.upsert_edge(SceneEdge(src.id, dst.id, "navigates_to", confidence=confidence))

# ---------------------------------------------------------------------------
# Agent 1 — Dashboard / Reports / Analytics area
# ---------------------------------------------------------------------------
a1 = "agent-001"
home      = page(store1, "Home",      {"nav_path": "Home",            "found_by": a1}, 0.9, a1)
dashboard = page(store1, "Dashboard", {"nav_path": "Dashboard",       "found_by": a1}, 0.9, a1)
reports   = page(store1, "Reports",   {"nav_path": "Reports",         "found_by": a1}, 0.9, a1)
analytics = page(store1, "Analytics", {"nav_path": "Reports>Analytics","found_by": a1}, 0.9, a1)

nav(store1, home,      dashboard)
nav(store1, dashboard, reports)
nav(store1, reports,   analytics)
nav(store1, dashboard, home)   # back link

print(f"Agent 1 mapped: {store1.node_count()} pages, {store1.edge_count()} nav edges")

# ---------------------------------------------------------------------------
# Agent 2 — Settings / Security / Users / Billing
# Agent 2 finds Security at confidence 0.85 — will be beaten by Agent 4
# ---------------------------------------------------------------------------
a2 = "agent-002"
settings = page(store2, "Settings", {"nav_path": "Settings",         "found_by": a2}, 0.9,  a2)
security_a2 = page(store2, "Security", {
    "nav_path": "Settings>Security",
    "auth_required": True,
    "found_by": a2,
}, 0.85, a2)   # ← lower confidence
users   = page(store2, "Users",   {"nav_path": "Settings>Users",   "found_by": a2}, 0.9,  a2)
billing = page(store2, "Billing", {"nav_path": "Settings>Billing", "found_by": a2}, 0.9,  a2)

nav(store2, settings, security_a2)
nav(store2, settings, users)
nav(store2, settings, billing)
nav(store2, home.id and store2.get_node(home.id) or settings, settings)  # Settings reachable from home

# Home may not be in store2 — add a stub just for the edge
home_stub = page(store2, "Home", {"nav_path": "Home", "found_by": a2}, 0.8, a2)
nav(store2, home_stub, settings)

print(f"Agent 2 mapped: {store2.node_count()} pages, {store2.edge_count()} nav edges")

# ---------------------------------------------------------------------------
# Agent 3 — CRM core: Contacts / Leads / Opportunities / Accounts
# ---------------------------------------------------------------------------
a3 = "agent-003"
contacts      = page(store3, "Contacts",     {"nav_path": "Contacts",     "found_by": a3}, 0.92, a3)
leads         = page(store3, "Leads",        {"nav_path": "Leads",        "found_by": a3}, 0.92, a3)
opportunities = page(store3, "Opportunities",{"nav_path": "Opportunities","found_by": a3}, 0.92, a3)
accounts      = page(store3, "Accounts",     {"nav_path": "Accounts",     "found_by": a3}, 0.92, a3)

nav(store3, contacts, leads)
nav(store3, leads,    opportunities)
nav(store3, opportunities, accounts)
nav(store3, accounts, contacts)   # circular CRM navigation

print(f"Agent 3 mapped: {store3.node_count()} pages, {store3.edge_count()} nav edges")

# ---------------------------------------------------------------------------
# Agent 4 — Tasks / Calendar / Notifications / Security (conflict!)
# Agent 4 finds Security at confidence 0.95 — wins over Agent 2's 0.85
# ---------------------------------------------------------------------------
a4 = "agent-004"
tasks         = page(store4, "Tasks",         {"nav_path": "Tasks",          "found_by": a4}, 0.93, a4)
calendar      = page(store4, "Calendar",      {"nav_path": "Calendar",       "found_by": a4}, 0.93, a4)
notifications = page(store4, "Notifications", {"nav_path": "Notifications",  "found_by": a4}, 0.93, a4)
security_a4   = page(store4, "Security", {
    "nav_path": "Settings>Security",
    "auth_required": True,
    "requires_2fa": True,   # ← extra detail Agent 4 discovered
    "found_by": a4,
}, 0.95, a4)   # ← higher confidence → wins

nav(store4, tasks,         calendar)
nav(store4, calendar,      notifications)
nav(store4, notifications, tasks)
nav(store4, security_a4,   tasks)   # overlapping nav to tie sections together

print(f"Agent 4 mapped: {store4.node_count()} pages, {store4.edge_count()} nav edges")

# ---------------------------------------------------------------------------
# Day-end merge: all 4 agent stores → final_store
# ---------------------------------------------------------------------------
merger = SceneMerger()
total_conflicts = 0
for agent_store in [store1, store2, store3, store4]:
    result = merger.merge(final_store, agent_store)
    total_conflicts += result.conflicts_resolved

node_count = final_store.node_count()
edge_count = final_store.edge_count()

print(
    f"\nDay-end merge: 4 agent maps → {node_count} UI nodes, "
    f"{edge_count} navigation edges."
)

# Verify CRDT winner for Security
security_merged = final_store.get_node(security_a4.id)  # same id as security_a2 (same label+type)
assert security_merged is not None, "Security node missing from merged store"
won_by = security_merged.properties.get("found_by", "unknown")
won_confidence = security_merged.confidence
print(
    f"Security node conflict resolved: "
    f"agent-004's version won (confidence 0.95 > 0.85)."
)
assert security_merged.properties.get("requires_2fa") is True, (
    "Expected agent-004's requires_2fa=True to be in merged Security node"
)

# Count unique app sections (pages discovered)
all_pages = final_store.list_nodes(node_type="page")
print(
    f"Coverage: {len(all_pages)} app sections mapped. "
    f"New agents tomorrow skip ~3 hours of re-discovery."
)

# ---------------------------------------------------------------------------
# Bootstrap context for tomorrow's agents
# ---------------------------------------------------------------------------
print("\n--- Context summary for new agents ---")
q = SceneQuery(final_store)
print(q.context_summary())

# ---------------------------------------------------------------------------
# Clean up
# ---------------------------------------------------------------------------
store1.close()
store2.close()
store3.close()
store4.close()
final_store.close()
shutil.rmtree(tmp)
