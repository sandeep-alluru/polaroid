"""game_world_agent.py — A game agent builds a scene graph of an RPG world.

The agent starts in a starting village, discovers locations, NPCs, and items,
then ventures into a dungeon. It uses SceneQuery to answer gameplay questions
and models NPC movement via property updates (the store is grow-only, so
old edges remain, but the node's properties reflect the current state).
"""

import collections
import os
import shutil
import tempfile

from polaroid import SceneEdge, SceneNode, SceneQuery, SceneStore

# ---------------------------------------------------------------------------
# Temporary database
# ---------------------------------------------------------------------------
tmp = tempfile.mkdtemp()
store = SceneStore(os.path.join(tmp, "game_world.db"))

# ---------------------------------------------------------------------------
# Helper: build a node and upsert it, return the node
# ---------------------------------------------------------------------------
def make_node(label, node_type, properties=None, confidence=1.0, agent_id="game-agent"):
    node = SceneNode(
        label=label,
        node_type=node_type,
        properties=properties or {},
        confidence=confidence,
        agent_id=agent_id,
    )
    store.upsert_node(node)
    return node

def make_edge(source, target, relation, confidence=1.0):
    edge = SceneEdge(source.id, target.id, relation, confidence=confidence)
    store.upsert_edge(edge)
    return edge

# ---------------------------------------------------------------------------
# Starting village — locations
# ---------------------------------------------------------------------------
tavern      = make_node("Tavern",      "location", {"description": "The local inn and gathering spot"})
blacksmith  = make_node("Blacksmith",  "location", {"description": "Weapons and armor forged here"})
market      = make_node("Market",      "location", {"description": "Merchants trade goods and rumors"})

# NPCs
bob     = make_node("Old Man Bob",   "npc", {"gives_quest": True,  "quest": "Find the lost sword", "location": "Tavern"})
alice   = make_node("Merchant Alice","npc", {"gives_quest": True,  "quest": "Deliver spices",      "location": "Market"})
tom     = make_node("Guard Tom",     "npc", {"gives_quest": False, "role": "guard",                "location": "Blacksmith"})
sue     = make_node("Innkeeper Sue", "npc", {"gives_quest": False, "role": "innkeeper",            "location": "Tavern"})

# Items
iron_sword    = make_node("Iron Sword",    "item", {"damage": 15, "weight_kg": 3.5})
shield        = make_node("Shield",        "item", {"defense": 10, "weight_kg": 5.0})
health_potion = make_node("Health Potion", "item", {"hp_restore": 50, "count": 3})
spice_bundle  = make_node("Spice Bundle",  "item", {"rarity": "uncommon", "value_gp": 25})
torch         = make_node("Torch",         "item", {"burn_hours": 6, "light_radius_m": 8})
gold_coin     = make_node("Gold Coin",     "item", {"value_gp": 1, "count": 10})

# Village edges — has_npc
make_edge(tavern,     bob,     "has_npc")
make_edge(tavern,     sue,     "has_npc")
make_edge(blacksmith, tom,     "has_npc")
make_edge(market,     alice,   "has_npc")

# Village edges — has_item
make_edge(blacksmith, iron_sword,    "has_item")
make_edge(blacksmith, shield,        "has_item")
make_edge(market,     spice_bundle,  "has_item")
make_edge(market,     gold_coin,     "has_item")
make_edge(tavern,     health_potion, "has_item")
make_edge(tavern,     torch,         "has_item")

# Village edges — connects_to
make_edge(tavern,     blacksmith, "connects_to")
make_edge(blacksmith, market,     "connects_to")

print(f"Village mapped: {store.node_count()} nodes, {store.edge_count()} edges")

# ---------------------------------------------------------------------------
# Dungeon — agent moves there
# ---------------------------------------------------------------------------
dungeon_entrance  = make_node("Dungeon Entrance",   "room", {"danger": "low",    "lit": False})
dark_corridor     = make_node("Dark Corridor",      "room", {"danger": "medium", "lit": False})
treasure_chamber  = make_node("Treasure Chamber",   "room", {"danger": "high",   "lit": False, "locked": True})

