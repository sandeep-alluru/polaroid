"""
End-to-end smoke test for scenemem.

Simulates a user who just cloned the repo and wants to verify everything works.
No mocking, no fixtures — real behaviour, real CLI, real HTTP server.

Run from repo root:
    python smoke_test.py
    python smoke_test.py --verbose

Exit 0 = all passed. Exit 1 = at least one failure.
"""

from __future__ import annotations

import importlib
import json
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path

# ── Colours ───────────────────────────────────────────────────────────────────

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

VERBOSE = "--verbose" in sys.argv or "-v" in sys.argv
REPO_ROOT = Path(__file__).parent
PYTHON = sys.executable

passed: list[str] = []
failed: list[tuple[str, str]] = []


def ok(name: str) -> None:
    passed.append(name)
    print(f"  {GREEN}✓{RESET} {name}")


def fail(name: str, reason: str) -> None:
    failed.append((name, reason))
    print(f"  {RED}✗{RESET} {name}")
    if VERBOSE:
        print(f"    {YELLOW}{reason}{RESET}")


def section(title: str) -> None:
    print(f"\n{BOLD}{title}{RESET}")


def run(name: str, fn):  # noqa: ANN001
    try:
        fn()
        ok(name)
    except Exception as exc:
        reason = str(exc) if not VERBOSE else traceback.format_exc().strip()
        fail(name, reason)


# ── 1. Package import ─────────────────────────────────────────────────────────

section("1. Package import")


def _test_import_version():
    import scenemem
    assert scenemem.__version__, "__version__ is empty"
    assert scenemem.__version__ != "0.0.0"


def _test_import_public_api():
    from scenemem import MergeResult, SceneEdge, SceneMerger, SceneNode, SceneQuery, SceneStore
    assert callable(SceneMerger)
    assert callable(SceneQuery)


run("scenemem package imports", _test_import_version)
run("Public API (SceneNode, SceneEdge, SceneMerger, SceneQuery, SceneStore)", _test_import_public_api)


# ── 2. Core data model ────────────────────────────────────────────────────────

section("2. Core data model (SceneNode, SceneEdge, SceneStore)")


def _test_node_content_addressed():
    from scenemem.graph import SceneNode
    n1 = SceneNode(label="door-1", node_type="object", properties={})
    n2 = SceneNode(label="door-1", node_type="object", properties={})
    assert n1.id == n2.id, "Same label+type must produce same ID"
    n3 = SceneNode(label="door-2", node_type="object", properties={})
    assert n1.id != n3.id


def _test_node_serialization():
    from scenemem.graph import SceneNode
    n = SceneNode(label="table-A", node_type="object", properties={"color": "brown"}, confidence=0.9)
    d = n.to_dict()
    assert d["label"] == "table-A"
    assert d["confidence"] == 0.9
    n2 = SceneNode.from_dict(d)
    assert n2.id == n.id
    assert n2.properties["color"] == "brown"


def _test_edge_content_addressed():
    from scenemem.graph import SceneEdge
    e1 = SceneEdge(source_id="aaa", target_id="bbb", relation="contains")
    e2 = SceneEdge(source_id="aaa", target_id="bbb", relation="contains")
    assert e1.id == e2.id
    e3 = SceneEdge(source_id="aaa", target_id="bbb", relation="adjacent-to")
    assert e1.id != e3.id


def _test_edge_serialization():
    from scenemem.graph import SceneEdge
    e = SceneEdge(source_id="src", target_id="tgt", relation="on-top-of", confidence=0.7)
    d = e.to_dict()
    e2 = SceneEdge.from_dict(d)
    assert e2.id == e.id
    assert e2.confidence == 0.7


def _test_store_upsert_and_get():
    from scenemem.graph import SceneNode
    from scenemem.store import SceneStore
    with tempfile.TemporaryDirectory() as tmp:
        with SceneStore(f"{tmp}/scene.db") as s:
            n = SceneNode(label="door-1", node_type="object", properties={})
            s.upsert_node(n)
            retrieved = s.get_node(n.id)
            assert retrieved is not None
            assert retrieved.label == "door-1"


