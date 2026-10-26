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