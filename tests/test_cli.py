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


def test_verify_nobody_references_exit_0_and_json_is_valid(tmp_path, capsys):
    import json
    db = str(tmp_path / "d.db")
    main(["scan", str(FIX / "routes_repo"), str(FIX / "consumer_repo"), "--db", db])
    capsys.readouterr()
    assert main(["verify", "ghost_field", "--db", db]) == 0
    assert "no consumers reference" in capsys.readouterr().out
    assert main(["verify", "ghost_field", "--json", "--db", db]) == 0
    assert json.loads(capsys.readouterr().out) == []


def test_usage_error_exits_1_not_2(capsys):
    # 2 is reserved for "verify found a fail row"
    assert main(["verify"]) == 1
    assert main(["explain-edge", "abc", "--db", "x.db"]) == 1


def test_scan_file_instead_of_dir_returns_1(tmp_path, capsys):
    f = tmp_path / "notadir"
    f.write_text("")
    assert main(["scan", str(f), "--db", str(tmp_path / "f.db")]) == 1
    assert not (tmp_path / "f.db").exists()


def test_scan_db_in_missing_dir_returns_1(tmp_path, capsys):
    assert main(["scan", str(FIX / "routes_repo"), "--db", str(tmp_path / "nodir" / "x.db")]) == 1
    assert "cannot open db" in capsys.readouterr().err.lower()


def test_missing_db_returns_1_for_every_query_command(tmp_path, capsys):
    db = str(tmp_path / "none.db")
    for argv in (["impact", "x"], ["verify", "x"], ["search", "x"], ["explain-edge", "1"]):
        assert main(argv + ["--db", db]) == 1
    assert not (tmp_path / "none.db").exists()
