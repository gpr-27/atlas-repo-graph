from atlas.db import open_db, replace_repo, fetch_nodes, fetch_edges, fetch_repos, replace_cross_edges
from atlas.models import Node, Edge, Evidence, RepoInfo

def _ev(): return Evidence(file="app.py", line=3, snippet='return {"customer_id": 1}', extractor="pyroutes", reason="dict literal in return")

def test_schema_is_idempotent(tmp_path):
    conn = open_db(tmp_path / "a.db"); conn.close()
    conn = open_db(tmp_path / "a.db")
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 1

def test_replace_repo_inserts_and_replaces(tmp_path):
    conn = open_db(tmp_path / "a.db")
    ep = Node("backend", "endpoint", "GET /users/{user_id}", "app.py", 2, {"method": "GET", "path": "/users/{user_id}", "pattern": "^/users/[^/]+$"})
    f = Node("backend", "field", "customer_id", "app.py", 3, {"endpoint": ep.name})
    e = Edge(ep.key, f.key, "EXPOSES", "exact", _ev())
    counts = replace_repo(conn, RepoInfo("backend", "/x/backend", "abc", None), [ep, f], [e], {ep.key: "@app.get", f.key: "return {"})
    assert counts == {"nodes": 2, "edges": 1}
    counts = replace_repo(conn, RepoInfo("backend", "/x/backend", "abc", None), [ep], [], {})
    assert counts == {"nodes": 1, "edges": 0}
    assert len(fetch_nodes(conn)) == 1 and len(fetch_edges(conn)) == 0
    assert fetch_repos(conn)[0]["name"] == "backend"

def test_cross_edges_link_nodes_from_different_repos(tmp_path):
    conn = open_db(tmp_path / "a.db")
    f = Node("backend", "field", "customer_id", "app.py", 3, {"endpoint": "GET /users/{user_id}"})
    r = Node("billing", "field_ref", "customer_id", "charge.py", 9, {"access": "subscript", "function": "charge"})
    replace_repo(conn, RepoInfo("backend", "/x/backend", None, None), [f], [], {})
    replace_repo(conn, RepoInfo("billing", "/x/billing", None, "python -m pytest -q"), [r], [], {})
    n = replace_cross_edges(conn, [Edge(r.key, f.key, "CONSUMES", "inferred", Evidence("charge.py", 9, 'data["customer_id"]', "link", "name match only"))])
    assert n == 1
    row = fetch_edges(conn, kind="CONSUMES")[0]
    assert row["confidence"] == "inferred" and row["ev_snippet"] == 'data["customer_id"]'
