# polaroid — Session Anchor

**Research spec:** `../tech-research/12-Embodied-and-Physical-World/polaroid-a-persistent-shared-spatial-semantic-memory-la/README.md`  
**One-liner:** SQLite-moment for physical-world memory — embeddable CRDT scene graph + universal sensor broker  
**Phase:** backlog  
**Stack:** Python, automerge-py (or py-crdt), paho-mqtt  

## Key decisions
<!-- fill in as decisions are made during build sessions -->

## Next step
Read the research spec, then evaluate automerge-py vs py-crdt for the scene graph backend.

## MVP definition
- `pip install polaroid` works
- Embeddable spatiotemporal scene graph (nodes = physical entities, edges = spatial relationships)
- CRDT-merged across multiple writers (no coordination overhead)
- MQTT sensor adapter (paho-mqtt)
- NL query interface: `polaroid.query("what's near the door?")`
- Demo: two concurrent Python processes write conflicting entity positions → merge without error
- README with warehouse/robotics example
