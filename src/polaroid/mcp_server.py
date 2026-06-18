"""MCP server for polaroid.

Start:  python -m polaroid.mcp_server
Or:     polaroid-mcp

Add to Claude Desktop (~/.config/claude/claude_desktop_config.json):
    {
        "mcpServers": {
            "polaroid": {
                "command": "polaroid-mcp"
            }
        }
    }
"""

from __future__ import annotations

import sys
from typing import Any


def _require_mcp() -> Any:
    try:
        import mcp.server.stdio
        import mcp.types as types
        from mcp.server import Server as _Server

        return mcp, types, _Server
    except ImportError:
        print(
            "MCP server requires: pip install 'polaroid[mcp]'",
            file=sys.stderr,
        )
        sys.exit(1)


def run_server() -> None:
    """Start the MCP server on stdio."""
    mcp_mod, types, server_cls = _require_mcp()

    from polaroid.graph import SceneNode
    from polaroid.query import SceneQuery
    from polaroid.store import SceneStore

    server = server_cls("polaroid")

    @server.list_tools()
    async def list_tools() -> list[types.Tool]:
        return [
            types.Tool(
                name="add_scene_node",
                description="Add or update a node in the polaroid scene graph.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "label": {"type": "string"},
                        "node_type": {"type": "string"},
                        "properties": {"type": "object"},
                        "confidence": {"type": "number"},
                        "agent_id": {"type": "string"},
                        "db": {"type": "string"},
                    },
                    "required": ["label", "node_type"],
                },
            ),
            types.Tool(
                name="query_nodes",
                description="Query scene graph nodes by type, label, or confidence.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "node_type": {"type": "string"},
                        "label_contains": {"type": "string"},
                        "min_confidence": {"type": "number"},
                        "db": {"type": "string"},
                    },
                },
            ),
            types.Tool(
                name="get_context",
                description="Get a text summary of the current scene graph.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "agent_id": {"type": "string"},
                        "db": {"type": "string"},
                    },
                },
            ),
        ]

    @server.call_tool()
    async def call_tool(
        name: str, arguments: dict[str, Any]
    ) -> list[types.TextContent]:
        db = arguments.get("db", ".polaroid/scene.db")

        if name == "add_scene_node":
            node = SceneNode(
                label=arguments["label"],
                node_type=arguments["node_type"],
                properties=arguments.get("properties", {}),
                confidence=arguments.get("confidence", 1.0),
                agent_id=arguments.get("agent_id", ""),
            )
            with SceneStore(db) as store:
                store.upsert_node(node)
            return [types.TextContent(type="text", text=f"Added node {node.id}: {node.label}")]

        if name == "query_nodes":
            with SceneStore(db) as store:
                q = SceneQuery(store)
                nodes = q.find_nodes(
                    node_type=arguments.get("node_type"),
                    label_contains=arguments.get("label_contains"),
                    min_confidence=arguments.get("min_confidence", 0.0),
                )
            lines = [f"{n.label} ({n.node_type}, conf={n.confidence:.2f})" for n in nodes]
            return [types.TextContent(type="text", text="\n".join(lines) or "No nodes found.")]

        if name == "get_context":
            with SceneStore(db) as store:
                q = SceneQuery(store)
                summary = q.context_summary(agent_id=arguments.get("agent_id", ""))
            return [types.TextContent(type="text", text=summary)]

        raise ValueError(f"Unknown tool: {name}")

    import asyncio

    async def _main() -> None:
        async with mcp_mod.server.stdio.stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream, server.create_initialization_options())

    asyncio.run(_main())


if __name__ == "__main__":
    run_server()
