# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
- 114 unit tests, 86% branch coverage
- `examples/demo.py` end-to-end demonstration

[Unreleased]: https://github.com/sandeep-alluru/polaroid/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/sandeep-alluru/polaroid/releases/tag/v0.1.0
