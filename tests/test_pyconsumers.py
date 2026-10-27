import ast
from pathlib import Path
from atlas.extract.pyconsumers import extract_py_consumers, url_to_path
FIX = Path(__file__).parent / "fixtures" / "consumer_repo"

def _expr(src): return ast.parse(src).body[0].value

def test_url_to_path():
    assert url_to_path(_expr('"http://h:1/users/5"')) == "/users/5"
    assert url_to_path(_expr('f"{BASE}/users/{uid}"')) == "/users/{}"
    assert url_to_path(_expr('BASE + "/users/" + str(uid)')) == "/users/{}"
    assert url_to_path(_expr('"http://h/health/"')) == "/health"
    assert url_to_path(_expr('make_url()')) is None

def test_http_calls_and_field_refs():
    r = extract_py_consumers("billing", FIX, known_fields={"customer_id", "email"})
    calls = {n.name: n for n in r.nodes if n.kind == "http_call"}
    assert set(calls) == {"GET /users/{}", "GET /health"}
    assert calls["GET /users/{}"].file == "charge.py" and calls["GET /users/{}"].line == 5
    assert calls["GET /users/{}"].meta == {"method": "GET", "path": "/users/{}", "library": "requests"}
    refs = sorted((n.file, n.line, n.name, n.meta["access"], n.meta["function"]) for n in r.nodes if n.kind == "field_ref")
    assert ("charge.py", 7, "email", "get", "charge_user") in refs
    assert ("charge.py", 8, "customer_id", "subscript", "charge_user") in refs
    assert ("report.py", 5, "customer_id", "subscript", "totals") in refs
    assert ("report.py", 5, "customer_id", "attr", "totals") in refs
    assert not any(n.name == "status_code" for n in r.nodes)   # attr not in known_fields

def test_requests_get_is_not_a_field_ref():
    r = extract_py_consumers("billing", FIX, known_fields=set())
    assert not any(n.kind == "field_ref" and n.name.startswith("http") for n in r.nodes)


def test_route_decorator_get_is_not_a_field_ref(tmp_path):
    """`@app.get("/x")` is a route decorator, not a dict .get("key") field access."""
    (tmp_path / "svc.py").write_text(
        '@app.get("/users/{user_id}")\n'
        "def handler(user_id, cfg):\n"
        '    return cfg.get("timeout")\n'
    )
    r = extract_py_consumers("svc", tmp_path, known_fields=set())
    names = {n.name for n in r.nodes if n.kind == "field_ref"}
    assert names == {"timeout"}          # the real dict .get() is kept; the decorator path is not


def test_attribute_receiver_is_http_call_not_field_ref(tmp_path):
    (tmp_path / "t.py").write_text('def t(self):\n    return self.client.get("/users/5")\n')
    r = extract_py_consumers("x", tmp_path, known_fields=set())
    calls = [n for n in r.nodes if n.kind == "http_call"]
    assert [c.name for c in calls] == ["GET /users/5"] and calls[0].meta["library"] == "client"
    assert not any(n.kind == "field_ref" for n in r.nodes)


def test_query_string_is_dropped():
    assert url_to_path(_expr('f"{BASE}/users?id={x}"')) == "/users"
    assert url_to_path(_expr('"http://h/users/?id=1#top"')) == "/users"


def test_unresolvable_url_is_skipped_with_reason(tmp_path):
    (tmp_path / "c.py").write_text("import requests\nrequests.get(make_url())\n")
    r = extract_py_consumers("x", tmp_path, known_fields=set())
    assert not any(n.kind == "http_call" for n in r.nodes)
    assert r.skipped == ["c.py:2: unresolvable url"]


def test_syntax_error_file_is_skipped(tmp_path):
    (tmp_path / "bad.py").write_text("def (:\n")
    r = extract_py_consumers("x", tmp_path, known_fields=set())
    assert r.nodes == [] and r.skipped == ["bad.py: SyntaxError"]