def _test_store_confidence_upsert():
    from scenemem.graph import SceneNode
    from scenemem.store import SceneStore
    with tempfile.TemporaryDirectory() as tmp:
        with SceneStore(f"{tmp}/scene.db") as s:
            n_low = SceneNode(label="door-1", node_type="object", properties={"state": "closed"}, confidence=0.3)
            s.upsert_node(n_low)
            n_high = SceneNode(label="door-1", node_type="object", properties={"state": "open"}, confidence=0.9)
            s.upsert_node(n_high)
            retrieved = s.get_node(n_low.id)
            assert retrieved is not None
            assert retrieved.confidence == 0.9
            assert retrieved.properties["state"] == "open"


run("SceneNode.id is content-addressed (same label+type = same ID)", _test_node_content_addressed)
run("SceneNode.to_dict() / from_dict() round-trip", _test_node_serialization)
run("SceneEdge.id is content-addressed (same source+target+relation = same ID)", _test_edge_content_addressed)
run("SceneEdge.to_dict() / from_dict() round-trip", _test_edge_serialization)
run("SceneStore.upsert_node() + get_node() round-trip", _test_store_upsert_and_get)
run("SceneStore confidence-weighted upsert (higher wins)", _test_store_confidence_upsert)


# ── 3. SceneMerger and SceneQuery ─────────────────────────────────────────────

section("3. SceneMerger + SceneQuery")


def _test_merger_adds_new_nodes():
    from scenemem.graph import SceneNode
    from scenemem.merger import SceneMerger
    from scenemem.store import SceneStore
    with tempfile.TemporaryDirectory() as tmp:
        with SceneStore(f"{tmp}/local.db") as local, \
             SceneStore(f"{tmp}/remote.db") as remote:
            n = SceneNode(label="door-1", node_type="object", properties={})
            remote.upsert_node(n)
            result = SceneMerger().merge(local, remote)
            assert len(result.added_nodes) == 1
            assert local.get_node(n.id) is not None


def _test_merger_conflict_resolution():
    from scenemem.graph import SceneNode
    from scenemem.merger import SceneMerger
    from scenemem.store import SceneStore
    with tempfile.TemporaryDirectory() as tmp:
        with SceneStore(f"{tmp}/local.db") as local, \
             SceneStore(f"{tmp}/remote.db") as remote:
            n_low = SceneNode(label="door-1", node_type="object", properties={"v": "old"}, confidence=0.3)
            local.upsert_node(n_low)
            n_high = SceneNode(label="door-1", node_type="object", properties={"v": "new"}, confidence=0.9)
            remote.upsert_node(n_high)
            result = SceneMerger().merge(local, remote)
            assert result.conflicts_resolved >= 1
            updated = local.get_node(n_low.id)
            assert updated is not None
            assert updated.properties["v"] == "new"


def _test_merger_idempotent():
    from scenemem.graph import SceneNode
    from scenemem.merger import SceneMerger
    from scenemem.store import SceneStore
    with tempfile.TemporaryDirectory() as tmp:
        with SceneStore(f"{tmp}/local.db") as local, \
             SceneStore(f"{tmp}/remote.db") as remote:
            n = SceneNode(label="x", node_type="object", properties={})
            remote.upsert_node(n)
            r1 = SceneMerger().merge(local, remote)
            r2 = SceneMerger().merge(local, remote)
            assert len(r1.added_nodes) == 1
            assert len(r2.added_nodes) == 0
            assert local.node_count() == 1


def _test_query_find_nodes():
    from scenemem.graph import SceneNode
    from scenemem.query import SceneQuery
    from scenemem.store import SceneStore
    with tempfile.TemporaryDirectory() as tmp:
        with SceneStore(f"{tmp}/scene.db") as s:
            s.upsert_node(SceneNode(label="door-1", node_type="object", properties={}))
            s.upsert_node(SceneNode(label="room-kitchen", node_type="room", properties={}))
            q = SceneQuery(s)
            objects = q.find_nodes(node_type="object")
            assert len(objects) == 1
            assert objects[0].label == "door-1"


