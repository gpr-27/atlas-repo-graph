from pathlib import Path
from atlas.extract import path_pattern
from atlas.extract.openapi import extract_openapi

FIX = Path(__file__).parent / "fixtures" / "openapi_repo"

def test_path_pattern():
    assert path_pattern("/users/{user_id}") == "^/users/[^/]+$"
    assert path_pattern("/a/:id/b") == "^/a/[^/]+/b$"
    assert path_pattern("/a/<int:id>") == "^/a/[^/]+$"
    assert path_pattern("/users") == "^/users$"

def test_extract_endpoints_and_fields():
    r = extract_openapi("backend", FIX)
    names = sorted(n.name for n in r.nodes if n.kind == "endpoint")
    assert names == ["GET /users", "GET /users/{user_id}"]
    fields = sorted((n.meta["endpoint"], n.name) for n in r.nodes if n.kind == "field")
    assert ("GET /users/{user_id}", "customer_id") in fields
    assert ("GET /users", "customer_id") in fields            # array items resolved
    assert len([e for e in r.edges if e.kind == "EXPOSES"]) == 6
    ep = next(n for n in r.nodes if n.name == "GET /users/{user_id}")
    assert ep.file == "openapi.yaml" and ep.line == 4 and ep.meta["pattern"] == "^/users/[^/]+$"
    assert all(e.evidence.extractor == "openapi" and e.evidence.snippet for e in r.edges)

def test_bad_yaml_is_skipped(tmp_path):
    (tmp_path / "openapi.yaml").write_text("paths: [unclosed")
    r = extract_openapi("x", tmp_path)
    assert r.nodes == [] and r.skipped and "openapi.yaml" in r.skipped[0]

def test_malformed_shapes_never_raise(tmp_path):
    (tmp_path / "openapi.yaml").write_text(
        "paths:\n  /a:\n    get:\n      responses:\n        '200':\n          content:\n"
        "            application/json:\n              schema:\n"
        "                $ref: '#/components/schemas/X'\ncomponents: [1]\n"
    )
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "openapi.yaml").write_text("paths:\n  1:\n    get: {}\n")
    r = extract_openapi("x", tmp_path)
    assert sorted(n.name for n in r.nodes if n.kind == "endpoint") == ["GET /a", "GET 1"]


def test_unexpected_error_is_skipped_not_raised(tmp_path, monkeypatch):
    import atlas.extract.openapi as mod
    (tmp_path / "openapi.yaml").write_text("paths:\n  /a:\n    get: {}\n")
    monkeypatch.setattr(mod, "path_pattern", lambda p: 1 / 0)
    r = extract_openapi("x", tmp_path)
    assert r.nodes == [] and r.skipped and "ZeroDivisionError" in r.skipped[0]


def test_tab_indented_json(tmp_path):
    (tmp_path / "openapi.json").write_text('{\n\t"paths": {\n\t\t"/a": {\n\t\t\t"get": {}\n\t\t}\n\t}\n}\n')
    r = extract_openapi("x", tmp_path)
    assert [n.name for n in r.nodes] == ["GET /a"] and r.nodes[0].line == 3 and not r.skipped


def test_inline_schema_field_line_anchored_at_path(tmp_path):
    def op(path, prop):
        return (f"  {path}:\n    get:\n      responses:\n        '200':\n          content:\n"
                f"            application/json:\n              schema:\n                properties:\n"
                f"                  {prop}: {{type: string}}\n")
    (tmp_path / "openapi.yaml").write_text("paths:\n" + op("/a", "id") + op("/b", "id"))
    r = extract_openapi("x", tmp_path)
    lines = {n.meta["endpoint"]: n.line for n in r.nodes if n.kind == "field"}
    assert lines == {"GET /a": 10, "GET /b": 19}


def test_snippet_truncated_to_200(tmp_path):
    long = "x" * 300
    (tmp_path / "openapi.yaml").write_text(
        "paths:\n  /a:\n    get:\n      responses:\n        '200':\n          content:\n"
        "            application/json:\n              schema:\n                properties:\n"
        f"                  {long}: {{type: string}}\n"
    )
    r = extract_openapi("x", tmp_path)
    assert len(r.edges) == 1 and len(r.edges[0].evidence.snippet) == 200
