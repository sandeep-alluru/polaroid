"""Command-line interface for scenemem."""

from __future__ import annotations

import click

from scenemem.graph import SceneEdge, SceneNode
from scenemem.merger import SceneMerger
from scenemem.query import SceneQuery
from scenemem.report import print_merge, print_scene, to_json
from scenemem.store import SceneStore


def _store(ctx: click.Context) -> SceneStore:
    """Return a SceneStore from the context or default path."""
    db_path = ctx.obj.get("db") if ctx.obj else ".scenemem/scene.db"
    return SceneStore(db_path)


@click.group()
@click.version_option(package_name="scenemem")
@click.option(
    "--db",
    default=".scenemem/scene.db",
    show_default=True,
    help="Path to the scenemem database.",
    envvar="SCENEMEM_DB",
)
@click.pass_context
def main(ctx: click.Context, db: str) -> None:
    """Embeddable CRDT scene graph for embodied AI agents.

    scenemem stores, merges, and queries spatial scene graphs so multiple
    robots/agents can share a persistent map without a central server.
    """
    ctx.ensure_object(dict)
    ctx.obj["db"] = db


@main.command("add-node")
@click.argument("label")
@click.argument("node_type")
@click.option("--confidence", type=float, default=1.0, show_default=True)
@click.option(
    "--property",
    "properties",
    multiple=True,
    metavar="K=V",
    help="Node property as KEY=VALUE. Repeat for multiple.",
)
@click.option("--agent-id", default="", help="Agent that observed this node.")
@click.pass_context
def add_node(
    ctx: click.Context,
    label: str,
    node_type: str,
    confidence: float,
    properties: tuple[str, ...],
    agent_id: str,
) -> None:
    """Add a node to the scene graph.

    \b
    Examples:
      scenemem add-node door-1 object --confidence 0.95 --property color=red
      scenemem add-node room-kitchen room
    """
    props: dict = {}
    for kv in properties:
        if "=" in kv:
            k, v = kv.split("=", 1)
            props[k] = v
        else:
            props[kv] = True

    node = SceneNode(
        label=label,
        node_type=node_type,
        properties=props,
        confidence=confidence,
        agent_id=agent_id,
    )
    with _store(ctx) as store:
        store.upsert_node(node)
    click.echo(f"Added node  {node.id}  {node.label}  ({node.node_type})")


@main.command("add-edge")
@click.argument("source")
@click.argument("target")
@click.argument("relation")
@click.option("--confidence", type=float, default=1.0, show_default=True)
@click.pass_context
def add_edge(
    ctx: click.Context,
    source: str,
    target: str,
    relation: str,
    confidence: float,
) -> None:
    """Add a directed edge between two nodes.

    SOURCE and TARGET are node IDs (16-char hex).

    \b
    Examples:
      scenemem add-edge <src-id> <tgt-id> contains
      scenemem add-edge <src-id> <tgt-id> adjacent-to --confidence 0.8
    """
    edge = SceneEdge(
        source_id=source,
        target_id=target,
        relation=relation,
        confidence=confidence,
    )
    with _store(ctx) as store:
        store.upsert_edge(edge)
    click.echo(f"Added edge  {edge.id}  {source[:8]}..  --{relation}-->  {target[:8]}..")


@main.command("query")
@click.option("--type", "node_type", default=None, help="Filter by node type.")
@click.option("--label", "label_contains", default=None, help="Filter label substring.")
@click.option(
    "--min-confidence",
    type=float,
    default=0.0,
    show_default=True,
    help="Minimum confidence threshold.",
)
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["rich", "json"]),
    default="rich",
    show_default=True,
)
@click.pass_context
def query(
    ctx: click.Context,
    node_type: str | None,
    label_contains: str | None,
    min_confidence: float,
    fmt: str,
) -> None:
    """Query nodes in the scene graph.

    \b
    Examples:
      scenemem query
      scenemem query --type object
      scenemem query --label door --min-confidence 0.8
    """
    with _store(ctx) as store:
        q = SceneQuery(store)
        nodes = q.find_nodes(
            node_type=node_type,
            label_contains=label_contains,
            min_confidence=min_confidence,
        )
        if fmt == "rich":
            print_scene(nodes)
        else:
            click.echo(to_json(nodes))


@main.command("merge")
@click.argument("other_db")
@click.pass_context
def merge(ctx: click.Context, other_db: str) -> None:
    """Merge another scene store into this one.

    OTHER_DB is the path to the remote/peer database file.

    \b
    Examples:
      scenemem merge /path/to/robot2.db
    """
    with _store(ctx) as local, SceneStore(other_db) as remote:
        merger = SceneMerger()
        result = merger.merge(local, remote)
        print_merge(result)


@main.command("status")
@click.pass_context
def status(ctx: click.Context) -> None:
    """Show node and edge counts in the scene store."""
    with _store(ctx) as store:
        q = SceneQuery(store)
        summary = q.context_summary()
        nc = store.node_count()
        ec = store.edge_count()
        click.echo(f"Nodes: {nc}  Edges: {ec}")
        click.echo(summary)


if __name__ == "__main__":
    main()