def _test_query_context_summary():
    from scenemem.graph import SceneEdge, SceneNode
    from scenemem.query import SceneQuery
    from scenemem.store import SceneStore
    with tempfile.TemporaryDirectory() as tmp:
        with SceneStore(f"{tmp}/scene.db") as s:
            n1 = SceneNode(label="room-kitchen", node_type="room", properties={})
            n2 = SceneNode(label="table-A", node_type="object", properties={})
            s.upsert_node(n1)
            s.upsert_node(n2)
            e = SceneEdge(source_id=n1.id, target_id=n2.id, relation="contains")
            s.upsert_edge(e)
            q = SceneQuery(s)
            summary = q.context_summary()
            assert "room" in summary.lower() or "object" in summary.lower()
            assert "relationship" in summary or "relation" in summary


run("SceneMerger merges new nodes from remote", _test_merger_adds_new_nodes)
run("SceneMerger resolves conflicts by confidence", _test_merger_conflict_resolution)
run("SceneMerger is idempotent (merging twice is a no-op)", _test_merger_idempotent)
run("SceneQuery.find_nodes() filters by type", _test_query_find_nodes)
run("SceneQuery.context_summary() describes the scene", _test_query_context_summary)


# ── 4. Report formatters ──────────────────────────────────────────────────────

section("4. Report formatters")


def _test_to_json_valid():
    from scenemem.graph import SceneNode
    from scenemem.report import to_json
    nodes = [SceneNode(label="x", node_type="object", properties={})]
    parsed = json.loads(to_json(nodes))
    assert parsed["node_count"] == 1
    assert "nodes" in parsed


def _test_to_json_with_edges():
    from scenemem.graph import SceneEdge, SceneNode
    from scenemem.report import to_json
    nodes = [SceneNode(label="x", node_type="object", properties={})]
    edges = [SceneEdge(source_id="a", target_id="b", relation="contains")]
    parsed = json.loads(to_json(nodes, edges))
    assert "edges" in parsed
    assert parsed["edge_count"] == 1


def _test_to_markdown():
    from scenemem.graph import SceneNode
    from scenemem.report import to_markdown
    nodes = [SceneNode(label="table-A", node_type="object", properties={}, confidence=0.9)]
    md = to_markdown(nodes)
    assert "scenemem" in md
    assert "table-A" in md
    assert "|" in md


def _test_print_scene():
    import io
    from rich.console import Console
    from scenemem.graph import SceneNode
    from scenemem.report import print_scene
    buf = io.StringIO()
    con = Console(file=buf, highlight=False)
    nodes = [SceneNode(label="door-1", node_type="object", properties={})]
    print_scene(nodes, console=con)
    output = buf.getvalue()
    assert "door-1" in output


def _test_print_merge():
    import io
    from rich.console import Console
    from scenemem.graph import MergeResult
    from scenemem.report import print_merge
    buf = io.StringIO()
    con = Console(file=buf, highlight=False)
    result = MergeResult(added_nodes=[], updated_nodes=[], added_edges=[], conflicts_resolved=0)
    print_merge(result, console=con)
    output = buf.getvalue()
    assert "merge" in output.lower() or "Merge" in output


run("to_json() returns valid JSON with node_count", _test_to_json_valid)
run("to_json() includes edges when provided", _test_to_json_with_edges)
run("to_markdown() produces Markdown table", _test_to_markdown)
run("print_scene() outputs node labels to console", _test_print_scene)
run("print_merge() outputs merge summary to console", _test_print_merge)


# ── 5. CLI ────────────────────────────────────────────────────────────────────

section("5. CLI (scenemem)")


def _test_cli_help():
    r = subprocess.run(
        [PYTHON, "-m", "scenemem.cli", "--help"],
        capture_output=True, text=True
    )
    assert r.returncode == 0
    assert len(r.stdout) > 20, "Help output is empty"


def _test_cli_add_node():
    with tempfile.TemporaryDirectory() as tmp:
        db = f"{tmp}/scene.db"
        r = subprocess.run(
            [PYTHON, "-m", "scenemem.cli", "--db", db, "add-node", "door-1", "object"],
            capture_output=True, text=True
        )
        assert r.returncode == 0, f"add-node failed: {r.stderr}"
        assert "door-1" in r.stdout


