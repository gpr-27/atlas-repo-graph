from pathlib import Path
from atlas.extract.pyroutes import extract_py_routes
FIX = Path(__file__).parent / "fixtures" / "routes_repo"

def test_routes_and_fields():
    r = extract_py_routes("backend", FIX)
    eps = {n.name: n for n in r.nodes if n.kind == "endpoint"}
    assert set(eps) == {"GET /users/{user_id}", "POST /orders", "GET /legacy/<int:id>", "DELETE /legacy/<int:id>", "GET /opaque"}
    assert eps["GET /users/{user_id}"].line == 6 and eps["GET /users/{user_id}"].meta["pattern"] == "^/users/[^/]+$"
    fields = {(n.meta["endpoint"], n.name): n for n in r.nodes if n.kind == "field"}
    assert ("GET /users/{user_id}", "customer_id") in fields
    assert fields[("GET /users/{user_id}", "customer_id")].line == 8
    assert ("POST /orders", "order_id") in fields
    assert ("GET /legacy/<int:id>", "ok") in fields and ("DELETE /legacy/<int:id>", "ok") in fields
    assert not any(k[0] == "GET /opaque" for k in fields)
    assert any("app.py:18" in s and "non-literal return" in s for s in r.skipped)
    edge = next(e for e in r.edges if e.dst_key == fields[("GET /users/{user_id}", "customer_id")].key)
    assert edge.kind == "EXPOSES" and edge.confidence == "exact" and edge.evidence.extractor == "pyroutes"
    assert "customer_id" in edge.evidence.snippet

def test_syntax_error_file_is_skipped(tmp_path):
    (tmp_path / "bad.py").write_text("def (:\n")
    r = extract_py_routes("x", tmp_path)
    assert r.nodes == [] and any("bad.py" in s for s in r.skipped)