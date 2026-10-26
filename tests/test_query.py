import pytest
from pathlib import Path
from atlas.scan import scan_repos
from atlas.db import open_db
from atlas.query import impact, search, explain_edge

FIX = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def conn(tmp_path_factory):
    db = tmp_path_factory.mktemp("db") / "a.db"
    scan_repos([FIX / "openapi_repo", FIX / "routes_repo", FIX / "consumer_repo"], db)
    c = open_db(db)
    yield c
    c.close()


def test_impact_lists_producers_and_consumers(conn):
    r = impact(conn, "customer_id")
    assert {p["endpoint"] for p in r.producers} >= {"GET /users/{user_id}"}
    rows = {(c.repo, c.file, c.line): c for c in r.consumers}
    exact = rows[("consumer_repo", "charge.py", 8)]
    assert exact.confidence == "exact" and exact.via == "GET /users/{user_id}" and 'data["customer_id"]' in exact.snippet
    inferred = rows[("consumer_repo", "report.py", 5)]
    assert inferred.confidence == "inferred" and inferred.via == "name match"
    assert all(c.edge_id > 0 for c in r.consumers)


def test_impact_unknown_symbol_is_empty(conn):
    r = impact(conn, "nope_field")
    assert r.producers == [] and r.consumers == []


def test_search_and_explain(conn):
    hits = search(conn, "health")
    assert hits and hits[0]["kind"] == "http_call"
    eid = impact(conn, "customer_id").consumers[0].edge_id
    e = explain_edge(conn, eid)
    assert e["kind"] == "CONSUMES" and e["src"]["repo"] == "consumer_repo"
    assert e["dst"]["repo"] in ("routes_repo", "openapi_repo")
    assert e["evidence"]["snippet"] and e["evidence"]["extractor"] == "link"
    assert explain_edge(conn, 999999) is None
