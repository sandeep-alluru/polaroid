# Real-world cases driving polaroid

Mined from farm_memory (Qdrant) and public multi-agent pathfinding research.

## Case DETACHED-PART / EMPTY-SCENE (farm + embodied) — CRITICAL

**Source:** Qdrant `farm_memory` Roblox experiment — thruster parts not welded
to root; drifted under physics. eagle-eyes matrix: polaroid was **NONE** until
this cycle.

**What failed:**

1. **Detached parts:** Scene claims (properties `attached_to` / part types)
   without spatial attachment edges (`contains`, `welded-to`, …) → bodies
   fragment (thrusters beside robot).
2. **Empty / phantom map:** Agents navigate or merge with zero nodes → silent
   “map ok” ornament.
3. **Disconnected rooms:** Multi-room maps without `adjacent-to` / `connects`
   edges → pathfinding impossible (PRIMAL3 class).

**Public twins:**

| Case | Mapping |
|------|---------|
| PRIMAL3 pathfinding (arXiv 2608.04905) | Multi-agent spatial connectivity |
| Hierarchical spatial memory papers | Graph must be load-bearing, not empty |

**Product fix in this repo:**

| Control | API |
|---------|-----|
| Empty scene | `gate_scene` → FAIL_LOUD |
| Detached parts | `gate_scene` / `gate_attachment` → FAIL |
| Navigation | `gate_navigable` — rooms need nav edges |
| Raise forms | `assert_scene_ok`, `assert_attached` |

**Tests:** `tests/test_closed_loop_scene.py`

**Non-Ornament:** Call `gate_scene` before merge/nav; weld parts with real
edges, not only property strings.

---

## Related IDs

- **DETACHED-PART** / **EMPTY-SCENE** — this case
- agentcrdt CONST-AS-STATE — refuse wrong class of state (sibling discipline)
