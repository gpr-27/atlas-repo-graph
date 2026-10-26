from pathlib import Path
from atlas.scan import scan_repos, detect_test_cmd
from atlas.db import open_db, fetch_edges, fetch_repos
from atlas.query import status
FIX = Path(__file__).parent / "fixtures"

def test_detect_test_cmd(tmp_path):
    assert detect_test_cmd(tmp_path) is None
    (tmp_path / "tests").mkdir()
    assert detect_test_cmd(tmp_path) == "python -m pytest -q"
    (tmp_path / ".atlas.yaml").write_text("test_cmd: make test\n")
    assert detect_test_cmd(tmp_path) == "make test"

def test_scan_three_repos_links_across(tmp_path):
    db = tmp_path / "atlas.db"
    s = scan_repos([FIX / "openapi_repo", FIX / "routes_repo", FIX / "consumer_repo"], db)
    assert [r["name"] for r in s["repos"]] == ["openapi_repo", "routes_repo", "consumer_repo"]
    assert s["cross_edges"] >= 3
    conn = open_db(db)
    kinds = {k: 0 for k in ("CALLS", "CONSUMES")}
    for e in fetch_edges(conn):
        if e["kind"] in kinds: kinds[e["kind"]] += 1
    assert kinds["CALLS"] >= 1 and kinds["CONSUMES"] >= 2
    st = status(conn)
    assert st["nodes"]["endpoint"] >= 5 and st["edges"]["EXPOSES"] >= 6 and len(st["repos"]) == 3

def test_scan_is_idempotent(tmp_path):
    db = tmp_path / "atlas.db"
    a = scan_repos([FIX / "routes_repo", FIX / "consumer_repo"], db)
    b = scan_repos([FIX / "routes_repo", FIX / "consumer_repo"], db)
    assert a == b