def _test_cli_status():
    with tempfile.TemporaryDirectory() as tmp:
        db = f"{tmp}/scene.db"
        subprocess.run(
            [PYTHON, "-m", "scenemem.cli", "--db", db, "add-node", "x", "object"],
            capture_output=True
        )
        r = subprocess.run(
            [PYTHON, "-m", "scenemem.cli", "--db", db, "status"],
            capture_output=True, text=True
        )
        assert r.returncode == 0
        assert "1" in r.stdout


run("scenemem --help returns 0", _test_cli_help)
run("scenemem add-node works and prints node label", _test_cli_add_node)
run("scenemem status shows node count", _test_cli_status)


# ── 6. FastAPI server ─────────────────────────────────────────────────────────

section("6. FastAPI server (scenemem[api])")


def _test_api_import():
    from scenemem.api import app
    assert app.title == "scenemem API"


def _test_api_health():
    from fastapi.testclient import TestClient
    from scenemem.api import app
    client = TestClient(app)
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert "version" in r.json()


def _test_api_node_and_context():
    from fastapi.testclient import TestClient
    from scenemem.api import app
    client = TestClient(app)
    with tempfile.TemporaryDirectory() as tmp:
        db = f"{tmp}/scene.db"
        r_node = client.post("/node", json={
            "label": "table-A", "node_type": "object",
            "properties": {"color": "brown"}, "db": db
        })
        assert r_node.status_code == 200
        node_id = r_node.json()["id"]
        assert node_id

        r_nodes = client.get("/nodes", params={"db": db})
        assert r_nodes.status_code == 200
        assert r_nodes.json()["count"] == 1

        r_ctx = client.get("/context", params={"db": db})
        assert r_ctx.status_code == 200
        assert "object" in r_ctx.json()["context"]


def _test_api_merge():
    from fastapi.testclient import TestClient
    from scenemem.api import app
    from scenemem.graph import SceneNode
    client = TestClient(app)
    with tempfile.TemporaryDirectory() as tmp:
        db = f"{tmp}/scene.db"
        remote_node = SceneNode(label="peer-node", node_type="object", properties={})
        r = client.post("/merge", json={
            "other_nodes": [remote_node.to_dict()],
            "other_edges": [],
            "db": db,
        })
        assert r.status_code == 200
        assert len(r.json()["added_nodes"]) == 1


run("scenemem.api imports and app.title is correct", _test_api_import)
run("GET /health returns {status: ok, version: ...}", _test_api_health)
run("POST /node + GET /nodes + GET /context workflow", _test_api_node_and_context)
run("POST /merge adds nodes from other store", _test_api_merge)


# ── 7. MCP server ─────────────────────────────────────────────────────────────

section("7. MCP server (scenemem[mcp])")


def _test_mcp_server_importable():
    import scenemem.mcp_server as m
    assert hasattr(m, "run_server")


def _test_mcp_server_loads_cleanly():
    import scenemem.mcp_server  # noqa: F401


run("mcp_server.py imports without error", _test_mcp_server_importable)
run("mcp_server module loads cleanly (no import-time crash)", _test_mcp_server_loads_cleanly)


# ── 8. Agent config files ─────────────────────────────────────────────────────

section("8. Agent config files (what a clone gives you)")


def _check_file_nonempty(rel: str) -> None:
    p = REPO_ROOT / rel
    assert p.exists(), f"Missing: {rel}"
    assert p.stat().st_size > 50, f"File too small (likely empty): {rel}"


def _check_json_valid(rel: str) -> None:
    p = REPO_ROOT / rel
    assert p.exists(), f"Missing: {rel}"
    json.loads(p.read_text())


def _check_yaml_parseable(rel: str) -> None:
    try:
        import yaml  # type: ignore[import-untyped]
        p = REPO_ROOT / rel
        assert p.exists(), f"Missing: {rel}"
        yaml.safe_load(p.read_text())
    except ImportError:
        content = (REPO_ROOT / rel).read_text()
        assert len(content) > 20, f"File appears empty: {rel}"


