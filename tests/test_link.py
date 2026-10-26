from atlas.link import link
from atlas.models import Node

def _n(repo, kind, name, file, line, **meta): return Node(repo, kind, name, file, line, meta)

EP = _n("backend", "endpoint", "GET /users/{user_id}", "app.py", 6, method="GET", path="/users/{user_id}", pattern="^/users/[^/]+$")
F  = _n("backend", "field", "customer_id", "app.py", 8, endpoint="GET /users/{user_id}")
EP2 = _n("backend", "endpoint", "GET /orders/{id}", "app.py", 20, method="GET", path="/orders/{id}", pattern="^/orders/[^/]+$")
F2 = _n("backend", "field", "id", "app.py", 21, endpoint="GET /orders/{id}")
F3 = _n("backend", "field", "id", "app.py", 7, endpoint="GET /users/{user_id}")
CALL = _n("billing", "http_call", "GET /users/{}", "charge.py", 5, method="GET", path="/users/{}", library="requests")
REF  = _n("billing", "field_ref", "customer_id", "charge.py", 8, access="subscript", function="charge_user")
REF_ID = _n("billing", "field_ref", "id", "charge.py", 9, access="subscript", function="charge_user")
ORPHAN_CALL = _n("billing", "http_call", "GET /nope", "charge.py", 30, method="GET", path="/nope", library="requests")
AN_REF = _n("analytics", "field_ref", "customer_id", "report.py", 5, access="subscript", function="totals")
SNIP = {CALL.key: 'resp = requests.get(f"{BASE}/users/{user_id}")', REF.key: 'data["customer_id"]', REF_ID.key: 'data["id"]', AN_REF.key: 'row["customer_id"]', ORPHAN_CALL.key: 'requests.get("/nope")'}

def test_calls_edge_matches_method_and_pattern():
    edges = link([EP, F, CALL], SNIP)
    e = [x for x in edges if x.kind == "CALLS"]
    assert len(e) == 1 and e[0].src_key == CALL.key and e[0].dst_key == EP.key and e[0].confidence == "exact"
    assert e[0].evidence.file == "charge.py" and e[0].evidence.line == 5 and "requests.get" in e[0].evidence.snippet

def test_consumes_exact_when_same_file_calls_endpoint():
    edges = link([EP, F, CALL, REF], SNIP)
    c = [x for x in edges if x.kind == "CONSUMES"]
    assert len(c) == 1 and c[0].confidence == "exact" and c[0].evidence.reason == "same file calls GET /users/{user_id}"

def test_consumes_inferred_without_call():
    edges = link([EP, F, AN_REF], SNIP)
    c = [x for x in edges if x.kind == "CONSUMES"]
    assert len(c) == 1 and c[0].confidence == "inferred" and c[0].evidence.reason == "name match only"

def test_same_field_name_in_two_endpoints_is_exact_only_toward_called_one():
    edges = link([EP, EP2, F2, F3, CALL, REF_ID], SNIP)
    c = {x.dst_key: x.confidence for x in edges if x.kind == "CONSUMES"}
    assert c[F3.key] == "exact" and c[F2.key] == "inferred"

def test_orphan_call_gets_no_edge_and_no_error():
    assert [x for x in link([EP, ORPHAN_CALL], SNIP) if x.kind == "CALLS"] == []

def test_no_edges_within_same_repo():
    same = _n("backend", "field_ref", "customer_id", "app.py", 40, access="subscript", function="x")
    assert link([EP, F, same], {same.key: "x"}) == []
