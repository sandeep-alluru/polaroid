# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- `export.py`: `to_dot()`, `to_json()`, `to_adjacency_matrix()` for scene graph export
- `subgraph.py`: `extract_subgraph()`, `filter_by_type()`, `neighborhood()` for subgraph operations
- `stats.py`: `GraphStats`, `compute_stats()`, `cluster_by_type()`, `most_connected()` for graph analytics
- CLI commands: `polaroid stats` and `polaroid export --format dot|json`

## [0.1.0] - 2026-06-18

### Added
- Content-addressed `SceneNode` and `SceneEdge` dataclasses (SHA-256[:16] IDs)
- SQLite-backed `SceneStore` with confidence-weighted upsert semantics
- `SceneMerger` implementing CRDT grow-only set + confidence-weighted LWW register merge
- `SceneQuery` with `find_nodes`, `find_neighbors`, and `context_summary`
- Rich/JSON/Markdown formatters in `report.py`
- Click CLI: `add-node`, `add-edge`, `query`, `merge`, `status`
- FastAPI REST server (`/node`, `/edge`, `/nodes`, `/merge`, `/context`, `/health`)
- MCP server with `add_scene_node`, `query_nodes`, `get_context` tools
- 202 unit tests, 86% branch coverage
- `examples/demo.py` end-to-end demonstration

[Unreleased]: https://github.com/sandeep-alluru/polaroid/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/sandeep-alluru/polaroid/releases/tag/v0.1.0
