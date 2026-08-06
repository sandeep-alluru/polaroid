# Closed loop — `polaroid`

**Status:** reader wired (eagle-eyes / 2026-08-06) — **DETACHED-PART / EMPTY-SCENE**  
**Owner loop:** Embodied only

## Load-bearing job

CRDT spatial scene graph for embodied agents

## Who reads the output?

- `gate_scene` / `gate_attachment` / `gate_navigable`
- Peer agents merge scene; navigation uses graph **after** gate

## What outcome changes?

Empty map → FAIL_LOUD. Detached parts without weld edges → FAIL.
Disconnected multi-room maps → FAIL. Shared map without central server when
structure is real.

## When NOT to use (anti-ornament)

Not for non-spatial content pipelines

## Non-Ornament checklist

- [x] Reader implemented (`closed_loop.gate_scene` + attachment/nav)
- [x] Empty/wrong output fails loudly
- [x] Not free MCP without gate
- [ ] Linked gap IDs in mem0 when improving

## Related failures (farm memory)

- 2026-07-22 MCP buffet trim: write-only tools removed from Foundry framework
- D-FOGHORN: misuse of append-only fact log as current state
- Dual-path mem0: never rely on MCP-only for critical memory

## Daily rotation note

This file exists so pillar **C (closed loop)** can rise with real wiring over time. Prefer small daily commits that move a checkbox toward done.

## Auto-run 2026-08-04
- pytest_rc: 0
- node: clawer-samurai-2

## Auto-run 2026-08-04
- pytest_rc: 0
- node: clawer-samurai-2

## Auto-run 2026-08-04
- pytest_rc: 0
- node: clawer-samurai-2

## Auto-run 2026-08-04
- pytest_rc: 0
- node: clawer-samurai-2

## Auto-run 2026-08-04
- pytest_rc: 0
- node: clawer-samurai-2

## Auto-run 2026-08-04
- pytest_rc: 0
- node: clawer-samurai-2

## Auto-run 2026-08-05
- pytest_rc: 0
- node: clawer-samurai-2

## Auto-run 2026-08-05
- pytest_rc: 0
- node: clawer-samurai-2

## Auto-run 2026-08-05
- pytest_rc: 0
- node: clawer-samurai-2

## Auto-run 2026-08-05
- pytest_rc: 0
- node: clawer-samurai-2

## Auto-run 2026-08-05
- pytest_rc: 0
- node: clawer-samurai-2

## Auto-run 2026-08-06
- pytest_rc: 0
- node: clawer-samurai-2

## Auto-run 2026-08-06
- pytest_rc: 0
- node: clawer-samurai-2

## Auto-run 2026-08-06
- pytest_rc: 0
- node: clawer-samurai-2

## Auto-run 2026-08-06
- pytest_rc: 0
- node: clawer-samurai-2
