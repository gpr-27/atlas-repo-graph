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


def test_rescanning_one_repo_keeps_links_to_other_repos(tmp_path):
    """FR-001: re-scan replaces that repo's rows; links involving other indexed repos must survive."""
    db = tmp_path / "atlas.db"
    all_repos = [FIX / "openapi_repo", FIX / "routes_repo", FIX / "consumer_repo"]
    first = scan_repos(all_repos, db)
    second = scan_repos([FIX / "consumer_repo"], db)      # incremental: only the consumer
    assert second["cross_edges"] == first["cross_edges"] > 0


def test_scanned_at_is_iso8601_utc(tmp_path):
    import re
    db = tmp_path / "atlas.db"
    scan_repos([FIX / "routes_repo"], db)
    ts = fetch_repos(open_db(db))[0]["scanned_at"]
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", ts), ts


def test_verbose_prints_per_file_counts_and_skipped_to_stderr(tmp_path, capsys):
    repo = tmp_path / "r"
    repo.mkdir()
    (repo / "good.py").write_text('def f(x):\n    return x["a"]\n')
    (repo / "bad.py").write_text("def (:\n")
    scan_repos([repo], tmp_path / "atlas.db", verbose=True)
    cap = capsys.readouterr()
    assert cap.out == ""                       # nothing on stdout
    assert "good.py" in cap.err and "skipped: bad.py" in cap.err


def test_bad_file_skipped_once_and_does_not_change_good_counts(tmp_path, capsys):
    good_only, both = tmp_path / "a" / "r", tmp_path / "b" / "r"
    for repo in (good_only, both):
        repo.mkdir(parents=True)
        (repo / "good.py").write_text('@app.get("/a")\ndef f():\n    return {"k": 1}\n')
    (both / "bad.py").write_text("def (:\n")
    a = scan_repos([good_only], tmp_path / "a.db")["repos"][0]
    b = scan_repos([both], tmp_path / "b.db", verbose=True)["repos"][0]
    assert (a["nodes"], a["edges"]) == (b["nodes"], b["edges"])
    assert b["skipped"] == ["bad.py: SyntaxError"]           # once, not once per extractor
    assert "good.py: 2 nodes (pyroutes 2)" in capsys.readouterr().err


def test_trailing_slash_route_gets_calls_edge(tmp_path):
    api, cli = tmp_path / "api", tmp_path / "cli"
    api.mkdir(); cli.mkdir()
    (api / "app.py").write_text('@app.get("/users/")\ndef users():\n    return {"id": 1}\n')
    (cli / "c.py").write_text('import requests\nrequests.get("http://h/users/")\n')
    db = tmp_path / "atlas.db"
    scan_repos([api, cli], db)
    assert [e for e in fetch_edges(open_db(db)) if e["kind"] == "CALLS"]
