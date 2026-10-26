from pathlib import Path
from atlas.cli import main
FIX = Path(__file__).parent / "fixtures"

def test_scan_and_status(tmp_path, capsys):
    db = str(tmp_path / "a.db")
    assert main(["scan", str(FIX / "routes_repo"), str(FIX / "consumer_repo"), "--db", db]) == 0
    assert main(["status", "--db", db]) == 0
    out = capsys.readouterr().out
    assert "routes_repo" in out and "consumer_repo" in out and "endpoint" in out

def test_status_missing_db_returns_1(tmp_path, capsys):
    assert main(["status", "--db", str(tmp_path / "none.db")]) == 1
    assert "not found" in capsys.readouterr().err.lower()


def test_impact_json(tmp_path, capsys):
    db = str(tmp_path / "b.db")
    main(["scan", str(FIX / "routes_repo"), str(FIX / "consumer_repo"), "--db", db])
    capsys.readouterr()  # drain scan output
    assert main(["impact", "customer_id", "--json", "--db", db]) == 0
    out = capsys.readouterr().out
    import json
    data = json.loads(out)
    assert "symbol" in data and "producers" in data and "consumers" in data


def test_explain_edge_not_found(tmp_path, capsys):
    db = str(tmp_path / "c.db")
    main(["scan", str(FIX / "routes_repo"), str(FIX / "consumer_repo"), "--db", db])
    assert main(["explain-edge", "999999", "--db", db]) == 1
    assert "edge not found" in capsys.readouterr().err.lower()


def test_scan_nonexistent_repo_returns_1(tmp_path, capsys):
    """Failure-path: repo path doesn't exist → exit 1, nothing written."""
    db = str(tmp_path / "x.db")
    rc = main(["scan", "/nonexistent/atlas_test_repo_xyz", "--db", db])
    assert rc == 1
    assert "not found" in capsys.readouterr().err.lower()
    assert not (tmp_path / "x.db").exists()  # nothing written