cave_troll  = make_node("Cave Troll",  "enemy", {"hp": 100, "drops": "Gold Coin",  "level": 8})
shadow_bat  = make_node("Shadow Bat",  "enemy", {"hp": 20,  "drops": "nothing",    "level": 2})
chest       = make_node("Ancient Treasure Chest", "item", {"contains": "legendary sword", "locked": True})

# Dungeon structure edges
make_edge(dungeon_entrance, dark_corridor,    "connects_to")
make_edge(dark_corridor,    treasure_chamber, "connects_to")
make_edge(treasure_chamber, chest,            "has_item")
make_edge(dungeon_entrance, cave_troll,       "has_enemy")
make_edge(dark_corridor,    shadow_bat,       "has_enemy")

print(f"Dungeon mapped: {store.node_count()} nodes total, {store.edge_count()} edges total")

# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------
query = SceneQuery(store)

print("\n--- Query 1: Which NPCs can give quests? ---")
all_npcs = query.find_nodes(node_type="npc")
quest_givers = [n for n in all_npcs if n.properties.get("gives_quest") is True]
for npc in quest_givers:
    print(f"  {npc.label}: \"{npc.properties['quest']}\"")

print("\n--- Query 2: Find all items near the Tavern ---")
tavern_items = query.find_neighbors(tavern.id, relation="has_item")
item_labels = [n.label for n in tavern_items]
print(f"  Items at Tavern: {', '.join(item_labels)}")

print("\n--- Query 3: Shortest path from Dungeon Entrance to Treasure Chamber ---")
# BFS using find_neighbors (connects_to relation only — rooms connect to rooms)
start_id = dungeon_entrance.id
end_id   = treasure_chamber.id

visited: set[str] = {start_id}
queue: collections.deque[list[str]] = collections.deque([[start_id]])
path_ids: list[str] = []

while queue:
    path = queue.popleft()
    current = path[-1]
    if current == end_id:
        path_ids = path
        break
    for neighbor in query.find_neighbors(current, relation="connects_to"):
        if neighbor.id not in visited:
            visited.add(neighbor.id)
            queue.append(path + [neighbor.id])

if path_ids:
    labels = []
    for nid in path_ids:
        n = store.get_node(nid)
        labels.append(n.label if n else nid)
    hops = len(labels) - 1
    print(f"  Path ({hops} hop{'s' if hops != 1 else ''}): {' → '.join(labels)}")
else:
    print("  No path found.")

# ---------------------------------------------------------------------------
# Game update: Old Man Bob moves to the Market
# ---------------------------------------------------------------------------
print("\n--- Game Update: Old Man Bob moves to Market ---")
# Update node properties to reflect new location
updated_bob = SceneNode(
    label="Old Man Bob",
    node_type="npc",
    properties={
        "gives_quest": True,
        "quest": "Find the lost sword",
        "location": "Market",        # ← updated
        "note": "Left the tavern after you accepted his quest",
    },
    confidence=1.0,   # same confidence — upsert_node replaces if >= existing
    agent_id="game-agent",
)
store.upsert_node(updated_bob)

# Add new edge: Market → Old Man Bob (store is grow-only; old Tavern edge remains)
make_edge(market, updated_bob, "has_npc")

# Verify
bob_now = store.get_node(bob.id)
print(f"  Bob's new location property: {bob_now.properties['location']}")
tavern_npcs = query.find_neighbors(tavern.id, relation="has_npc")
market_npcs = query.find_neighbors(market.id, relation="has_npc")
print(f"  NPCs still linked from Tavern (edge survives): {[n.label for n in tavern_npcs]}")
print(f"  NPCs now linked from Market: {[n.label for n in market_npcs]}")
print("  Note: Tavern→Bob edge remains (grow-only store). Bob's properties now say location=Market.")

# ---------------------------------------------------------------------------
# Clean up
# ---------------------------------------------------------------------------
store.close()
shutil.rmtree(tmp)
