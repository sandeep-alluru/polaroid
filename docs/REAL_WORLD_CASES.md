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

## Case PATH-INJECTION (CodeQL py/path-injection) — HIGH

**Source:** GitHub Code Scanning alert
https://github.com/sandeep-alluru/polaroid/security/code-scanning/1

**What failed:** REST/MCP `db` query/body fields were passed straight into
`SceneStore(path)` → `Path(path).parent.mkdir` / `sqlite3.connect`, so a caller
could open or create files outside the intended data directory
(`../../../etc/passwd` class).

**Product fix:**

| Control | API |
|---------|-----|
| Path confine | `safe_db_path` / `POLAROID_DATA_DIR` (default `.polaroid`) |
| Store gate | `SceneStore(..., data_root=)` rejects escapes (`PathEscapeError`) |
| HTTP | API maps escape → **400** |

**Tests:** `tests/test_path_injection.py`

---

## Case LINE-OF-SIGHT — observe/target without visibility path

**Source:** Track B embodied / computer-use spatial failures (PRIMAL3 pathfinding
class + CUA agents that click/observe through walls). Twin of `gate_navigable`
(room connectivity) for **visibility**.

**What fails:**

1. Agents claim they can **see** or **click** a target when no `sees` /
   visibility path exists in the scene graph.
2. Occluders (`occludes`, `blocks-view`) sit on the only path to the target.
3. Navigation connectivity alone is treated as LOS.

**Product in this repo:**

| Control | API |
|---------|-----|
| LOS relations | `LOS_RELATIONS` / `OCCLUSION_RELATIONS` |
| Predicate | `has_line_of_sight(store, observer, target)` |
| Gate | `gate_line_of_sight(...)` |
| Raise form | `assert_line_of_sight` |

**Rules (load-bearing):**

- Empty scene / missing nodes → **FAIL_LOUD**
- No LOS path (sees/nav BFS, occluders cut) → **FAIL**
- Direct `sees` or clear path → **PASS**

**Tests:** `tests/test_line_of_sight.py`

**Non-Ornament:** Call `gate_line_of_sight` before observe/target/click on
embodied or GUI-mapped scene graphs. Pair with `gate_navigable` and
`clickproof.gate_click_attempt`.

---

## Related IDs

- **DETACHED-PART** / **EMPTY-SCENE** — this case
- **LINE-OF-SIGHT** — visibility path (this section)
- agentcrdt CONST-AS-STATE — refuse wrong class of state (sibling discipline)