def _test_claude_commands():
    commands = list((REPO_ROOT / ".claude/commands").glob("*.md"))
    assert len(commands) >= 4, f"Expected ≥4 slash commands, found {len(commands)}"


def _test_openai_tools_valid():
    _check_json_valid("tools/openai-tools.json")
    tools = json.loads((REPO_ROOT / "tools/openai-tools.json").read_text())
    assert len(tools) >= 3
    assert all("function" in t for t in tools)


def _test_openapi_yaml_parseable():
    _check_yaml_parseable("openapi.yaml")


run("AGENTS.md exists and non-empty", lambda: _check_file_nonempty("AGENTS.md"))
run("CLAUDE.md exists and non-empty", lambda: _check_file_nonempty("CLAUDE.md"))
run("CODEX.md exists and non-empty", lambda: _check_file_nonempty("CODEX.md"))
run(".github/copilot-instructions.md exists", lambda: _check_file_nonempty(".github/copilot-instructions.md"))


def _test_cursor_rules():
    mdc_files = list((REPO_ROOT / ".cursor/rules").glob("*.mdc"))
    assert len(mdc_files) >= 1, f"Expected ≥1 .mdc file in .cursor/rules/, found none"


run(".cursor/rules/ has at least one .mdc file", _test_cursor_rules)
run(".windsurfrules exists", lambda: _check_file_nonempty(".windsurfrules"))
run(".aider.conf.yml exists", lambda: _check_file_nonempty(".aider.conf.yml"))
run(".continue/config.json is valid JSON", lambda: _check_json_valid(".continue/config.json"))
run(".claude/commands/ has ≥4 slash commands", _test_claude_commands)
run("tools/openai-tools.json is valid JSON with ≥3 tools", _test_openai_tools_valid)
run("openapi.yaml is parseable YAML", _test_openapi_yaml_parseable)


# ── 9. Docs site ──────────────────────────────────────────────────────────────

section("9. MkDocs documentation site")


def _test_mkdocs_yml():
    _check_file_nonempty("mkdocs.yml")
    content = (REPO_ROOT / "mkdocs.yml").read_text()
    assert "site_name" in content
    assert "material" in content


def _test_docs_pages():
    docs = list((REPO_ROOT / "docs").glob("*.md"))
    assert len(docs) >= 8, f"Expected ≥8 doc pages, found {len(docs)}"
    names = {p.name for p in docs}
    for required in ("index.md", "quickstart.md", "architecture.md", "api-reference.md"):
        assert required in names, f"Missing docs/{required}"


run("mkdocs.yml exists with site_name and material theme", _test_mkdocs_yml)
run("docs/ has ≥8 pages including index, quickstart, architecture, api-reference", _test_docs_pages)


# ── 10. examples/demo.py ─────────────────────────────────────────────────────

section("10. examples/demo.py end-to-end")


def _test_demo_runs():
    demo = REPO_ROOT / "examples" / "demo.py"
    assert demo.exists(), "examples/demo.py not found"
    r = subprocess.run(
        [PYTHON, str(demo)],
        capture_output=True, text=True,
        cwd=str(REPO_ROOT)
    )
    if r.returncode != 0:
        raise AssertionError(f"demo.py exited {r.returncode}:\n{r.stderr[-500:]}")


run("examples/demo.py runs end-to-end without error", _test_demo_runs)


# ── Summary ───────────────────────────────────────────────────────────────────

total = len(passed) + len(failed)
print(f"\n{'═'*60}")
print(f"{BOLD}Results: {len(passed)}/{total} passed{RESET}")

if failed:
    print(f"{RED}Failed ({len(failed)}):{RESET}")
    for name, reason in failed:
        print(f"  {RED}✗{RESET} {name}")
        short = reason.split("\n")[0][:120]
        print(f"    {YELLOW}→ {short}{RESET}")
    print(f"\n{YELLOW}Tip: run with --verbose for full tracebacks{RESET}")
else:
    print(f"{GREEN}All {total} checks passed — scenemem is ready to ship{RESET}")

print(f"{'═'*60}\n")
sys.exit(0 if not failed else 1)
